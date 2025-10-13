"""Schedule platform for Smarter Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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


class SmartHeatPumpSchedule(CoordinatorEntity, SwitchEntity):
    """Smarter Heat Pump schedule entity."""

    _attr_has_entity_name = True
    _attr_name = "Schedule"
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
        self._is_on = False
        self._attributes = {}

    @property
    def is_on(self) -> bool:
        """Return true if the schedule is on."""
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the schedule on."""
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the schedule off."""
        self._is_on = False
        self.async_write_ha_state()

    async def async_set_attributes(self, attributes: dict[str, Any]) -> None:
        """Set the schedule attributes."""
        self._attributes.update(attributes)
        self.async_write_ha_state()
