"""Schedule platform for Smarter Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarter Heat Pump schedule entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SmartHeatPumpSchedule(coordinator, config_entry)])


class SmartHeatPumpSchedule(CoordinatorEntity, SensorEntity):
    """Smarter Heat Pump schedule entity."""

    _attr_has_entity_name = True
    _attr_name = "Schedule Status"
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: SmartHeatPumpCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the schedule entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_schedule"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smarter Heat Pump"),
            "manufacturer": "Smarter Heat Pump Integration",
            "model": "Smarter Heat Pump",
        }

    @property
    def native_value(self) -> str:
        """Return the schedule status."""
        if self.coordinator.data is None:
            return "unknown"

        schedule_active = self.coordinator.data.get("schedule_active", False)
        return "active" if schedule_active else "inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}

        schedule_attributes = self.coordinator.data.get("schedule_attributes", {})
        return schedule_attributes
