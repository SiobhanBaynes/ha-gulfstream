"""Shared base entity for the Gulfstream Pool Heater integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import GulfstreamDevice
from .const import DOMAIN, KEY_UNITS, MANUFACTURER
from .coordinator import GulfstreamCoordinator


class GulfstreamEntity(CoordinatorEntity[GulfstreamCoordinator]):
    """Common device wiring for all Gulfstream entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GulfstreamCoordinator, key: str) -> None:
        """Initialise the entity for a single device key."""
        super().__init__(coordinator)
        self._key = key
        device = coordinator.data[key]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            manufacturer=MANUFACTURER,
            model=device.model,
            name=device.name,
        )

    @property
    def _device(self) -> GulfstreamDevice:
        return self.coordinator.data[self._key]

    @property
    def _state(self) -> dict[str, Any]:
        return self._device.state

    @property
    def available(self) -> bool:
        """Available while the coordinator succeeds and the device is online."""
        return super().available and self._device.online

    @property
    def _temperature_unit(self) -> str:
        """Native temperature unit per the device's CF flag (0 = °F)."""
        unit = self._state.get(KEY_UNITS, 0)
        return (
            UnitOfTemperature.FAHRENHEIT
            if unit in (0, "0")
            else UnitOfTemperature.CELSIUS
        )
