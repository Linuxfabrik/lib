#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Functions to convert raw numbers, times etc. to a human readable representation (and sometimes
   back).
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025121201'

import math

# Pre-computed thresholds for bits2human (descending order)
_BITS_THRESHOLDS = (
    ('YiB', 9671406556917033397649408),
    ('ZiB', 9444732965739290427392),
    ('EiB', 9223372036854775808),
    ('PiB', 9007199254740992),
    ('TiB', 8796093022208),
    ('GiB', 8589934592),
    ('MiB', 8388608),
    ('KiB', 8192),
    ('B', 8),
)

# Pre-computed thresholds for bps2human (descending order)
_BPS_THRESHOLDS = (
    ('Ybps', 1000000000000000000000000),
    ('Zbps', 1000000000000000000000),
    ('Ebps', 1000000000000000000),
    ('Pbps', 1000000000000000),
    ('Tbps', 1000000000000),
    ('Gbps', 1000000000),
    ('Mbps', 1000000),
    ('Kbps', 1000),
    ('bps', 1),
)

# Pre-computed thresholds for bytes2human (descending order)
_BYTES_THRESHOLDS = (
    ('YiB', 1208925819614629174706176),
    ('ZiB', 1180591620717411303424),
    ('EiB', 1152921504606846976),
    ('PiB', 1125899906842624),
    ('TiB', 1099511627776),
    ('GiB', 1073741824),
    ('MiB', 1048576),
    ('KiB', 1024),
    ('B', 1),
)

# Pre-computed multipliers for human2bytes (binary units always 1024-based)
_BINARY_MULTIPLIERS = (
    ('yib', 1208925819614629174706176),
    ('zib', 1180591620717411303424),
    ('eib', 1152921504606846976),
    ('pib', 1125899906842624),
    ('tib', 1099511627776),
    ('gib', 1073741824),
    ('mib', 1048576),
    ('kib', 1024),
)

# Pre-computed multipliers for human2bytes (decimal, base 1024)
_DECIMAL_1024_MULTIPLIERS = (
    ('yb', 1208925819614629174706176),
    ('y', 1208925819614629174706176),
    ('zb', 1180591620717411303424),
    ('z', 1180591620717411303424),
    ('eb', 1152921504606846976),
    ('e', 1152921504606846976),
    ('pb', 1125899906842624),
    ('p', 1125899906842624),
    ('tb', 1099511627776),
    ('t', 1099511627776),
    ('gb', 1073741824),
    ('g', 1073741824),
    ('mb', 1048576),
    ('m', 1048576),
    ('kb', 1024),
    ('k', 1024),
)

# Pre-computed multipliers for human2bytes (decimal, base 1000)
_DECIMAL_1000_MULTIPLIERS = (
    ('yb', 1000000000000000000000000),
    ('y', 1000000000000000000000000),
    ('zb', 1000000000000000000000),
    ('z', 1000000000000000000000),
    ('eb', 1000000000000000000),
    ('e', 1000000000000000000),
    ('pb', 1000000000000000),
    ('p', 1000000000000000),
    ('tb', 1000000000000),
    ('t', 1000000000000),
    ('gb', 1000000000),
    ('g', 1000000000),
    ('mb', 1000000),
    ('m', 1000000),
    ('kb', 1000),
    ('k', 1000),
)

# Pre-computed unit to seconds mapping for human2seconds
_UNIT_TO_SECONDS = {
    's': 1,
    'm': 60,
    'h': 3600,
    'D': 86400,
    'W': 604800,
    'M': 2592000,
    'Y': 31536000,
}

# Pre-computed SI prefixes for number2human
_SI_PREFIXES = ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
_SI_PREFIXES_MAX_IDX = 8  # len(_SI_PREFIXES) - 1

# Pre-computed time units for seconds2human (full names)
_TIME_UNITS_FULL = (
    ('years', 31536000),
    ('months', 2592000),
    ('weeks', 604800),
    ('days', 86400),
    ('hours', 3600),
    ('minutes', 60),
    ('seconds', 1),
    ('millisecs', 1e-3),
    ('microsecs', 1e-6),
    ('nanosecs', 1e-9),
    ('picosecs', 1e-12),
)

# Pre-computed time units for seconds2human (short names)
_TIME_UNITS_SHORT = (
    ('Y', 31536000),
    ('M', 2592000),
    ('W', 604800),
    ('D', 86400),
    ('h', 3600),
    ('m', 60),
    ('s', 1),
    ('ms', 1e-3),
    ('us', 1e-6),
    ('ns', 1e-9),
    ('ps', 1e-12),
)


