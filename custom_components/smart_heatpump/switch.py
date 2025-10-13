"""Switch platform for Smarter Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_VIRTUAL_SWITCH,
    CONF_POWER_ON_COMMAND,
    CONF_POWER_OFF_COMMAND,
)
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarter Heat Pump switch entity."""
    if config_entry.data.get(CONF_VIRTUAL_SWITCH):
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        async_add_entities([SmartHeatPumpSwitch(coordinator, config_entry)])


class SmartHeatPumpSwitch(CoordinatorEntity, SwitchEntity):
    """Smarter Heat Pump power switch entity."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_power_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
        }

    @property
    def is_on(self) -> bool:
        """Return true if the physical heat pump is on."""
        return self.coordinator.physical_heat_pump_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}

        if self.coordinator.data and self.coordinator.data.get("cycle_start_time"):
            attrs["cycle_start_time"] = self.coordinator.data["cycle_start_time"]

        if self.coordinator.is_in_minimum_cycle():
            attrs["in_minimum_cycle"] = True

        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the physical heat pump on."""
        if not self.coordinator.physical_heat_pump_on and self.coordinator.can_change_state():
            command = self._config_entry.data.get(CONF_POWER_ON_COMMAND)
            if command:
                success = await self.coordinator.send_ir_command(command)
                if success:
                    self.coordinator.physical_heat_pump_on = True
                    _LOGGER.info("Physical heat pump turned on via power switch")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the physical heat pump off."""
        if self.coordinator.physical_heat_pump_on and self.coordinator.can_change_state():

            command = self._config_entry.data.get(CONF_POWER_OFF_COMMAND)
            if command:
                success = await self.coordinator.send_ir_command(command)
                if success:
                    self.coordinator.physical_heat_pump_on = False
                    _LOGGER.info("Physical heat pump turned off via power switch")