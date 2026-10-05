"""Switch entities for the Anthem A/V Receivers integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_MAC, CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnthemavConfigEntry
from .entity import AnthemavEntity, zone_device_info
from .protocol import NotifyingAVR


@dataclass(frozen=True, kw_only=True)
class AnthemavSwitchDescription(SwitchEntityDescription):
    """Describe a switch backed by a boolean receiver setting."""

    value_fn: Callable[[NotifyingAVR], bool | None]
    set_fn: Callable[[NotifyingAVR, bool], None]
    is_supported: Callable[[NotifyingAVR], bool]


def _set_arc(avr: NotifyingAVR, value: bool) -> None:
    avr.arc = value


def _set_standby_control(avr: NotifyingAVR, value: bool) -> None:
    avr.standby_control = value


SWITCHES: tuple[AnthemavSwitchDescription, ...] = (
    # On x40 models ARC is a per-input setting, so this follows the current input.
    AnthemavSwitchDescription(
        key="arc",
        translation_key="arc",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda avr: avr.arc,
        set_fn=_set_arc,
        is_supported=lambda avr: avr.support_arc,
    ),
    AnthemavSwitchDescription(
        key="standby_control",
        translation_key="standby_control",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda avr: avr.standby_control,
        set_fn=_set_standby_control,
        is_supported=lambda avr: avr.has_x20_settings,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthemavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the receiver setting switches."""
    avr = config_entry.runtime_data.protocol
    mac_address = config_entry.data[CONF_MAC]
    device_info = zone_device_info(
        avr, config_entry.title, mac_address, config_entry.data[CONF_MODEL], 1
    )
    async_add_entities(
        AnthemavSwitch(avr, config_entry.entry_id, mac_address, device_info, description)
        for description in SWITCHES
        if description.is_supported(avr)
    )


class AnthemavSwitch(AnthemavEntity, SwitchEntity):
    """Switch for a boolean receiver setting."""

    entity_description: AnthemavSwitchDescription

    def __init__(
        self,
        avr: NotifyingAVR,
        entry_id: str,
        mac_address: str,
        device_info: DeviceInfo,
        description: AnthemavSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(avr, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._attr_device_info = device_info
        self.set_states()

    @override
    def set_states(self) -> None:
        """Read the setting from the receiver."""
        super().set_states()
        self._attr_is_on = self.entity_description.value_fn(self.avr)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        self.entity_description.set_fn(self.avr, True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        self.entity_description.set_fn(self.avr, False)
