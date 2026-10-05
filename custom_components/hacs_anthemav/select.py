"""Select entities for the Anthem A/V Receivers integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import CONF_MAC, CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnthemavConfigEntry
from .entity import AnthemavEntity, zone_device_info
from .protocol import NotifyingAVR


@dataclass(frozen=True, kw_only=True)
class AnthemavSelectDescription(SelectEntityDescription):
    """Describe a select backed by a numbered receiver setting.

    The receiver reports each option as its position in `options`.
    """

    value_fn: Callable[[NotifyingAVR], str | int | None]
    set_fn: Callable[[NotifyingAVR, int], None]
    is_supported: Callable[[NotifyingAVR], bool]


def _set_dynamic_range(avr: NotifyingAVR, index: int) -> None:
    avr.dolby_dynamic_range = index


def _set_panel_brightness(avr: NotifyingAVR, index: int) -> None:
    avr.panel_brightness = index


SELECTS: tuple[AnthemavSelectDescription, ...] = (
    AnthemavSelectDescription(
        key="dolby_dynamic_range",
        translation_key="dolby_dynamic_range",
        entity_category=EntityCategory.CONFIG,
        options=["normal", "reduced", "late_night"],
        value_fn=lambda avr: avr.dolby_dynamic_range,
        set_fn=_set_dynamic_range,
        # Not reported by MDX models, which the library flags via this property.
        is_supported=lambda avr: avr.support_audio_listening_mode,
    ),
    AnthemavSelectDescription(
        key="panel_brightness",
        translation_key="panel_brightness",
        entity_category=EntityCategory.CONFIG,
        options=["off", "low", "medium", "high"],
        value_fn=lambda avr: avr.panel_brightness,
        set_fn=_set_panel_brightness,
        is_supported=lambda avr: avr.has_x20_settings,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthemavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the receiver setting selects."""
    avr = config_entry.runtime_data.protocol
    mac_address = config_entry.data[CONF_MAC]
    device_info = zone_device_info(
        hass,
        avr,
        config_entry.title,
        mac_address,
        config_entry.data[CONF_MODEL],
        1,
        config_entry.entry_id,
    )
    async_add_entities(
        AnthemavSelect(avr, config_entry.entry_id, mac_address, device_info, description)
        for description in SELECTS
        if description.is_supported(avr)
    )


class AnthemavSelect(AnthemavEntity, SelectEntity):
    """Select for a numbered receiver setting."""

    entity_description: AnthemavSelectDescription

    def __init__(
        self,
        avr: NotifyingAVR,
        entry_id: str,
        mac_address: str,
        device_info: DeviceInfo,
        description: AnthemavSelectDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(avr, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._attr_device_info = device_info
        self.set_states()

    @override
    def set_states(self) -> None:
        """Map the receiver's numeric value to an option."""
        super().set_states()
        options = self.entity_description.options or []
        try:
            index = int(self.entity_description.value_fn(self.avr))
        except (TypeError, ValueError):
            index = -1
        self._attr_current_option = options[index] if 0 <= index < len(options) else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Send the chosen option to the receiver."""
        self.entity_description.set_fn(
            self.avr, (self.entity_description.options or []).index(option)
        )
