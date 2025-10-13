"""Button platform for Smarter Heat Pump."""
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
    """Set up the Smarter Heat Pump button entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SmartHeatPumpFixButton(coordinator, config_entry)])


class SmartHeatPumpFixButton(CoordinatorEntity, ButtonEntity):
    """Fix button for Smarter Heat Pump to sync state."""

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
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
        }

    async def async_press(self) -> None:
        """Handle the button press to toggle tracked state without sending IR commands."""
        # Toggle the internal power state without sending any IR commands
        # This is used when someone manually changes the heat pump state with a physical remote
        new_state: bool = not self.coordinator.heat_pump_power_state
        self.coordinator.heat_pump_power_state = new_state

        _LOGGER.info(
            "Fix State button pressed - toggled internal state to: %s (no IR command sent)",
            "ON" if new_state else "OFF"
        )

        await self.coordinator.async_request_refresh()