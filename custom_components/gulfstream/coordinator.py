"""DataUpdateCoordinator for the Gulfstream Pool Heater integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GulfstreamApi,
    GulfstreamAuthError,
    GulfstreamDevice,
    GulfstreamError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type GulfstreamConfigEntry = ConfigEntry["GulfstreamCoordinator"]


class GulfstreamCoordinator(DataUpdateCoordinator[dict[str, GulfstreamDevice]]):
    """Polls the cloud API and keeps per-device state fresh."""

    config_entry: GulfstreamConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GulfstreamConfigEntry,
        api: GulfstreamApi,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self._devices: dict[str, GulfstreamDevice] = {}

    async def _async_update_data(self) -> dict[str, GulfstreamDevice]:
        """Fetch the device list and each device's current register state."""
        try:
            devices = await self.api.async_get_devices()
            result: dict[str, GulfstreamDevice] = {}
            for device in devices:
                device.state = await self.api.async_get_detail(device.key)
                result[device.key] = device
        except GulfstreamAuthError as err:
            # Trigger HA's reauth flow.
            raise ConfigEntryAuthFailed(str(err)) from err
        except GulfstreamError as err:
            raise UpdateFailed(str(err)) from err

        self._devices = result
        return result