def bits2human(n, decimals=1, space=False):
    """
    Converts a given number of bits to a human-readable string, with f-string formatting.

    ### Parameters
    - **n** (`int` or `float`): The number of bits to convert.
    - **decimals** (`int`, optional): Number of decimal places. Defaults to 1.
    - **space** (`bool`, optional): If True, adds a space between the value and unit.
      Defaults to False.

    ### Returns
    - **str**: A string like '1.0KiB' or '1.0 KiB'.

    ### Example
    >>> bits2human(8192)
    '1.0KiB'

    >>> bits2human(8192, decimals=2)
    '1.00KiB'

    >>> bits2human(8192, space=True)
    '1.0 KiB'

    >>> bits2human(8192, decimals=3, space=True)
    '1.000 KiB'
    """
    sep = ' ' if space else ''

    for symbol, threshold in _BITS_THRESHOLDS:
        if n >= threshold:
            value = float(n) / threshold
            return f'{value:.{decimals}f}{sep}{symbol}'

    return f'{n:.{decimals}f}{sep}B'


def bps2human(n, decimals=1, space=False):
    """
    Converts a given number of bits per second to a human-readable format (e.g., bps, Kbps, Mbps,
    etc.).

    This function takes an integer number of bits per second and converts it to a more readable
    format, using appropriate units like bits per second, kilobits per second, megabits per second,
    etc., depending on the size of the input.

    ### Parameters
    - **n** (`int` or `float`): The number of bits per second to convert.
    - **decimals** (`int`, optional): Number of decimal places. Defaults to 1.
    - **space** (`bool`, optional): If True, adds a space between the value and unit. Defaults to False.

    ### Returns
    - **str**: The human-readable representation of the input bits per second with the appropriate
      unit (e.g., '72Mbps').

    ### Example
    >>> bps2human(72000000)
    '72.0Mbps'

    >>> bps2human(72000000, decimals=0)
    '72Mbps'

    >>> bps2human(72000000, decimals=2, space=True)
    '72.00 Mbps'
    """
    sep = ' ' if space else ''

    for symbol, threshold in _BPS_THRESHOLDS:
        if n >= threshold:
            value = float(n) / threshold
            return f'{value:.{decimals}f}{sep}{symbol}'

    return f'{n:.{decimals}f}{sep}bps'


def bytes2human(n, decimals=1, space=False):
    """
    Converts a given number of bytes to a human-readable format (e.g., B, KiB, MiB, etc.).

    This function converts an integer number of bytes into a more readable format, using
    appropriate units such as bytes, kilobytes, megabytes, gigabytes, etc., depending on the size
    of the input.

    ### Parameters
    - **n** (`int` or `float`): The number of bytes to convert.
    - **decimals** (`int`, optional): Number of decimal places. Defaults to 1.
    - **space** (`bool`, optional): Whether to add a space between value and unit.
      Defaults to False.

    ### Returns
    - **str**: The human-readable representation of the input bytes with the appropriate unit
      (e.g., '1.0KiB').

    ### Example
    >>> bytes2human(1023)
    '1023.0B'

    >>> bytes2human(1024)
    '1.0KiB'

    >>> bytes2human(1536, decimals=2)
    '1.50KiB'

    >>> bytes2human(1048576, decimals=1, space=True)
    '1.0 MiB'
    """
    sep = ' ' if space else ''

    for symbol, threshold in _BYTES_THRESHOLDS:
        if n >= threshold:
            value = float(n) / threshold
            return f'{value:.{decimals}f}{sep}{symbol}'

    return f'{n:.{decimals}f}{sep}B'


def extract_hrnumbers(s, boundaries=None):
    """
    Extracts all numbers from a string that start with a digit and end with a known boundary.

    This function scans the input string and extracts substrings that start with a digit and end
    with a known boundary character (such as 's', 'm', 'h', etc.), and returns these substrings
    as a list.

    ### Parameters
    - **s** (`str`): The input string to extract numbers from.
    - **boundaries** (`list`, optional): A list of boundary characters that signify the end of
      a number. Defaults to ['s', 'm', 'h', 'D', 'W', 'M', 'Y'].

    ### Returns
    - **list**: A list of strings representing the extracted numbers along with their boundaries.

    ### Example
    >>> string = '31Y 20M7s  88  abc12xyz   4s 5'
    >>> extract_hrnumbers(string)
    ['31Y', '20M', '7s', '4s']

    >>> string = '17G 3M 4B'
    >>> extract_hrnumbers(string, boundaries=['G', 'M', 'B'])
    ['17G', '3M', '4B']
    """
    if boundaries is None:
        boundaries = ['s', 'm', 'h', 'D', 'W', 'M', 'Y']

    extracted = []
    start_idx = None

    for idx, char in enumerate(s):
        if char.isdigit() and start_idx is None:
            start_idx = idx
        elif char in boundaries and start_idx is not None:
            extracted.append(s[start_idx:idx + 1])
            start_idx = None
        elif not char.isdigit():
            start_idx = None

    return extracted


