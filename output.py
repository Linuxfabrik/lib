#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://nagios-plugins.org/doc/guidelines.html

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020040101'

from .globals import *

import math


def unpack_perfdata(label, value, uom, warn, crit, min, max):
    msg = label + '=' + str(value)
    if uom is not None:
        msg += uom
    msg += ';'
    if warn is not None:
        msg += str(warn)
    msg += ';'
    if crit is not None:
        msg += str(crit)
    msg += ';'
    if min is not None:
        msg += str(min)
    msg += ';'
    if max is not None:
        msg += str(max)
    msg += '; '
    return msg


def bytes2human(n, format="%(value).1f%(symbol)s"):
    """Used by various scripts. See:
    https://github.com/giampaolo/psutil/blob/master/psutil/_common.py
    http://goo.gl/zeJZl

    >>> bytes2human(10000)
    '9.8K'
    >>> bytes2human(100001221)
    '95.4M'
    """
    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)


def number2human(n):
    """
    >>> number2human(123456.8)
    '123K'
    >>> number2human(123456789.0)
    '123 Mill.'
    """
    millnames = ['', 'K', ' Mill.', ' Bill.', ' Trill.']
    n = float(n)
    millidx = max(0, min(len(millnames) - 1,
                        int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))
    return '{:.1f}{}'.format(n / 10**(3 * millidx), millnames[millidx])


def unix_time_to_iso(timestamp):
    import datetime

    timestamp = float(timestamp)
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def seconds2human(seconds, full_name=False):
    seconds = int(seconds)
    if full_name:
        intervals = (
            ('weeks', 604800),  # 60 * 60 * 24 * 7
            ('days', 86400),    # 60 * 60 * 24
            ('hours', 3600),    # 60 * 60
            ('minutes', 60),
            ('seconds', 1),
    )
    else:
        intervals = (
            ('w', 604800),      # 60 * 60 * 24 * 7
            ('d', 86400),       # 60 * 60 * 24
            ('h', 3600),        # 60 * 60
            ('m', 60),
            ('s', 1),
    )

    result = []

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if full_name and value == 1:
                name = name.rstrip('s') # "days" becomes "day"
            result.append('{:.0f}{}'.format(value, name))
    return ' '.join(result)


# inspired by https://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/
def format_as_table(data,
                    keys,
                    header=None,
                    sort_by_key=None,
                    sort_order_reverse=False):
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        keys - List of keys in the dictionary. (Type: List)

    Optional Parameters:
        header - The table header. (Type: List)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: Boolean)
    """
    from operator import itemgetter
    from collections import OrderedDict

    if not data:
        return ''

    # Sort the data if a sort key is specified (default sort order
    # is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, add header to data
    if header:
        # Get the length of each header and create a divider based
        # on that length
        header_divider = []
        for name in header:
            header_divider.append('-' * len(name))

        # Create a list of dictionary from the keys and the header and
        # insert it at the beginning of the list. Do the same for the
        # divider and insert below the header.
        header_divider = dict(zip(keys, header_divider))
        data.insert(0, header_divider)
        header = dict(zip(keys, header))
        data.insert(0, header)

    column_widths = OrderedDict()
    for key in keys:
        column_widths[key] = max(len(str(column[key])) for column in data)

    table = ''
    for element in data:
        for key, width in column_widths.items():
            table += '{:<{}} '.format(element[key], width)
        table += '\n'

    return table


def state_to_string(state, return_ok=False):
    if state == STATE_CRIT:
        return 'CRIT'
    if state == STATE_WARN:
        return 'WARN'
    if state == STATE_OK:
        if return_ok:
            return 'OK'
        else:
            return ''
    if state == STATE_UNKNOWN:
        return 'UNKNOWN'

    return state
