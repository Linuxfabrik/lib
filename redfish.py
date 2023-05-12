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
__version__ = '2023051201'

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
    data = {}
    data['Mode'] = redfish.get('Mode', '')
    data['Name'] = redfish.get('Name', '')
    data['Status_State'] = redfish.get('Status', {}).get('State', '')                   # Enabled
    data['Status_Health'] = redfish.get('Status', {}).get('Health', '')                 # OK
    return data


def get_chassis_thermal_temperatures(redfish):
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
    vendor = redfish.get('Vendor', '')
    if not vendor:
        oem = redfish.get('Oem', {})
        if oem:
            # get the first existing key from Oem dict
            vendor = list(oem)[0]
    if vendor:
        vendor = vendor.lower()
    else:
        vendor = 'generic'
    return vendor