def human2bytes(string, binary=True):
    """
    Converts a human-readable string to the equivalent number of bytes.

    This function converts a string representation of a file size, such as '3.072GiB' or '3.072GB',
    into the corresponding number of bytes. It supports both binary (base 1024) and decimal
    (base 1000) units.

    ### Parameters
    - **string** (`str`): A string representing the size to convert. It can include any of the
      common size units like 'GiB', 'GB', 'MB', 'kB', etc.
    - **binary** (`bool`, optional): If True (default), the function will use binary units
      (base 1024). If False, it will use decimal units (base 1000).

    ### Returns
    - **int**: The equivalent size in bytes, or 0 if the conversion fails.

    ### Example
    >>> human2bytes('3.072GiB')
    3298534883

    >>> human2bytes('3.072G', binary=False)
    3072000000
    """
    try:
        string_lower = string.lower()

        # Check binary units first (always 1024-based)
        for unit, multiplier in _BINARY_MULTIPLIERS:
            if unit in string_lower:
                return int(float(string_lower.replace(unit, '').strip()) * multiplier)

        # Check decimal units (base depends on binary parameter)
        multipliers = _DECIMAL_1024_MULTIPLIERS if binary else _DECIMAL_1000_MULTIPLIERS
        for unit, multiplier in multipliers:
            if unit in string_lower:
                return int(float(string_lower.replace(unit, '').strip()) * multiplier)

        # Check for plain 'b' (bytes)
        if 'b' in string_lower:
            return int(float(string_lower.replace('b', '').strip()))

        return 0
    except Exception:
        return 0


def human2seconds(string):
    """
    Converts a human-readable duration into seconds.

    This function converts durations given in a human-readable format (e.g., '2.5h', '26Y')
    into the corresponding number of seconds. The units supported are: years (Y), months (M),
    weeks (W), days (D), hours (h), minutes (m), and seconds (s).

    ### Parameters
    - **string** (`str`): A string representing the duration. It should include a numeric
      value followed by one of the supported units ('Y', 'M', 'W', 'D', 'h', 'm', or 's').

    ### Returns
    - **int**: The equivalent duration in seconds, rounded down to the nearest integer.
      Returns 0 if invalid.

    ### Example
    >>> human2seconds('26Y')
    819936000

    >>> human2seconds('26M')
    62899200

    >>> human2seconds('26W')
    15724800

    >>> human2seconds('26D')
    2246400

    >>> human2seconds('26h')
    93600

    >>> human2seconds('26m')
    1560

    >>> human2seconds('26s')
    26

    >>> human2seconds('1.5W')
    907200

    >>> lib.human.human2seconds('0.5D')
    43200

    >>> human2seconds('2.5h')
    9000

    >>> human2seconds('a7.3X')
    0

    >>> human2seconds('invalid')
    0
    """
    string = string.strip()
    if not string or len(string) < 2:
        return 0

    unit = string[-1]
    value_str = string[:-1]

    if unit not in _UNIT_TO_SECONDS:
        return 0

    try:
        value = float(value_str)
    except (ValueError, TypeError):
        return 0

    return int(value * _UNIT_TO_SECONDS[unit])


def humanduration2seconds(text):
    """
    Converts a complex human-readable duration string into seconds by summing individual durations.

    This function processes a string that may contain multiple duration components
    (e.g., '3Y 2M 7s') and converts each component into seconds. It ignores non-valid components
    (e.g., 'any-error') and sums the valid ones.

    ### Parameters
    - **text** (`str`): A string containing one or more human-readable durations, where each
      duration is represented by a number followed by a unit (e.g., '3Y', '2M', '7s').
      Invalid components are ignored.

    ### Returns
    - **int**: The total duration in seconds, summing all valid duration components. Returns 0 if
      no valid components are found.

    ### Example
    >>> text = '3Y 2M any-error 3d7s'  # means: valid is '3Y 2M 7s'
    >>> humanduration2seconds(text)
    99792007
    """
    return sum(human2seconds(duration) for duration in extract_hrnumbers(text))


