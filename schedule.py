"""Schedule platform for Smart Heat Pump."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import TemplateError

from .const import (
    DOMAIN,
    CONF_SCHEDULE_ENABLED,
    CONF_SCHEDULE_TEMPLATE,
    CONF_SCHEDULE_ATTRIBUTES,
    CONF_ROOM_TEMP_SENSOR,
    CONF_WEATHER_ENTITY,
    DEFAULT_SCHEDULE_TEMPLATE,
    DEFAULT_SCHEDULE_ATTRIBUTES,
    ATTR_SCHEDULE_TARGET_TEMP,
    ATTR_SCHEDULE_MODE,
)
from .coordinator import SmartHeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smart Heat Pump schedule entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    if config_entry.data.get(CONF_SCHEDULE_ENABLED, False):
        async_add_entities([SmartHeatPumpSchedule(coordinator, config_entry)])


class SmartHeatPumpSchedule(CoordinatorEntity, SwitchEntity):
    """Smart Heat Pump schedule entity with Jinja templating support."""

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
            "name": config_entry.data.get("name", "Smart Heat Pump"),
            "manufacturer": "Smart Heat Pump Integration",
            "model": "Smart Heat Pump",
        }
        
        # Template setup
        self._template: Template | None = None
        self._template_variables: dict[str, Any] = {}
        self._last_result: dict[str, Any] = {}
        self._setup_template()

    def _setup_template(self) -> None:
        """Set up the Jinja template and variables."""
        template_str: str = self._config_entry.data.get(CONF_SCHEDULE_TEMPLATE, DEFAULT_SCHEDULE_TEMPLATE)
        
        # Create template
        self._template = Template(template_str, self.hass)
        
        # Setup template variables from config and defaults
        self._template_variables = dict(DEFAULT_SCHEDULE_ATTRIBUTES)
        
        # Override with user-configured attributes
        user_attributes: dict[str, Any] = self._config_entry.data.get(CONF_SCHEDULE_ATTRIBUTES, {})
        if isinstance(user_attributes, dict):
            self._template_variables.update(user_attributes)
        
        # Always include the actual entity IDs from config
        self._template_variables["room_temp_sensor"] = self._config_entry.data.get(CONF_ROOM_TEMP_SENSOR)
        self._template_variables["weather_entity"] = self._config_entry.data.get(CONF_WEATHER_ENTITY)

    async def _async_evaluate_template(self) -> dict[str, Any]:
        """Evaluate the Jinja template and return the result."""
        try:
            if self._template is None:
                return {"active": False, "error": "Template not initialized"}
            
            # Render the template
            result_str: str = self._template.async_render(self._template_variables)
            result_str = result_str.strip()
            
            _LOGGER.debug("Template result: %s", result_str)
            
            # Try to parse as JSON for structured output
            try:
                result: Any = json.loads(result_str)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, TypeError):
                pass
            
            # Fall back to boolean interpretation
            if result_str.lower() in ("true", "on", "yes", "1"):
                return {"active": True}
            elif result_str.lower() in ("false", "off", "no", "0"):
                return {"active": False}
            else:
                # Try to interpret as boolean
                return {"active": bool(result_str)}
                
        except TemplateError as err:
            _LOGGER.error("Template evaluation error: %s", err)
            return {"active": False, "error": str(err)}
        except Exception as err:
            _LOGGER.error("Unexpected error in template evaluation: %s", err)
            return {"active": False, "error": str(err)}

    @property
    def is_on(self) -> bool:
        """Return true if the schedule is active."""
        return self._last_result.get("active", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = dict(self._last_result)
        
        # Add template variables for reference
        attrs["template_variables"] = self._template_variables
        
        # Add template source for debugging (truncated for UI)
        if self._template:
            template_src: str = str(self._template.template)
            attrs["template_source"] = template_src[:200] + "..." if len(template_src) > 200 else template_src
        
        # Add control information
        from .const import CONF_SCHEDULE_AUTO_CONTROL
        attrs["auto_control_enabled"] = self._config_entry.data.get(CONF_SCHEDULE_AUTO_CONTROL, True)
        
        # Add schedule-specific attributes for other entities to use
        if "target_temp" in self._last_result:
            attrs["schedule_target_temp"] = self._last_result["target_temp"]
        if "mode" in self._last_result:
            attrs["schedule_mode"] = self._last_result["mode"]
        
        return attrs

    async def async_update(self) -> None:
        """Update the schedule state by evaluating the template."""
        await super().async_update()
        self._last_result = await self._async_evaluate_template()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the schedule (enable schedule control)."""
        # This entity represents the schedule's evaluation, not manual control
        # Users should modify the template or attributes to change behavior
        _LOGGER.info("Schedule entity is template-driven and cannot be manually turned on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the schedule (disable schedule control)."""
        # This entity represents the schedule's evaluation, not manual control
        # Users should modify the template or attributes to change behavior
        _LOGGER.info("Schedule entity is template-driven and cannot be manually turned off")

    @property
    def should_heat_pump_be_on(self) -> bool:
        """Return whether the heat pump should be on according to the schedule."""
        return self._last_result.get("active", False)

    @property
    def schedule_target_temperature(self) -> float | None:
        """Return the target temperature from the schedule."""
        target = self._last_result.get("target_temp")
        if target is not None:
            try:
                return float(target)
            except (ValueError, TypeError):
                pass
        return None

    @property
    def schedule_mode(self) -> str | None:
        """Return the current schedule mode."""
        return self._last_result.get("mode")

    def get_schedule_attributes(self) -> dict[str, Any]:
        """Get all schedule attributes for use by other entities."""
        result: dict[str, Any] = {
            "active": self.is_on,
            ATTR_SCHEDULE_TARGET_TEMP: self.schedule_target_temperature,
            ATTR_SCHEDULE_MODE: self.schedule_mode,
        }
        
        # Add other attributes from last result
        for k, v in self._last_result.items():
            if k not in ("active", "target_temp", "mode"):
                result[k] = v
        
        return result