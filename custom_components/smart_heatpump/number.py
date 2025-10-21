"""Number platform for Smarter Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_TEMP_UP_COMMAND,
    CONF_TEMP_DOWN_COMMAND,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
)
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarter Heat Pump number entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Only create the number entity if temperature commands are configured
    has_temp_commands = bool(
        config_entry.data.get(CONF_TEMP_UP_COMMAND) and config_entry.data.get(CONF_TEMP_DOWN_COMMAND)
    )

    if has_temp_commands:
        async_add_entities([SmartHeatPumpTargetTempNumber(coordinator, config_entry)])


class SmartHeatPumpTargetTempNumber(CoordinatorEntity, NumberEntity):
    """Number entity to control heat pump set temperature via IR commands."""

    _attr_has_entity_name = True
    _attr_name = "Set Temperature"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "°C"

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_target_temp_number"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
        }
        self._attr_native_min_value = self._config_entry.data.get(
            CONF_MIN_TEMP, DEFAULT_MIN_TEMP
        )
        self._attr_native_max_value = self._config_entry.data.get(
            CONF_MAX_TEMP, DEFAULT_MAX_TEMP
        )

    @property
    def native_value(self) -> float | None:
        """Return the physical heat pump's set temperature."""
        return self.coordinator.heat_pump_set_temp

    @property
    def available(self) -> bool:
        """Return if entity is available - only when physical heat pump is on."""
        return self.coordinator.physical_heat_pump_on

    async def async_set_native_value(self, value: float) -> None:
        """Set new heat pump temperature by sending IR commands."""
        # Only allow changes when physical heat pump is on
        if not self.coordinator.physical_heat_pump_on:
            _LOGGER.warning(
                "Cannot change temperature: physical heat pump is off and doesn't accept IR commands"
            )
            return

        if not self.coordinator.can_change_state():
            _LOGGER.warning("Cannot change temperature: state change not allowed")
            return

        current_temp = self.coordinator.heat_pump_set_temp
        temp_diff = value - current_temp

        if abs(temp_diff) < 0.5:
            return

        steps = int(abs(temp_diff))
        command = (
            self._config_entry.data.get(CONF_TEMP_UP_COMMAND)
            if temp_diff > 0
            else self._config_entry.data.get(CONF_TEMP_DOWN_COMMAND)
        )

        if command:
            for _ in range(steps):
                success = await self.coordinator.send_ir_command(command)
                if not success:
                    _LOGGER.error("Failed to send IR command")
                    break

            # Update the coordinator's tracked physical heat pump temperature
            self.coordinator.heat_pump_set_temp = value
            self.async_write_ha_state()
