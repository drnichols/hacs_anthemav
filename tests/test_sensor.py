"""Tests for the input information sensors."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.hacs_anthemav.const import DOMAIN

from .test_init import MAC, mock_connection, setup_entry


def sensor_id(hass: HomeAssistant, key: str) -> str:
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{MAC}_{key}")


def sensor_connection():
    avr = mock_connection()
    protocol = avr.protocol
    protocol.video_input_resolution_text = "4K"
    protocol.audio_input_format_text = "Dolby"
    protocol.audio_input_channels_text = "5.1 channel"
    protocol.audio_input_name = "Dolby Digital"
    protocol.audio_input_ratename = "48 kHz"
    protocol.audio_input_bitrate = 640
    protocol.audio_input_samplerate = 48
    protocol.dolby_dialog_normalization = -27
    protocol.horizontal_resolution = 3840
    protocol.vertical_resolution = 2160
    return avr


async def test_sensors_report_receiver_values(hass: HomeAssistant) -> None:
    await setup_entry(hass, sensor_connection())

    expected = {
        "video_input_resolution": "4K",
        "audio_input_format": "Dolby",
        "audio_input_channels": "5.1 channel",
        "audio_input_name": "Dolby Digital",
        "audio_input_rate": "48 kHz",
        "audio_input_bitrate": "640",
        "audio_input_samplerate": "48",
        "dolby_dialog_normalization": "-27",
    }
    for key, value in expected.items():
        assert hass.states.get(sensor_id(hass, key)).state == value, key


async def test_resolution_sensors_disabled_by_default(hass: HomeAssistant) -> None:
    await setup_entry(hass, sensor_connection())

    registry = er.async_get(hass)
    for key in ("horizontal_resolution", "vertical_resolution"):
        entry = registry.async_get(sensor_id(hass, key))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entry.entity_id) is None


async def test_sensors_unknown_while_powered_off(hass: HomeAssistant) -> None:
    avr = sensor_connection()
    _, create = await setup_entry(hass, avr)
    entity = sensor_id(hass, "audio_input_format")
    assert hass.states.get(entity).state == "Dolby"

    avr.protocol.zones[1].power = False
    create.call_args.kwargs["update_callback"]("Z1POW0")
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == STATE_UNKNOWN


async def test_empty_values_are_unknown(hass: HomeAssistant) -> None:
    avr = sensor_connection()
    avr.protocol.audio_input_name = ""
    avr.protocol.audio_input_bitrate = None
    await setup_entry(hass, avr)

    assert hass.states.get(sensor_id(hass, "audio_input_name")).state == STATE_UNKNOWN
    assert hass.states.get(sensor_id(hass, "audio_input_bitrate")).state == STATE_UNKNOWN


async def test_sensors_follow_connection_state(hass: HomeAssistant) -> None:
    avr = sensor_connection()
    _, create = await setup_entry(hass, avr)
    entity = sensor_id(hass, "audio_input_format")

    avr.protocol.connected = False
    create.call_args.kwargs["update_callback"]("connection_lost")
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == STATE_UNAVAILABLE


async def test_sensors_attach_to_receiver_device(hass: HomeAssistant) -> None:
    from homeassistant.helpers import device_registry as dr

    await setup_entry(hass, sensor_connection())

    entry = er.async_get(hass).async_get(sensor_id(hass, "video_input_resolution"))
    device = dr.async_get(hass).async_get(entry.device_id)
    assert (DOMAIN, MAC) in device.identifiers


async def test_no_sensors_without_input_information(hass: HomeAssistant) -> None:
    avr = sensor_connection()
    avr.protocol.support_audio_listening_mode = False
    await setup_entry(hass, avr)

    assert sensor_id(hass, "video_input_resolution") is None
