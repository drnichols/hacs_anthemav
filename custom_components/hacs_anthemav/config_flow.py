"""Config flow for Anthem A/V Receivers integration."""

import logging
from typing import Any, override

import anthemav
from anthemav.connection import Connection
from anthemav.device_error import DeviceError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_SOURCE_PLAYERS, DEFAULT_NAME, DEFAULT_PORT, DEVICE_TIMEOUT_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def connect_device(user_input: dict[str, Any]) -> Connection:
    """Connect to the AVR device."""
    avr = await anthemav.Connection.create(
        host=user_input[CONF_HOST], port=user_input[CONF_PORT], auto_reconnect=False
    )
    await avr.reconnect()
    await avr.protocol.wait_for_device_initialised(DEVICE_TIMEOUT_SECONDS)
    return avr


class AnthemAVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anthem A/V Receivers."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return AnthemAVOptionsFlow()

    async def _async_probe(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Connect to the receiver and return its details, or form errors."""
        avr: Connection | None = None
        try:
            avr = await connect_device(user_input)
        except OSError:
            _LOGGER.error(
                "Couldn't establish connection to %s:%s",
                user_input[CONF_HOST],
                user_input[CONF_PORT],
            )
            return None, {"base": "cannot_connect"}
        except DeviceError:
            _LOGGER.error(
                "Couldn't receive device information from %s:%s",
                user_input[CONF_HOST],
                user_input[CONF_PORT],
            )
            return None, {"base": "cannot_receive_deviceinfo"}
        else:
            return {
                CONF_MAC: format_mac(avr.protocol.macaddress),
                CONF_MODEL: avr.protocol.model,
            }, {}
        finally:
            if avr is not None:
                avr.close()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            details, errors = await self._async_probe(user_input)
            if details is not None:
                await self.async_set_unique_id(details[CONF_MAC])
                # Adding a receiver that already exists with a new address
                # updates the stored address instead of failing.
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )
                return self.async_create_entry(
                    title=DEFAULT_NAME, data={**user_input, **details}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    @override
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the host or port of an existing receiver."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            details, errors = await self._async_probe(user_input)
            if details is not None:
                await self.async_set_unique_id(details[CONF_MAC])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates={**user_input, **details}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )


class AnthemAVOptionsFlow(OptionsFlow):
    """Map receiver inputs to media players that supply now-playing details."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a media player for each receiver input."""
        entry = self.config_entry
        if not hasattr(entry, "runtime_data"):
            return self.async_abort(reason="not_loaded")

        inputs = entry.runtime_data.protocol.input_list
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SOURCE_PLAYERS: {
                        name: player for name, player in user_input.items() if player
                    }
                }
            )

        schema = vol.Schema(
            {
                vol.Optional(name): EntitySelector(
                    EntitySelectorConfig(domain="media_player")
                )
                for name in inputs
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, entry.options.get(CONF_SOURCE_PLAYERS, {})
            ),
        )
