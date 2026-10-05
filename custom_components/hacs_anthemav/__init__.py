"""The Anthem A/V Receivers integration."""

import logging

import anthemav
from anthemav.device_error import DeviceError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ANTHEMAV_UPDATE_SIGNAL, DEVICE_TIMEOUT_SECONDS, DOMAIN, MANUFACTURER
from .entity import device_versions
from .protocol import NotifyingAVR

type AnthemavConfigEntry = ConfigEntry[anthemav.Connection]

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: AnthemavConfigEntry) -> bool:
    """Set up Anthem A/V Receivers from a config entry."""

    @callback
    def async_anthemav_update_callback(message: str) -> None:
        """Receive notification from transport that new data exists."""
        _LOGGER.debug("Received update callback from AVR: %s", message)
        _async_sync_device_versions(hass, entry)
        async_dispatcher_send(hass, f"{ANTHEMAV_UPDATE_SIGNAL}_{entry.entry_id}")

    try:
        avr = await anthemav.Connection.create(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            update_callback=async_anthemav_update_callback,
            protocol_class=NotifyingAVR,
        )

        # Wait for the zones to be initialised based on the model
        await avr.protocol.wait_for_device_initialised(DEVICE_TIMEOUT_SECONDS)
    except (OSError, DeviceError) as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = avr

    # Register the zone 1 receiver first so higher zones can link to it as a
    # via device when their entities are created.
    mac_address = entry.data[CONF_MAC]
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, mac_address)},
        connections={(CONNECTION_NETWORK_MAC, mac_address)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=entry.data[CONF_MODEL],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Source player mappings are read at setup, so reload to apply changes.
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))

    @callback
    def close_avr(event: Event) -> None:
        avr.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_avr)
    )

    return True


@callback
def _async_sync_device_versions(hass: HomeAssistant, entry: AnthemavConfigEntry) -> None:
    """Record the software and hardware versions once the receiver reports them.

    These arrive after the device is initialised, so they cannot be set when the
    device is first registered.
    """
    avr = getattr(entry, "runtime_data", None)
    if avr is None:
        return
    versions = {k: v for k, v in device_versions(avr.protocol).items() if v}
    if not versions:
        return
    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, entry.data[CONF_MAC])})
    if device and any(getattr(device, k) != v for k, v in versions.items()):
        registry.async_update_device(device.id, **versions)


async def _async_reload_on_update(hass: HomeAssistant, entry: AnthemavConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AnthemavConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Only drop the connection once the entities are gone, otherwise a failed
    # unload would leave live entities attached to a closed connection.
    if unload_ok:
        _LOGGER.debug("Close avr connection")
        entry.runtime_data.close()

    return unload_ok
