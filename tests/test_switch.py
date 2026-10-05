"""Tests for the receiver setting switches."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.hacs_anthemav.const import DOMAIN

from .test_init import MAC, mock_connection, setup_entry


def switch_id(hass: HomeAssistant, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{MAC}_{key}")


async def switch(hass: HomeAssistant, service: str, entity: str) -> None:
    await hass.services.async_call(
        "switch", service, {"entity_id": entity}, blocking=True
    )


async def test_switches_reflect_receiver_values(hass: HomeAssistant) -> None:
    await setup_entry(hass, mock_connection())

    assert hass.states.get(switch_id(hass, "arc")).state == "on"
    assert hass.states.get(switch_id(hass, "standby_control")).state == "off"


async def test_switches_follow_receiver_updates(hass: HomeAssistant) -> None:
    avr = mock_connection()
    _, create = await setup_entry(hass, avr)

    avr.protocol.standby_control = True
    create.call_args.kwargs["update_callback"]("SIP1")
    await hass.async_block_till_done()

    assert hass.states.get(switch_id(hass, "standby_control")).state == "on"


async def test_turning_arc_on_and_off(hass: HomeAssistant) -> None:
    avr = mock_connection()
    await setup_entry(hass, avr)
    entity = switch_id(hass, "arc")

    await switch(hass, "turn_off", entity)
    assert avr.protocol.arc is False
    await switch(hass, "turn_on", entity)
    assert avr.protocol.arc is True


async def test_turning_standby_control_on_and_off(hass: HomeAssistant) -> None:
    avr = mock_connection()
    await setup_entry(hass, avr)
    entity = switch_id(hass, "standby_control")

    await switch(hass, "turn_on", entity)
    assert avr.protocol.standby_control is True
    await switch(hass, "turn_off", entity)
    assert avr.protocol.standby_control is False


async def test_arc_unknown_until_reported(hass: HomeAssistant) -> None:
    # x40 receivers report ARC per input, so it is None until the input's value arrives.
    avr = mock_connection()
    avr.protocol.arc = None
    await setup_entry(hass, avr)

    assert hass.states.get(switch_id(hass, "arc")).state == STATE_UNKNOWN


async def test_switches_unavailable_when_disconnected(hass: HomeAssistant) -> None:
    avr = mock_connection()
    _, create = await setup_entry(hass, avr)

    avr.protocol.connected = False
    create.call_args.kwargs["update_callback"]("connection_lost")
    await hass.async_block_till_done()

    assert hass.states.get(switch_id(hass, "arc")).state == STATE_UNAVAILABLE


async def test_standby_control_only_on_x20(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.has_x20_settings = False
    await setup_entry(hass, avr)

    assert switch_id(hass, "standby_control") is None
    assert switch_id(hass, "arc") is not None


async def test_no_arc_without_room_correction(hass: HomeAssistant) -> None:
    avr = mock_connection()
    avr.protocol.support_arc = False
    await setup_entry(hass, avr)

    assert switch_id(hass, "arc") is None
