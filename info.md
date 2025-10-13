# Smarter Heat Pump Integration

A comprehensive Home Assistant integration for controlling IR-based heat pumps with smart features, state tracking, and power estimation.

## Features

- **Climate Entity**: Full HVAC control with temperature setting and modes
- **Power Switch**: Manual on/off with cycle duration protection
- **Smart State Tracking**: Maintains internal state since IR remotes provide no feedback
- **Power Estimation**: COP-based consumption calculation considering temperature differentials
- **Binary Sensor**: For graphing and automation compatibility
- **Fix Button**: Sync state when manual remote usage occurs
- **Smart Schedule**: Advanced Jinja template-based scheduling with infinite customization

## Key Benefits

- **Flexible Outside Temperature**: Supports both weather entities and temperature sensors
- **Minimum Cycle Duration**: Prevents rapid on/off cycling that can damage equipment
- **Weather-Aware Power Estimation**: Uses outside temperature and COP for realistic calculations
- **Template-Based Scheduling**: Create any heating logic you can imagine
- **Strong Type Safety**: Enterprise-level Python typing throughout

## Perfect For

- Heat pumps controlled via Broadlink or other IR controllers
- Users wanting intelligent scheduling beyond basic time-based control
- Setups requiring power consumption monitoring without dedicated meters
- Systems needing state synchronization between manual and automated control

## Getting Started

1. Install via HACS
2. Add integration through Home Assistant UI
3. Configure your temperature sensors and IR commands
4. Optionally set up smart scheduling with custom templates
5. Enjoy intelligent heat pump control!
