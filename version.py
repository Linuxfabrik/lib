#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides functions for handling software versions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

import os
import re

from .globals import STATE_OK, STATE_UNKNOWN, STATE_WARN
from . import base
from . import disk
from . import shell
from . import time


def check_eol(endoflife_date, version, pattern='%Y-%m-%d'):
    """Check if a software version is End of Life (EOL) by comparing it to a JSON object
    compatible to the https://endoflife.date API. Return the status and the EOL message.

    >>> ENDOFLIFE_DATE = [
    ...     {"cycle": "3.7","eol": False},
    ...     {"cycle": "3.8","eol": "2020-12-31"},
    ...     {"cycle": "4.0","eol": "2100-12-31"},
    ... ]
    >>>
    >>> check_eol(ENDOFLIFE_DATE, '3.7')
    (STATE_OK, 'EOL unknown')
    >>>
    >>> check_eol(ENDOFLIFE_DATE, '3.8')
    (STATE_WARN, 'EOL 2020-12-31')
    >>>
    >>> check_eol(ENDOFLIFE_DATE, '3.9')
    (STATE_UNKOWN, 'version unknown')
    >>>
    >>> check_eol(ENDOFLIFE_DATE, '4.0')
    (STATE_OK, 'EOL 2100-12-31')
    """
    eol = base.lookup_lod(
        endoflife_date,
        'cycle',
        version,
    )
    if not eol:
        # version not found
        return STATE_UNKNOWN, 'version unknown'
    state = STATE_OK
    if not eol['eol']:
        # EOL is false, no EOL date given
        return state, 'EOL unknown'
    # we got an EOL timestamp, so check it
    if time.now(as_type='datetime') > time.timestr2datetime(eol['eol'], pattern=pattern):
        state = STATE_WARN
    return state, 'EOL {}{}'.format(eol['eol'], base.state2str(state, prefix=' '))


def get_os_info():
    """Return OS version information.
    """
    success, result = shell.shell_exec('. /etc/os-release && echo $NAME $VERSION', shell=True)
    if success:
        stdout, stderr, retc = result
        return stdout.strip()
    return ''


def version(v):
    """Use this function to compare string-based version numbers.

    >>> '3.0.7' < '3.0.11'
    False
    >>> version('3.0.7') < version('3.0.11')
    True
    >>> version('v3.0.7-2') < version('3.0.11')
    True
    >>> version(psutil.__version__) >= version('5.3.0')
    True

    Parameters
    ----------
    v : str
        A version string, for example "v5.13.19-4-pve".

    Returns
    -------
    tuple
        A tuple of version numbers, for example (5, 13, 19, 4).
    """
    # if we get something like "v5.13.19-4-pve", remove everything except "." and "-",
    # and convert "-" to "."
    v = re.sub(r'[^0-9\.-]', '', v)
    v = v.replace('-', '.')
    v = v.split('.')
    # remove all empty strings from the list of strings
    v = list(filter(None, v))
    # create a return tuple, for example (5, 13, 19, 4)
    return tuple(map(int, v))


def version2float(v):
    """Just get the version number as a float.

    >>> version2float('Version v17.3.2.0')
    17.320
    >>> version2float('21.60-53-93285')
    21.605393285
    """
    v = re.sub(r'[^0-9\.]', '', v)  # remove everything except 0-9 and .
    v = v.split('.')
    if len(v) > 1:
        return float('{}.{}'.format(v[0], ''.join(v[1:])))
    return float(''.join(v))
