"""Config flow for Smarter Heat Pump integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    CONF_ROOM_TEMP_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_CLIMATE_ENTITY,
    CONF_REMOTE_ENTITY,
    CONF_REMOTE_DEVICE,
    CONF_VIRTUAL_SWITCH,
    CONF_ACTUATOR_SWITCH,
    CONF_MIN_CYCLE_DURATION,
    CONF_HEAT_TOLERANCE,
    CONF_COLD_TOLERANCE,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_INITIAL_HEAT_PUMP_TEMP,
    CONF_INITIAL_CLIMATE_TEMP,
    CONF_POWER_ON_COMMAND,
    CONF_POWER_OFF_COMMAND,
    CONF_TEMP_UP_COMMAND,
    CONF_TEMP_DOWN_COMMAND,
    CONF_SCHEDULE_ENTITY,
    CONF_MIN_POWER_CONSUMPTION,
    CONF_COP_VALUE,
    CONF_OUTSIDE_TEMP_DIFF,
    CONF_MIN_OUTSIDE_TEMP,
    CONF_SCHEDULE_ENABLED,
    DEFAULT_MIN_CYCLE_DURATION,
    DEFAULT_HEAT_TOLERANCE,
    DEFAULT_COLD_TOLERANCE,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_INITIAL_HEAT_PUMP_TEMP,
    DEFAULT_INITIAL_CLIMATE_TEMP,
    DEFAULT_MIN_POWER_CONSUMPTION,
    DEFAULT_COP_VALUE,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Smart Heat Pump"): str,
        vol.Required(CONF_ROOM_TEMP_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
        vol.Optional(CONF_OUTSIDE_TEMP_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_CLIMATE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="climate")
        ),
        vol.Required(CONF_REMOTE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="remote")
        ),
        vol.Optional(CONF_ACTUATOR_SWITCH): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="switch")
        ),
        vol.Optional(CONF_VIRTUAL_SWITCH, default=True): bool,
        vol.Optional(CONF_SCHEDULE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="schedule")
        ),
    }
)

STEP_COMMANDS_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_REMOTE_DEVICE): str,
        vol.Required(CONF_POWER_ON_COMMAND): str,
        vol.Required(CONF_POWER_OFF_COMMAND): str,
        vol.Required(CONF_TEMP_UP_COMMAND): str,
        vol.Required(CONF_TEMP_DOWN_COMMAND): str,
    }
)

STEP_SETTINGS_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MIN_CYCLE_DURATION, default=DEFAULT_MIN_CYCLE_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=60, max=3600)
        ),
        vol.Optional(CONF_HEAT_TOLERANCE, default=DEFAULT_HEAT_TOLERANCE): vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=5.0)
        ),
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_COLD_TOLERANCE): vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=5.0)
        ),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.All(
            vol.Coerce(int), vol.Range(min=-20, max=40)
        ),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.All(
            vol.Coerce(int), vol.Range(min=-20, max=40)
        ),
        vol.Optional(CONF_INITIAL_HEAT_PUMP_TEMP, default=DEFAULT_INITIAL_HEAT_PUMP_TEMP): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=35)
        ),
        vol.Optional(CONF_INITIAL_CLIMATE_TEMP, default=DEFAULT_INITIAL_CLIMATE_TEMP): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=35)
        ),
        vol.Optional(CONF_MIN_POWER_CONSUMPTION, default=DEFAULT_MIN_POWER_CONSUMPTION): vol.All(
            vol.Coerce(int), vol.Range(min=100, max=10000)
        ),
        vol.Optional(CONF_COP_VALUE, default=DEFAULT_COP_VALUE): vol.All(
            vol.Coerce(float), vol.Range(min=1.0, max=10.0)
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    # Validate that required entities exist
    required_entities = [CONF_ROOM_TEMP_SENSOR, CONF_REMOTE_ENTITY]
    for entity_key in required_entities:
        entity_id: str | None = data.get(entity_key)
        if entity_id and not hass.states.get(entity_id):
            raise ValueError(f"Entity {entity_id} not found")

    # Validate that at least one outside temperature source is provided
    weather_entity: str | None = data.get(CONF_WEATHER_ENTITY)
    outside_temp_sensor: str | None = data.get(CONF_OUTSIDE_TEMP_SENSOR)

    if not weather_entity and not outside_temp_sensor:
        raise ValueError("missing_outside_temp")

    # Validate optional entities if provided
    for entity_key in [CONF_WEATHER_ENTITY, CONF_OUTSIDE_TEMP_SENSOR]:
        entity_id: str | None = data.get(entity_key)
        if entity_id and not hass.states.get(entity_id):
            raise ValueError(f"Entity {entity_id} not found")

    return {"title": str(data[CONF_NAME])}


class SmartHeatPumpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smarter Heat Pump."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info: dict[str, str] = await validate_input(self.hass, user_input)

                # If no actuator switch provided, default virtual_switch to True
                if not user_input.get(CONF_ACTUATOR_SWITCH):
                    user_input[CONF_VIRTUAL_SWITCH] = user_input.get(CONF_VIRTUAL_SWITCH, True)

                self._data.update(user_input)
                return await self.async_step_commands()
            except ValueError as err:
                _LOGGER.error("Validation error: %s", err)
                error_msg = str(err)
                if error_msg == "missing_outside_temp":
                    errors["base"] = "missing_outside_temp"
                else:
                    errors["base"] = "invalid_entity"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_commands(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the commands configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_settings()

        return self.async_show_form(
            step_id="commands",
            data_schema=STEP_COMMANDS_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the settings configuration step."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)

        return self.async_show_form(
            step_id="settings",
            data_schema=STEP_SETTINGS_DATA_SCHEMA,
        )
