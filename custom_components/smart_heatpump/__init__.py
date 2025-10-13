"""Smart Heat Pump Integration for Home Assistant."""
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

# Conditionally add schedule platform if enabled
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Heat Pump from a config entry."""
    from .const import CONF_SCHEDULE_ENABLED
    
    # Create coordinator for data updates
    coordinator: SmartHeatPumpCoordinator = SmartHeatPumpCoordinator(hass, entry)
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Determine which platforms to set up
    platforms_to_setup: list[Platform | str] = list(PLATFORMS)
    if entry.data.get(CONF_SCHEDULE_ENABLED, False):
        platforms_to_setup.append("schedule")
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms_to_setup)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Determine which platforms were set up
    platforms_to_unload: list[Platform | str] = list(PLATFORMS)
    if entry.data.get("schedule_enabled", False):
        platforms_to_unload.append("schedule")
    
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, platforms_to_unload)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok