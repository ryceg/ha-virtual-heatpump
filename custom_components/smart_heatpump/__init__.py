"""Smarter Heat Pump Integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final, Any

from homeassistant.components.diagnostics import async_redact_data
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
    Platform.NUMBER,
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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SmartHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get sensitive data to redact
    to_redact = [
        "remote_entity",  # Could contain API keys or sensitive device info
        "remote_device",  # Could contain device identifiers
        "actuator_switch",  # Could contain switch entity IDs with sensitive info
        "room_temp_sensor",  # Could contain entity IDs
        "weather_entity",  # Could contain entity IDs
        "outside_temp_sensor",  # Could contain entity IDs
        "schedule_entity",  # Could contain entity IDs
    ]

    return {
        "entry_data": async_redact_data(entry.data, to_redact),
        "coordinator_data": {
            "climate_system_on": coordinator.climate_system_on,
            "physical_heat_pump_on": coordinator.physical_heat_pump_on,
            "heat_pump_set_temp": coordinator.heat_pump_set_temp,
            "target_temperature": coordinator.target_temperature,
            "last_turn_on_time": coordinator._last_turn_on_time.isoformat() if coordinator._last_turn_on_time else None,
            "last_turn_on_source": coordinator._last_turn_on_source,
            "last_command_time": coordinator._last_command_time.isoformat() if coordinator._last_command_time else None,
            "cycle_start_time": coordinator._cycle_start_time.isoformat() if coordinator._cycle_start_time else None,
        },
        "runtime_data": coordinator.data if coordinator.data else {},
        "schedule_info": {
            "schedule_entity_configured": entry.data.get("schedule_entity") is not None,
            "schedule_attributes_count": len(coordinator._schedule_attributes.get(entry.data.get("schedule_entity"), {})),
        },
    }