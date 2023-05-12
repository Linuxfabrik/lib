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
__version__ = '2023051201'

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

        if 'k' in string:  # matches "kb" or "k"
            string = string.replace('kb', '').replace('k', '').strip()
            if binary:
                return int(float(string) * 1024)
            return int(float(string) * 1000)
        if 'm' in string:  # matches "mb" or "m"
            string = string.replace('mb', '').replace('m', '').strip()
            if binary:
                return int(float(string) * 1024**2)
            return int(float(string) * 1000**2)
        if 'g' in string:  # matches "gb" or "g"
            string = string.replace('gb', '').replace('g', '').strip()
            if binary:
                return int(float(string) * 1024**3)
            return int(float(string) * 1000**3)
        if 't' in string:  # matches "tb" or "t"
            string = string.replace('tb', '').replace('t', '').strip()
            if binary:
                return int(float(string) * 1024**4)
            return int(float(string) * 1000**4)
        if 'p' in string:  # matches "pb" or "p"
            string = string.replace('pb', '').replace('p', '').strip()
            if binary:
                return int(float(string) * 1024**5)
            return int(float(string) * 1000**5)
        if 'b' in string:
            return int(float(string.replace('b', '').strip()))
        return 0
    except:
        return 0


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
