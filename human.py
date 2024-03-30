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
__version__ = '2024033002'

import math


def bits2human(n, _format='%(value).1f%(symbol)s'):
    """Converts n bits to a human readable format.

    >>> bits2human(8191)
    '1023.9B'
    >>> bits2human(8192)
    '1.0KiB'
    """
    symbols = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    prefix = {}
    prefix['B'] = 8
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1024**(i + 1) * 8
    for symbol in reversed(symbols):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]   # pylint: disable=W0641
            return _format % locals()
    return _format % dict(symbol=symbols[0], value=n)


def bps2human(n, _format='%(value).1f%(symbol)s'):
    """Converts n bits per scond to a human readable format.

    >>> bps2human(72000000)
    '72Mbps'
    """
    symbols = ('bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps', 'Pbps', 'Ebps', 'Zbps', 'Ybps')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1000**(i + 1)
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]   # pylint: disable=W0641
            return _format % locals()
    return _format % dict(symbol=symbols[0], value=n)


def bytes2human(n, _format='%(value).1f%(symbol)s'):
    """Converts n bytes to a human readable format.

    >>> bytes2human(1023)
    '1023.0B'
    >>> bytes2human(1024)
    '1.0KiB'

    https://github.com/giampaolo/psutil/blob/master/psutil/_common.py
    """
    symbols = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        # Returns 1 with the bits shifted to the left by (i + 1)*10 places
        # (and new bits on the right-hand-side are zeros). This is the same
        # as multiplying x by 2**y.
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]   # pylint: disable=W0641
            return _format % locals()
    return _format % dict(symbol=symbols[0], value=n)


def extract_hrnumbers(s, boundaries=['s', 'm', 'h', 'D', 'W', 'M', 'Y']):
    """Return a list of all numbers from a string, beginning with a digit and ending
    with a known boundary.

    >>> string = '31Y 20M7s  88  abc12xyz   4s 5'
    >>> extract_hrnumbers(string)
    ['31Y', '20M', '7s', '4s']
    >>> string = '17G 3M 4B'
    >>> extract_hrnumbers(string, boundaries=['G', 'M', 'B'])
    ['17G', '3M', '4B']
    """
    words = []  # List to store the extracted words
    start_index = None  # Start index of a word
    for i, char in enumerate(s):
        # Check if we're at the start of a potential word
        if char.isdigit() and start_index is None:
            start_index = i
        # Check if we're at the end of a word
        elif char in boundaries and start_index is not None:
            # Extract and append the word
            words.append(s[start_index:i+1])
            start_index = None  # Reset the start index for the next word
        # Reset start_index if current char is not a digit and we're not in a word
        elif not char.isdigit():
            start_index = None
    return words


