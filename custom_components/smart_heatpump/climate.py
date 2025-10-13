"""Climate platform for Smart Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_POWER_ON_COMMAND,
    CONF_POWER_OFF_COMMAND,
    CONF_TEMP_UP_COMMAND,
    CONF_TEMP_DOWN_COMMAND,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    ATTR_HEAT_PUMP_TARGET_TEMP,
)
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smart Heat Pump climate entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SmartHeatPumpClimate(coordinator, config_entry)])


class SmartHeatPumpClimate(CoordinatorEntity, ClimateEntity):
    """Smart Heat Pump climate entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Heat Pump"),
            "manufacturer": "Smart Heat Pump Integration",
            "model": "Smart Heat Pump",
        }

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._config_entry.data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._config_entry.data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.get("room_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.coordinator.heat_pump_target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self.coordinator.heat_pump_power_state:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        if not self.coordinator.heat_pump_power_state:
            return HVACAction.OFF
        
        current_temp = self.current_temperature
        target_temp = self.target_temperature
        
        if current_temp is not None and target_temp is not None:
            if current_temp < target_temp:
                return HVACAction.HEATING
            else:
                return HVACAction.IDLE
        
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            ATTR_HEAT_PUMP_TARGET_TEMP: self.coordinator.heat_pump_target_temp,
            "climate_target_temp": self.coordinator.data.get("climate_target_temp"),
        }
        
        if self.coordinator.data.get("outside_temperature") is not None:
            attrs["outside_temperature"] = self.coordinator.data["outside_temperature"]
        
        if self.coordinator.data.get("estimated_power") is not None:
            attrs["estimated_power"] = self.coordinator.data["estimated_power"]
        
        # Add schedule information
        if self.coordinator.data.get("schedule_enabled", False):
            attrs["schedule_enabled"] = True
            attrs["schedule_active"] = self.coordinator.data.get("schedule_active", False)
            
            # Add schedule target temperature if available
            schedule_attrs = self.coordinator.data.get("schedule_attributes", {})
            if "schedule_target_temp" in schedule_attrs:
                attrs["schedule_target_temp"] = schedule_attrs["schedule_target_temp"]
            if "schedule_mode" in schedule_attrs:
                attrs["schedule_mode"] = schedule_attrs["schedule_mode"]
        
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        current_temp = self.coordinator.heat_pump_target_temp
        temp_diff = target_temp - current_temp
        
        if abs(temp_diff) < 0.5:
            return
        
        steps = int(abs(temp_diff))
        command = (
            self._config_entry.data.get(CONF_TEMP_UP_COMMAND)
            if temp_diff > 0
            else self._config_entry.data.get(CONF_TEMP_DOWN_COMMAND)
        )
        
        if command and self.coordinator.can_change_state():
            for _ in range(steps):
                await self.coordinator.send_ir_command(command)
            
            self.coordinator.heat_pump_target_temp = target_temp

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Turn the heat pump on."""
        if not self.coordinator.heat_pump_power_state and self.coordinator.can_change_state():
            command = self._config_entry.data.get(CONF_POWER_ON_COMMAND)
            if command:
                success = await self.coordinator.send_ir_command(command)
                if success:
                    self.coordinator.heat_pump_power_state = True

    async def async_turn_off(self) -> None:
        """Turn the heat pump off."""
        if self.coordinator.heat_pump_power_state and self.coordinator.can_change_state():
            if self.coordinator.is_in_minimum_cycle():
                _LOGGER.warning("Cannot turn off heat pump during minimum cycle duration")
                return
            
            command = self._config_entry.data.get(CONF_POWER_OFF_COMMAND)
            if command:
                success = await self.coordinator.send_ir_command(command)
                if success:
                    self.coordinator.heat_pump_power_state = False