"""Diagnostic sensors for the Anthem A/V Receivers integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MAC,
    CONF_MODEL,
    EntityCategory,
    UnitOfDataRate,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnthemavConfigEntry
from .entity import AnthemavEntity, zone_device_info
from .protocol import NotifyingAVR


@dataclass(frozen=True, kw_only=True)
class AnthemavSensorDescription(SensorEntityDescription):
    """Describe a sensor backed by a receiver property."""

    value_fn: Callable[[NotifyingAVR], str | int | None]


def _text(value: str | None) -> str | None:
    """Treat the library's empty string as no value yet."""
    return value or None


SENSORS: tuple[AnthemavSensorDescription, ...] = (
    AnthemavSensorDescription(
        key="video_input_resolution",
        translation_key="video_input_resolution",
        value_fn=lambda avr: _text(avr.video_input_resolution_text),
    ),
    AnthemavSensorDescription(
        key="audio_input_format",
        translation_key="audio_input_format",
        value_fn=lambda avr: _text(avr.audio_input_format_text),
    ),
    AnthemavSensorDescription(
        key="audio_input_channels",
        translation_key="audio_input_channels",
        value_fn=lambda avr: _text(avr.audio_input_channels_text),
    ),
    AnthemavSensorDescription(
        key="audio_input_name",
        translation_key="audio_input_name",
        value_fn=lambda avr: _text(avr.audio_input_name),
    ),
    AnthemavSensorDescription(
        key="audio_input_rate",
        translation_key="audio_input_rate",
        value_fn=lambda avr: _text(avr.audio_input_ratename),
    ),
    AnthemavSensorDescription(
        key="audio_input_bitrate",
        translation_key="audio_input_bitrate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        value_fn=lambda avr: avr.audio_input_bitrate,
    ),
    AnthemavSensorDescription(
        key="audio_input_samplerate",
        translation_key="audio_input_samplerate",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.KILOHERTZ,
        value_fn=lambda avr: avr.audio_input_samplerate,
    ),
    AnthemavSensorDescription(
        key="dolby_dialog_normalization",
        translation_key="dolby_dialog_normalization",
        native_unit_of_measurement="dB",
        value_fn=lambda avr: avr.dolby_dialog_normalization,
    ),
    AnthemavSensorDescription(
        key="horizontal_resolution",
        translation_key="horizontal_resolution",
        native_unit_of_measurement="px",
        entity_registry_enabled_default=False,
        value_fn=lambda avr: avr.horizontal_resolution,
    ),
    AnthemavSensorDescription(
        key="vertical_resolution",
        translation_key="vertical_resolution",
        native_unit_of_measurement="px",
        entity_registry_enabled_default=False,
        value_fn=lambda avr: avr.vertical_resolution,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthemavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the input information sensors."""
    avr = config_entry.runtime_data.protocol

    # MDX receivers do not report any of this input information. The library
    # exposes that distinction through its listening mode support flag.
    if not avr.support_audio_listening_mode:
        return

    mac_address = config_entry.data[CONF_MAC]
    device_info = zone_device_info(
        avr, config_entry.title, mac_address, config_entry.data[CONF_MODEL], 1
    )
    async_add_entities(
        AnthemavSensor(avr, config_entry.entry_id, mac_address, device_info, description)
        for description in SENSORS
    )


class AnthemavSensor(AnthemavEntity, SensorEntity):
    """Sensor reporting the audio or video input details of zone 1."""

    entity_description: AnthemavSensorDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        avr: NotifyingAVR,
        entry_id: str,
        mac_address: str,
        device_info,
        description: AnthemavSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(avr, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._attr_device_info = device_info
        self.set_states()

    def set_states(self) -> None:
        """Read the value, which only means something while the receiver is on."""
        super().set_states()
        self._attr_native_value = (
            self.entity_description.value_fn(self.avr)
            if self.avr.zones[1].power
            else None
        )
