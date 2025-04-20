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
__version__ = '2025042001'

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


# ('0x0400', '4', '48'): {'dminame': 'Processor Information', 'dmisize': 48, 'dmitype': 4, 'Socket Designation': 'CPU 1', 'Type': 'Central Processor', 'Family': 'Core i7', 'Manufacturer': 'Intel(R) Corporation', 'ID': 'C1 06 08 00 FF FB EB BF', 'Signature': 'Type 0, Family 6, Model 140, Stepping 1', 'Version': '11th Gen Intel(R) Core(TM) i7-1185G7 @ 3.00GHz', 'Voltage': '0.8 V', 'External Clock': '100 MHz', 'Max Speed': '3000 MHz', 'Current Speed': '3000 MHz', 'Status': 'Populated, Enabled', 'Upgrade': 'Other', 'L1 Cache Handle': '0x0701', 'L2 Cache Handle': '0x0702', 'L3 Cache Handle': '0x0703', 'Serial Number': ' ', 'Asset Tag': ' ', 'Part Number': ' ', 'Core Count': '4', 'Core Enabled': '4', 'Thread Count': '8'}, 


def cpu_cores(dmi):
    """
    Calculate the total number of CPU cores.

    This function sums the core count from all processor entries in the given DMI data structure.
    If a processor entry does not specify a core count, it is treated as zero.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **int**:
      The total number of CPU cores found across all processors.

    ### Notes
    - Entries are retrieved using `dmiget(dmi, 'Processor')`.
    - Missing or invalid core counts default to zero.

    ### Example
    >>> cpu_cores(parsed_dmi)
    8
    """
    return sum(int(cpu.get('Core Count', 0)) for cpu in dmiget(dmi, 'Processor'))


def cpu_cores_enabled(dmi):
    """
    Calculate the total number of enabled CPU cores.

    This function sums the enabled core count from all processor entries in the given DMI data
    structure. If a processor entry does not specify enabled cores, it is treated as zero.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **int**:
      The total number of enabled CPU cores across all processors.

    ### Notes
    - Entries are retrieved using `dmiget(dmi, 'Processor')`.
    - Missing or invalid enabled core counts default to zero.

    ### Example
    >>> cpu_cores_enabled(parsed_dmi)
    8
    """
    return sum(int(cpu.get('Core Enabled', 0)) for cpu in dmiget(dmi, 'Processor'))


def cpu_speed(dmi):
    """
    Retrieve the CPU speed in megahertz (MHz).

    This function checks all processor entries in the given DMI data and returns the speed
    of the first valid CPU found. Speeds are expected to be specified in MHz.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **int**:
      The CPU speed in MHz. If no valid entry is found, returns `0`.

    ### Notes
    - Entries without a proper `Current Speed` field are skipped.
    - Only the first valid speed encountered is returned.

    ### Example
    >>> cpu_speed(parsed_dmi)
    3200
    """
    for cpu in dmiget(dmi, 'Processor'):
        current_speed = cpu.get('Current Speed', '')
        if current_speed.endswith(' MHz'):
            return int(current_speed.replace(' MHz', '').strip())
    return 0


def cpu_threads(dmi):
    """
    Calculate the total number of CPU threads.

    This function sums the thread count from all processor entries in the given DMI data structure.
    If a processor entry does not specify a thread count, it is treated as zero.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **int**:
      The total number of CPU threads across all processors.

    ### Notes
    - Entries are retrieved using `dmiget(dmi, 'Processor')`.
    - Missing or invalid thread counts default to zero.

    ### Example
    >>> cpu_threads(parsed_dmi)
    16
    """
    return sum(int(cpu.get('Thread Count', 0)) for cpu in dmiget(dmi, 'Processor'))


def cpu_type(dmi):
    """
    Retrieve the CPU type string.

    This function extracts the CPU type from the `Version` field of the first enabled processor
    entry in the given DMI data. Trademark symbols like `(R)` and `(TM)` are removed for clarity.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **str**:
      The CPU type as a clean string. Returns `'n/a'` if no valid CPU entry is found.

    ### Notes
    - The `Version` field is sanitized to remove `(R)`, `(TM)`, and `'NotSpecified'` strings.
    - Only the first enabled CPU entry is considered.

    ### Example
    >>> cpu_type(parsed_dmi)
    'Intel Xeon Silver 4210 CPU'
    """
    for cpu in dmiget(dmi, 'Processor'):
        if int(cpu.get('Core Enabled', 0)) > 0:
            cpu_version = cpu.get('Version', '').replace('(R)', '').replace('(TM)', '').strip()
            if 'NotSpecified' in cpu_version or not cpu_version:
                return 'n/a'
            return cpu_version
    return 'n/a'


