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
__version__ = '2024120901'

import datetime
import json
import re

from .globals import STATE_OK, STATE_UNKNOWN, STATE_WARN
from . import base
from . import cache
from . import shell
from . import time
from . import url


def check_eol(product, version_string, offset_eol=-30,
              check_major=False, check_minor=False, check_patch=False, pattern='%Y-%m-%d',
              extended_support=False,
              insecure=False, no_proxy=False, timeout=8):
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

    # gather eol data - first load from cache
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
        success, eol = url.fetch_json(
            product,
            insecure=insecure,
            no_proxy=no_proxy,
            timeout=timeout,
        )
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

    # find "the cycle's end of life date" automatically upon the given version
    installed_version = version(version_string)
    lookup_version = ''
    for v in installed_version:
        # search for versions "3", "3.7", "3.7.2", "3.7.2.9", ... in "cycle"
        if lookup_version:
            lookup_version += '.{}'.format(v)
        else:
            lookup_version = str(v)
        _, cycles_eoldate = base.lookup_lod(
            eol,
            'cycle',
            lookup_version,
        )
        if cycles_eoldate:
            break

    if not cycles_eoldate:
        # version not found, so don't know if it's up-to-date or not
        return STATE_UNKNOWN, 'version {} unknown'.format(version_string)

    # got an EOL date like "False" or "2022-12-31"
    msg = ''
    state = STATE_OK

    if 'support' in cycles_eoldate and isinstance(cycles_eoldate['support'], str):
        # if support has ended, no new features will be added to the product. no need to worry,
        # but notify (of course definition depends on the vendor)
        if time.now(as_type='datetime') > time.timestr2datetime(cycles_eoldate['support'], pattern=pattern):
            msg += 'full support ended on {}; '.format(cycles_eoldate['support'])

    # if user wants to check for extended support, and there is one, use this date
    if extended_support and 'extendedSupport' in cycles_eoldate:
        eol_col = 'extendedSupport'
    else:
        eol_col = 'eol'

    if isinstance(cycles_eoldate[eol_col], str) and cycles_eoldate[eol_col]:
        msg += 'EOL {} {}d'.format(
            cycles_eoldate[eol_col],
            offset_eol if offset_eol < 0 else '+{}'.format(offset_eol),
        )
        if time.now(as_type='datetime') > time.timestr2datetime(cycles_eoldate[eol_col], pattern=pattern) + datetime.timedelta(offset_eol):
            state = STATE_WARN
            msg += base.state2str(state, prefix=' ')
    else:
        # EOL is false, no EOL date given
        msg += 'EOL unknown'

    # search for newer versions, alert if wanted
    # no need for "cycle", just let's have a look at all "latest" versions
    try:
        eol_versions = [item['latest'] for item in eol]
    except:
        return state, msg
    installed_major, installed_minor, installed_patch = installed_version

    # check major
    eol_major, _, _  = version(eol_versions[0])
    if eol_major > installed_major:
        msg += ', major {} available'.format(eol_versions[0])
        if check_major:
            state = STATE_WARN
            msg += base.state2str(state, prefix=' ')

    # check minor
    for v in eol_versions:
        eol_major, eol_minor, eol_patch = version(v)
        # find the latest entry for the installed major version
        if eol_major == installed_major:
            if eol_minor > installed_minor:
                msg += ', minor {} available'.format(v)
                if check_minor:
                    state = STATE_WARN
                    msg += base.state2str(state, prefix=' ')
            break

    # check patch
    for v in eol_versions:
        eol_major, eol_minor, eol_patch = version(v)
        # find the latest entry for the installed major.minor version
        if eol_major == installed_major and eol_minor == installed_minor:
            if eol_patch > installed_patch:
                msg += ', patch {} available'.format(v)
                if check_patch:
                    state = STATE_WARN
                    msg += base.state2str(state, prefix=' ')
            break

    return state, msg


def get_os_info():
    """Return OS version information.
    """
    success, result = shell.shell_exec('. /etc/os-release && echo $NAME $VERSION', shell=True)
    if success:
        stdout, stderr, retc = result
        return stdout.strip()
    return ''


def version(ver, maxlen=3):
    """Returns a tuple based on a (semantic) version string.
    Use this function to compare version numbers.

    >>> version('1')
    (1, 0, 0)
    >>> version('1.2')
    (1, 2, 0)
    >>> version('1.2.3alpha')
    (1, 2, 3)
    >>> version('v5.13.19-4-pve')
    (5, 13, 19)
    >>> version('v5.13.19-4-pve', maxlen=4)
    (5, 13, 19, 4)
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
    ver = tuple(filter(None, ver))
    if len(ver) < maxlen:
        ver = ver + (0,) * (maxlen - len(ver))
    else:
        ver = ver[:maxlen]
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
