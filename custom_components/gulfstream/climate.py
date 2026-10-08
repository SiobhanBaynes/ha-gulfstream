"""Climate platform for the Gulfstream Pool Heater integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import GulfstreamDevice
from .const import (
    DEFAULT_MAX_TEMP_F,
    DEFAULT_MIN_TEMP_F,
    DOMAIN,
    KEY_CURRENT_TEMP,
    KEY_MAX_SETPOINT,
    KEY_MIN_SETPOINT,
    KEY_MODE,
    KEY_SETPOINT,
    KEY_SETPOINT_SPA,
    KEY_UNITS,
    MANUFACTURER,
    MODE_HEAT,
    MODE_OFF,
)
from .coordinator import GulfstreamConfigEntry, GulfstreamCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GulfstreamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one climate entity per device on the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        GulfstreamClimate(coordinator, key) for key in coordinator.data
    )


class GulfstreamClimate(CoordinatorEntity[GulfstreamCoordinator], ClimateEntity):
    """A GulfStream pool heat pump exposed as a climate entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "heater"
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: GulfstreamCoordinator, key: str) -> None:
        """Initialise the entity for a single device key."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = key
        device = coordinator.data[key]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            manufacturer=MANUFACTURER,
            model=device.model,
            name=device.name,
        )

    # -- helpers ------------------------------------------------------------
    @property
    def _device(self) -> GulfstreamDevice:
        return self.coordinator.data[self._key]

    @property
    def _state(self) -> dict[str, Any]:
        return self._device.state

    def _reg(self, field: str, default: int | None = None) -> int | None:
        value = self._state.get(field, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # -- entity properties --------------------------------------------------
    @property
    def available(self) -> bool:
        """Only available while the coordinator succeeds and the device is online."""
        return super().available and self._device.online

    @property
    def temperature_unit(self) -> str:
        """0 = Fahrenheit, anything else = Celsius (inferred from CF)."""
        if self._reg(KEY_UNITS, 0) == 0:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self) -> float:
        return float(self._reg(KEY_MIN_SETPOINT, DEFAULT_MIN_TEMP_F))

    @property
    def max_temp(self) -> float:
        return float(self._reg(KEY_MAX_SETPOINT, DEFAULT_MAX_TEMP_F))

    @property
    def current_temperature(self) -> float | None:
        return self._reg(KEY_CURRENT_TEMP)

    @property
    def target_temperature(self) -> float | None:
        return self._reg(KEY_SETPOINT)

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self._reg(KEY_MODE, 0) == MODE_HEAT else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        if self._reg(KEY_MODE, 0) != MODE_HEAT:
            return HVACAction.OFF
        current = self.current_temperature
        target = self.target_temperature
        if current is not None and target is not None and current < target:
            return HVACAction.HEATING
        return HVACAction.IDLE

    # -- commands -----------------------------------------------------------
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature, preserving spa setpoint and mode."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.api.async_write_setpoint_and_mode(
            self._key,
            setpoint=round(temperature),
            spa_setpoint=self._reg(KEY_SETPOINT_SPA, round(temperature)),
            mode=self._reg(KEY_MODE, MODE_HEAT),
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the heater on (HEAT) or off, preserving setpoints."""
        mode = MODE_HEAT if hvac_mode == HVACMode.HEAT else MODE_OFF
        await self.coordinator.api.async_write_setpoint_and_mode(
            self._key,
            setpoint=self._reg(KEY_SETPOINT, DEFAULT_MIN_TEMP_F),
            spa_setpoint=self._reg(KEY_SETPOINT_SPA, DEFAULT_MIN_TEMP_F),
            mode=mode,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the heater on (heat mode)."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the heater off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
