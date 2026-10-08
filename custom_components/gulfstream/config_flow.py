"""Config flow for the Gulfstream Pool Heater integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GulfstreamApi, GulfstreamAuthError, GulfstreamError
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class GulfstreamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gulfstream Pool Heater."""

    VERSION = 1

    async def _validate(self, username: str, password: str) -> str | None:
        """Return an error key, or None if the credentials work."""
        api = GulfstreamApi(async_get_clientsession(self.hass), username, password)
        try:
            devices = await api.async_validate()
        except GulfstreamAuthError:
            return "invalid_auth"
        except GulfstreamError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001 - surface anything unexpected as a generic error
            _LOGGER.exception("Unexpected error validating Gulfstream credentials")
            return "unknown"
        if not devices:
            return "no_devices"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            error = await self._validate(username, password)
            if error is None:
                return self.async_create_entry(title=username, data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the stored credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with new credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            username = reauth_entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            error = await self._validate(username, password)
            if error is None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_PASSWORD: password},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME]
            },
            errors=errors,
        )
