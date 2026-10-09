"""Binary sensor platform for the Gulfstream Pool Heater integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import KEY_FAULT
from .coordinator import GulfstreamConfigEntry, GulfstreamCoordinator
from .entity import GulfstreamEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GulfstreamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gulfstream binary sensors for each device."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for key in coordinator.data:
        entities.append(GulfstreamConnectivity(coordinator, key))
        entities.append(GulfstreamFault(coordinator, key))
    async_add_entities(entities)


class GulfstreamConnectivity(GulfstreamEntity, BinarySensorEntity):
    """Whether the device is reporting online to the cloud."""

    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GulfstreamCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{key}_connectivity"

    @property
    def available(self) -> bool:
        # Stay available even when the device is offline, so it can report "off".
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        return self._device.online


class GulfstreamFault(GulfstreamEntity, BinarySensorEntity):
    """Device fault flag (inferred from the FLT register)."""

    _attr_translation_key = "fault"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GulfstreamCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{key}_fault"

    @property
    def is_on(self) -> bool | None:
        value = self._state.get(KEY_FAULT)
        try:
            return int(value) != 0
        except (TypeError, ValueError):
            return None
