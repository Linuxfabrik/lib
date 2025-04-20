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
__version__ = '2025042001'

import math


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
    symbols = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    prefix = {'B': 8}
    for i, symbol in enumerate(symbols[1:], 1):
        prefix[symbol] = 1024 ** i * 8

    for symbol in reversed(symbols):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            sep = ' ' if space else ''
            return f'{value:.{decimals}f}{sep}{symbol}'

    sep = ' ' if space else ''
    return f'{n:.{decimals}f}{sep}{symbols[0]}'


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
    symbols = ('bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps', 'Pbps', 'Ebps', 'Zbps', 'Ybps')
    prefix = {symbol: 1000 ** i for i, symbol in enumerate(symbols)}

    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            sep = ' ' if space else ''
            return f'{value:.{decimals}f}{sep}{symbol}'

    sep = ' ' if space else ''
    return f'{n:.{decimals}f}{sep}{symbols[0]}'


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
    symbols = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    prefix = {symbol: 1 << (i + 1) * 10 for i, symbol in enumerate(symbols[1:])}

    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            sep = ' ' if space else ''
            return f'{value:.{decimals}f}{sep}{symbol}'

    sep = ' ' if space else ''
    return f'{n:.{decimals}f}{sep}{symbols[0]}'


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
        string = string.lower()
        if 'kib' in string:
            return int(float(string.replace('kib', '').strip()) * 1024)
        if 'mib' in string:
            return int(float(string.replace('mib', '').strip()) * 1024**2)
        if 'gib' in string:
            return int(float(string.replace('gib', '').strip()) * 1024**3)
        if 'tib' in string:
            return int(float(string.replace('tib', '').strip()) * 1024**4)
        if 'pib' in string:
            return int(float(string.replace('pib', '').strip()) * 1024**5)
        if 'eib' in string:
            return int(float(string.replace('eib', '').strip()) * 1024**6)
        if 'zib' in string:
            return int(float(string.replace('zib', '').strip()) * 1024**7)
        if 'yib' in string:
            return int(float(string.replace('yib', '').strip()) * 1024**8)

        base = 1024 if binary else 1000
        if 'k' in string:  # matches "kb" or "k"
            return int(float(string.replace('kb', '').replace('k', '').strip()) * base)
        if 'm' in string:
            return int(float(string.replace('mb', '').replace('m', '').strip()) * base**2)
        if 'g' in string:
            return int(float(string.replace('gb', '').replace('g', '').strip()) * base**3)
        if 't' in string:
            return int(float(string.replace('tb', '').replace('t', '').strip()) * base**4)
        if 'p' in string:
            return int(float(string.replace('pb', '').replace('p', '').strip()) * base**5)
        if 'e' in string:
            return int(float(string.replace('eb', '').replace('e', '').strip()) * base**6)
        if 'z' in string:
            return int(float(string.replace('zb', '').replace('z', '').strip()) * base**7)
        if 'y' in string:
            return int(float(string.replace('yb', '').replace('y', '').strip()) * base**8)
        if 'b' in string:
            return int(float(string.replace('b', '').strip()))
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
    unit_to_seconds = {
        's': 1,
        'm': 60,
        'h': 3600,
        'D': 86400,
        'W': 604800,
        'M': 2592000,
        'Y': 31536000,
    }

    string = string.strip()
    if not string or len(string) < 2:
        return 0

    unit = string[-1]
    value_str = string[:-1]

    if unit not in unit_to_seconds:
        return 0

    try:
        value = float(value_str)
    except (ValueError, TypeError):
        return 0

    return int(value * unit_to_seconds[unit])


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
    millnames = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
    try:
        number = float(number)
    except Exception:
        return number

    if number == 0:
        millidx = 0
    else:
        millidx = int(math.floor(math.log10(abs(number)) / 3))

    millidx = max(0, min(len(millnames) - 1, millidx))
    scaled = number / 10**(3 * millidx)
    return f'{scaled:.1f}{millnames[millidx]}'


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

    units = (
        ('years', 60 * 60 * 24 * 365),
        ('months', 60 * 60 * 24 * 30),
        ('weeks', 60 * 60 * 24 * 7),
        ('days', 60 * 60 * 24),
        ('hours', 60 * 60),
        ('minutes', 60),
        ('seconds', 1),
        ('millisecs', 1e-3),
        ('microsecs', 1e-6),
        ('nanosecs', 1e-9),
        ('picosecs', 1e-12),
    ) if full_name else (
        ('Y', 60 * 60 * 24 * 365),
        ('M', 60 * 60 * 24 * 30),
        ('W', 60 * 60 * 24 * 7),
        ('D', 60 * 60 * 24),
        ('h', 60 * 60),
        ('m', 60),
        ('s', 1),
        ('ms', 1e-3),
        ('us', 1e-6),
        ('ns', 1e-9),
        ('ps', 1e-12),
    )

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
