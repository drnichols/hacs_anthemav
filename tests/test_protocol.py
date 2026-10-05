"""Tests for the connection-notifying protocol."""

import asyncio
from unittest.mock import MagicMock, patch

from anthemav.protocol import AVR

from custom_components.hacs_anthemav.protocol import NotifyingAVR


async def test_connection_lost_notifies_and_marks_disconnected() -> None:
    callback = MagicMock()
    avr = NotifyingAVR(
        connection_lost_callback=None,
        loop=asyncio.get_running_loop(),
        update_callback=callback,
    )
    avr.transport = MagicMock()
    assert avr.connected

    avr.connection_lost(None)
    await asyncio.sleep(0)

    assert not avr.connected
    callback.assert_called_once_with("connection_lost")


async def test_x20_settings_only_on_x20_models() -> None:
    avr = NotifyingAVR(loop=asyncio.get_running_loop())
    avr.transport = MagicMock()
    for model, expected in (("MRX 520", True), ("MRX 540", False), ("MDX 8", False)):
        avr.set_model_command(model)
        assert avr.has_x20_settings is expected, model


async def test_connection_made_notifies() -> None:
    callback = MagicMock()
    avr = NotifyingAVR(
        connection_lost_callback=None,
        loop=asyncio.get_running_loop(),
        update_callback=callback,
    )
    with patch.object(AVR, "connection_made"):
        avr.connection_made(MagicMock())
    await asyncio.sleep(0)

    callback.assert_called_once_with("connection_made")
