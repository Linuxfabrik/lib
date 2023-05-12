#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Library for parsing information from dmidecode. Have a look at `man dmidecode` for details
about dmidecode.
Copied and refactored from py-dmidecode (https://github.com/zaibon/py-dmidecode).
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

import re
import subprocess

from . import shell


HANDLE_RE = re.compile('^Handle\\s+(.+),\\s+DMI\\s+type\\s+(\\d+),\\s+(\\d+)\\s+bytes$')
IN_BLOCK_RE = re.compile('^\\t\\t(.+)$')
RECORD_RE = re.compile('\\t(.+):\\s+(.+)$')
RECORD2_RE = re.compile('\\t(.+):$')

TYPE2STR = {
    0: 'BIOS',
    1: 'System',
    2: 'Baseboard',
    3: 'Chassis',
    4: 'Processor',
    5: 'Memory Controller',
    6: 'Memory Module',
    7: 'Cache',
    8: 'Port Connector',
    9: 'System Slots',
    10: 'On Board Devices',
    11: 'OEM Strings',
    12: 'System Configuration Options',
    13: 'BIOS Language',
    14: 'Group Associations',
    15: 'System Event Log',
    16: 'Physical Memory Array',
    17: 'Memory Device',
    18: '32-bit Memory Error',
    19: 'Memory Array Mapped Address',
    20: 'Memory Device Mapped Address',
    21: 'Built-in Pointing Device',
    22: 'Portable Battery',
    23: 'System Reset',
    24: 'Hardware Security',
    25: 'System Power Controls',
    26: 'Voltage Probe',
    27: 'Cooling Device',
    28: 'Temperature Probe',
    29: 'Electrical Current Probe',
    30: 'Out-of-band Remote Access',
    31: 'Boot Integrity Services',
    32: 'System Boot',
    33: '64-bit Memory Error',
    34: 'Management Device',
    35: 'Management Device Component',
    36: 'Management Device Threshold Data',
    37: 'Memory Channel',
    38: 'IPMI Device',
    39: 'Power Supply',
    40: 'Additional Information',
    41: 'Onboard Devices Extended Information',
    42: 'Management Controller Host Interface',
}


def dmiget(dmi, type_id):
    if isinstance(type_id, str):
        for type_num, type_str in TYPE2STR.items():
            if type_str == type_id:
                type_id = type_num
    result = list()
    for item in dmi.values():
        if item['dmitype'] == type_id:
            result.append(item)
    return result


# ---------

# ('0x0400', '4', '48'): {'dminame': 'Processor Information', 'dmisize': 48, 'dmitype': 4, 'Socket Designation': 'CPU 1', 'Type': 'Central Processor', 'Family': 'Core i7', 'Manufacturer': 'Intel(R) Corporation', 'ID': 'C1 06 08 00 FF FB EB BF', 'Signature': 'Type 0, Family 6, Model 140, Stepping 1', 'Version': '11th Gen Intel(R) Core(TM) i7-1185G7 @ 3.00GHz', 'Voltage': '0.8 V', 'External Clock': '100 MHz', 'Max Speed': '3000 MHz', 'Current Speed': '3000 MHz', 'Status': 'Populated, Enabled', 'Upgrade': 'Other', 'L1 Cache Handle': '0x0701', 'L2 Cache Handle': '0x0702', 'L3 Cache Handle': '0x0703', 'Serial Number': ' ', 'Asset Tag': ' ', 'Part Number': ' ', 'Core Count': '4', 'Core Enabled': '4', 'Thread Count': '8'}, 

def cpu_cores(dmi):
    cores = 0
    for cpu in dmiget(dmi, 'Processor'):
        cores += int(cpu.get('Core Count', 0))
    return cores


def cpu_cores_enabled(dmi):
    cores = 0
    for cpu in dmiget(dmi, 'Processor'):
        cores += int(cpu.get('Core Enabled', 0))
    return cores


def cpu_speed(dmi):
    speed = 0
    for cpu in dmiget(dmi, 'Processor'):
        if not any(item in cpu['Current Speed'] for item in [' MHz']):
            # "No module installed"
            continue
        speed = int(cpu.get('Current Speed', '0').replace (' MHz', ''))
    return speed


def cpu_threads(dmi):
    cores = 0
    for cpu in dmiget(dmi, 'Processor'):
        cores += int(cpu.get('Thread Count', 0))
    return cores


def cpu_type(dmi):
    cpu_type = 'n/a'
    for cpu in dmiget(dmi, 'Processor'):
        if cpu.get('Core Enabled'):
            cpu_type = cpu.get('Version', 'n/a').replace('(R)', '').replace('(TM)', '')
    return cpu_type.replace('NotSpecified', 'n/a')


def firmware(dmi):
    return dmiget(dmi, 'BIOS')[0].get('Firmware Revision', 'n/a')


def manufacturer(dmi):
    return dmiget(dmi, 'System')[0].get('Manufacturer', 'n/a')


def model(dmi):
    return dmiget(dmi, 'System')[0].get('Product Name', 'n/a')


def ram(dmi):
    """Returns sum of all ram slotes in Bytes.
    """
    _sum = 0
    for slot in dmiget(dmi, 'Memory Device'):
        if not any(item in slot['Size'] for item in [' MB', ' GB']):
            # "No module installed"
            continue
        size = int(slot['Size'].replace(' MB', '').replace(' GB', ''))
        if 'GB' in slot['Size']:
            size = size * 1024 * 1024 * 1024
        if 'MB' in slot['Size']:
            size = size * 1024 * 1024
        _sum += size
    return _sum


def serno(dmi):
    return dmiget(dmi, 'System')[0].get('Serial Number', 'n/a').replace('Not Specified', 'n/a')

# ---------

def dmidecode_parse(output):
    data = {}
    # each record is separated by double newlines
    for record in output.split('\n\n'):
        record_element = record.splitlines()

        # entries with less than 3 lines are incomplete / inactive
        # skip them
        if len(record_element) < 3:
            continue

        handle_data = HANDLE_RE.findall(record_element[0])
        if not handle_data:
            continue
        dmi_handle = handle_data[0]

        data[dmi_handle] = {}
        data[dmi_handle]['dminame'] = record_element[1]     # 2nd line == name
        data[dmi_handle]['dmisize'] = int(dmi_handle[2])
        data[dmi_handle]['dmitype'] = int(dmi_handle[1])

        in_block_element = ''
        in_block_list = ''

        # loop over the rest of the record, gathering values
        for i in range(2, len(record_element), 1):
            if i >= len(record_element):
                break
            # check whether we are inside a \t\t block
            if in_block_element != '':
                in_block_data = IN_BLOCK_RE.findall(record_element[1])
                if in_block_data:
                    if not in_block_list:
                        in_block_list = in_block_data[0][0]
                    else:
                        in_block_list = in_block_list + '\t\t'
                        +in_block_data[0][1]
                    data[dmi_handle][in_block_element] = in_block_list
                    continue
                else:
                    # we are out of the \t\t block; reset it again, and let the parsing continue
                    in_block_element = ''

            record_data = RECORD_RE.findall(record_element[i])

            # is this the line containing handle identifier, type, size?
            if record_data:
                data[dmi_handle][record_data[0][0]] = record_data[0][1]
                continue

            # didn't find regular entry, maybe an array of data?
            record_data2 = RECORD2_RE.findall(record_element[i])

            if record_data2:
                # this is an array of data - let the loop know we are inside an array block
                in_block_element = record_data2[0][0]

    return data


def get_data():
    success, result = shell.shell_exec('sudo dmidecode')
    if not success:
        return False
    stdout, stderr, retc = result
    if retc > 0:
        return False
    return dmidecode_parse(stdout)
