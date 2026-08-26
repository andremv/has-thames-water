"""Config flow for Thames Water."""

from __future__ import annotations

from typing import Any

import requests
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .api import ThamesWaterAuthError, ThamesWaterClient, ThamesWaterError
from .const import CONF_ACCOUNT_NUMBER, DOMAIN


class ThamesWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thames Water."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()

            try:
                client = ThamesWaterClient(
                    requests.Session(),
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                    account_number=user_input.get(CONF_ACCOUNT_NUMBER),
                )
                await self.hass.async_add_executor_job(client.get_usage)
            except ThamesWaterAuthError:
                errors["base"] = "invalid_auth"
            except ThamesWaterError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=f"Thames Water ({user_input[CONF_EMAIL]})",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ACCOUNT_NUMBER: user_input.get(CONF_ACCOUNT_NUMBER, ""),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_ACCOUNT_NUMBER): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
