"""Data update coordinator for Smarter Heat Pump."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_ROOM_TEMP_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_CLIMATE_ENTITY,
    CONF_MIN_CYCLE_DURATION,
    CONF_HEAT_TOLERANCE,
    CONF_COLD_TOLERANCE,
    CONF_MIN_POWER_CONSUMPTION,
    CONF_COP_VALUE,
    CONF_SCHEDULE_ENABLED,
    CONF_SCHEDULE_AUTO_CONTROL,
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
        self._heat_pump_power_state: bool = False
        self._heat_pump_target_temp: float = 20.0
        self._last_command_time: datetime | None = None
        self._cycle_start_time: datetime | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Return the configuration."""
        return self.entry.data

    @property
    def heat_pump_power_state(self) -> bool:
        """Return the current heat pump power state."""
        return self._heat_pump_power_state

    @heat_pump_power_state.setter
    def heat_pump_power_state(self, value: bool) -> None:
        """Set the heat pump power state."""
        if value != self._heat_pump_power_state:
            self._heat_pump_power_state = value
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

            # Get climate entity state
            climate_entity = self.config.get(CONF_CLIMATE_ENTITY)
            if climate_entity:
                climate_state: State | None = self.hass.states.get(climate_entity)
                if climate_state:
                    data["climate_state"] = climate_state.state
                    data["climate_target_temp"] = climate_state.attributes.get("temperature")
                    data["climate_current_temp"] = climate_state.attributes.get("current_temperature")

            # Calculate estimated power consumption
            data["estimated_power"] = self._calculate_power_consumption(data)

            # Add internal state
            data["heat_pump_power_state"] = self._heat_pump_power_state
            data["heat_pump_target_temp"] = self._heat_pump_target_temp
            data["cycle_start_time"] = self._cycle_start_time

            # Add schedule data if schedule is enabled
            if self.config.get(CONF_SCHEDULE_ENABLED, False):
                data["schedule_enabled"] = True
                schedule_entity = f"switch.smart_heatpump_{self.entry.entry_id}_schedule"
                schedule_state: State | None = self.hass.states.get(schedule_entity)
                if schedule_state:
                    data["schedule_active"] = schedule_state.state == "on"
                    data["schedule_attributes"] = dict(schedule_state.attributes)
                else:
                    data["schedule_active"] = False
                    data["schedule_attributes"] = {}
            else:
                data["schedule_enabled"] = False
                data["schedule_active"] = False
                data["schedule_attributes"] = {}

            # Apply schedule control after data is updated (if enabled)
            if self.config.get(CONF_SCHEDULE_AUTO_CONTROL, True):
                await self.apply_schedule_control()

            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with sensors: {err}") from err

    def _calculate_power_consumption(self, data: dict[str, Any]) -> float:
        """Calculate estimated power consumption based on COP and conditions."""
        if not self._heat_pump_power_state:
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

    async def send_ir_command(self, command_service: str | None) -> bool:
        """Send IR command via Home Assistant service call."""
        try:
            if not command_service:
                _LOGGER.warning("No command service configured")
                return False

            # Parse service call format: domain.service with optional data
            if "." in command_service:
                domain, service = command_service.split(".", 1)
                await self.hass.services.async_call(domain, service, {})
                self._last_command_time = dt_util.utcnow()
                return True
            else:
                _LOGGER.error("Invalid command format: %s", command_service)
                return False

        except Exception as err:
            _LOGGER.error("Failed to send IR command %s: %s", command_service, err)
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

        min_cycle: int = self.config.get(CONF_MIN_CYCLE_DURATION, DEFAULT_MIN_CYCLE_DURATION)
        elapsed: float = (dt_util.utcnow() - self._cycle_start_time).total_seconds()
        return elapsed < min_cycle

    def get_schedule_entity(self) -> State | None:
        """Get the schedule entity if it exists."""
        if not self.config.get(CONF_SCHEDULE_ENABLED, False):
            return None

        schedule_entity_id: str = f"switch.{DOMAIN}_{self.entry.entry_id}_schedule"
        return self.hass.states.get(schedule_entity_id)

    async def apply_schedule_control(self) -> bool:
        """Apply schedule-based control to the heat pump."""
        if not self.config.get(CONF_SCHEDULE_ENABLED, False):
            return False

        if self.data is None:
            return False

        schedule_data: dict[str, Any] = self.data.get("schedule_attributes", {})
        schedule_active: bool = self.data.get("schedule_active", False)

        # Get schedule target temperature if available
        schedule_target_temp: float | None = schedule_data.get("schedule_target_temp")

        # Determine if heat pump should be on according to schedule
        should_be_on: bool = schedule_active

        # Apply schedule control
        if should_be_on and not self._heat_pump_power_state:
            # Schedule says turn on, but heat pump is off
            if self.can_change_state():
                success = await self.send_ir_command(
                    self.config.get(CONF_POWER_ON_COMMAND)
                )
                if success:
                    self._heat_pump_power_state = True

                    # Set target temperature if specified by schedule
                    if schedule_target_temp is not None:
                        await self._set_schedule_target_temperature(schedule_target_temp)

                    _LOGGER.info("Schedule turned heat pump ON")
                    return True

        elif not should_be_on and self._heat_pump_power_state:
            # Schedule says turn off, but heat pump is on
            if self.can_change_state() and not self.is_in_minimum_cycle():
                success = await self.send_ir_command(
                    self.config.get(CONF_POWER_OFF_COMMAND)
                )
                if success:
                    self._heat_pump_power_state = False
                    _LOGGER.info("Schedule turned heat pump OFF")
                    return True
            else:
                _LOGGER.debug("Cannot turn off heat pump: minimum cycle or rate limit")

        elif should_be_on and self._heat_pump_power_state and schedule_target_temp is not None:
            # Heat pump is on and schedule specifies a target temperature
            await self._set_schedule_target_temperature(schedule_target_temp)

        return False

    async def _set_schedule_target_temperature(self, target_temp: float) -> None:
        """Set heat pump target temperature based on schedule."""
        current_temp: float = self._heat_pump_target_temp
        temp_diff: float = target_temp - current_temp

        if abs(temp_diff) < 0.5:  # Already close enough
            return

        if not self.can_change_state():
            return

        # Send appropriate commands to reach target
        steps: int = int(abs(temp_diff))
        command: str | None = (
            self.config.get(CONF_TEMP_UP_COMMAND)
            if temp_diff > 0
            else self.config.get(CONF_TEMP_DOWN_COMMAND)
        )

        if command:
            for _ in range(min(steps, 3)):  # Limit to 3 steps at once for schedule
                await self.send_ir_command(command)

            self._heat_pump_target_temp = target_temp
            _LOGGER.info("Schedule adjusted target temperature to %s°C", target_temp)