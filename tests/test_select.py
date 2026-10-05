"""Tests for the receiver setting selects."""

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.hacs_anthemav.const import DOMAIN

from .test_init import MAC, mock_connection, setup_entry


def select_id(hass: HomeAssistant, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{MAC}_{key}")


async def choose(hass: HomeAssistant, entity: str, option: str) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity, "option": option},
        blocking=True,
    )


async def test_selects_reflect_receiver_values(hass: HomeAssistant) -> None:
    await setup_entry(hass, mock_connection())

    assert hass.states.get(select_id(hass, "dolby_dynamic_range")).state == "reduced"
    assert hass.states.get(select_id(hass, "panel_brightness")).state == "medium"


async def test_selects_follow_receiver_updates(hass: HomeAssistant) -> None:
    avr = mock_connection()
    _, create = await setup_entry(hass, avr)

    avr.protocol.dolby_dynamic_range = "2"
    create.call_args.kwargs["update_callback"]("Z1DYN2")
    await hass.async_block_till_done()

    assert hass.states.get(select_id(hass, "dolby_dynamic_range")).state == "late_night"


@pytest.mark.parametrize("value", ["", None, "9"])
async def test_unreported_or_invalid_value_is_unknown(
    hass: HomeAssistant, value: str | None
) -> None:
    avr = mock_connection()
    avr.protocol.dolby_dynamic_range = value
    await setup_entry(hass, avr)

    assert hass.states.get(select_id(hass, "dolby_dynamic_range")).state == STATE_UNKNOWN


async def test_choosing_dynamic_range_sets_its_index(hass: HomeAssistant) -> None:
    avr = mock_connection()
    await setup_entry(hass, avr)

    await choose(hass, select_id(hass, "dolby_dynamic_range"), "late_night")
    assert avr.protocol.dolby_dynamic_range == 2


async def test_choosing_panel_brightness_sets_its_index(hass: HomeAssistant) -> None:
    avr = mock_connection()
    await setup_entry(hass, avr)

    await choose(hass, select_id(hass, "panel_brightness"), "high")
    assert avr.protocol.panel_brightness == 3


async def test_panel_brightness_only_on_x20(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.has_x20_settings = False
    await setup_entry(hass, avr)

    assert select_id(hass, "panel_brightness") is None
    assert select_id(hass, "dolby_dynamic_range") is not None


async def test_no_dynamic_range_on_mdx(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.support_audio_listening_mode = False
    await setup_entry(hass, avr)

    assert select_id(hass, "dolby_dynamic_range") is None
