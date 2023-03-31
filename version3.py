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
__version__ = '2023033101'

from .globals3 import STATE_OK, STATE_UNKNOWN, STATE_WARN
from . import base3
from . import time3


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
    eol = base3.lookup_lod(
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
    if time3.now(as_type='datetime') > time3.timestr2datetime(eol['eol'], pattern=pattern):
        state = STATE_WARN
    return state, 'EOL {}{}'.format(eol['eol'], base3.state2str(state, prefix=' '))
