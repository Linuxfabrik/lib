#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library parses data returned from the Redfish API.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025041901'

from . import base
from . import human
from .globals import STATE_OK, STATE_WARN, STATE_CRIT


# The "Status" property is common to many Redfish schema, and contains:
#
#   Health: This represents the health state of this resource in the absence
#           of its dependent resources
#   * Critical  A critical condition exists that requires immediate attention.
#   * OK        Normal.
#   * Warning   A condition exists that requires attention
#
#   HealthRollup: This represents the overall health state from the view of this
#                 resource
#   * Critical  A critical condition exists that requires immediate attention.
#   * OK        Normal.
#   * Warning   A condition exists that requires attention.
#
#   State:
#   * Absent                This function or resource is not present or not detected.
#   * Deferring             The element will not process any commands but will queue new
#                           requests.
#   * Disabled              This function or resource has been disabled.
#   * Enabled               This function or resource has been enabled.
#   * InTest                This function or resource is undergoing testing.
#   * Quiesced              The element is enabled but only processes a restricted set of
#                           commands.
#   * StandbyOffline        This function or resource is enabled, but awaiting an external action to
#                           activate it.
#   * StandbySpare          This function or resource is part of a redundancy set and is awaiting a
#                           failover or other external action to activate it.
#   * Starting              This function or resource is starting.
#   * UnavailableOffline    This function or resource is present but cannot be used.
#   * Updating              The element is updating and may be unavailable or degraded.


