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
__version__ = '2025052801'

import datetime
import sys
import time
if sys.version_info >= (3, 9):
    import zoneinfo  # available in python 3.9+


def epoch2iso(timestamp):
    """
    Converts a UNIX epoch timestamp to an ISO-formatted date and time string.

    This function takes a UNIX timestamp (int or float) and returns a string representing the local
    time in ISO 8601 format (YYYY-MM-DD HH:MM:SS).

    ### Parameters
    - **timestamp** (`int` or `float`): UNIX epoch timestamp (seconds since 1970-01-01).

    ### Returns
    - **str**: Local date and time in ISO 8601 format.

    ### Example
    >>> epoch2iso(1620459129)
    '2021-05-08 09:32:09'
    """
    try:
        ts = float(timestamp)
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
    except (TypeError, ValueError):
        return ''


def get_timezone(tz_name):
    """
    Load an IANA time-zone by name and return a ZoneInfo object, defaulting to UTC if invalid.

    This function takes an IANA time-zone name (str) and returns the corresponding
    zoneinfo.ZoneInfo object. If loading fails, UTC ("Etc/UTC") is returned.

    ### Parameters
    - **tz_name** (`str`): IANA time-zone identifier (e.g. "Europe/London").

    ### Returns
    - **ZoneInfo**: A `zoneinfo.ZoneInfo` object for the requested zone, or UTC if not found.

    ### Example
    >>> get_timezone("Europe/London").key
    'Europe/London'
    >>> get_timezone("Invalid/Zone").key
    'Etc/UTC'
    """
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        # Fallback to UTC if the name isn't found
        try:
            return zoneinfo.ZoneInfo('Etc/UTC')
        except Exception:
            # Python < 3.9
            return datetime.timezone.utc


def now(as_type=''):
    """
    Returns the current date and time in various formats.

    Depending on `as_type`, this returns:
    - Integer UNIX epoch (default)
    - Floating-point UNIX epoch ('float')
    - datetime.datetime object ('datetime')
    - ISO string 'YYYY-MM-DD HH:MM:SS' ('iso')

    ### Parameters
    - **as_type** (`str`, optional):
      '', 'epoch', 'float', 'datetime', or 'iso'. Defaults to ''.

    ### Returns
    - **int**, **float**, **datetime.datetime**, or **str**: Current time in the requested format.

    ### Example
    >>> now()
    1586422786
    >>> now(as_type='float')
    1586422786.1521912
    >>> now(as_type='datetime')
    datetime.datetime(2020, 4, 9, 11, 1, 41, 228752)
    >>> now(as_type='iso')
    '2020-04-09 11:31:24'
    """
    if as_type == 'datetime':
        return datetime.datetime.now()
    if as_type == 'iso':
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if as_type == 'float':
        return time.time()
    return int(time.time())


def timestr2datetime(timestr, pattern='%Y-%m-%d %H:%M:%S'):
    """
    Converts a time string into a datetime object using the specified format.

    This function parses a string representing a date and time into a `datetime.datetime`
    object based on the provided format pattern. The default format is ISO (YYYY-MM-DD HH:MM:SS).

    ### Parameters
    - **timestr** (`str`): A string representing the date and time.
    - **pattern** (`str`, optional): The format string corresponding to the structure of `timestr`.  
      Defaults to '%Y-%m-%d %H:%M:%S'. For more details on format codes, see:  
      https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

    ### Returns
    - **datetime.datetime**: A datetime object corresponding to the parsed date and time.

    ### Example
    >>> timestr2datetime("2021-05-08 09:32:09")
    datetime.datetime(2021, 5, 8, 9, 32, 9)
    """
    return datetime.datetime.strptime(timestr, pattern)


def timestr2epoch(timestr, pattern='%Y-%m-%d %H:%M:%S', tzinfo=None):
    """
    Converts a time string to a UNIX epoch timestamp.

    ### Parameters
    - **timestr** (`str`): The time string to convert.
    - **pattern** (`str`): The format of the time string (default is '%Y-%m-%d %H:%M:%S').
    - **tzinfo** (`datetime.tzinfo`, optional): Timezone information.  
      If provided, the parsed datetime is set to this timezone.  
      If None, the time is assumed to be local time.

    ### Returns
    - **float**: The UNIX epoch timestamp (seconds since January 1, 1970, 00:00:00 UTC).

    ### Raises
    - **ValueError**: If the time string does not match the provided format.

    ### Example
        # Convert a time string in local time:
        epoch_local = timestr2epoch("2025-03-01 12:00:00")

        # Convert a time string assuming it's in UTC:
        epoch_utc = timestr2epoch("2025-03-01 12:00:00", tzinfo=datetime.timezone.utc)
    """
    dt = datetime.datetime.strptime(timestr, pattern)

    # If a timezone is provided, make the datetime timezone-aware.
    if tzinfo is not None:
        dt = dt.replace(tzinfo=tzinfo)

    return dt.timestamp()


def timestrdiff(timestr1, timestr2, pattern1='%Y-%m-%d %H:%M:%S', pattern2='%Y-%m-%d %H:%M:%S'):
    """
    Computes the absolute difference in seconds between two datetime strings.

    This function converts two datetime strings into `datetime.datetime` objects using
    their respective format patterns, then calculates the absolute time difference between them.
    By default, both strings are expected to be in ISO format (YYYY-MM-DD HH:MM:SS).

    ### Parameters
    - **timestr1** (`str`): The first datetime string.
    - **timestr2** (`str`): The second datetime string.
    - **pattern1** (`str`, optional): The format pattern for `timestr1`. Defaults to '%Y-%m-%d %H:%M:%S'.
    - **pattern2** (`str`, optional): The format pattern for `timestr2`. Defaults to '%Y-%m-%d %H:%M:%S'.  
      For more information on format codes, refer to:  
      https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

    ### Returns
    - **float**: The absolute difference between the two timestamps in seconds.

    ### Example
    >>> timestrdiff("2021-05-08 09:32:09", "2021-05-08 09:30:00")
    129.0
    """
    dt1 = timestr2datetime(timestr1, pattern1)
    dt2 = timestr2datetime(timestr2, pattern2)
    return abs((dt1 - dt2).total_seconds())


def utc_offset():
    """
    Retrieves the current local UTC offset as a string.

    This function returns the local timezone's UTC offset formatted as a string
    in the format ±HHMM (e.g., '+0200' or '-0500'), where HH represents hours and MM represents
    minutes.

    ### Returns
    - **str**: The current local UTC offset.

    ### Example
    >>> utc_offset()
    '+0200'
    """
    return time.strftime("%z")
