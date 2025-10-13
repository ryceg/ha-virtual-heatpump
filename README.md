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

### Smart Features

- **Minimum Cycle Duration**: Prevents rapid on/off cycling

- **Power Estimation**: Uses COP and temperature differentials to estimate consumption

- **Weather Integration**: Considers outside temperature for efficiency calculations

- **Manual Override Support**: "Fix" button to resync when heat pump is manually operated

## Configuration

### Required Entities

- **Room Temperature Sensor**: Any temperature sensor entity for room monitoring

- **Outside Temperature Source**: Either a weather entity OR an outside temperature sensor

  - **Weather Entity**: Weather integration (provides temperature via attributes)

  - **Outside Temperature Sensor**: Direct temperature sensor for outside conditions

- **Remote Entity**: Your remote entity for sending IR commands (e.g., `remote.broadlink_rm_pro`)

### Optional Entities

- **Schedule Entity**: A Home Assistant `schedule` helper entity for scheduling.

- **Actuator Switch**: A physical switch that controls the heat pump's power.

### IR Commands

Configure your IR commands (e.g., Base64 encoded commands for Broadlink):

- Power On Command

- Power Off Command

- Temperature Up Command

- Temperature Down Command

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

## Scheduling with Automations

The recommended way to schedule the heat pump is by using a Home Assistant `schedule` helper and automations. This approach allows for powerful and flexible scheduling, including conditional logic and dynamic target temperatures.

### 1. Create a Schedule Helper

First, create a `schedule` helper in Home Assistant:

1.  Go to **Settings > Devices & Services > Helpers**.
2.  Click **Create Helper** and choose **Schedule**.
3.  Give it a name (e.g., "Heat Pump Schedule").
4.  Configure the desired on/off times.

### 2. Create an Automation

Next, create an automation that uses the `smart_heatpump.set_schedule_attributes` service to set the desired attributes on your schedule entity. This service allows you to set a `target_temperature` and a `run_if` condition.

**Automation Example**

This automation triggers at 10 PM and sets the overnight temperature to 18°C, but only if it's a weekday.

```yaml
automation:
  - alias: "Set Overnight Heat Pump Schedule"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: smart_heatpump.set_schedule_attributes
        target:
          entity_id: schedule.heat_pump_schedule
        data:
          data:
            target_temperature: 18
            run_if: "{{ is_state('binary_sensor.workday_sensor', 'on') }}"
```

### How it Works

1.  **`schedule.heat_pump_schedule`**: This is the `schedule` helper you created. The heat pump will only run when this schedule is `on`.
2.  **`smart_heatpump.set_schedule_attributes`**: This is a custom service provided by the integration. It allows you to set custom attributes on your schedule entity.
3.  **`target_temperature`**: This is the temperature the heat pump will be set to when the schedule is active and the `run_if` condition is met.
4.  **`run_if`**: This is a Home Assistant template that is evaluated when the schedule is active. If the template evaluates to `true`, the `target_temperature` will be applied. This allows for complex conditional logic, such as checking if a window is open, if someone is home, or if it's a specific day of the week.

This approach provides a powerful and flexible way to schedule your heat pump, allowing you to create complex logic using Home Assistant's built-in automation editor.

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
