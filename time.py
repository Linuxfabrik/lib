#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides datetime functions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

import datetime
import time


def epoch2iso(timestamp):
    """Returns the ISO representaton of a UNIX timestamp (epoch).

    >>> epoch2iso(1620459129)
    '2021-05-08 09:32:09'
    """
    timestamp = float(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


def now(as_type=''):
    """Returns the current date and time as UNIX time in seconds (default), or
    as a datetime object.

    lib.base.now()
    >>> 1586422786

    lib.base.now(as_type='float')
    >>> 1586422786.1521912

    lib.base.now(as_type='epoch')
    >>> 1586422786

    lib.base.now(as_type='datetime')
    >>> datetime.datetime(2020, 4, 9, 11, 1, 41, 228752)

    lib.base.now(as_type='iso')
    >>> '2020-04-09 11:31:24'
    """
    if as_type == 'datetime':
        return datetime.datetime.now()
    if as_type == 'iso':
        return time.strftime("%Y-%m-%d %H:%M:%S")
    if as_type == 'float':
        return time.time()
    return int(time.time())


def timestr2datetime(timestr, pattern='%Y-%m-%d %H:%M:%S'):
    """Takes a string (default: ISO format) and returns a
    datetime object.
    https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    """
    return datetime.datetime.strptime(timestr, pattern)


def timestrdiff(timestr1, timestr2, pattern1='%Y-%m-%d %H:%M:%S', pattern2='%Y-%m-%d %H:%M:%S'):
    """Returns the difference between two datetime strings in seconds. This
    function expects two ISO timestamps, by default each in ISO format.
    https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    """
    timestr1 = timestr2datetime(timestr1, pattern1)
    timestr2 = timestr2datetime(timestr2, pattern2)
    timedelta = abs(timestr1 - timestr2)
    return timedelta.total_seconds()


def utc_offset():
    """Returns the current local UTC offset, for example '+0200'.

    utc_offset()
    >>> '+0200'
    """
    return time.strftime("%z")