def dmidecode_parse(output):
    """
    Parse the raw output of `dmidecode` into a structured dictionary.

    This function processes the raw textual output of the `dmidecode` tool and extracts
    structured information about system hardware, organized by DMI handle.

    ### Parameters
    - **output** (`str`):
      The raw string output from the `dmidecode` command.

    ### Returns
    - **dict**:
      A dictionary keyed by DMI handle. Each value contains fields such as dminame, dmisize,
      dmitype, and parsed key-value pairs from the output.

    ### Notes
    - Records are separated by double newlines in the output.
    - Only records with at least three lines are considered valid.
    - Multi-line blocks are handled if needed.

    ### Example
    >>> dmidecode_parse(dmidecode_output)
    {
        ('0xDA00', '218', '251'): {
            'dminame': 'OEM-specific Type',
            'dmisize': 251,
            'dmitype': 218,
            'H': 'D\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0'
        },
        ('0x0001', '0', '26'): {
            'dminame': 'BIOS Information',
            'dmisize': 26,
            'dmitype': 0,
            'Vendor': 'Dell Inc.',
            'Version': '1.7.1',
            'Release Date': '12/06/2024',
            'ROM Size': '64 MB',
            ...,
        },
        ...
    }
    """
    data = {}

    for record in output.split('\n\n'):
        record_element = record.splitlines()
        if len(record_element) < 3:
            continue

        handle_data = HANDLE_RE.findall(record_element[0])
        if not handle_data:
            continue

        dmi_handle = handle_data[0]
        data[dmi_handle] = {
            'dminame': record_element[1],
            'dmisize': int(dmi_handle[2]),
            'dmitype': int(dmi_handle[1]),
        }

        in_block_element = None
        in_block_list = []

        for line in record_element[2:]:
            if in_block_element:
                in_block_data = IN_BLOCK_RE.findall(line)
                if in_block_data:
                    in_block_list.append(in_block_data[0][0])
                    data[dmi_handle][in_block_element] = '\t\t'.join(in_block_list)
                    continue
                else:
                    in_block_element = None
                    in_block_list = []

            record_data = RECORD_RE.findall(line)
            if record_data:
                key, value = record_data[0]
                data[dmi_handle][key] = value
                continue

            record_data2 = RECORD2_RE.findall(line)
            if record_data2:
                in_block_element = record_data2[0][0]
                in_block_list = []

    return data


def dmiget(dmi, type_id):
    """
    Retrieve DMI entries of a specific type.

    This function filters a parsed DMI data structure, returning all entries matching the specified
    type ID. If a string type name is given, it is internally mapped to its numeric type ID.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.
    - **type_id** (`int` or `str`):
      The DMI type as an integer or string. If a string is given, it is matched against known
      type names.

    ### Returns
    - **list**:
      A list of DMI entries (dicts) matching the specified type ID.

    ### Notes
    - The `TYPE2STR` mapping must be available globally to resolve string type names.
    - Useful for extracting subsets like BIOS information, baseboard details, or memory devices.

    ### Example
    >>> dmiget(parsed_dmi, 'Memory Device')
    [{'Handle': '0x1100', 'Size': '8 GB', 'Form Factor': 'SODIMM', ...}]
    """
    if isinstance(type_id, str):
        type_id = next(
            (type_num for type_num, type_str in TYPE2STR.items() if type_str == type_id),
            None
        )
        if type_id is None:
            return []

    return [item for item in dmi.values() if item.get('dmitype') == type_id]


def firmware(dmi):
    """
    Retrieve the firmware revision from DMI data.

    This function extracts the firmware revision string from the BIOS information in the given
    DMI data. If not available, returns `'n/a'`.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **str**:
      The firmware revision string, or `'n/a'` if not found.

    ### Notes
    - Assumes that BIOS entries exist and uses the first entry (`dmiget(dmi, 'BIOS')[0]`).

    ### Example
    >>> firmware(parsed_dmi)
    '1.2.3'
    """
    bios_entries = dmiget(dmi, 'BIOS')
    if bios_entries:
        return bios_entries[0].get('Firmware Revision', 'n/a')
    return 'n/a'


