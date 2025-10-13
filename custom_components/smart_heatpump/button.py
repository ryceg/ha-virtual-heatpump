"""Button platform for Smart Heat Pump."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_CLIMATE_ENTITY,
)
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smart Heat Pump button entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SmartHeatPumpFixButton(coordinator, config_entry)])


class SmartHeatPumpFixButton(CoordinatorEntity, ButtonEntity):
    """Fix button for Smart Heat Pump to sync state."""

    _attr_has_entity_name = True
    _attr_name = "Fix State"
    _attr_icon = "mdi:sync"

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_fix_button"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Heat Pump"),
            "manufacturer": "Smart Heat Pump Integration",
            "model": "Smart Heat Pump",
        }

    async def async_press(self) -> None:
        """Handle the button press to fix/sync state."""
        _LOGGER.info("Fix button pressed - syncing heat pump state")
        
        # Get the underlying climate entity state to determine if heat pump should be on
        climate_entity: str | None = self._config_entry.data.get(CONF_CLIMATE_ENTITY)
        if climate_entity:
            climate_state: State | None = self.hass.states.get(climate_entity)
            if climate_state:
                # If climate entity is calling for heat and target > current, assume heat pump should be on
                climate_target: float | None = climate_state.attributes.get("temperature")
                climate_current: float | None = climate_state.attributes.get("current_temperature")
                
                should_be_on: bool = (
                    climate_state.state != "off" 
                    and climate_target is not None 
                    and climate_current is not None 
                    and climate_target > climate_current
                )
                
                # Update our internal state to match what it should be
                if should_be_on != self.coordinator.heat_pump_power_state:
                    self.coordinator.heat_pump_power_state = should_be_on
                    _LOGGER.info(
                        "Fixed heat pump state: %s (based on climate entity)", 
                        "ON" if should_be_on else "OFF"
                    )
                
                # Also sync target temperature if available
                if climate_target is not None:
                    self.coordinator.heat_pump_target_temp = float(climate_target)
                    _LOGGER.info("Synced target temperature to %s°C", climate_target)
        
        # Force an update to propagate the changes
        await self.coordinator.async_request_refresh()