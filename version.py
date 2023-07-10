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
__version__ = '2023071001'

import json
import re

from .globals import STATE_OK, STATE_UNKNOWN, STATE_WARN
from . import base
from . import cache
from . import shell
from . import time
from . import url


def check_eol(product, ver, pattern='%Y-%m-%d'):
    """Check if a software version is End of Life (EOL) by comparing it to a JSON object
    compatible to the https://endoflife.date API. Return the status and the EOL message.

    EOL dates are taken from:
    1. Local SQLite DB cache (valid for 24h). If not successful...
    2. From https://endoflife.date/api (and then cached). If not successful...
    3. From local JSON definition file, definition copied from endoflife.date (and then cached).

    >>> check_eol('https://endoflife.date/api/example.json', '3.7')
    (STATE_OK, 'EOL unknown')
    >>>
    >>> check_eol('https://endoflife.date/api/example.json', '3.8')
    (STATE_WARN, 'EOL 2020-12-31')
    >>>
    >>> check_eol('https://endoflife.date/api/example.json', '3.9')
    (STATE_UNKOWN, 'version unknown')
    >>>
    >>> check_eol('https://endoflife.date/api/example.json', '4.0')
    (STATE_OK, 'EOL 2100-12-31')
    """
    # first load from cache
    eol = cache.get(
        product,
        filename='linuxfabrik-lib-version.db',
    )
    if eol:
        try:
            eol = json.loads(eol)
        except json.decoder.JSONDecodeError:
            # don't care, we'll fetch new info
            eol = False
    if not eol:
        # nothing or nothing valid found? load from web
        success, eol = url.fetch_json(product)
        if not success or not eol:
            # not working? timeout? load from local definition
            try:
                from . import endoflifedate # pylint: disable=C0415
                eol = endoflifedate.ENDOFLIFE_DATE[product]
            except KeyError:
                # ok, give up
                return STATE_UNKNOWN, 'product {} unknown'.format(product)
        # update the cache with the new info
        retc = cache.set(
            product,
            json.dumps(eol),
            expire=time.now() + 24*60*60,
            filename='linuxfabrik-lib-version.db',
        )
    eol = base.lookup_lod(
        eol,
        'cycle',
        ver,
    )
    if not eol:
        # version not found
        return STATE_UNKNOWN, 'version {} unknown'.format(eol)
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


def version(ver):
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
    ver : str
        A version string, for example "v5.13.19-4-pve".

    Returns
    -------
    tuple
        A tuple of version numbers, for example (5, 13, 19, 4).
    """
    # if we get something like "v5.13.19-4-pve", remove everything except "." and "-",
    # and convert "-" to "."
    ver = re.sub(r'[^0-9\.-]', '', ver)
    ver = ver.replace('-', '.')
    ver = ver.split('.')
    # remove all empty strings from the list of strings
    ver = list(filter(None, ver))
    # create a return tuple, for example (5, 13, 19, 4)
    return tuple(map(int, ver))


def version2float(ver):
    """Just get the version number as a float.

    >>> version2float('Version v17.3.2.0')
    17.320
    >>> version2float('21.60-53-93285')
    21.605393285
    """
    ver = re.sub(r'[^0-9\.]', '', ver)  # remove everything except 0-9 and .
    ver = ver.split('.')
    if len(ver) > 1:
        return float('{}.{}'.format(ver[0], ''.join(ver[1:])))
    return float(''.join(ver))