def human2bytes(string, binary=True):
    """Converts a string such as '3.072GiB' to 3298534883 bytes. If "binary" is set to True
    (default due to Microsoft), it will use powers of 1024, otherwise powers of 1000 (decimal).
    Returns 0 on failure.

    Works with:
    * 3.072GiB (always multiplied by 1024)
    * 3.072GB  (multiplied by 1024 if binary == True, else multiplied by 1000)
    * 3.072G   (multiplied by 1024 if binary == True, else multiplied by 1000)
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

        if binary:
            base = 1024
        else:
            base = 1000
        if 'k' in string:  # matches "kb" or "k"
            string = string.replace('kb', '').replace('k', '').strip()
            return int(float(string) * base)
        if 'm' in string:  # matches "mb" or "m"
            string = string.replace('mb', '').replace('m', '').strip()
            return int(float(string) * base**2)
        if 'g' in string:  # matches "gb" or "g"
            string = string.replace('gb', '').replace('g', '').strip()
            return int(float(string) * base**3)
        if 't' in string:  # matches "tb" or "t"
            string = string.replace('tb', '').replace('t', '').strip()
            return int(float(string) * base**4)
        if 'p' in string:  # matches "pb" or "p"
            string = string.replace('pb', '').replace('p', '').strip()
            return int(float(string) * base**5)
        if 'e' in string:  # matches "eb" or "e"
            string = string.replace('eb', '').replace('e', '').strip()
            return int(float(string) * base**6)
        if 'z' in string:  # matches "zb" or "z"
            string = string.replace('zb', '').replace('z', '').strip()
            return int(float(string) * base**7)
        if 'y' in string:  # matches "yb" or "y"
            string = string.replace('yb', '').replace('y', '').strip()
            return int(float(string) * base**8)
        if 'b' in string:
            return int(float(string.replace('b', '').strip()))
        return 0
    except:
        return 0


def human2seconds(string):
    """Converts a simple human-readable duration into seconds.

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
    >>> human2seconds('a7.3X')
    0
    """
    unit_to_seconds = {
        's': 1,
        'm': 60,
        'h': 60*60,
        'D': 24*60*60,
        'W': 7*24*60*60,
        'M': 30*24*60*60,  # Assuming exactly 30 days
        'Y': 365*24*60*60,  # Assuming 365 days in a year
    }

    # Extract the numeric part and the unit from the input string
    unit = string[-1]
    try:
        value = int(string.replace(unit, ''))
    except:
        return 0

    # Check if the unit is valid
    if unit not in unit_to_seconds:
        return 0

    # Convert the duration to seconds
    return value * unit_to_seconds[unit]


def humanduration2seconds(string):
    """Converts a more complex string into seconds by summing the individual words.

    >>> string = '3Y 2M any-error 3d7s'  # means: valid is '3Y 2M 7s'
    >>> humanduration2seconds(string)
    99446407
    """
    durations = extract_hrnumbers(string)
    seconds = 0
    for duration in durations:
        seconds += human2seconds(duration)
    return seconds


def humanrange2bytes(string):
    """Converts a Nagios range to bytes. Base is always 1024.

    >>> string = '@4K:5 MiB'
    >>> humanrange2bytes(string)
    @4096:5242880
    """
    result = []
    for s in string.split(':'):
        if not s:
            continue
        size = s.replace('-', '').replace('~', '').replace('@', '')
        result.append(s.replace(size, str(human2bytes(size))))
    if string.startswith(':'):
        return ':' + ':'.join(result)
    if string.endswith(':'):
        return ':'.join(result) + ':'
    return ':'.join(result)


def humanrange2seconds(string):
    """Converts a Nagios range to seconds.

    >>> string = '@10m:1Y1D'
    >>> humanrange2seconds(string)
    @600:31622400
    """
    result = []
    for s in string.split(':'):
        if not s:
            continue
        duration = s.replace('-', '').replace('~', '').replace('@', '')
        result.append(s.replace(duration, str(humanduration2seconds(duration))))
    if string.startswith(':'):
        return ':' + ':'.join(result)
    if string.endswith(':'):
        return ':'.join(result) + ':'
    return ':'.join(result)


def number2human(n):
    """
    >>> number2human(123456.8)
    '123K'
    >>> number2human(123456789.0)
    '123M'
    >>> number2human(9223372036854775808)
    '9.2E'
    """
    # according to the SI Symbols at
    # https://en.wikipedia.org/w/index.php?title=Names_of_large_numbers&section=5#Extensions_of_the_standard_dictionary_numbers
    millnames = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
    try:
        n = float(n)
    except:
        return n
    millidx = max(0, min(len(millnames) - 1,
                         int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))
    return '{:.1f}{}'.format(n / 10**(3 * millidx), millnames[millidx])


def seconds2human(seconds, keep_short=True, full_name=False):
    """Returns a human readable time range string for a number of seconds.

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

    if full_name:
        symbols = (
            ('years', 60*60*24*365),
            ('months', 60*60*24*30),
            ('weeks', 60*60*24*7),
            ('days', 60*60*24),
            ('hours', 60*60),
            ('minutes', 60),
            ('seconds', 1),
            ('millisecs', 1e-3),
            ('microsecs', 1e-6),
            ('nanosecs', 1e-9),
            ('picosecs', 1e-12),
        )
    else:
        symbols = (
            ('Y', 60*60*24*365),
            ('M', 60*60*24*30),
            ('W', 60*60*24*7),
            ('D', 60*60*24),
            ('h', 60*60),
            ('m', 60),
            ('s', 1),
            ('ms', 1e-3),
            ('us', 1e-6),
            ('ns', 1e-9),
            ('ps', 1e-12),
        )

    result = []
    for name, count in symbols:
        value = seconds // count
        if value:
            seconds -= value * count
            if full_name and value == 1:
                name = name.rstrip('s') # "days" becomes "day"
            result.append('{:.0f}{}'.format(value, name))

    if len(result) > 2 and keep_short:
        return ' '.join(result[:2])
    return ' '.join(result)
