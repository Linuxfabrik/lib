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
__version__ = '2025090901'

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
    Parse `dmidecode` output into a dict, collapsing near-duplicates in an admin-friendly way.

    Type-aware dedupe rules:
      - Type 4 (Processor Information): ignore per-thread/core/socket noise fields; merge;
        add dedup_count/dedup_sockets
      - Type 17 (Memory Device): drop unpopulated; ignore slot labels; merge;
        add dedup_count/dedup_slots
      - Other types: generic dedupe (exact content after normalization)

    Returns:
      { dmi_handle_tuple: parsed_record_dict, ... }
      where parsed_record_dict includes keys: dminame, dmisize, dmitype, parsed fields,
      and possibly:
        - dedup_count (int >= 1)
        - dedup_sockets / dedup_slots (sorted list of labels encountered)
        - dedup_handles (list of original DMI handle strings that were merged)
    """
    data = {}
    seen = {}  # fp -> (first_handle, aggregated_record)

    # --- helpers -------------------------------------------------------------
    def _normalize(s):
        if s is None:
            return ''
        s = str(s).strip()
        # treat common "unknown" variants as empty so they don't block dedupe
        if s.lower() in {'unknown', 'not specified', 'not provided', 'n/a'}:
            return ''
        # collapse whitespace
        return ' '.join(s.split())

    def _lower(s):
        return _normalize(s).lower()

    def _drop_unpopulated_type17(rec):
        size = _lower(rec.get('Size'))
        if not size:
            return True
        if 'no module installed' in size:
            return True
        # Sometimes vendors encode 0-sized entries
        if size.startswith('0 ') or size == '0':
            return True
        return False

    # Fields to ignore by DMI type when constructing fingerprints (order-independent)
    IGNORE_BY_TYPE = {
        4: {  # Processor Information
            'Socket Designation', 'ID',
            'L1 Cache Handle', 'L2 Cache Handle', 'L3 Cache Handle',
            'Serial Number', 'Asset Tag', 'Part Number',
            'Core Count', 'Core Enabled',  # often bogus or per-core
        },
        17: {  # Memory Device
            'Locator', 'Bank Locator', 'Device Locator',
            'Memory Array Mapped Address Handle', 'Mem Array Error Info Handle',
            'Total Width', 'Data Width',  # width can vary by board reporting; not essential
            'Serial Number',  # sometimes blank; can differ even for identical sticks
        },
    }

    def _fingerprint(rec):
        """Build a stable, type-aware fingerprint for dedupe."""
        dtype = int(rec.get('dmitype', -1))
        ignore = IGNORE_BY_TYPE.get(dtype, set())
        base = (_normalize(rec.get('dminame', '')), dtype)

        # normalize all fields except ignored + meta
        items = []
        for k in sorted(rec.keys()):
            if k in ('dminame', 'dmitype', 'dmisize'):
                continue
            if k in ignore:
                continue
            v = rec[k]
            # Multi-line blocks were joined with tabs; normalize them
            items.append((k, _normalize(v)))
        return base + tuple(items)

    # --- parse loop ----------------------------------------------------------
    for record in output.split('\n\n'):
        record_element = record.splitlines()
        if len(record_element) < 3:
            continue

        handle_data = HANDLE_RE.findall(record_element[0])
        if not handle_data:
            continue

        dmi_handle = handle_data[0]  # ('0x0004','4','42')
        current = {
            'dminame': record_element[1],
            'dmisize': int(dmi_handle[2]),
            'dmitype': int(dmi_handle[1]),
        }

        in_block_element = None
        in_block_list = []

        for line in record_element[2:]:
            if in_block_element is not None:
                in_block_data = IN_BLOCK_RE.findall(line)
                if in_block_data:
                    in_block_list.append(in_block_data[0][0])
                    current[in_block_element] = '\t\t'.join(in_block_list)
                    continue
                else:
                    in_block_element = None
                    in_block_list = []

            record_data = RECORD_RE.findall(line)
            if record_data:
                key, value = record_data[0]
                current[key] = value
                continue

            record_data2 = RECORD2_RE.findall(line)
            if record_data2:
                in_block_element = record_data2[0][0]
                in_block_list = []

        # Type-specific filters (drop obviously irrelevant entries)
        dtype = int(current.get('dmitype', -1))
        if dtype == 4:
            # keep only populated/enabled when reported
            status = _lower(current.get('Status'))
            if status and not ('populated' in status and 'enabled' in status):
                continue
        if dtype == 17:
            if _drop_unpopulated_type17(current):
                continue

        # Build type-aware fingerprint and aggregate
        fp = _fingerprint(current)
        if fp not in seen:
            # first occurrence becomes the representative
            # attach dedupe metadata containers up-front (lazy-friendly)
            rep = dict(current)
            rep['dedup_count'] = 1
            rep['dedup_handles'] = [dmi_handle[0]]
            # capture socket/slot labels if present for admin visibility
            if dtype == 4 and 'Socket Designation' in current:
                rep['dedup_sockets'] = [current['Socket Designation']]
            if dtype == 17:
                labels = []
                for k in ('Locator', 'Device Locator', 'Bank Locator'):
                    if current.get(k):
                        labels.append(current[k])
                if labels:
                    rep['dedup_slots'] = sorted({*labels})
            seen[fp] = (dmi_handle, rep)
            data[dmi_handle] = rep
        else:
            first_handle, rep = seen[fp]
            rep['dedup_count'] = int(rep.get('dedup_count', 1)) + 1
            rep['dedup_handles'].append(dmi_handle[0])
            # enrich socket/slot lists
            if dtype == 4 and current.get('Socket Designation'):
                sockets = set(rep.get('dedup_sockets', []))
                sockets.add(current['Socket Designation'])
                rep['dedup_sockets'] = sorted(sockets)
            if dtype == 17:
                slots = set(rep.get('dedup_slots', []))
                for k in ('Locator', 'Device Locator', 'Bank Locator'):
                    if current.get(k):
                        slots.add(current[k])
                if slots:
                    rep['dedup_slots'] = sorted(slots)

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
