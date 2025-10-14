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
    CONF_REMOTE_DEVICE,
    CONF_ACTUATOR_SWITCH,
    CONF_MIN_CYCLE_DURATION,
    CONF_MIN_POWER_CONSUMPTION,
    CONF_COP_VALUE,
    CONF_SCHEDULE_ENTITY,
    CONF_POWER_ON_COMMAND,
    CONF_POWER_OFF_COMMAND,
    CONF_TEMP_UP_COMMAND,
    CONF_TEMP_DOWN_COMMAND,
    CONF_INITIAL_HEAT_PUMP_TEMP,
    CONF_INITIAL_TARGET_TEMP,
    DEFAULT_COP_VALUE,
    DEFAULT_MIN_POWER_CONSUMPTION,
    DEFAULT_INITIAL_HEAT_PUMP_TEMP,
    DEFAULT_INITIAL_TARGET_TEMP,
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

        # Initialize temperatures from config or use defaults
        self._heat_pump_set_temp: float = float(
            entry.data.get(CONF_INITIAL_HEAT_PUMP_TEMP, DEFAULT_INITIAL_HEAT_PUMP_TEMP)
        )  # Physical heat pump's set temperature
        self._target_temperature: float = float(
            entry.data.get(CONF_INITIAL_TARGET_TEMP, DEFAULT_INITIAL_TARGET_TEMP)
        )  # User's desired target temperature

        self._last_command_time: datetime | None = None
        self._cycle_start_time: datetime | None = None
        self._schedule_attributes: dict[str, Any] = {}

        # Track how the heat pump was last turned on for smart schedule behavior
        self._last_turn_on_time: datetime | None = None
        self._last_turn_on_source: str | None = None  # "schedule", "climate", "fix", "manual"

    async def async_set_schedule_attributes(self, entity_id: str, attributes: dict[str, Any]) -> None:
        """Set the schedule attributes."""
        self._schedule_attributes[entity_id] = attributes
        await self.async_request_refresh()

    def record_turn_on_source(self, source: str) -> None:
        """Record how the heat pump was turned on for diagnostic purposes."""
        self._last_turn_on_source = source
        if source in ["schedule", "climate", "fix", "manual"]:
            self._last_turn_on_time = dt_util.utcnow()

    def should_auto_turn_off_schedule(self, schedule_entity_id: str) -> bool:
        """Check if heat pump should auto-turn-off when schedule ends."""
        # Don't auto-turn-off if it wasn't turned on by schedule
        if self._last_turn_on_source != "schedule":
            return False

        # Check if there's a keep_on flag in the schedule attributes
        schedule_attributes = self._schedule_attributes.get(schedule_entity_id, {})
        schedule_entity = self.hass.states.get(schedule_entity_id)
        if schedule_entity:
            entity_attributes = dict(schedule_entity.attributes)
            entity_attributes.pop("schedule", None)
            entity_attributes.pop("friendly_name", None)
            entity_attributes.pop("icon", None)
            schedule_attributes.update(entity_attributes)

        keep_on = schedule_attributes.get("keep_on", False)
        if keep_on:
            return False

        # Check if there's another active schedule entry that would "roll into"
        return not self._has_upcoming_schedule_entry(schedule_entity_id)

    def _has_upcoming_schedule_entry(self, schedule_entity_id: str) -> bool:
        """Check if there's another schedule entry that starts within the next 30 minutes."""
        schedule_entity = self.hass.states.get(schedule_entity_id)
        if not schedule_entity:
            return False

        schedule_data = schedule_entity.attributes.get("schedule", {})
        if not schedule_data:
            return False

        now = dt_util.now()
        next_30_min = now + timedelta(minutes=30)

        for schedule_entry in schedule_data.get("schedule", []):
            from_time = schedule_entry.get("from")
            to_time = schedule_entry.get("to")
            weekdays = schedule_entry.get("weekdays", [])

            if not from_time or not to_time:
                continue

            # Check if this schedule entry would be active in the next 30 minutes
            entry_start_today = self._time_to_datetime(from_time)
            entry_end_today = self._time_to_datetime(to_time)

            # Handle overnight schedules
            if entry_end_today < entry_start_today:
                entry_end_today += timedelta(days=1)

            # Check if entry is active now or will be active soon
            if entry_start_today <= now <= entry_end_today:
                return True

            # Check if entry starts within next 30 minutes
            if entry_start_today > now and entry_start_today <= next_30_min:
                return True

        return False

    def _time_to_datetime(self, time_str: str) -> datetime:
        """Convert time string (HH:MM) to datetime for today."""
        try:
            hours, minutes = map(int, time_str.split(":"))
            now = dt_util.now()
            return now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        except (ValueError, AttributeError):
            return dt_util.now()

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
                self._last_turn_on_time = dt_util.utcnow()
            else:
                self._cycle_start_time = None
            if self.data is not None:
                self.async_set_updated_data(self.data)

    @property
    def heat_pump_set_temp(self) -> float:
        """Return the physical heat pump's set temperature."""
        return self._heat_pump_set_temp

    @heat_pump_set_temp.setter
    def heat_pump_set_temp(self, value: float) -> None:
        """Set the physical heat pump's set temperature."""
        if value != self._heat_pump_set_temp:
            self._heat_pump_set_temp = value
            if self.data is not None:
                self.async_set_updated_data(self.data)

    @property
    def target_temperature(self) -> float:
        """Return the user's desired target temperature."""
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, value: float) -> None:
        """Set the user's desired target temperature."""
        if value != self._target_temperature:
            self._target_temperature = value
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
            data["heat_pump_set_temp"] = self._heat_pump_set_temp
            data["target_temperature"] = self._target_temperature
            data["cycle_start_time"] = self._cycle_start_time

            # Add schedule data if a schedule entity is configured
            schedule_entity = self.config.get(CONF_SCHEDULE_ENTITY)
            if schedule_entity:
                schedule_state: State | None = self.hass.states.get(schedule_entity)
                if schedule_state:
                    data["schedule_active"] = self._is_schedule_active(schedule_state)
                    # Get attributes from both sources for display
                    schedule_entity_attributes = dict(schedule_state.attributes)
                    schedule_entity_attributes.pop("schedule", None)
                    schedule_entity_attributes.pop("friendly_name", None)
                    schedule_entity_attributes.pop("icon", None)
                    data["schedule_attributes"] = {**self._schedule_attributes.get(schedule_entity, {}), **schedule_entity_attributes}
                else:
                    data["schedule_active"] = False
                    data["schedule_attributes"] = {}
            else:
                data["schedule_active"] = False
                data["schedule_attributes"] = {}

            # Add diagnostic information
            if self._last_turn_on_time:
                data["last_turn_on_time"] = self._last_turn_on_time.isoformat()
            else:
                data["last_turn_on_time"] = None

            data["last_turn_on_source"] = self._last_turn_on_source

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
        target_temp: float = self._heat_pump_set_temp

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

    async def turn_on_device(self) -> bool:
        """Turn on the physical device (via actuator switch or IR command)."""
        actuator_switch = self.config.get(CONF_ACTUATOR_SWITCH)

        if actuator_switch:
            # Control via actuator switch
            try:
                await self.hass.services.async_call(
                    "switch",
                    "turn_on",
                    {"entity_id": actuator_switch},
                    blocking=True,
                )
                self._last_command_time = dt_util.utcnow()
                return True
            except Exception as err:
                _LOGGER.error("Failed to turn on actuator switch %s: %s", actuator_switch, err)
                return False
        else:
            # Control via IR command
            command = self.config.get(CONF_POWER_ON_COMMAND)
            return await self.send_ir_command(command)

    async def turn_on_device_with_source(self, source: str) -> bool:
        """Turn on the physical device and record the source."""
        self.record_turn_on_source(source)
        return await self.turn_on_device()

    async def turn_off_device(self) -> bool:
        """Turn off the physical device (via actuator switch or IR command)."""
        actuator_switch = self.config.get(CONF_ACTUATOR_SWITCH)

        if actuator_switch:
            # Control via actuator switch
            try:
                await self.hass.services.async_call(
                    "switch",
                    "turn_off",
                    {"entity_id": actuator_switch},
                    blocking=True,
                )
                self._last_command_time = dt_util.utcnow()
                return True
            except Exception as err:
                _LOGGER.error("Failed to turn off actuator switch %s: %s", actuator_switch, err)
                return False
        else:
            # Control via IR command
            command = self.config.get(CONF_POWER_OFF_COMMAND)
            return await self.send_ir_command(command)

    async def send_ir_command(self, command: str | None) -> bool:
        """Send IR command via Home Assistant service call."""
        try:
            if not command:
                _LOGGER.warning("No command configured")
                return False

            remote_entity = self.config.get(CONF_REMOTE_ENTITY)
            if not remote_entity:
                _LOGGER.error("No remote entity configured")
                return False

            # Build service data
            service_data: dict[str, Any] = {
                "entity_id": remote_entity,
                "command": command,
            }

            # Add device parameter if configured (needed for Broadlink remotes)
            remote_device = self.config.get(CONF_REMOTE_DEVICE)
            if remote_device:
                service_data["device"] = remote_device

            await self.hass.services.async_call(
                "remote",
                "send_command",
                service_data,
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
        if not schedule_state:
            return

        # Check if schedule is currently active based on its schedule data
        schedule_active = self._is_schedule_active(schedule_state)

        # If schedule is not active, check if we should turn off (schedule ended)
        if not schedule_active and self._physical_heat_pump_on:
            if self.should_auto_turn_off_schedule(schedule_entity_id):
                _LOGGER.info("Schedule ended, turning off heat pump (not rolling into another entry)")
                if self.can_change_state():
                    success = await self.turn_off_device()
                    if success:
                        self._physical_heat_pump_on = False
                        self._climate_system_on = False
            return

        # If schedule is active, apply attributes
        if schedule_active:
            # Get custom attributes - first check schedule entity's attributes, then fall back to service-set attributes
            schedule_entity_attributes = dict(schedule_state.attributes)
            # Remove built-in schedule attributes to avoid conflicts
            schedule_entity_attributes.pop("schedule", None)
            schedule_entity_attributes.pop("friendly_name", None)
            schedule_entity_attributes.pop("icon", None)

            attributes = {**self._schedule_attributes.get(schedule_entity_id, {}), **schedule_entity_attributes}

            # Check run_if condition
            run_if_template = attributes.get("run_if")
            if run_if_template:
                try:
                    from homeassistant.helpers.template import Template
                    template = Template(run_if_template, self.hass)
                    if not template.async_render():
                        return
                except Exception as err:
                    _LOGGER.error("Error rendering run_if template: %s", err)
                    return

            # Apply all matching attributes
            await self._apply_schedule_attributes(attributes)

    def _is_schedule_active(self, schedule_state: State) -> bool:
        """Check if the schedule entity is currently active based on its schedule data."""
        # Check if schedule entity has schedule information
        schedule_data = schedule_state.attributes.get("schedule", {})
        if not schedule_data:
            return False

        # Get current time
        now = dt_util.now()

        # Check each schedule entry
        for schedule_entry in schedule_data.get("schedule", []):
            # Parse the schedule entry
            from_time = schedule_entry.get("from")
            to_time = schedule_entry.get("to")
            weekdays = schedule_entry.get("weekdays", [])

            if not from_time or not to_time:
                continue

            # Convert times to minutes since midnight for easier comparison
            from_minutes = self._time_to_minutes(from_time)
            to_minutes = self._time_to_minutes(to_time)
            current_minutes = now.hour * 60 + now.minute

            # Handle overnight schedules (when to_time is next day)
            if to_minutes < from_minutes:
                if current_minutes >= from_minutes or current_minutes <= to_minutes:
                    active = True
                else:
                    active = False
            else:
                if from_minutes <= current_minutes <= to_minutes:
                    active = True
                else:
                    active = False

            # Check weekdays if specified
            if weekdays and active:
                current_weekday = now.weekday()  # 0 = Monday, 6 = Sunday
                # Convert HA weekdays to Python weekdays (HA: 1=Monday, 7=Sunday)
                ha_weekdays = weekdays if isinstance(weekdays, list) else [weekdays]
                python_weekdays = [(wd - 1) % 7 for wd in ha_weekdays]  # Convert to 0-6
                if current_weekday not in python_weekdays:
                    active = False

            if active:
                return True

        return False

    def _time_to_minutes(self, time_str: str) -> int:
        """Convert time string (HH:MM) to minutes since midnight."""
        try:
            hours, minutes = map(int, time_str.split(":"))
            return hours * 60 + minutes
        except (ValueError, AttributeError):
            _LOGGER.warning("Invalid time format: %s", time_str)
            return 0

    async def _apply_schedule_attributes(self, attributes: dict[str, Any]) -> None:
        """Apply schedule attributes to the heat pump."""
        # Apply set temperature (what gets sent to the physical device)
        set_temperature = attributes.get("set_temperature")
        if set_temperature is not None:
            current_temp = self.heat_pump_set_temp
            temp_diff = set_temperature - current_temp
            if abs(temp_diff) >= 0.5:  # Only change if difference is significant
                steps = int(abs(temp_diff))
                command = (
                    self.config.get(CONF_TEMP_UP_COMMAND)
                    if temp_diff > 0
                    else self.config.get(CONF_TEMP_DOWN_COMMAND)
                )

                if command and self.can_change_state():
                    for _ in range(steps):
                        await self.send_ir_command(command)
                    self.heat_pump_set_temp = set_temperature
                    _LOGGER.info("Schedule set device temperature: %.1f°C", set_temperature)

        # Apply HVAC mode if specified
        hvac_mode = attributes.get("hvac_mode")
        if hvac_mode:
            if hvac_mode == "off" and self._climate_system_on:
                if self._physical_heat_pump_on and self.can_change_state():
                    success = await self.turn_off_device()
                    if success:
                        self._physical_heat_pump_on = False
                self._climate_system_on = False
                _LOGGER.info("Schedule turned off climate system")
            elif hvac_mode == "heat" and not self._climate_system_on:
                self._climate_system_on = True
                if not self._physical_heat_pump_on and self.can_change_state():
                    success = await self.turn_on_device_with_source("schedule")
                    if success:
                        self._physical_heat_pump_on = True
                _LOGGER.info("Schedule turned on climate system")

        # Apply target temperature if specified
        target_temp = attributes.get("target_temperature")
        if target_temp is not None and target_temp != self._target_temperature:
            self._target_temperature = target_temp
            _LOGGER.info("Schedule set target temperature: %.1f°C", target_temp)

        # Apply preset mode if specified
        preset_mode = attributes.get("preset_mode")
        if preset_mode:
            try:
                from homeassistant.components.climate import ClimatePresetMode

                # Define preset temperatures (same as in climate entity)
                preset_temperatures = {
                    ClimatePresetMode.HOME: 21.0,
                    ClimatePresetMode.AWAY: 16.0,
                    ClimatePresetMode.SLEEP: 18.0,
                    ClimatePresetMode.COMFORT: 22.0,
                }

                if preset_mode in preset_temperatures:
                    preset_temp = preset_temperatures[preset_mode]
                    if preset_temp != self._target_temperature:
                        self._target_temperature = preset_temp
                        _LOGGER.info("Schedule set preset mode %s with temperature %.1f°C", preset_mode, preset_temp)
                else:
                    _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            except ImportError:
                _LOGGER.error("ClimatePresetMode not available")

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

        # Compare room temperature against target temperature (user's desired temp)
        target_temp = self._target_temperature
        temp_diff = target_temp - room_temp

        # Hysteresis: 0.5 degrees
        # If room is too cold and physical pump is off, turn it on
        if temp_diff > 0.5 and not self._physical_heat_pump_on:
            success = await self.turn_on_device()
            if success:
                self._physical_heat_pump_on = True
                _LOGGER.info(
                    "Automatically turned physical heat pump ON (room: %.1f°C, target: %.1f°C)",
                    room_temp,
                    target_temp
                )

        # If room has reached target and physical pump is on, turn it off (go to idle)
        elif temp_diff < -0.5 and self._physical_heat_pump_on:
            success = await self.turn_off_device()
            if success:
                self._physical_heat_pump_on = False
                _LOGGER.info(
                    "Automatically turned physical heat pump OFF (room: %.1f°C, target: %.1f°C)",
                    room_temp,
                    target_temp
                )