def get_data():
    """
    Retrieve and parse DMI data using `dmidecode`.

    This function executes the `dmidecode` command, parses its output, and returns structured
    DMI data. If execution fails or returns a non-zero exit code, returns `False`.

    ### Parameters
    - *(none)*

    ### Returns
    - **dict**:
      Parsed DMI data if successful.

    - **bool**:
      `False` on failure (e.g., command failed, permission denied, `dmidecode` not installed).

    ### Notes
    - Requires root privileges to run `dmidecode`.
    - Depends on a shell execution helper (`shell.shell_exec`).

    ### Example
    >>> get_data()
    {
        ('0xDA00', '218', '251'): {
            'dminame': 'OEM-specific Type',
            'dmisize': 251,
            'dmitype': 218,
            'H': 'D\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0'
        },
        ('0x0001', '0', '26'): {
            'dminame': 'BIOS Information',
            'dmisize': 26,
            'dmitype': 0,
            'Vendor': 'Dell Inc.',
            'Version': '1.7.1',
            'Release Date': '12/06/2024',
            'ROM Size': '64 MB',
            ...,
        },
        ...
    }
    """
    success, result = shell.shell_exec('sudo dmidecode')
    if not success:
        return False

    stdout, stderr, retc = result
    if retc != 0:
        return False

    return dmidecode_parse(stdout)


def manufacturer(dmi):
    """
    Retrieve the system manufacturer from DMI data.

    This function extracts the manufacturer name from the system information in the given
    DMI data. If not available, returns `'n/a'`.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **str**:
      The manufacturer name, or `'n/a'` if not found.

    ### Notes
    - Assumes that system entries exist and uses the first entry (`dmiget(dmi, 'System')[0]`).

    ### Example
    >>> manufacturer(parsed_dmi)
    'Dell Inc.'
    """
    system_entries = dmiget(dmi, 'System')
    if system_entries:
        return system_entries[0].get('Manufacturer', 'n/a')
    return 'n/a'


def model(dmi):
    """
    Retrieve the system model name from DMI data.

    This function extracts the model (product) name from the system information in the given
    DMI data. If not available, returns `'n/a'`.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **str**:
      The model name, or `'n/a'` if not found.

    ### Notes
    - Assumes that system entries exist and uses the first entry (`dmiget(dmi, 'System')[0]`).

    ### Example
    >>> model(parsed_dmi)
    'PowerEdge R640'
    """
    system_entries = dmiget(dmi, 'System')
    if system_entries:
        return system_entries[0].get('Product Name', 'n/a')
    return 'n/a'


def ram(dmi):
    """
    Calculate the total amount of RAM installed in bytes.

    This function sums the memory size of all populated memory slots found in the given
    DMI data. Slot sizes given in megabytes (MB) or gigabytes (GB) are normalized to bytes.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **int**:
      The total amount of RAM in bytes.

    ### Notes
    - Only slots reporting a size in MB or GB are considered.
    - Entries reporting "No module installed" are skipped.

    ### Example
    >>> ram(parsed_dmi)
    34359738368
    """
    total = 0
    for slot in dmiget(dmi, 'Memory Device'):
        size_field = slot.get('Size', '').upper()
        if 'GB' in size_field:
            size = int(size_field.replace(' GB', '').strip()) * 1024**3
            total += size
        elif 'MB' in size_field:
            size = int(size_field.replace(' MB', '').strip()) * 1024**2
            total += size
    return total


def serno(dmi):
    """
    Retrieve the system serial number from DMI data.

    This function extracts the serial number from the system information in the given DMI data.
    If the serial number is missing or marked as "Not Specified", returns `'n/a'`.

    ### Parameters
    - **dmi** (`dict`):
      The parsed DMI data, typically a dictionary from SMBIOS or `dmidecode` output.

    ### Returns
    - **str**:
      The system serial number, or `'n/a'` if not found.

    ### Notes
    - Assumes that system entries exist and uses the first entry (`dmiget(dmi, 'System')[0]`).
    - Normalizes "Not Specified" to `'n/a'`.

    ### Example
    >>> serno(parsed_dmi)
    '4C4C4544-0032-5A10-8050-B5C04F503632'
    """
    system_entries = dmiget(dmi, 'System')
    if system_entries:
        serno = system_entries[0].get('Serial Number', 'n/a')
        return serno.replace('Not Specified', 'n/a')
    return 'n/a'
