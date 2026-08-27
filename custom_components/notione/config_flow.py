"""Config flow for the notiOne integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NotiOneApiError, NotiOneAuthError, NotiOneClient, NotiOneDevice
from .const import CONF_TRACKED_DEVICES, DOMAIN

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def _validate_and_list_devices(
    hass: HomeAssistant, username: str, password: str
) -> list[NotiOneDevice]:
    """Check the credentials against the live API and return the trackers."""
    client = NotiOneClient(async_get_clientsession(hass), username, password)
    return await client.async_get_devices()


class NotiOneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect credentials, then let the user pick which trackers to follow."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}
        self._devices: list[NotiOneDevice] = []

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> NotiOneOptionsFlow:
        return NotiOneOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._devices = await _validate_and_list_devices(
                    self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except NotiOneAuthError:
                errors["base"] = "invalid_auth"
            except NotiOneApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                self._credentials = user_input
                return await self.async_step_devices()
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._credentials[CONF_USERNAME],
                data=self._credentials,
                options={
                    CONF_TRACKED_DEVICES: user_input[CONF_TRACKED_DEVICES]
                },
            )
        choices = {str(dev.device_id): dev.name for dev in self._devices}
        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TRACKED_DEVICES, default=list(choices)
                    ): cv.multi_select(choices)
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _validate_and_list_devices(
                    self.hass,
                    entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except NotiOneAuthError:
                errors["base"] = "invalid_auth"
            except NotiOneApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )


class NotiOneOptionsFlow(OptionsFlow):
    """Change which trackers are followed."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_TRACKED_DEVICES, [])
        try:
            devices = await _validate_and_list_devices(
                self.hass,
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
            choices = {str(dev.device_id): dev.name for dev in devices}
        except (NotiOneAuthError, NotiOneApiError):
            choices = {device_id: device_id for device_id in current}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TRACKED_DEVICES, default=current
                    ): cv.multi_select(choices)
                }
            ),
        )
