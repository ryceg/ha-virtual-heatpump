"""Climate platform for Smarter Heat Pump."""
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
    """Set up the Smarter Heat Pump climate entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SmartHeatPumpClimate(coordinator, config_entry)])


class SmartHeatPumpClimate(CoordinatorEntity, ClimateEntity):
    """Smarter Heat Pump climate entity."""

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
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
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
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("room_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the virtual climate target temperature."""
        return self.coordinator.climate_target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self.coordinator.climate_system_on:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        # If climate system is off, report OFF
        if not self.coordinator.climate_system_on:
            return HVACAction.OFF

        # Climate is on, check physical heat pump state
        if self.coordinator.physical_heat_pump_on:
            return HVACAction.HEATING
        else:
            # Climate is on but physical pump is off = idle/waiting
            return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            ATTR_HEAT_PUMP_TARGET_TEMP: self.coordinator.heat_pump_set_temp,
        }

        if self.coordinator.data is not None:
            attrs["climate_target_temp"] = self.coordinator.data.get("climate_target_temp")

            if self.coordinator.data.get("outside_temperature") is not None:
                attrs["outside_temperature"] = self.coordinator.data["outside_temperature"]

            if self.coordinator.data.get("estimated_power") is not None:
                attrs["estimated_power"] = self.coordinator.data["estimated_power"]

            # Add schedule information
            if self.coordinator.data.get("schedule_active") is not None:
                attrs["schedule_active"] = self.coordinator.data.get("schedule_active")

        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new virtual climate target temperature (no IR commands sent)."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        # Just update the virtual target temperature
        # The automatic control logic will handle turning the physical pump on/off
        self.coordinator.climate_target_temp = target_temp

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Turn the climate system on."""
        if not self.coordinator.climate_system_on:
            # Turn on climate system
            self.coordinator.climate_system_on = True

            # Also turn on physical heat pump if we can
            if not self.coordinator.physical_heat_pump_on and self.coordinator.can_change_state():
                success = await self.coordinator.turn_on_device()
                if success:
                    self.coordinator.physical_heat_pump_on = True

    async def async_turn_off(self) -> None:
        """Turn the climate system off."""
        if self.coordinator.climate_system_on:
            # Turn off climate system
            self.coordinator.climate_system_on = False

            # Also turn off physical heat pump if it's on
            if self.coordinator.physical_heat_pump_on and self.coordinator.can_change_state():
                success = await self.coordinator.turn_off_device()
                if success:
                    self.coordinator.physical_heat_pump_on = False