def humanrange2bytes(text):
    """
    Converts a Nagios range (e.g., `@4K:5 MiB`) into a range in bytes, where the base is always
    1024.

    This function processes a Nagios-style range string that may contain units such as 'K', 'M',
    'B', etc., and converts each part into bytes using the `human2bytes` function. The result is
    a string with the range values expressed in bytes.

    ### Parameters
    - **text** (`str`): A Nagios-style range string, such as '@4K:5 MiB', where units like K, M,
      or B are used.

    ### Returns
    - **str**: The range with each value converted into bytes, using 1024 as the base for 
      conversions.

    ### Example
    >>> text = '@4K:5 MiB'
    >>> humanrange2bytes(text)
    '@4096:5242880'
    """
    parts = []
    for part in text.split(':'):
        if not part:
            continue
        size = part.replace('-', '').replace('~', '').replace('@', '')
        size_bytes = human2bytes(size)
        parts.append(part.replace(size, str(size_bytes)))

    result = ':'.join(parts)
    if text.startswith(':'):
        result = ':' + result
    if text.endswith(':'):
        result += ':'
    return result


def humanrange2seconds(string):
    """
    Converts a Nagios range to seconds by interpreting the duration components and summing them.

    This function processes a Nagios-style range string (e.g., `@10m:1Y1D`) and converts each part
    into seconds using the `humanduration2seconds` function. The result is a string with the range
    values expressed in seconds.

    ### Parameters
    - **string** (`str`): A Nagios-style range string, such as '@10m:1Y1D', where units like 'm',
      'Y', 'D' are used.

    ### Returns
    - **str**: The range with each value converted into seconds.

    ### Example
    >>> string = '@10m:1Y1D'
    >>> humanrange2seconds(string)
    '@600:31622400'
    """
    result = []
    for part in string.split(':'):
        if not part:
            continue
        duration = part.replace('-', '').replace('~', '').replace('@', '')
        seconds = humanduration2seconds(duration)
        result.append(part.replace(duration, f'{seconds}'))

    if string.startswith(':'):
        return ':' + ':'.join(result)
    if string.endswith(':'):
        return ':'.join(result) + ':'
    return ':'.join(result)


def number2human(number):
    """
    Converts a number into a human-readable format using SI prefixes.

    This function converts large numbers into a more concise format with SI prefixes
    (e.g., 1,000 becomes '1K', 1,000,000 becomes '1M'). It supports values from 1 to extremely large
    numbers (up to 'Y' for 10^24).

    ### Parameters
    - **number** (`int` or `float`): The number to convert into a human-readable format.

    ### Returns
    - **str**: The number formatted with an appropriate SI prefix.

    ### Example
    >>> number2human(123456.8)
    '123.5K'

    >>> number2human(123456789.0)
    '123.5M'

    >>> number2human(9223372036854775808)
    '9.2E'
    """
    try:
        number = float(number)
    except Exception:
        return number

    if number == 0:
        millidx = 0
    else:
        millidx = int(math.floor(math.log10(abs(number)) / 3))

    millidx = max(0, min(_SI_PREFIXES_MAX_IDX, millidx))
    scaled = number / 10**(3 * millidx)
    return f'{scaled:.1f}{_SI_PREFIXES[millidx]}'


def seconds2human(seconds, keep_short=True, full_name=False):
    """
    Converts a number of seconds into a human-readable time range string.

    This function takes a number of seconds and returns a string that expresses that duration in
    a more understandable format. It supports both short and full-form time units (e.g., "1m" for
    minutes, "1 hour 30 minutes" for the full form).

    ### Parameters
    - **seconds** (`int` or `float` or `str`): The number of seconds to convert.
    - **keep_short** (`bool`, optional): If True, returns only the largest two time units
      (default is True).
    - **full_name** (`bool`, optional): If True, returns full names for the time units
      (default is False).

    ### Returns
    - **str**: The formatted time duration in a human-readable format.

    ### Example
    >>> seconds2human(0.125)
    '0.12s'

    >>> seconds2human(1)
    '1s'

    >>> seconds2human(59)
    '59s'

    >>> seconds2human(60)
    '1m'

    >>> seconds2human(61)
    '1m 1s'

    >>> seconds2human(1387775)
    '2W 2D'

    >>> seconds2human('1387775')
    '2W 2D'

    >>> seconds2human('1387775', full_name=True)
    '2weeks 2days'

    >>> seconds2human(1387775, keep_short=False, full_name=True)
    '2weeks 2days 1hour 29minutes 35seconds'
    """
    seconds = float(seconds)

    units = _TIME_UNITS_FULL if full_name else _TIME_UNITS_SHORT

    result = []
    for name, count in units:
        value = seconds // count
        if value:
            seconds -= value * count
            if full_name and value == 1:
                name = name.rstrip('s')
            result.append(f'{int(value)}{name}')

    if keep_short and len(result) > 2:
        return ' '.join(result[:2])
    return ' '.join(result)
