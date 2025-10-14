# Smarter Heat Pump Integration for Home Assistant

A comprehensive Home Assistant integration for controlling IR-based heat pumps with smart features, state tracking, and power estimation.

## Features

### Core Functionality

- **Climate Entity**: Full climate control with temperature setting and HVAC modes

- **Power Switch**: Manual on/off control with cycle duration protection

- **State Tracking**: Maintains internal state since IR remotes provide no feedback

- **Schedule Helper Integration**: Integrates with Home Assistant's schedule helper for flexible scheduling.

### Entities Created

1. **Climate Entity** - Main heat pump controller

2. **Power Switch** - Manual power control

3. **Current Temperature Sensor** - Room temperature display

4. **Heat Pump Target Temperature Sensor** - Shows heat pump's set temperature

5. **Estimated Power Consumption Sensor** - COP-based power estimation

6. **Status Binary Sensor** - For use in graphs and automations

7. **Fix State Button** - Sync state when manual changes occur

**Note**: The schedule entity is created automatically when you configure a schedule entity ID in the integration settings, but it's used internally for schedule monitoring and doesn't appear as a user-controllable switch.

### Smart Features

- **Minimum Cycle Duration**: Prevents rapid on/off cycling

- **Power Estimation**: Uses COP and temperature differentials to estimate consumption

- **Weather Integration**: Considers outside temperature for efficiency calculations

- **Manual Override Support**: "Fix" button to resync when heat pump is manually operated

## Configuration

### Required Entities

- **Room Temperature Sensor**: Any temperature sensor entity for room monitoring

- **Control Method** (choose ONE):
  - **IR Remote Entity**: Your remote entity for sending IR commands (e.g., `remote.broadlink_rm_pro`)
  - **Actuator Switch**: A physical switch entity (e.g., smart plug) that controls the heater's power

### Optional Entities

- **Outside Temperature Source**: Either a weather entity OR an outside temperature sensor (optional for simple heaters with flat power consumption)

  - **Weather Entity**: Weather integration (provides temperature via attributes)

  - **Outside Temperature Sensor**: Direct temperature sensor for outside conditions

- **Schedule Entity**: A Home Assistant `schedule` helper entity for scheduling

### IR Commands (required only if using IR Remote)

Configure your IR commands (e.g., Base64 encoded commands for Broadlink):

- Power On Command

- Power Off Command

- Temperature Up Command

- Temperature Down Command

**Note**: IR commands are only needed if you're using an IR remote entity. If you're using an actuator switch (smart plug), the integration will control the switch directly and IR commands are not required.

### Settings

- **Minimum Cycle Duration**: Prevents turning off during minimum runtime (default: 300s)

- **Heat/Cold Tolerance**: Temperature tolerance for heating decisions (default: 0.5°C)

- **Temperature Limits**: Min/max temperature ranges (default: 10-30°C)

- **Power Settings**: Minimum power consumption and COP value for estimation

## Installation

1. Copy this integration to your `custom_components/smart_heatpump/` directory

2. Restart Home Assistant

3. Go to Settings → Devices & Services → Add Integration

4. Search for "Smarter Heat Pump" and follow the configuration steps

## Scheduling

The integration provides seamless integration with Home Assistant's `schedule` helper for flexible and powerful scheduling. The schedule acts as a simple pass-through mechanism that automatically applies attributes when the schedule is active.

### 1. Create a Schedule Helper

First, create a `schedule` helper in Home Assistant:

1.  Go to **Settings > Devices & Services > Helpers**.
2.  Click **Create Helper** and choose **Schedule**.
3.  Give it a name (e.g., "Heat Pump Schedule").
4.  Configure the desired schedule times and days.

### 2. Configure Schedule Attributes

The integration reads attributes directly from your schedule entity. You can set these attributes in several ways:

**Option 1: Use the Service (Recommended)**

```yaml
service: smart_heatpump.set_schedule_attributes
target:
  entity_id: schedule.heat_pump_schedule
data:
  data:
    target_temperature: 22
    run_if: "{{ is_state('binary_sensor.workday_sensor', 'on') }}"
    hvac_mode: "heat"
```

**Option 2: Set Directly on the Entity**
You can also set attributes directly on the schedule entity through:

- **Developer Tools > States** in Home Assistant UI
- **Service calls** to `homeassistant.update_entity`
- **Automations** that modify entity attributes

The integration will automatically use whichever attributes are present on the schedule entity when it's active.

### Available Schedule Attributes

The integration automatically applies the following attributes when the schedule is active and the `run_if` condition passes:

- **`target_temperature`**: Sets the heat pump's target temperature (e.g., `22`)
- **`climate_target_temperature`**: Sets the climate entity's target temperature (e.g., `20`)
- **`hvac_mode`**: Controls the climate system (`"heat"` or `"off"`)
- **`run_if`**: Template condition that must evaluate to `true` for attributes to be applied
- **`keep_on`**: If `true`, prevents auto-turn-off when schedule ends (default: `false`)

### How It Works

1. **Direct Passthrough**: The integration reads attributes directly from your schedule entity's current state, making it a true passthrough mechanism.

