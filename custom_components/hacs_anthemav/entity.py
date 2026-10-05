"""Shared base entity and device info for the Anthem A/V Receivers integration."""

from typing import override

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import ANTHEMAV_UPDATE_SIGNAL, DOMAIN, MANUFACTURER
from .protocol import NotifyingAVR


def _known(value: str | None) -> str | None:
    """Drop the library's "Unknown ..." placeholders for values not yet received."""
    if not value or value.startswith("Unknown"):
        return None
    return value


def device_versions(avr: NotifyingAVR) -> dict[str, str | None]:
    """Return the software and hardware versions reported by the receiver."""
    return {
        "sw_version": _known(avr.swversion),
        "hw_version": _known(avr.hwversion),
    }


def zone_device_info(
    hass: HomeAssistant,
    avr: NotifyingAVR,
    name: str,
    mac_address: str,
    model: str,
    zone_number: int,
    entry_id: str,
) -> DeviceInfo:
    """Build the device info for a zone.

    Zone 1 is the physical receiver that owns the network MAC; higher zones are
    via_device children and carry no connection.
    """
    if zone_number > 1:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{mac_address}_{zone_number}")},
            name=f"Zone {zone_number}",
            manufacturer=MANUFACTURER,
            model=model,
            via_device_id=dr.async_get(hass).async_get_device_id_by_identifier(
                (DOMAIN, mac_address), config_entry_id=entry_id
            ),
        )
    return DeviceInfo(
        identifiers={(DOMAIN, mac_address)},
        connections={(CONNECTION_NETWORK_MAC, mac_address)},
        name=name,
        manufacturer=MANUFACTURER,
        model=model,
        **device_versions(avr),
    )


class AnthemavEntity(Entity):
    """Base entity that refreshes whenever the receiver reports a change."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, avr: NotifyingAVR, entry_id: str) -> None:
        """Initialize the entity with the receiver protocol."""
        super().__init__()
        self.avr = avr
        self._entry_id = entry_id

    def set_states(self) -> None:
        """Copy the receiver state onto the entity."""
        self._attr_available = self.avr.connected

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver updates."""
        self.set_states()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{ANTHEMAV_UPDATE_SIGNAL}_{self._entry_id}",
                self.update_states,
            )
        )

    @callback
    def update_states(self) -> None:
        """Refresh the entity from the receiver and publish the new state."""
        self.set_states()
        self.async_write_ha_state()
