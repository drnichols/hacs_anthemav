"""Tests for the Anthem A/V config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from anthemav.device_error import DeviceError
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_anthemav.const import DEFAULT_NAME, DOMAIN

USER_INPUT = {CONF_HOST: "192.0.2.10", CONF_PORT: 14999}
CONNECT = "custom_components.hacs_anthemav.config_flow.connect_device"


def mock_avr() -> MagicMock:
    avr = MagicMock()
    avr.protocol.macaddress = "00:11:22:33:44:55"
    avr.protocol.model = "MRX 540"
    return avr


async def test_form_creates_entry(hass: HomeAssistant) -> None:
    """A reachable receiver creates an entry keyed by its MAC address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with (
        patch(CONNECT, AsyncMock(return_value=mock_avr())),
        patch(
            "custom_components.hacs_anthemav.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_MAC] == "00:11:22:33:44:55"
    assert result["data"][CONF_MODEL] == "MRX 540"


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(CONNECT, AsyncMock(side_effect=OSError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_receive_deviceinfo(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(CONNECT, AsyncMock(side_effect=DeviceError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_receive_deviceinfo"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN, unique_id="00:11:22:33:44:55", data=USER_INPUT
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(CONNECT, AsyncMock(return_value=mock_avr())):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_already_configured_updates_host(hass: HomeAssistant) -> None:
    """Re-adding a known receiver at a new address updates the stored address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:11:22:33:44:55",
        data={CONF_HOST: "192.0.2.99", CONF_PORT: 14999},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(CONNECT, AsyncMock(return_value=mock_avr())),
        patch("custom_components.hacs_anthemav.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.10"


def reconfigure_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:11:22:33:44:55",
        data={
            CONF_HOST: "192.0.2.99",
            CONF_PORT: 14999,
            CONF_MAC: "00:11:22:33:44:55",
            CONF_MODEL: "MRX 540",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure_updates_host(hass: HomeAssistant) -> None:
    entry = reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(CONNECT, AsyncMock(return_value=mock_avr())),
        patch("custom_components.hacs_anthemav.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.0.2.10"


async def test_reconfigure_rejects_different_receiver(hass: HomeAssistant) -> None:
    entry = reconfigure_entry(hass)
    other = mock_avr()
    other.protocol.macaddress = "aa:bb:cc:dd:ee:ff"

    result = await entry.start_reconfigure_flow(hass)
    with patch(CONNECT, AsyncMock(return_value=other)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data[CONF_HOST] == "192.0.2.99"


async def test_reconfigure_cannot_connect(hass: HomeAssistant) -> None:
    entry = reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(CONNECT, AsyncMock(side_effect=OSError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
