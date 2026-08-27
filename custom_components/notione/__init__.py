"""The notiOne integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import NotiOneApiError, NotiOneAuthError, NotiOneClient, NotiOneDevice
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]

type NotiOneConfigEntry = ConfigEntry[NotiOneCoordinator]


class NotiOneCoordinator(DataUpdateCoordinator[dict[str, NotiOneDevice]]):
    """Polls the notiOne API for all trackers of the account."""

    def __init__(
        self, hass: HomeAssistant, entry: NotiOneConfigEntry, client: NotiOneClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, NotiOneDevice]:
        try:
            devices = await self._client.async_get_devices()
        except NotiOneAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NotiOneApiError as err:
            raise UpdateFailed(str(err)) from err
        return {str(device.device_id): device for device in devices}


async def async_setup_entry(hass: HomeAssistant, entry: NotiOneConfigEntry) -> bool:
    """Set up notiOne from a config entry."""
    client = NotiOneClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = NotiOneCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: NotiOneConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NotiOneConfigEntry) -> bool:
    """Unload a notiOne config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
