# Smart Heat Pump Integration for Home Assistant

A comprehensive Home Assistant integration for controlling IR-based heat pumps with smart features, state tracking, and power estimation.

## Features

### Core Functionality
- **Climate Entity**: Full climate control with temperature setting and HVAC modes
- **Power Switch**: Manual on/off control with cycle duration protection
- **State Tracking**: Maintains internal state since IR remotes provide no feedback
- **Smart Scheduling**: Weather-aware scheduling with configurable conditions

### Entities Created
1. **Climate Entity** - Main heat pump controller
2. **Power Switch** - Manual power control
3. **Current Temperature Sensor** - Room temperature display
4. **Heat Pump Target Temperature Sensor** - Shows heat pump's set temperature
5. **Estimated Power Consumption Sensor** - COP-based power estimation
6. **Status Binary Sensor** - For use in graphs and automations
7. **Fix State Button** - Sync state when manual changes occur
8. **Smart Schedule Switch** - Template-driven intelligent scheduling (optional)

### Smart Features
- **Intelligent Scheduling**: Fully customizable Jinja template-based scheduling system
- **Minimum Cycle Duration**: Prevents rapid on/off cycling
- **Power Estimation**: Uses COP and temperature differentials to estimate consumption
- **Weather Integration**: Considers outside temperature for efficiency calculations
- **Manual Override Support**: "Fix" button to resync when heat pump is manually operated
- **Flexible Logic**: JSON-based template output for complex scheduling decisions

## Configuration

### Required Entities
- **Room Temperature Sensor**: Any temperature sensor entity for room monitoring
- **Weather Entity**: Weather integration for outside temperature
- **Climate Entity**: Your existing climate entity (the "real" one)

### IR Commands
Configure your Broadlink (or other IR) service calls:
- Power On: `remote.send_command` or your IR service
- Power Off: `remote.send_command` or your IR service  
- Temperature Up: `remote.send_command` or your IR service
- Temperature Down: `remote.send_command` or your IR service

### Settings
- **Minimum Cycle Duration**: Prevents turning off during minimum runtime (default: 300s)
- **Heat/Cold Tolerance**: Temperature tolerance for heating decisions (default: 0.5°C)
- **Temperature Limits**: Min/max temperature ranges (default: 10-30°C)
- **Power Settings**: Minimum power consumption and COP value for estimation
- **Smart Schedule**: Optional Jinja template-based scheduling with custom variables

## Installation

1. Copy this integration to your `custom_components/smart_heatpump/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Smart Heat Pump" and follow the configuration steps

## Power Consumption Estimation

The integration estimates power consumption using:
- **Base Power**: Your configured minimum power consumption (default: 1200W)
- **COP (Coefficient of Performance)**: Efficiency rating (default: 3.0)
- **Temperature Differentials**: Outside vs target temperature affects efficiency
- **Load Factor**: Room vs target temperature affects power demand

Formula (simplified):
```
efficiency_factor = max(0.5, 1.0 - (temp_diff / 50.0))
load_factor = min(2.0, 1.0 + (room_target_diff / 10.0))
estimated_power = min_power * load_factor / (cop * efficiency_factor)
```

## Smart Schedule System

The integration includes a powerful template-based scheduling system that allows infinite customization of heating logic.

### Template Output Formats

Your template can return either:

**Simple Boolean:**
```jinja
{%- if states('sensor.room_temperature') | float < 18 -%}
  true
{%- else -%}
  false
{%- endif -%}
```

**Rich JSON Object:**
```jinja
{%- set room_temp = states('sensor.room_temperature') | float(0) -%}
{%- set outside_temp = state_attr('weather.home', 'temperature') | float(0) -%}
{%- set current_time = now().strftime('%H:%M') -%}

{%- if current_time >= '22:00' or current_time < '06:30' -%}
  {%- if room_temp < min_temp -%}
    {"active": true, "target_temp": 15, "mode": "night_minimum"}
  {%- else -%}
    {"active": false, "target_temp": 15, "mode": "night_idle"}
  {%- endif -%}
{%- elif current_time == '06:30' and (room_temp - outside_temp) | abs > temp_diff_threshold -%}
  {"active": true, "target_temp": 20, "mode": "morning_warmup"}
{%- elif room_temp < target_temp -%}
  {"active": true, "target_temp": 20, "mode": "day_heating"}
{%- else -%}
  {"active": false, "target_temp": 20, "mode": "day_comfortable"}
{%- endif -%}
```

### Available Template Variables

The template has access to:
- **Built-in entities**: `room_temp_sensor`, `weather_entity`
- **Custom attributes**: All variables you define in the configuration
- **Home Assistant functions**: `states()`, `state_attr()`, `now()`, `is_state()`
- **Common variables**: `min_temp`, `target_temp`, `max_temp`, `temp_diff_threshold`

### Example Use Cases

**1. Night Mode with Minimum Temperature:**
```jinja
{%- set room_temp = states(room_temp_sensor) | float(0) -%}
{%- set is_night = now().hour >= 22 or now().hour < 7 -%}

