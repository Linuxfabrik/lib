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
__version__ = '2025030101'

import datetime
import time


def epoch2iso(timestamp):
    """Converts a UNIX epoch timestamp to an ISO-formatted date and time string.

    This function takes a UNIX timestamp (which can be an integer or float) and returns a string
    representing the corresponding local time in ISO 8601 format (YYYY-MM-DD HH:MM:SS).

    Parameters:
        timestamp (int or float): A UNIX epoch timestamp (seconds since January 1, 1970).

    Returns:
        str: A string representing the date and time in ISO format, based on the local timezone.

    Example:
        >>> epoch2iso(1620459129)
        '2021-05-08 09:32:09'
    """
    timestamp = float(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


def now(as_type=''):
    """Returns the current date and time in various formats.

    Depending on the value of the `as_type` parameter, this function returns:
    - An integer UNIX epoch (seconds since January 1, 1970) by default.
    - A floating-point UNIX epoch if 'float' is specified.
    - A datetime object if 'datetime' is specified.
    - An ISO formatted string (YYYY-MM-DD HH:MM:SS) if 'iso' is specified.

    Parameters:
        as_type (str, optional): A string indicating the desired return type.
            Accepted values:
                - '' or 'epoch': Returns an integer UNIX epoch timestamp.
                - 'float': Returns a floating-point UNIX epoch timestamp.
                - 'datetime': Returns a `datetime.datetime` object representing the current time.
                - 'iso': Returns a string formatted as "YYYY-MM-DD HH:MM:SS".
            Defaults to '' (integer UNIX epoch).

    Returns:
        int, float, datetime.datetime, or str: The current time in the specified format.

    Examples:
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
        return time.strftime("%Y-%m-%d %H:%M:%S")
    if as_type == 'float':
        return time.time()
    return int(time.time())


def timestr2datetime(timestr, pattern='%Y-%m-%d %H:%M:%S'):
    """Converts a time string into a datetime object using the specified format.

    This function parses a string representing a date and time into a `datetime.datetime`
    object based on the provided format pattern. The default format is ISO (YYYY-MM-DD HH:MM:SS).

    Parameters:
        timestr (str): A string representing the date and time.
        pattern (str, optional): The format string corresponding to the structure of `timestr`.
            Defaults to '%Y-%m-%d %H:%M:%S'. For more details on format codes, see:
            https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

    Returns:
        datetime.datetime: A datetime object corresponding to the parsed date and time.

    Example:
        >>> timestr2datetime("2021-05-08 09:32:09")
        datetime.datetime(2021, 5, 8, 9, 32, 9)
    """
    return datetime.datetime.strptime(timestr, pattern)


def timestr2epoch(timestr, pattern='%Y-%m-%d %H:%M:%S', tzinfo=None):
    """Converts a time string to a UNIX epoch timestamp.
    Parameters:
        timestr (str): The time string to convert.
        pattern (str): The format of the time string (default is '%Y-%m-%d %H:%M:%S').
        tzinfo (datetime.tzinfo, optional): 
            Timezone information. If provided, the parsed datetime is set to this timezone.
            If None, the time is assumed to be local time.

    Returns:
        float: The UNIX epoch timestamp (seconds since January 1, 1970, 00:00:00 UTC).

    Raises:
        ValueError: If the time string does not match the provided format.

    Examples:
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
    """Computes the absolute difference in seconds between two datetime strings.

    This function converts two datetime strings into `datetime.datetime` objects using
    their respective format patterns, then calculates the absolute time difference between them.
    By default, both strings are expected to be in ISO format (YYYY-MM-DD HH:MM:SS).

    Parameters:
        timestr1 (str): The first datetime string.
        timestr2 (str): The second datetime string.
        pattern1 (str, optional): The format pattern for `timestr1`. Defaults to '%Y-%m-%d %H:%M:%S'.
        pattern2 (str, optional): The format pattern for `timestr2`. Defaults to '%Y-%m-%d %H:%M:%S'.
            For more information on format codes, refer to:
            https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

    Returns:
        float: The absolute difference between the two timestamps in seconds.

    Example:
        >>> timestrdiff("2021-05-08 09:32:09", "2021-05-08 09:30:00")
        129.0
    """
    timestr1 = timestr2datetime(timestr1, pattern1)
    timestr2 = timestr2datetime(timestr2, pattern2)
    timedelta = abs(timestr1 - timestr2)
    return timedelta.total_seconds()


def utc_offset():
    """Retrieves the current local UTC offset as a string.

    This function returns the local timezone's UTC offset formatted as a string
    in the format ±HHMM (e.g., '+0200' or '-0500'), where HH represents hours and MM represents
    minutes.

    Returns:
        str: The current local UTC offset.

    Example:
        >>> utc_offset()
        '+0200'
    """
    return time.strftime("%z")
