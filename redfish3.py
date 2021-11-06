#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library parses data from the Redfish API.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021110601'

from . import base3
from .globals3 import STATE_OK, STATE_UNKNOWN, STATE_WARN, STATE_CRIT


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


def get_state(data):
    if data.get('Status_State', '') in ['Enabled', 'Quiesced']:
        if data.get('Status_HealthRollup', '').lower() == 'critical':
            return STATE_CRIT
        if data.get('Status_HealthRollup', '').lower() == 'warning':
            return STATE_WARN
        if data.get('Status_Health', '').lower() == 'critical':
            return STATE_CRIT
        if data.get('Status_Health', '').lower() == 'warning':
            return STATE_WARN
    return STATE_OK


def get_value_state(data, key='Reading', warn_late=False):
    """
    UpperThresholdFatal: Above normal range and is fatal.
    UpperThresholdCritical: Above normal range but not yet fatal.
    UpperThresholdNonCritical: Above normal range.
    LowerThresholdNonCritical: Below normal range.
    LowerThresholdCritical: Below normal range but not yet fatal
    LowerThresholdFatal: Below normal range and is fatal.
    """
    value = data[key]
    if data.get('UpperThresholdCritical', '') and value >= data['UpperThresholdCritical']:
        return STATE_CRIT
    if data.get('LowerThresholdCritical', '') and value <= data['LowerThresholdCritical']:
        return STATE_CRIT
    if data.get('UpperThresholdNonCritical', '') and value >= data['UpperThresholdNonCritical']:
        return STATE_WARN
    if data.get('LowerThresholdNonCritical', '') and value <= data['LowerThresholdNonCritical']:
        return STATE_WARN
    return STATE_OK


def get_perfdata(data):
    value = ''
    if data.get('ReadingCelsius', ''):
        value = data['ReadingCelsius']
    if data.get('Reading', ''):
        value = data['Reading']
    if not value or not (isinstance(value, int) or isinstance(value, float)):
        return ''
    key = data['Name']
    uom = None  # maybe data['ReadingUnits']
    if data.get('UpperThresholdNonCritical', ''):
        warn = data['UpperThresholdNonCritical']
    else:
        warn = None
    if data.get('UpperThresholdCritical', ''):
        crit = data['UpperThresholdCritical']
    else:
        crit = None
    return base3.get_perfdata(key, value, uom, warn, crit, None, None)


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