{%- if is_night and room_temp < 15 -%}
  {"active": true, "target_temp": 15, "mode": "night_protection"}
{%- elif not is_night and room_temp < 20 -%}
  {"active": true, "target_temp": 20, "mode": "day_comfort"}
{%- else -%}
  {"active": false, "mode": "satisfied"}
{%- endif -%}
```

**2. Weather-Dependent Morning Warmup:**
```jinja
{%- set room_temp = states(room_temp_sensor) | float(0) -%}
{%- set outside_temp = state_attr(weather_entity, 'temperature') | float(0) -%}
{%- set current_time = now().strftime('%H:%M') -%}

{%- if current_time == '06:30' -%}
  {%- if (room_temp - outside_temp) | abs > 2 -%}
    {"active": true, "target_temp": 21, "mode": "morning_boost"}
  {%- else -%}
    {"active": false, "mode": "morning_skip"}
  {%- endif -%}
{%- else -%}
  {"active": room_temp < 19, "target_temp": 19, "mode": "standard"}
{%- endif -%}
```

**3. Presence-Based Scheduling:**
```jinja
{%- set room_temp = states(room_temp_sensor) | float(0) -%}
{%- set home_occupied = is_state('binary_sensor.occupancy', 'on') -%}

{%- if not home_occupied -%}
  {%- if room_temp < 12 -%}
    {"active": true, "target_temp": 12, "mode": "away_protection"}
  {%- else -%}
    {"active": false, "mode": "away_off"}
  {%- endif -%}
{%- else -%}
  {"active": room_temp < 20, "target_temp": 20, "mode": "occupied"}
{%- endif -%}
```

## Usage Examples

### Basic Automation
```yaml
automation:
  - alias: "Heat Pump Smart Control"
    trigger:
      - platform: numeric_state
        entity_id: sensor.room_temperature
        below: 19
    condition:
      - condition: state
        entity_id: binary_sensor.smart_heatpump_status
        state: 'off'
    action:
      - service: climate.turn_on
        target:
          entity_id: climate.smart_heatpump
```

### Power Monitoring
```yaml
sensor:
  - platform: integration
    source: sensor.smart_heatpump_estimated_power_consumption
    name: "Heat Pump Daily Energy"
    unit_prefix: k
    round: 2
```

### Manual Fix When Someone Uses Remote
```yaml
automation:
  - alias: "Heat Pump Manual Override Detection"
    trigger:
      - platform: state
        entity_id: sensor.room_temperature
    condition:
      - condition: template
        value_template: >
          {{ states('binary_sensor.smart_heatpump_status') == 'off' and
             states('sensor.room_temperature') | float > 
             states('sensor.smart_heatpump_heat_pump_target_temperature') | float + 2 }}
    action:
      - service: button.press
        target:
          entity_id: button.smart_heatpump_fix_state
```

## Troubleshooting

### Common Issues

**1. Heat Pump Not Responding**
- Verify IR commands are correctly configured
- Check Broadlink device is functioning
- Ensure minimum time between commands (5 seconds)

**2. State Out of Sync**
- Use the "Fix State" button to resync
- Check that your climate entity reflects actual room conditions
- Verify room temperature sensor is accurate

**3. Power Estimation Inaccurate**
- Adjust COP value based on your heat pump specifications
- Fine-tune minimum power consumption based on actual measurements
- Consider seasonal COP variations

### Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.smart_heatpump: debug
```

## Advanced Configuration

### Schedule Integration
If you have a schedule entity, the integration can use it for smart scheduling:
```yaml
# Example schedule entity
input_boolean:
  heat_pump_schedule:
    name: "Heat Pump Schedule Active"
```

### Weather-Based Control
The integration considers outside temperature for:
- Power consumption estimation
- Scheduling decisions (only run if outside temp difference > threshold)
- Efficiency calculations

## Contributing

This integration follows Home Assistant development best practices:
- Uses DataUpdateCoordinator for efficient updates
- Implements proper error handling and logging
- Supports device registry for automatic device grouping
- Includes comprehensive configuration validation

## Support

For issues or feature requests, please check:
1. Home Assistant logs for error messages
2. Entity states in Developer Tools
3. Configuration validation during setup

The integration is designed to be robust and handle various failure scenarios gracefully.