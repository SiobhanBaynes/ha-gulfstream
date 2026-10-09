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
    MODE_OFF,
    MODE_POOL,
    MODE_SPA,
    PRESET_POOL,
    PRESET_SPA,
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
    """A GulfStream pool/spa heat pump exposed as a climate entity.

    The device's operating mode (register ``MD``) is a three-value enum:
    off / pool heat / spa. This maps to Home Assistant as HVAC ``off`` plus
    ``heat`` with two presets (Pool / Spa), each using its own setpoint
    register (pool = ``RSV1``, spa = ``RSV2``).
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "heater"
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [PRESET_POOL, PRESET_SPA]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
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

    @property
    def _mode(self) -> int:
        """Current operating mode (register MD)."""
        return self._reg(KEY_MODE, MODE_OFF) or MODE_OFF

    async def _apply(
        self,
        *,
        rsv1: int | None = None,
        rsv2: int | None = None,
        mode: int | None = None,
    ) -> None:
        """Write the 27..33 block, keeping unspecified values at their current state."""
        current_rsv1 = self._reg(KEY_SETPOINT, DEFAULT_MIN_TEMP_F)
        current_rsv2 = self._reg(KEY_SETPOINT_SPA, DEFAULT_MIN_TEMP_F)
        await self.coordinator.api.async_write_setpoint_and_mode(
            self._key,
            setpoint=current_rsv1 if rsv1 is None else rsv1,
            spa_setpoint=current_rsv2 if rsv2 is None else rsv2,
            mode=self._mode if mode is None else mode,
        )
        await self.coordinator.async_request_refresh()

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
    def preset_mode(self) -> str:
        """Which heating mode is (or was last) selected."""
        return PRESET_SPA if self._mode == MODE_SPA else PRESET_POOL

    @property
    def target_temperature(self) -> float | None:
        """Spa mode targets RSV2; pool/off target RSV1."""
        if self._mode == MODE_SPA:
            return self._reg(KEY_SETPOINT_SPA)
        return self._reg(KEY_SETPOINT)

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self._mode == MODE_OFF else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        if self._mode == MODE_OFF:
            return HVACAction.OFF
        current = self.current_temperature
        target = self.target_temperature
        if current is not None and target is not None and current < target:
            return HVACAction.HEATING
        return HVACAction.IDLE

    # -- commands -----------------------------------------------------------
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the setpoint for the currently active mode (pool->RSV1, spa->RSV2)."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        value = round(temperature)
        if self._mode == MODE_SPA:
            await self._apply(rsv2=value)
        else:
            await self._apply(rsv1=value)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn off, or turn on into the currently selected preset's mode."""
        if hvac_mode == HVACMode.OFF:
            await self._apply(mode=MODE_OFF)
            return
        target = MODE_SPA if self.preset_mode == PRESET_SPA else MODE_POOL
        await self._apply(mode=target)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Switch between pool and spa heating (also turns the heater on)."""
        await self._apply(mode=MODE_SPA if preset_mode == PRESET_SPA else MODE_POOL)

    async def async_turn_on(self) -> None:
        """Turn the heater on (into the selected preset's mode)."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the heater off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
