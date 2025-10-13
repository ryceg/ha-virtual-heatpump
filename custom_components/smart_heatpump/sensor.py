"""Sensor platform for Smarter Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_COP_VALUE,
    DEFAULT_COP_VALUE,
)
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarter Heat Pump sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        SmartHeatPumpCurrentTempSensor(coordinator, config_entry),
        SmartHeatPumpTargetTempSensor(coordinator, config_entry),
        SmartHeatPumpPowerSensor(coordinator, config_entry),
    ]

    async_add_entities(entities)


class SmartHeatPumpCurrentTempSensor(CoordinatorEntity, SensorEntity):
    """Current temperature sensor for Smarter Heat Pump."""

    _attr_has_entity_name = True
    _attr_name = "Current Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer"

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_current_temp"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("room_temperature")


class SmartHeatPumpTargetTempSensor(CoordinatorEntity, SensorEntity):
    """Target temperature sensor for Smarter Heat Pump."""

    _attr_has_entity_name = True
    _attr_name = "Heat Pump Target Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_target_temp"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
        }

    @property
    def native_value(self) -> float | None:
        """Return the heat pump target temperature."""
        return self.coordinator.heat_pump_target_temp

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}
        if self.coordinator.data:
            attrs["climate_target_temp"] = self.coordinator.data.get("climate_target_temp")
        return attrs


class SmartHeatPumpPowerSensor(CoordinatorEntity, SensorEntity):
    """Power consumption sensor for Smarter Heat Pump."""

    _attr_has_entity_name = True
    _attr_name = "Estimated Power Consumption"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:flash"

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_power"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
        }

    @property
    def native_value(self) -> float | None:
        """Return the estimated power consumption."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("estimated_power")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {
            "cop": self._config_entry.data.get(CONF_COP_VALUE, DEFAULT_COP_VALUE),
            "heat_pump_on": self.coordinator.heat_pump_power_state,
        }

        if self.coordinator.data:
            outside_temp: float | None = self.coordinator.data.get("outside_temperature")
            if outside_temp is not None:
                attrs["outside_temperature"] = outside_temp

            room_temp: float | None = self.coordinator.data.get("room_temperature")
            if room_temp is not None:
                attrs["room_temperature"] = room_temp

        return attrs