def get_chassis(redfish):
    """
    Extract chassis information from a Redfish API response.

    This function retrieves specific chassis details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish chassis data.

    ### Returns
    - **dict**: A dictionary containing the following chassis details:
      - **AssetTag** (`str`): The asset tag of the chassis.
      - **ChassisType** (`str`): The type of the chassis.
      - **Id** (`str`): The ID of the chassis.
      - **IndicatorLED** (`str`): The status of the indicator LED.
      - **Manufacturer** (`str`): The manufacturer of the chassis.
      - **Model** (`str`): The model of the chassis.
      - **PartNumber** (`str`): The part number of the chassis.
      - **PowerState** (`str`): The power state of the chassis (e.g., "On").
      - **SerialNumber** (`str`): The serial number of the chassis.
      - **SKU** (`str`): The SKU of the chassis.
      - **Sensors_@odata.id** (`str`): The sensors' OData ID.
      - **Status_State** (`str`): The state of the chassis (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the chassis (e.g., "OK").
      - **Status_HealthRollup** (`str`): The health rollup status of the chassis (e.g., "OK").

    ### Example
    >>> redfish_data = {'AssetTag': '12345', 'ChassisType': 'Rackmount', 'Id': '1', 'PowerState': 'On'}
    >>> get_chassis(redfish_data)
    {'AssetTag': '12345', 'ChassisType': 'Rackmount', 'Id': '1', 'PowerState': 'On', ...}
    """
    data = {}
    data['AssetTag'] = redfish.get('AssetTag', '')
    data['ChassisType'] = redfish.get('ChassisType', '')
    data['Id'] = redfish.get('Id', '')
    data['IndicatorLED'] = redfish.get('IndicatorLED', '')
    data['Manufacturer'] = redfish.get('Manufacturer', '')
    data['Model'] = redfish.get('Model', '')
    data['PartNumber'] = redfish.get('PartNumber', '')
    data['PowerState'] = redfish.get('PowerState', '')                                  # On
    data['SerialNumber'] = redfish.get('SerialNumber', '')
    data['SKU'] = redfish.get('SKU', '')
    data['Sensors_@odata.id'] = redfish.get('Sensors', {}).get('@odata.id', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    data['Status_HealthRollup'] = redfish.get('Status', {}).get('HealthRollup', '')     # OK
    return data


def get_chassis_power_powersupplies(redfish):
    """
    Extract power supply information from a Redfish API response.

    This function retrieves specific power supply details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish power supply data.

    ### Returns
    - **dict**: A dictionary containing the following power supply details:
      - **FirmwareVersion** (`str`): The firmware version of the power supply.
      - **LastPowerOutputWatts** (`str`): The last reported power output in watts.
      - **LineInputVoltage** (`str`): The input voltage of the power supply.
      - **LineInputVoltageType** (`str`): The type of input voltage.
      - **Manufacturer** (`str`): The manufacturer of the power supply.
      - **Model** (`str`): The model of the power supply.
      - **PartNumber** (`str`): The part number of the power supply.
      - **PowerCapacityWatts** (`str`): The power capacity of the power supply in watts.
      - **PowerSupplyType** (`str`): The type of power supply.
      - **SerialNumber** (`str`): The serial number of the power supply.
      - **SparePartNumber** (`str`): The spare part number of the power supply.
      - **Status_State** (`str`): The state of the power supply (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the power supply (e.g., "OK").

    ### Example
    >>> redfish_data = {'FirmwareVersion': '1.0', 'LastPowerOutputWatts': 200, 'PowerCapacityWatts': 500}
    >>> get_chassis_power_powersupplies(redfish_data)
    {'FirmwareVersion': '1.0', 'LastPowerOutputWatts': 200, 'PowerCapacityWatts': 500, ...}
    """
    data = {}
    data['FirmwareVersion'] = redfish.get('FirmwareVersion', '')
    data['LastPowerOutputWatts'] = redfish.get('LastPowerOutputWatts', '')
    if data['LastPowerOutputWatts'] is None:
        data['LastPowerOutputWatts'] = redfish.get('PowerOutputWatts', '')  # DELL uses this instead
    data['LineInputVoltage'] = redfish.get('LineInputVoltage', '')
    data['LineInputVoltageType'] = redfish.get('LineInputVoltageType', '')
    data['Manufacturer'] = redfish.get('Manufacturer', '')
    data['Model'] = redfish.get('Model', '')
    data['PartNumber'] = redfish.get('PartNumber', '')
    data['PowerCapacityWatts'] = redfish.get('PowerCapacityWatts', '')
    data['PowerSupplyType'] = redfish.get('PowerSupplyType', '')
    data['SerialNumber'] = redfish.get('SerialNumber', '')
    data['SparePartNumber'] = redfish.get('SparePartNumber', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    return data


def get_chassis_power_voltages(redfish):
    """
    Extract power voltage information from a Redfish API response.

    This function retrieves specific power voltage details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish power voltage data.

    ### Returns
    - **dict**: A dictionary containing the following power voltage details:
      - **LowerThresholdCritical** (`str`): The critical lower threshold voltage.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold voltage.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold voltage.
      - **Name** (`str`): The name of the voltage.
      - **PhysicalContext** (`str`): The physical context of the voltage.
      - **ReadingVolts** (`str`): The current voltage reading.
      - **UpperThresholdCritical** (`str`): The critical upper threshold voltage.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold voltage.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold voltage.
      - **Status_State** (`str`): The state of the voltage (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the voltage (e.g., "OK").

    ### Example
    >>> redfish_data = {'LowerThresholdCritical': 10, 'ReadingVolts': 12, 'UpperThresholdCritical': 15}
    >>> get_chassis_power_voltages(redfish_data)
    {'LowerThresholdCritical': 10, 'ReadingVolts': 12, 'UpperThresholdCritical': 15, ...}
    """
    data = {}
    data['LowerThresholdCritical'] = redfish.get('LowerThresholdCritical', '')
    data['LowerThresholdFatal'] = redfish.get('LowerThresholdFatal', '')
    data['LowerThresholdNonCritical'] = redfish.get('LowerThresholdNonCritical', '')
    data['Name'] = redfish.get('Name', '')
    data['PhysicalContext'] = redfish.get('PhysicalContext', '')
    data['ReadingVolts'] = redfish.get('ReadingVolts', '')
    data['UpperThresholdCritical'] = redfish.get('UpperThresholdCritical', '')
    data['UpperThresholdFatal'] = redfish.get('UpperThresholdFatal', '')
    data['UpperThresholdNonCritical'] = redfish.get('UpperThresholdNonCritical', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    return data


def get_chassis_sensors(redfish):
    """
    Extract sensor information from a Redfish API response.

    This function retrieves specific sensor details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish sensor data.

    ### Returns
    - **dict**: A dictionary containing the following sensor details:
      - **Id** (`str`): The ID of the sensor.
      - **Name** (`str`): The name of the sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **Reading** (`str`): The current reading of the sensor.
      - **ReadingRangeMax** (`str`): The maximum reading range of the sensor.
      - **ReadingRangeMin** (`str`): The minimum reading range of the sensor.
      - **ReadingUnits** (`str`): The units of the sensor reading.
      - **Thresholds_LowerCaution** (`str`): The lower caution threshold for the sensor.
      - **Thresholds_LowerCritical** (`str`): The lower critical threshold for the sensor.
      - **Thresholds_UpperCaution** (`str`): The upper caution threshold for the sensor.
      - **Thresholds_UpperCritical** (`str`): The upper critical threshold for the sensor.
      - **Status_State** (`str`): The state of the sensor (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the sensor (e.g., "OK").
      - **Status_HealthRollup** (`str`): The health rollup status of the sensor (e.g., "OK").

    ### Example
    >>> redfish_data = {'Id': 'sensor1', 'Reading': 75, 'ReadingRangeMax': 100, 'Thresholds_LowerCaution': 30}
    >>> get_chassis_sensors(redfish_data)
    {'Id': 'sensor1', 'Reading': 75, 'ReadingRangeMax': 100, 'Thresholds_LowerCaution': 30, ...}
    """
    data = {}
    data['Id'] = redfish.get('Id', '')
    data['Name'] = redfish.get('Name', '')
    data['PhysicalContext'] = redfish.get('PhysicalContext', '')
    data['Reading'] = redfish.get('Reading', '')
    data['ReadingRangeMax'] = redfish.get('ReadingRangeMax', '')
    data['ReadingRangeMin'] = redfish.get('ReadingRangeMin', '')
    data['ReadingUnits'] = redfish.get('ReadingUnits', '')
    data['Thresholds_LowerCaution'] = redfish.get('Thresholds', {}).get('LowerCaution', {}).get('Reading', '')
    data['Thresholds_LowerCritical'] = redfish.get('Thresholds', {}).get('LowerCritical', {}).get('Reading', '')
    data['Thresholds_UpperCaution'] = redfish.get('Thresholds', {}).get('UpperCaution', {}).get('Reading', '')
    data['Thresholds_UpperCritical'] = redfish.get('Thresholds', {}).get('UpperCritical', {}).get('Reading', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    data['Status_HealthRollup'] = redfish.get('Status', {}).get('HealthRollup', '')     # OK
    return data


def get_chassis_thermal_fans(redfish):
    """
    Extract thermal fan information from a Redfish API response.

    This function retrieves specific thermal fan details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal fan data.

    ### Returns
    - **dict**: A dictionary containing the following thermal fan details:
      - **FanName** (`str`): The name of the fan.
      - **HotPluggable** (`str`): Indicates if the fan is hot pluggable.
      - **LowerThresholdCritical** (`str`): The critical lower threshold for the fan's reading.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold for the fan's reading.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold for the fan's
         reading.
      - **Name** (`str`): The name of the sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **Reading** (`str`): The current reading of the fan.
      - **ReadingUnits** (`str`): The units of the fan's reading.
      - **SensorNumber** (`str`): The number of the fan's sensor.
      - **UpperThresholdCritical** (`str`): The critical upper threshold for the fan's reading.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold for the fan's reading.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold for the fan's
         reading.
      - **Status_State** (`str`): The state of the fan (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the fan (e.g., "OK").

    ### Example
    >>> redfish_data = {'FanName': 'Fan1', 'Reading': 80, 'UpperThresholdCritical': 100}
    >>> get_chassis_thermal_fans(redfish_data)
    {'FanName': 'Fan1', 'Reading': 80, 'UpperThresholdCritical': 100, ...}
    """
    data = {}
    data['FanName'] = redfish.get('FanName', '')
    data['HotPluggable'] = redfish.get('HotPluggable', '')
    data['LowerThresholdCritical'] = redfish.get('LowerThresholdCritical', '')
    data['LowerThresholdFatal'] = redfish.get('LowerThresholdFatal', '')
    data['LowerThresholdNonCritical'] = redfish.get('LowerThresholdNonCritical', '')
    data['Name'] = redfish.get('Name', '')
    data['PhysicalContext'] = redfish.get('PhysicalContext', '')
    data['Reading'] = redfish.get('Reading', '')
    data['ReadingUnits'] = redfish.get('ReadingUnits', '')
    data['SensorNumber'] = redfish.get('SensorNumber', '')
    data['UpperThresholdCritical'] = redfish.get('UpperThresholdCritical', '')
    data['UpperThresholdFatal'] = redfish.get('UpperThresholdFatal', '')
    data['UpperThresholdNonCritical'] = redfish.get('UpperThresholdNonCritical', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    return data


def get_chassis_thermal_redundancy(redfish):
    """
    Extract thermal redundancy information from a Redfish API response.

    This function retrieves specific thermal redundancy details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal redundancy data.

    ### Returns
    - **dict**: A dictionary containing the following thermal redundancy details:
      - **Mode** (`str`): The mode of the thermal redundancy.
      - **Name** (`str`): The name of the thermal redundancy.
      - **Status_State** (`str`): The state of the thermal redundancy (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the thermal redundancy (e.g., "OK").

    ### Example
    >>> redfish_data = {'Mode': 'Active', 'Name': 'Thermal Redundancy', 'Status': {'State': 'Enabled', 'Health': 'OK'}}
    >>> get_chassis_thermal_redundancy(redfish_data)
    {'Mode': 'Active', 'Name': 'Thermal Redundancy', 'Status_State': 'Enabled', 'Status_Health': 'OK'}
    """
    data = {}
    data['Mode'] = redfish.get('Mode', '')
    data['Name'] = redfish.get('Name', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    return data


def get_chassis_thermal_temperatures(redfish):
    """
    Extract thermal temperature information from a Redfish API response.

    This function retrieves specific thermal temperature details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal temperature data.

    ### Returns
    - **dict**: A dictionary containing the following thermal temperature details:
      - **LowerThresholdCritical** (`str`): The critical lower threshold temperature.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold temperature.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold temperature.
      - **Name** (`str`): The name of the thermal temperature sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **ReadingCelsius** (`str`): The current temperature reading in Celsius.
      - **UpperThresholdCritical** (`str`): The critical upper threshold temperature.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold temperature.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold temperature.
      - **Status_State** (`str`): The state of the thermal sensor (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the thermal sensor (e.g., "OK").

    ### Example
    >>> redfish_data = {'LowerThresholdCritical': '10', 'LowerThresholdFatal': '5', 'LowerThresholdNonCritical': '15', 'Name': 'Thermal Sensor', 'ReadingCelsius': '22', 'Status': {'State': 'Enabled', 'Health': 'OK'}}
    >>> get_chassis_thermal_temperatures(redfish_data)
    {'LowerThresholdCritical': '10', 'LowerThresholdFatal': '5', 'LowerThresholdNonCritical': '15', 'Name': 'Thermal Sensor', 'ReadingCelsius': '22', 'Status_State': 'Enabled', 'Status_Health': 'OK'}
    """
    data = {}
    data['LowerThresholdCritical'] = redfish.get('LowerThresholdCritical', '')
    data['LowerThresholdFatal'] = redfish.get('LowerThresholdFatal', '')
    data['LowerThresholdNonCritical'] = redfish.get('LowerThresholdNonCritical', '')
    data['Name'] = redfish.get('Name', '')
    data['PhysicalContext'] = redfish.get('PhysicalContext', '')
    data['ReadingCelsius'] = redfish.get('ReadingCelsius', '')
    data['UpperThresholdCritical'] = redfish.get('UpperThresholdCritical', '')
    data['UpperThresholdFatal'] = redfish.get('UpperThresholdFatal', '')
    data['UpperThresholdNonCritical'] = redfish.get('UpperThresholdNonCritical', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    return data


def get_manager_logservices_sel_entries(redfish):
    """
    Fetch and format SEL (System Event Log) entries from the Redfish API.

    This function retrieves log entries from the Redfish API, processes each entry based on its
    severity, and formats them into a message string. It also determines the overall state of the
    log entries (OK, WARNING, CRITICAL).

    ### Parameters
    - **redfish** (`dict`): A dictionary containing the Redfish log entries under the 'Members' key.

    ### Returns
    - **tuple**:
      - **msg** (`str`): A formatted string containing the log entries, including the created time,
        message, and severity state.
      - **state** (`int`): The worst state across all log entries, which can be one of the
        following:
        - `STATE_OK` (0): All logs are OK.
        - `STATE_WARN` (1): Some logs are warnings.
        - `STATE_CRIT` (2): Some logs are critical.

    ### Example
    >>> redfish_data = {
    ...     'Members': [
    ...         {'Created': '2021-08-01', 'Message': 'Temperature is high', 'Severity': 'Critical'},
    ...         {'Created': '2021-08-02', 'Message': 'Fan speed normal', 'Severity': 'OK'}
    ...     ]
    ... }
    >>> get_manager_logservices_sel_entries(redfish_data)
    ('* 2021-08-01: Temperature is high [CRITICAL]\n', 2)
    """
    msg = ''
    state = STATE_OK
    msg_state = STATE_OK
    for entry in redfish.get('Members', []):
        if entry.get('Severity', '').lower() == 'ok':
            continue
        if entry.get('Severity', '').lower() == 'critical':
            msg_state = STATE_CRIT
        if entry.get('Severity', '').lower() == 'warning':
            msg_state = STATE_WARN
        msg += '* {}: {}{}\n'.format(
            entry.get('Created', ''),
            entry.get('Message', ''),
            base.state2str(msg_state, prefix=' '),
        )
        state = base.get_worst(state, msg_state)
    return msg, state


def get_perfdata(data, key='Reading'):
    """
    Retrieve the performance data for a specific key from the provided data.

    This function extracts performance-related values such as the reading value, thresholds, and
    range from the provided dictionary. It formats this data and returns a performance data string,
    suitable for monitoring.

    ### Parameters
    - **data** (`dict`): A dictionary containing performance data and related information.
    - **key** (`str`, optional): The key in the dictionary whose value should be extracted.
      Defaults to `'Reading'`.

    ### Returns
    - **str**: A formatted string containing performance data in the format:
      `'label=value[unit];[warn];[crit];[min];[max]'`, or an empty string if the required data is invalid or missing.

    ### Example
    >>> data = {
    ...     'Name': 'Temperature Sensor 1',
    ...     'PhysicalContext': 'Chassis',
    ...     'Reading': 75.0,
    ...     'ReadingUnits': '%',
    ...     'Thresholds_UpperCaution': 80,
    ...     'Thresholds_UpperCritical': 90,
    ...     'ReadingRangeMin': 0,
    ...     'ReadingRangeMax': 100,
    ... }
    >>> get_perfdata(data)
    'Chassis_Temperature_Sensor_1=75.0%;80;90;0;100'
    """
    value = data.get(key, '')
    if not value or not isinstance(value, (int, float)):
        return ''
    name = data.get('Name')
    physical_context = data.get('PhysicalContext')
    uom = '%' if data.get('ReadingUnits', '') == '%' else None
    warn = data['Thresholds_UpperCaution'] if data.get('Thresholds_UpperCaution', '') else None
    crit = data['Thresholds_UpperCritical'] if data.get('Thresholds_UpperCritical', '') else None
    _min = data['ReadingRangeMin'] if data.get('ReadingRangeMin', '') else None
    _max = data['ReadingRangeMax'] if data.get('ReadingRangeMax', '') else None
    return base.get_perfdata('{}_{}'.format(physical_context, name).replace(' ', '_'), value, uom, warn, crit, _min, _max)


def get_sensor_state(data, key='Reading'):
    """
    Determine the state of a sensor based on its reading and threshold values.

    This function evaluates the reading of a sensor and compares it against the defined
    thresholds to determine its state. It returns one of the predefined states: `STATE_OK`,
    `STATE_WARN`, or `STATE_CRIT`.

    ### Parameters
    - **data** (`dict`): A dictionary containing the sensor data and its thresholds (e.g.,
      'Reading', 'Thresholds_UpperCritical', etc.).
    - **key** (`str`, optional): The key in the dictionary whose value should be evaluated.
      Defaults to `'Reading'`.

    ### Returns
    - **int**: The state of the sensor, which can be:
      - `STATE_OK` (0): If the sensor reading is within acceptable thresholds.
      - `STATE_WARN` (1): If the sensor reading is in a warning range.
      - `STATE_CRIT` (2): If the sensor reading exceeds critical thresholds.

    ### Example
    >>> data = {
    ...     'Reading': 75.0,
    ...     'Thresholds_UpperCritical': 80,
    ...     'Thresholds_LowerCritical': 10,
    ...     'Thresholds_UpperCaution': 70,
    ...     'Thresholds_LowerCaution': 20,
    ... }
    >>> get_sensor_state(data)
    1  # STATE_WARN
    """
    value = data.get(key, '')
    if not value or not isinstance(value, (int, float)):
        return STATE_OK
    if data.get('Thresholds_UpperCritical', '') and value >= data['Thresholds_UpperCritical']:
        return STATE_CRIT
    if data.get('Thresholds_LowerCritical', '') and value <= data['Thresholds_LowerCritical']:
        return STATE_CRIT
    if data.get('Thresholds_UpperCaution', '') and value >= data['Thresholds_UpperCaution']:
        return STATE_WARN
    if data.get('Thresholds_LowerCaution', '') and value <= data['Thresholds_LowerCaution']:
        return STATE_WARN
    return STATE_OK


def get_state(data):
    """
    Determine the state of an entity based on its health and status.

    This function checks the `Status_State` and `Status_HealthRollup` values in the provided data
    dictionary and returns a state based on these values. It assigns `STATE_CRIT` if the status or
    health rollup indicates a critical state, `STATE_WARN` for warning states, or `STATE_OK` if no
    critical or warning states are found.

    ### Parameters
    - **data** (`dict`): A dictionary containing the status and health information of the entity
      (e.g., `Status_State`, `Status_Health`, `Status_HealthRollup`).

    ### Returns
    - **int**: The state of the entity, which can be:
      - `STATE_OK` (0): If the entity is in a normal or healthy state.
      - `STATE_WARN` (1): If the entity's health or status indicates a warning.
      - `STATE_CRIT` (2): If the entity's health or status indicates a critical state.

    ### Example
    >>> data = {
    ...     'Status_State': 'Enabled',
    ...     'Status_Health': 'Warning',
    ...     'Status_HealthRollup': 'Critical',
    ... }
    >>> get_state(data)
    2  # STATE_CRIT
    """
    if data.get('Status_State', '') in ['Enabled', 'Quiesced']:
        if data.get('Status_HealthRollup') is not None and data.get('Status_HealthRollup').lower() == 'critical':
            return STATE_CRIT
        if data.get('Status_HealthRollup') is not None and data.get('Status_HealthRollup').lower() == 'warning':
            return STATE_WARN
        if data.get('Status_Health') is not None and data.get('Status_Health').lower() == 'critical':
            return STATE_CRIT
        if data.get('Status_Health') is not None and data.get('Status_Health').lower() == 'warning':
            return STATE_WARN
    return STATE_OK


def get_systems(redfish):
    """
    Retrieves system information from the Redfish API response.

    This function processes a Redfish API response to extract system details such as BIOS version,
    host name, manufacturer, model, processor summary, power state, and system health status.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing system-related
      information such as BIOS version, processor details, and status information.

    ### Returns
    - **dict**: A dictionary containing the following system details:
      - `BiosVersion`: The BIOS version.
      - `HostName`: The system's host name.
      - `Id`: The unique identifier for the system.
      - `IndicatorLED`: The system's indicator LED state.
      - `Manufacturer`: The manufacturer of the system.
      - `Model`: The model of the system.
      - `PowerState`: The current power state of the system (e.g., "On").
      - `ProcessorSummary_Count`: The number of processors.
      - `ProcessorSummary_LogicalProcessorCount`: The number of logical processors.
      - `ProcessorSummary_Model`: The model of the processor.
      - `SerialNumber`: The system's serial number.
      - `SKU`: The system's SKU (Stock Keeping Unit).
      - `Storage_@odata.id`: The OData ID for the system's storage.
      - `Status_State`: The system's status state (e.g., "Enabled").
      - `Status_Health`: The system's health status (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the system.

    ### Example
    >>> redfish_data = {
    ...     'BiosVersion': '1.0.0',
    ...     'HostName': 'System1',
    ...     'Id': '12345',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ...     'ProcessorSummary': {'Count': 2, 'LogicalProcessorCount': 4, 'Model': 'Intel Xeon'},
    ...     'PowerState': 'On',
    ... }
    >>> get_systems(redfish_data)
    {
        'BiosVersion': '1.0.0',
        'HostName': 'System1',
        'Id': '12345',
        'IndicatorLED': '',
        'Manufacturer': '',
        'Model': '',
        'PowerState': 'On',
        'ProcessorSummary_Count': 2,
        'ProcessorSummary_LogicalProcessorCount': 4,
        'ProcessorSummary_Model': 'Intel Xeon',
        'SerialNumber': '',
        'SKU': '',
        'Storage_@odata.id': '',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {}
    data['BiosVersion'] = redfish.get('BiosVersion', '')
    data['HostName'] = redfish.get('HostName', '')
    data['Id'] = redfish.get('Id', '')
    data['IndicatorLED'] = redfish.get('IndicatorLED', '')
    data['Manufacturer'] = redfish.get('Manufacturer', '')
    data['Model'] = redfish.get('Model', '')
    data['PowerState'] = redfish.get('PowerState', '')                                  # On
    data['ProcessorSummary_Count'] = redfish.get('ProcessorSummary', {}).get('Count', '')
    data['ProcessorSummary_LogicalProcessorCount'] = redfish.get('ProcessorSummary', {}).get('LogicalProcessorCount', '')
    data['ProcessorSummary_Model'] = redfish.get('ProcessorSummary', {}).get('Model', '')
    data['SerialNumber'] = redfish.get('SerialNumber', '')
    data['SKU'] = redfish.get('SKU', '')
    data['Storage_@odata.id'] = redfish.get('Storage', {}).get('@odata.id', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    data['Status_HealthRollup'] = redfish.get('Status', {}).get('HealthRollup', '')     # OK
    return data


def get_systems_storage(redfish):
    """
    Retrieves storage system information from the Redfish API response.

    This function processes a Redfish API response to extract storage-related system details such
    as the storage description, number of drives, storage ID, name, and health status.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing storage-related
      information such as description, status, and health.

    ### Returns
    - **dict**: A dictionary containing the following storage system details:
      - `Description`: A description of the storage system.
      - `Drives@odata.count`: The number of drives in the storage system.
      - `Id`: The unique identifier for the storage system.
      - `Name`: The name of the storage system.
      - `Status_State`: The status state of the storage system (e.g., "Enabled").
      - `Status_Health`: The health status of the storage system (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the storage system.

    ### Example
    >>> redfish_data = {
    ...     'Description': 'RAID Storage',
    ...     'Drives@odata.count': 5,
    ...     'Id': '6789',
    ...     'Name': 'StorageSystem1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ... }
    >>> get_systems_storage(redfish_data)
    {
        'Description': 'RAID Storage',
        'Drives@odata.count': 5,
        'Id': '6789',
        'Name': 'StorageSystem1',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {}
    data['Description'] = redfish.get('Description', '')
    data['Drives@odata.count'] = redfish.get('Drives@odata.count', '')
    data['Id'] = redfish.get('Id', '')
    data['Name'] = redfish.get('Name', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    data['Status_HealthRollup'] = redfish.get('Status', {}).get('HealthRollup', '')     # OK
    return data


def get_systems_storage_drives(redfish):
    """
    Retrieves storage drive details from the Redfish API response.

    This function processes the Redfish API response to extract information about storage drives, 
    including attributes such as capacity, encryption status, failure prediction, speed, and other
    properties.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing details about
      storage drives such as capacity, health status, and manufacturer.

    ### Returns
    - **dict**: A dictionary containing the following storage drive details:
      - `BlockSizeBytes`: The block size of the storage drive in bytes.
      - `CapableSpeedGbs`: The capable speed of the drive in gigabits per second (Gbps).
      - `CapacityBytes`: The capacity of the drive in human-readable format (converted from bytes).
      - `Description`: A description of the storage drive.
      - `EncryptionAbility`: The encryption ability status of the storage drive.
      - `EncryptionStatus`: The current encryption status of the storage drive.
      - `FailurePredicted`: A boolean indicating whether failure of the drive is predicted.
      - `HotspareType`: The type of hot spare (if any) associated with the drive.
      - `Id`: The unique identifier for the storage drive.
      - `Manufacturer`: The manufacturer of the storage drive.
      - `MediaType`: The type of media used by the storage drive (e.g., SSD, HDD).
      - `Model`: The model of the storage drive.
      - `Name`: The name of the storage drive.
      - `NegotiatedSpeedGbs`: The negotiated speed of the drive in gigabits per second (Gbps).
      - `PartNumber`: The part number of the storage drive.
      - `PredictedMediaLifeLeftPercent`: The predicted remaining life of the storage media in
         percentage.
      - `Protocol`: The protocol used by the storage drive (e.g., SATA, NVMe).
      - `Revision`: The revision number of the storage drive.
      - `RotationSpeedRPM`: The rotational speed of the drive (if applicable) in revolutions per
         minute (RPM).
      - `SerialNumber`: The serial number of the storage drive.
      - `WriteCacheEnabled`: A boolean indicating whether write cache is enabled on the drive.
      - `Status_State`: The state of the storage drive (e.g., "Enabled").
      - `Status_Health`: The health status of the storage drive (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the storage drive (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'CapacityBytes': 500000000000,
    ...     'Description': 'SSD Drive',
    ...     'Manufacturer': 'Samsung',
    ...     'Model': '970 EVO',
    ...     'SerialNumber': '1234567890',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ... }
    >>> get_systems_storage_drives(redfish_data)
    {
        'CapacityBytes': '500.0 GB',
        'Description': 'SSD Drive',
        'Manufacturer': 'Samsung',
        'Model': '970 EVO',
        'SerialNumber': '1234567890',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {}
    data['BlockSizeBytes'] = redfish.get('BlockSizeBytes', '')
    data['CapableSpeedGbs'] = redfish.get('CapableSpeedGbs', '')
    data['CapacityBytes'] = human.bytes2human(redfish.get('CapacityBytes', ''))
    data['Description'] = redfish.get('Description', '')
    data['EncryptionAbility'] = redfish.get('EncryptionAbility', '')
    data['EncryptionStatus'] = redfish.get('EncryptionStatus', '')
    data['FailurePredicted'] = redfish.get('FailurePredicted', '')
    data['HotspareType'] = redfish.get('HotspareType', '')
    data['Id'] = redfish.get('Id', '')
    data['Manufacturer'] = redfish.get('Manufacturer', '')
    data['MediaType'] = redfish.get('MediaType', '')
    data['Model'] = redfish.get('Model', '')
    data['Name'] = redfish.get('Name', '')
    data['NegotiatedSpeedGbs'] = redfish.get('NegotiatedSpeedGbs', '')
    data['PartNumber'] = redfish.get('PartNumber', '')
    data['PredictedMediaLifeLeftPercent'] = redfish.get('PredictedMediaLifeLeftPercent', '')
    data['Protocol'] = redfish.get('Protocol', '')
    data['Revision'] = redfish.get('Revision', '')
    data['RotationSpeedRPM'] = redfish.get('RotationSpeedRPM', '')
    data['SerialNumber'] = redfish.get('SerialNumber', '')
    data['WriteCacheEnabled'] = redfish.get('WriteCacheEnabled', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    data['Status_HealthRollup'] = redfish.get('Status', {}).get('HealthRollup', '')     # OK
    return data


def get_vendor(redfish):
    """
    Retrieves the vendor information from the Redfish API response.

    This function checks for the 'Vendor' key in the Redfish API response. If it's not found,
    it looks in the  'Oem' dictionary for the first key and uses that as the vendor. If no vendor
    information is available, it returns 'generic'.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing information about
      the system, including vendor details.

    ### Returns
    - **str**: The vendor name in lowercase, or 'generic' if no vendor information is found.

    ### Example
    >>> redfish_data = {
    ...     'Vendor': 'DELL',
    ... }
    >>> get_vendor(redfish_data)
    'dell'

    >>> redfish_data = {
    ...     'Oem': {'SomeOtherVendor': 'details'},
    ... }
    >>> get_vendor(redfish_data)
    'someothervendor'

    >>> redfish_data = {}
    >>> get_vendor(redfish_data)
    'generic'
    """
    vendor = redfish.get('Vendor', '')
    if not vendor:
        oem = redfish.get('Oem', {})
        if oem:
            # get the first existing key from Oem dict
            vendor = list(oem)[0]
    if vendor:
        return vendor.lower()
    return 'generic'
