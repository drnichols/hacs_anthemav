"""Tests for setting up, updating and unloading the integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_anthemav.const import DOMAIN

MAC = "00:11:22:33:44:55"


def mock_connection() -> MagicMock:
    zone = MagicMock()
    zone.power = True
    zone.mute = False
    zone.volume_as_percentage = 0.5
    zone.input_name = "HDMI 1"
    zone.input_format = "PCM"

    avr = MagicMock()
    avr.dump_conndata = ""
    avr.protocol.connected = True
    avr.protocol.zones = {1: zone}
    avr.protocol.input_list = ["HDMI 1", "HDMI 2"]
    avr.protocol.support_audio_listening_mode = True
    avr.protocol.audio_listening_mode = "02"
    avr.protocol.audio_listening_mode_list = ["None", "AnthemLogic Cinema", "AnthemLogic Music"]
    avr.protocol._alm_number = {"None": 0, "AnthemLogic Cinema": 1, "AnthemLogic Music": 2}
    avr.protocol.swversion = "1.2.3"
    avr.protocol.hwversion = "A1"
    avr.protocol.wait_for_device_initialised = AsyncMock()
    return avr


async def setup_entry(hass: HomeAssistant, avr: MagicMock):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        title="Anthem AV (HACS)",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 14999,
            CONF_MAC: MAC,
            CONF_MODEL: "MRX 540",
        },
    )
    entry.add_to_hass(hass)
    create = AsyncMock(return_value=avr)
    with patch("anthemav.Connection.create", create):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, create


def entity_id(hass: HomeAssistant) -> str:
    return er.async_get(hass).async_get_entity_id("media_player", DOMAIN, MAC)


async def test_entity_follows_connection_state(hass: HomeAssistant) -> None:
    avr = mock_connection()
    entry, create = await setup_entry(hass, avr)

    assert hass.states.get(entity_id(hass)).state == "on"

    # The library reports a dropped connection through the update callback.
    avr.protocol.connected = False
    create.call_args.kwargs["update_callback"]("connection_lost")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass)).state == STATE_UNAVAILABLE

    avr.protocol.connected = True
    create.call_args.kwargs["update_callback"]("connection_made")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass)).state == "on"


async def test_unload_closes_connection(hass: HomeAssistant) -> None:
    avr = mock_connection()
    entry, _ = await setup_entry(hass, avr)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    avr.close.assert_called_once()


async def test_failed_platform_unload_keeps_connection(hass: HomeAssistant) -> None:
    avr = mock_connection()
    entry, _ = await setup_entry(hass, avr)

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)
    ):
        from custom_components.hacs_anthemav import async_unload_entry

        assert not await async_unload_entry(hass, entry)
    avr.close.assert_not_called()


def receiver_device(hass: HomeAssistant):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MAC)})


async def test_device_reports_versions(hass: HomeAssistant) -> None:
    await setup_entry(hass, mock_connection())

    device = receiver_device(hass)
    assert device.sw_version == "1.2.3"
    assert device.hw_version == "A1"


async def test_versions_arriving_after_setup_update_device(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.swversion = "Unknown Version"
    avr.protocol.hwversion = "Unknown Version"
    _, create = await setup_entry(hass, avr)

    device = receiver_device(hass)
    assert device.sw_version is None
    assert device.hw_version is None

    avr.protocol.swversion = "1.2.3"
    create.call_args.kwargs["update_callback"]("IDS1.2.3")
    await hass.async_block_till_done()

    device = receiver_device(hass)
    assert device.sw_version == "1.2.3"
    assert device.hw_version is None
