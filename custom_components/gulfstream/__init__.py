"""The Gulfstream Pool Heater integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GulfstreamApi
from .const import CONF_PASSWORD, CONF_USERNAME
from .coordinator import GulfstreamConfigEntry, GulfstreamCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: GulfstreamConfigEntry
) -> bool:
    """Set up Gulfstream Pool Heater from a config entry."""
    session = async_get_clientsession(hass)
    api = GulfstreamApi(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinator = GulfstreamCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GulfstreamConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
