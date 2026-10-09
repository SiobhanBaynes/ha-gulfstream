"""Sensor platform for the Gulfstream Pool Heater integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    KEY_CURRENT_TEMP,
    KEY_MODE,
    KEY_SETPOINT,
    KEY_SETPOINT_SPA,
    MODE_OFF,
    MODE_POOL,
    MODE_SPA,
)
from .coordinator import GulfstreamConfigEntry
from .entity import GulfstreamEntity

_MODE_NAMES = {MODE_OFF: "off", MODE_POOL: "pool", MODE_SPA: "spa"}


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class GulfstreamSensorDescription(SensorEntityDescription):
    """Describes a Gulfstream sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]
    is_temperature: bool = False


SENSORS: tuple[GulfstreamSensorDescription, ...] = (
    GulfstreamSensorDescription(
        key="water_temperature",
        translation_key="water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        is_temperature=True,
        value_fn=lambda s: _as_int(s.get(KEY_CURRENT_TEMP)),
    ),
    GulfstreamSensorDescription(
        key="pool_setpoint",
        translation_key="pool_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_temperature=True,
        value_fn=lambda s: _as_int(s.get(KEY_SETPOINT)),
    ),
    GulfstreamSensorDescription(
        key="spa_setpoint",
        translation_key="spa_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_temperature=True,
        value_fn=lambda s: _as_int(s.get(KEY_SETPOINT_SPA)),
    ),
    GulfstreamSensorDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "pool", "spa", "unknown"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: _MODE_NAMES.get(_as_int(s.get(KEY_MODE)), "unknown"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GulfstreamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gulfstream sensors for each device."""
    coordinator = entry.runtime_data
    async_add_entities(
        GulfstreamSensor(coordinator, key, description)
        for key in coordinator.data
        for description in SENSORS
    )


class GulfstreamSensor(GulfstreamEntity, SensorEntity):
    """A read-only value from the device's register state."""

    entity_description: GulfstreamSensorDescription

    def __init__(
        self, coordinator, key: str, description: GulfstreamSensorDescription
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, key)
        self.entity_description = description
        self._attr_unique_id = f"{key}_{description.key}"

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self._state)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.is_temperature:
            return self._temperature_unit
        return self.entity_description.native_unit_of_measurement
