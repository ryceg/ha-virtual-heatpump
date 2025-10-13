"""Smarter Heat Pump Integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final[list[Platform]] = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=30)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smarter Heat Pump from a config entry."""
    coordinator = SmartHeatPumpCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_set_schedule_attributes(call):
        """Handle the service call to set the schedule attributes."""
        entity_id = call.data.get("entity_id")
        data = call.data.get("data")
        if entity_id and data:
            await coordinator.async_set_schedule_attributes(entity_id, data)

    hass.services.async_register(
        DOMAIN, "set_schedule_attributes", async_set_schedule_attributes
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms_to_unload: list[Platform | str] = list(PLATFORMS)
    
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, platforms_to_unload)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok