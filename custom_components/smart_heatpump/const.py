"""Constants for the Smarter Heat Pump integration."""
from __future__ import annotations

from typing import Final

from homeassistant.const import UnitOfTemperature, UnitOfPower

DOMAIN: Final[str] = "smart_heatpump"

# Configuration keys
CONF_ROOM_TEMP_SENSOR: Final[str] = "room_temp_sensor"
CONF_WEATHER_ENTITY: Final[str] = "weather_entity"
CONF_OUTSIDE_TEMP_SENSOR: Final[str] = "outside_temp_sensor"
CONF_CLIMATE_ENTITY: Final[str] = "climate_entity"
CONF_REMOTE_ENTITY: Final[str] = "remote_entity"
CONF_ACTUATOR_SWITCH: Final[str] = "actuator_switch"
CONF_VIRTUAL_SWITCH: Final[str] = "virtual_switch"
CONF_MIN_CYCLE_DURATION: Final[str] = "min_cycle_duration"
CONF_HEAT_TOLERANCE: Final[str] = "heat_tolerance"
CONF_COLD_TOLERANCE: Final[str] = "cold_tolerance"
CONF_MIN_TEMP: Final[str] = "min_temp"
CONF_MAX_TEMP: Final[str] = "max_temp"
CONF_INITIAL_HEAT_PUMP_TEMP: Final[str] = "initial_heat_pump_temp"
CONF_INITIAL_CLIMATE_TEMP: Final[str] = "initial_climate_temp"
CONF_POWER_ON_COMMAND: Final[str] = "power_on_command"
CONF_POWER_OFF_COMMAND: Final[str] = "power_off_command"
CONF_TEMP_UP_COMMAND: Final[str] = "temp_up_command"
CONF_TEMP_DOWN_COMMAND: Final[str] = "temp_down_command"
CONF_REMOTE_DEVICE: Final[str] = "remote_device"
CONF_SCHEDULE_ENTITY: Final[str] = "schedule_entity"
CONF_MIN_POWER_CONSUMPTION: Final[str] = "min_power_consumption"
CONF_COP_VALUE: Final[str] = "cop_value"
CONF_OUTSIDE_TEMP_DIFF: Final[str] = "outside_temp_diff"
CONF_MIN_OUTSIDE_TEMP: Final[str] = "min_outside_temp"

# Schedule configuration
CONF_SCHEDULE_ENABLED: Final[str] = "schedule_enabled"

# Default values
DEFAULT_MIN_CYCLE_DURATION: Final[int] = 300  # 5 minutes
DEFAULT_HEAT_TOLERANCE: Final[float] = 0.5
DEFAULT_COLD_TOLERANCE: Final[float] = 0.5
DEFAULT_MIN_TEMP: Final[int] = 16
DEFAULT_MAX_TEMP: Final[int] = 30
DEFAULT_INITIAL_HEAT_PUMP_TEMP: Final[int] = 20
DEFAULT_INITIAL_CLIMATE_TEMP: Final[int] = 22
DEFAULT_MIN_POWER_CONSUMPTION: Final[int] = 1200  # 1.2kW in watts
DEFAULT_COP_VALUE: Final[float] = 3.0
DEFAULT_OUTSIDE_TEMP_DIFF: Final[int] = 5
DEFAULT_MIN_OUTSIDE_TEMP: Final[int] = -10

# Schedule defaults


# Entity keys
ENTITY_CLIMATE: Final[str] = "climate"
ENTITY_SWITCH: Final[str] = "switch"
ENTITY_CURRENT_TEMP_SENSOR: Final[str] = "current_temp_sensor"
ENTITY_TARGET_TEMP_SENSOR: Final[str] = "target_temp_sensor"
ENTITY_POWER_SENSOR: Final[str] = "power_sensor"
ENTITY_STATUS_BINARY_SENSOR: Final[str] = "status_binary_sensor"
ENTITY_FIX_BUTTON: Final[str] = "fix_button"
ENTITY_FIX_BUTTON: Final[str] = "fix_button"
ENTITY_SCHEDULE: Final[str] = "schedule"

# Attributes
ATTR_HEAT_PUMP_TARGET_TEMP: Final[str] = "heat_pump_target_temp"
ATTR_ESTIMATED_POWER: Final[str] = "estimated_power"
ATTR_COP: Final[str] = "cop"
ATTR_OUTSIDE_TEMP: Final[str] = "outside_temp"
ATTR_SCHEDULE_ACTIVE: Final[str] = "schedule_active"
ATTR_SCHEDULE_TARGET_TEMP: Final[str] = "schedule_target_temp"
ATTR_SCHEDULE_MODE: Final[str] = "schedule_mode"
ATTR_SCHEDULE_NEXT_CHANGE: Final[str] = "schedule_next_change"