2. **Schedule Detection**: The integration monitors your schedule entity's schedule configuration and automatically detects when it should be active based on the current time and configured days.

3. **Condition Check**: When the schedule is active, the `run_if` template is evaluated. If it returns `true` (or is not specified), the schedule attributes are applied.

4. **Automatic Application**: Matching attributes are automatically applied to the heat pump:

   - Temperature changes are sent via IR commands
   - HVAC mode changes control the climate system state
   - Climate target temperature updates the virtual thermostat

5. **Smart Auto-Off**: When a schedule turns on the heat pump, it tracks this and will automatically turn off when the schedule ends (unless overridden by `keep_on: true` or if it "rolls into" another schedule entry).

6. **Manual Override Protection**: If the heat pump was turned on manually (not by schedule), it will stay on until manually turned off.

7. **Real-time Updates**: The integration checks schedule status every 30 seconds and applies changes immediately when conditions are met.

### Example: Workday Morning Schedule

To turn on the heat pump at 6:00 AM on weekdays if the workday sensor is on, and turn it off at 7:25 AM:

1. **Create the schedule** in the UI with times from 06:00 to 07:25 on Monday-Friday
2. **Set the attributes** using the service (or set them directly on the entity):

```yaml
service: smart_heatpump.set_schedule_attributes
target:
  entity_id: schedule.heat_pump_schedule
data:
  data:
    target_temperature: 21
    climate_target_temperature: 19
    hvac_mode: "heat"
    run_if: "{{ is_state('binary_sensor.workday_sensor', 'on') }}"
```

### Example: Multiple Time Periods in One Schedule

You can add multiple time periods to the same schedule helper:

1. **Create one schedule** with two time periods:
   - **Morning**: 06:00 to 07:25 on Monday-Friday (with workday condition)
   - **Afternoon**: 16:30 onwards on Tuesday, Wednesday, Friday
2. **Set the attributes** for the entire schedule:

```yaml
service: smart_heatpump.set_schedule_attributes
target:
  entity_id: schedule.heat_pump_schedule
data:
  data:
    target_temperature: 21 # Will apply to both time periods
    hvac_mode: "heat"
```

**For different settings per time period**, you can use conditional logic in the attributes:

```yaml
service: smart_heatpump.set_schedule_attributes
target:
  entity_id: schedule.heat_pump_schedule
data:
  data:
    target_temperature: "{{ 23 if now().hour >= 16 else 21 }}"
    hvac_mode: "heat"
    run_if: "{{ is_state('binary_sensor.workday_sensor', 'on') if now().hour < 16 else true }}"
```

**To keep the heat pump on after schedule ends** (useful for events or when you want manual control):

```yaml
service: smart_heatpump.set_schedule_attributes
target:
  entity_id: schedule.heat_pump_schedule
data:
  data:
    target_temperature: 22
    hvac_mode: "heat"
    keep_on: true # Won't auto-turn-off when schedule ends
```

This approach provides a simple and powerful way to schedule your heat pump without complex automation logic. The schedule helper handles the timing, while the integration handles the conditional application of settings.

### Diagnostic Information

The integration tracks diagnostic information about when and how the heat pump was last turned on. This information is available in the schedule sensor's attributes:

- **`last_turn_on_time`**: ISO timestamp of when the heat pump was last turned on
- **`last_turn_on_source`**: How it was turned on (`"schedule"`, `"climate"`, `"fix"`, or `"manual"`)

This helps you understand the heat pump's behavior and troubleshoot issues. For example, if you see `last_turn_on_source: "manual"`, you'll know someone used the physical remote or climate entity directly.

## Power Consumption Estimation

The integration estimates power consumption using:

- **Base Power**: Your configured minimum power consumption (default: 1200W)

- **COP (Coefficient of Performance)**: Efficiency rating (default: 3.0)

- **Temperature Differentials**: Outside vs target temperature affects efficiency (if configured)

- **Load Factor**: Room vs target temperature affects power demand

**Note**: For simple heaters with actuator switches (smart plugs), you can:

- Use the smart plug's built-in power monitoring for accurate real-time consumption
- Set the estimated power to match your heater's rated power
- Skip outside temperature configuration if you don't need COP-based estimation

Formula (simplified):

```

efficiency_factor = max(0.5, 1.0 - (temp_diff / 50.0))

load_factor = min(2.0, 1.0 + (room_target_diff / 10.0))

estimated_power = min_power * load_factor / (cop * efficiency_factor)

# If no outside temperature is configured, uses base power only

```

## Usage Examples

### Simple Heater with Smart Plug

Perfect for dumb heaters controlled by a smart plug:

```yaml
# Configuration:
# - Room Temperature Sensor: sensor.bedroom_temperature
# - Actuator Switch: switch.bedroom_heater_plug
# - No remote entity needed
# - No outside temperature needed (flat power consumption tracked by plug)

# The integration will automatically control the smart plug based on room temperature
# Use the climate entity to set your target temperature
# Use schedule helpers to create time-based temperature schedules
```

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

        state: "off"

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

If you configure a schedule entity, the integration will expose its state as an attribute on the climate entity. You can then use this attribute in your automations.

### Weather-Based Control

The integration considers outside temperature for:

- Power consumption estimation

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
