"""Data update coordinator for Smarter Heat Pump."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_ROOM_TEMP_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_REMOTE_ENTITY,
    CONF_MIN_CYCLE_DURATION,
    CONF_MIN_POWER_CONSUMPTION,
    CONF_COP_VALUE,
    CONF_SCHEDULE_ENTITY,
    CONF_POWER_ON_COMMAND,
    CONF_POWER_OFF_COMMAND,
    CONF_TEMP_UP_COMMAND,
    CONF_TEMP_DOWN_COMMAND,
    DEFAULT_COP_VALUE,
    DEFAULT_MIN_POWER_CONSUMPTION,
)

_LOGGER = logging.getLogger(__name__)


class SmartHeatPumpCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Smarter Heat Pump data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry
        self.hass = hass

        # Internal state tracking
        self._climate_system_on: bool = False  # Climate entity on/off (system enabled)
        self._physical_heat_pump_on: bool = False  # Physical device power state
        self._heat_pump_target_temp: float = 20.0
        self._last_command_time: datetime | None = None
        self._cycle_start_time: datetime | None = None
        self._schedule_attributes: dict[str, Any] = {}

    async def async_set_schedule_attributes(self, entity_id: str, attributes: dict[str, Any]) -> None:
        """Set the schedule attributes."""
        self._schedule_attributes[entity_id] = attributes
        await self.async_request_refresh()

    @property
    def config(self) -> dict[str, Any]:
        """Return the configuration."""
        return self.entry.data

    @property
    def climate_system_on(self) -> bool:
        """Return whether the climate system is enabled."""
        return self._climate_system_on

    @climate_system_on.setter
    def climate_system_on(self, value: bool) -> None:
        """Set the climate system state."""
        if value != self._climate_system_on:
            self._climate_system_on = value
            if self.data is not None:
                self.async_set_updated_data(self.data)

    @property
    def physical_heat_pump_on(self) -> bool:
        """Return the physical heat pump power state."""
        return self._physical_heat_pump_on

    @physical_heat_pump_on.setter
    def physical_heat_pump_on(self, value: bool) -> None:
        """Set the physical heat pump power state."""
        if value != self._physical_heat_pump_on:
            self._physical_heat_pump_on = value
            if value:
                self._cycle_start_time = dt_util.utcnow()
            else:
                self._cycle_start_time = None
            if self.data is not None:
                self.async_set_updated_data(self.data)

    @property
    def heat_pump_target_temp(self) -> float:
        """Return the current heat pump target temperature."""
        return self._heat_pump_target_temp

    @heat_pump_target_temp.setter
    def heat_pump_target_temp(self, value: float) -> None:
        """Set the heat pump target temperature."""
        if value != self._heat_pump_target_temp:
            self._heat_pump_target_temp = value
            if self.data is not None:
                self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors."""
        await self.apply_schedule_control()
        await self.apply_automatic_control()
        try:
            data: dict[str, Any] = {}

            # Get room temperature
            room_temp_entity = self.config.get(CONF_ROOM_TEMP_SENSOR)
            if room_temp_entity:
                room_temp_state: State | None = self.hass.states.get(room_temp_entity)
                if room_temp_state and room_temp_state.state not in ("unknown", "unavailable"):
                    try:
                        data["room_temperature"] = float(room_temp_state.state)
                    except (ValueError, TypeError):
                        data["room_temperature"] = None
                else:
                    data["room_temperature"] = None

            # Get outside temperature data (from weather entity or temperature sensor)
            outside_temp: float | None = None

            # Try weather entity first
            weather_entity = self.config.get(CONF_WEATHER_ENTITY)
            if weather_entity:
                weather_state: State | None = self.hass.states.get(weather_entity)
                if weather_state and weather_state.attributes.get("temperature"):
                    outside_temp = weather_state.attributes["temperature"]

            # If no weather entity or no temperature from weather, try temperature sensor
            if outside_temp is None:
                outside_temp_sensor = self.config.get(CONF_OUTSIDE_TEMP_SENSOR)
                if outside_temp_sensor:
                    temp_state: State | None = self.hass.states.get(outside_temp_sensor)
                    if temp_state and temp_state.state not in ("unknown", "unavailable"):
                        try:
                            outside_temp = float(temp_state.state)
                        except (ValueError, TypeError):
                            outside_temp = None

            data["outside_temperature"] = outside_temp

            # Calculate estimated power consumption
            data["estimated_power"] = self._calculate_power_consumption(data)

            # Add internal state
            data["climate_system_on"] = self._climate_system_on
            data["physical_heat_pump_on"] = self._physical_heat_pump_on
            data["heat_pump_target_temp"] = self._heat_pump_target_temp
            data["cycle_start_time"] = self._cycle_start_time

            # Add schedule data if a schedule entity is configured
            schedule_entity = self.config.get(CONF_SCHEDULE_ENTITY)
            if schedule_entity:
                schedule_state: State | None = self.hass.states.get(schedule_entity)
                if schedule_state:
                    data["schedule_active"] = schedule_state.state == "on"
                    data["schedule_attributes"] = self._schedule_attributes.get(schedule_entity, {})
                else:
                    data["schedule_active"] = False
            else:
                data["schedule_active"] = False

            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with sensors: {err}") from err

    def _calculate_power_consumption(self, data: dict[str, Any]) -> float:
        """Calculate estimated power consumption based on COP and conditions."""
        if not self._physical_heat_pump_on:
            return 0.0

        min_power: int = self.config.get(CONF_MIN_POWER_CONSUMPTION, DEFAULT_MIN_POWER_CONSUMPTION)
        cop: float = self.config.get(CONF_COP_VALUE, DEFAULT_COP_VALUE)

        room_temp: float | None = data.get("room_temperature")
        outside_temp: float | None = data.get("outside_temperature")
        target_temp: float = self._heat_pump_target_temp

        # Base power consumption
        estimated_power: float = float(min_power)

        if room_temp is not None and outside_temp is not None:
            # Temperature difference affects efficiency
            temp_diff: float = abs(target_temp - outside_temp)
            room_target_diff: float = abs(target_temp - room_temp)

            # Higher temperature difference reduces COP efficiency
            # This is a simplified model - real COP varies significantly
            efficiency_factor: float = max(0.5, 1.0 - (temp_diff / 50.0))
            load_factor: float = min(2.0, 1.0 + (room_target_diff / 10.0))

            estimated_power = float(min_power) * load_factor / (cop * efficiency_factor)

        return round(estimated_power, 1)

    async def send_ir_command(self, command: str | None) -> bool:
        """Send IR command via Home Assistant service call."""
        try:
            if not command:
                _LOGGER.warning("No command service configured")
                return False

            remote_entity = self.config.get(CONF_REMOTE_ENTITY)
            if not remote_entity:
                _LOGGER.error("No remote entity configured")
                return False

            await self.hass.services.async_call(
                "remote",
                "send_command",
                {
                    "entity_id": remote_entity,
                    "command": command,
                },
            )
            self._last_command_time = dt_util.utcnow()
            return True

        except Exception as err:
            _LOGGER.error("Failed to send IR command %s: %s", command, err)
            return False

    def can_change_state(self) -> bool:
        """Check if enough time has passed since last command."""
        if self._last_command_time is None:
            return True

        min_interval: timedelta = timedelta(seconds=5)  # Minimum 5 seconds between commands
        return dt_util.utcnow() - self._last_command_time > min_interval

    def is_in_minimum_cycle(self) -> bool:
        """Check if we're still in minimum cycle duration."""
        if not self._cycle_start_time:
            return False

        min_cycle: int = self.config.get(CONF_MIN_CYCLE_DURATION, 300)
        elapsed: float = (dt_util.utcnow() - self._cycle_start_time).total_seconds()
        return elapsed < min_cycle

    async def apply_schedule_control(self) -> None:
        """Apply schedule-based control to the heat pump."""
        schedule_entity_id = self.config.get(CONF_SCHEDULE_ENTITY)
        if not schedule_entity_id:
            return

        schedule_state = self.hass.states.get(schedule_entity_id)
        if not schedule_state or schedule_state.state != "on":
            return

        attributes = self._schedule_attributes.get(schedule_entity_id, {})
        run_if_template = attributes.get("run_if")
        target_temperature = attributes.get("target_temperature")

        if run_if_template:
            try:
                from homeassistant.helpers.template import Template
                template = Template(run_if_template, self.hass)
                if not template.async_render():
                    return
            except Exception as err:
                _LOGGER.error("Error rendering run_if template: %s", err)
                return

        if target_temperature is not None:
            current_temp = self.heat_pump_target_temp
            temp_diff = target_temperature - current_temp
            if abs(temp_diff) < 0.5:
                return

            steps = int(abs(temp_diff))
            command = (
                self.config.get(CONF_TEMP_UP_COMMAND)
                if temp_diff > 0
                else self.config.get(CONF_TEMP_DOWN_COMMAND)
            )

            if command and self.can_change_state():
                for _ in range(steps):
                    await self.send_ir_command(command)
                self.heat_pump_target_temp = target_temperature

    async def apply_automatic_control(self) -> None:
        """Automatically control physical heat pump based on temperature when climate is on."""
        # Only apply automatic control if climate system is enabled
        if not self._climate_system_on:
            return

        # Can't control if we're in minimum cycle period
        if self.is_in_minimum_cycle():
            return

        # Can't control if commands were sent too recently
        if not self.can_change_state():
            return

        # Get current room temperature
        room_temp_entity = self.config.get(CONF_ROOM_TEMP_SENSOR)
        if not room_temp_entity:
            return

        room_temp_state: State | None = self.hass.states.get(room_temp_entity)
        if not room_temp_state or room_temp_state.state in ("unknown", "unavailable"):
            return

        try:
            room_temp = float(room_temp_state.state)
        except (ValueError, TypeError):
            return

        target_temp = self._heat_pump_target_temp
        temp_diff = target_temp - room_temp

        # Hysteresis: 0.5 degrees
        # If room is too cold and physical pump is off, turn it on
        if temp_diff > 0.5 and not self._physical_heat_pump_on:
            command = self.config.get(CONF_POWER_ON_COMMAND)
            if command:
                success = await self.send_ir_command(command)
                if success:
                    self._physical_heat_pump_on = True
                    _LOGGER.info(
                        "Automatically turned physical heat pump ON (room: %.1f°C, target: %.1f°C)",
                        room_temp,
                        target_temp
                    )

        # If room has reached target and physical pump is on, turn it off (go to idle)
        elif temp_diff < -0.5 and self._physical_heat_pump_on:
            command = self.config.get(CONF_POWER_OFF_COMMAND)
            if command:
                success = await self.send_ir_command(command)
                if success:
                    self._physical_heat_pump_on = False
                    _LOGGER.info(
                        "Automatically turned physical heat pump OFF (room: %.1f°C, target: %.1f°C)",
                        room_temp,
                        target_temp
                    )
