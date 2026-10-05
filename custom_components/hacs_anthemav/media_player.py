"""Support for Anthem Network Receivers and Processors."""

from collections.abc import Mapping
import hashlib
import logging
from typing import Any, override
from urllib.parse import parse_qs, urlsplit

from homeassistant.components.media_player import (
    DATA_COMPONENT,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_TITLE,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    CONF_MAC,
    CONF_MODEL,
    STATE_IDLE,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnthemavConfigEntry
from .const import ANTHEMAV_UPDATE_SIGNAL, CONF_SOURCE_PLAYERS, DOMAIN, MANUFACTURER
from .protocol import NotifyingAVR

_LOGGER = logging.getLogger(__name__)
VOLUME_STEP = 0.01

# Attributes copied from the mapped player while its source is selected.
MIRRORED_ATTRS = {
    ATTR_MEDIA_TITLE: "_attr_media_title",
    ATTR_MEDIA_ARTIST: "_attr_media_artist",
    ATTR_MEDIA_ALBUM_NAME: "_attr_media_album_name",
    ATTR_MEDIA_ALBUM_ARTIST: "_attr_media_album_artist",
    ATTR_MEDIA_SERIES_TITLE: "_attr_media_series_title",
    ATTR_MEDIA_SEASON: "_attr_media_season",
    ATTR_MEDIA_EPISODE: "_attr_media_episode",
    ATTR_MEDIA_CONTENT_TYPE: "_attr_media_content_type",
    ATTR_MEDIA_DURATION: "_attr_media_duration",
    ATTR_MEDIA_POSITION: "_attr_media_position",
    ATTR_MEDIA_POSITION_UPDATED_AT: "_attr_media_position_updated_at",
}
INACTIVE_STATES = {STATE_OFF, STATE_IDLE, STATE_UNAVAILABLE, STATE_UNKNOWN}


def _picture_hash(picture: str) -> str:
    """Hash a player's entity picture, ignoring its rotating access token."""
    query = parse_qs(urlsplit(picture).query)
    stable = query["cache"][0] if "cache" in query else picture
    return hashlib.sha256(stable.encode()).hexdigest()[:16]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthemavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    name = config_entry.title
    mac_address = config_entry.data[CONF_MAC]
    model = config_entry.data[CONF_MODEL]

    avr = config_entry.runtime_data

    _LOGGER.debug("Connection data dump: %s", avr.dump_conndata)

    async_add_entities(
        AnthemAVR(
            hass,
            avr.protocol,
            name,
            mac_address,
            model,
            zone_number,
            config_entry.entry_id,
            config_entry.options.get(CONF_SOURCE_PLAYERS, {}),
        )
        for zone_number in avr.protocol.zones
    )


class AnthemAVR(MediaPlayerEntity):
    """Entity reading values from Anthem AVR protocol."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_volume_step = VOLUME_STEP

    def __init__(
        self,
        hass: HomeAssistant,
        avr: NotifyingAVR,
        name: str,
        mac_address: str,
        model: str,
        zone_number: int,
        entry_id: str,
        source_players: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize entity with transport."""
        super().__init__()
        self.avr = avr
        self._entry_id = entry_id
        self._source_players = dict(source_players or {})
        self._mirror_entity_id: str | None = None
        self._zone_number = zone_number
        self._zone = avr.zones[zone_number]
        if zone_number > 1:
            unique_id = f"{mac_address}_{zone_number}"
            self._attr_unique_id = unique_id
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                name=f"Zone {zone_number}",
                manufacturer=MANUFACTURER,
                model=model,
                via_device_id=dr.async_get_device_id_by_identifier(
                    hass,
                    (DOMAIN, mac_address),
                    config_entry_id=entry_id,
                ),
            )
        else:
            # Zone 1 is the physical receiver that owns the network MAC; higher
            # zones are via_device children and carry no connection.
            self._attr_unique_id = mac_address
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, mac_address)},
                connections={(CONNECTION_NETWORK_MAC, mac_address)},
                name=name,
                manufacturer=MANUFACTURER,
                model=model,
            )
        self.set_states()

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        # hass is unset during __init__, so mirror the mapped player now.
        self.set_states()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{ANTHEMAV_UPDATE_SIGNAL}_{self._entry_id}",
                self.update_states,
            )
        )
        if self._source_players:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    list(self._source_players.values()),
                    self._handle_source_player_change,
                )
            )

    @callback
    def _handle_source_player_change(self, event: Any) -> None:
        """Refresh when a mapped media player changes."""
        self.update_states()

    @callback
    def update_states(self) -> None:
        """Update states for the current zone."""
        self.set_states()
        self.async_write_ha_state()

    def set_states(self) -> None:
        """Set all the states from the device to the entity."""
        self._attr_available = self.avr.connected
        self._attr_state = (
            MediaPlayerState.ON if self._zone.power else MediaPlayerState.OFF
        )
        self._attr_is_volume_muted = self._zone.mute
        self._attr_volume_level = self._zone.volume_as_percentage
        self._attr_media_title = self._zone.input_name
        self._attr_app_name = self._zone.input_format
        self._attr_source = self._zone.input_name
        self._attr_source_list = self.avr.input_list
        self._apply_source_player()

    def _apply_source_player(self) -> None:
        """Mirror now-playing details from the player mapped to this source."""
        for attr in MIRRORED_ATTRS.values():
            if attr != "_attr_media_title":
                setattr(self, attr, None)
        self._attr_media_image_remotely_accessible = False
        self._attr_media_image_hash = None
        self._mirror_entity_id = None

        entity_id = self._source_players.get(self._zone.input_name)
        if (
            entity_id is None
            or self.hass is None
            or (state := self.hass.states.get(entity_id)) is None
            or state.state in INACTIVE_STATES
        ):
            return

        self._mirror_entity_id = entity_id
        for key, attr in MIRRORED_ATTRS.items():
            if (value := state.attributes.get(key)) is not None:
                setattr(self, attr, value)
        if picture := state.attributes.get(ATTR_ENTITY_PICTURE):
            self._attr_media_image_hash = _picture_hash(picture)

    @override
    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch cover art from the mapped media player."""
        if self._mirror_entity_id is None:
            return None, None
        source = self.hass.data[DATA_COMPONENT].get_entity(self._mirror_entity_id)
        if source is None:
            return None, None
        return await source.async_get_media_image()

    @override
    async def async_select_source(self, source: str) -> None:
        """Change AVR to the designated source (by name)."""
        self._zone.input_name = source

    @override
    async def async_turn_off(self) -> None:
        """Turn AVR power off."""
        self._zone.power = False

    @override
    async def async_turn_on(self) -> None:
        """Turn AVR power on."""
        self._zone.power = True

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set AVR volume (0 to 1)."""
        self._zone.volume_as_percentage = volume

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Engage AVR mute."""
        self._zone.mute = mute
