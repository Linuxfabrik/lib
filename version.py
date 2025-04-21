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
__version__ = '2025042101'

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
              check_major=False, check_minor=False, check_patch=False,
              pattern='%Y-%m-%d', extended_support=False,
              insecure=False, no_proxy=False, timeout=8):
    """
    Check if a software version is End of Life (EOL) by comparing it to endoflife.date data.

    This function checks the EOL status based on local cache, online API or bundled definitions.
    It reports whether the installed version is outdated, nearing EOL, or fully supported.

    ### Parameters
    - **product** (`str`): Product name or endoflife.date JSON URL.
    - **version_string** (`str`): The version string of the installed software.
    - **offset_eol** (`int`, optional): Days before EOL to trigger a warning. Default: `-30`.
    - **check_major** (`bool`, optional): Warn if a newer major version exists.
    - **check_minor** (`bool`, optional): Warn if a newer minor version exists.
    - **check_patch** (`bool`, optional): Warn if a newer patch version exists.
    - **pattern** (`str`, optional): Datetime parsing pattern. Default: `'%Y-%m-%d'`.
    - **extended_support** (`bool`, optional): Check extended support EOL if available.
    - **insecure** (`bool`, optional): Disable SSL certificate verification.
    - **no_proxy** (`bool`, optional): Ignore proxy settings.
    - **timeout** (`int`, optional): Network timeout in seconds. Default: `8`.

    ### Returns
    - **tuple** (`int`, `str`):
      Nagios state and a descriptive status message.

    ### Notes
    - Data is cached locally for 24 hours.

    ### Example
    >>> check_eol('https://endoflife.date/api/python.json', '3.10')
    (STATE_WARN, 'EOL 2026-10-01')
    """
    now = time.now(as_type='datetime')

    try:
        eol_data = cache.get(product, filename='linuxfabrik-lib-version.db')
        eol = json.loads(eol_data) if eol_data else None
    except (json.JSONDecodeError, TypeError):
        eol = None

    if not eol:
        success, eol = url.fetch_json(product, insecure=insecure, no_proxy=no_proxy, timeout=timeout)
        if not success or not eol:
            try:
                from . import endoflifedate
                eol = endoflifedate.ENDOFLIFE_DATE[product]
            except (ImportError, KeyError):
                return STATE_UNKNOWN, f'product {product} unknown'
        cache.set(product, json.dumps(eol), expire=time.now() + 86400,
                  filename='linuxfabrik-lib-version.db')

    installed = version(version_string)

    cycles_eoldate = None
    for i in range(1, len(installed) + 1):
        lookup = '.'.join(map(str, installed[:i]))
        _, cycles_eoldate = base.lookup_lod(eol, 'cycle', lookup)
        if cycles_eoldate:
            break

    if not cycles_eoldate:
        return STATE_UNKNOWN, f'version {version_string} unknown'

    msg = []
    state = STATE_OK

    support = cycles_eoldate.get('support')
    if support and isinstance(support, str):
        if now > time.timestr2datetime(support, pattern=pattern):
            msg.append(f'full support ended on {support}; ')

    eol_key = 'extendedSupport' if extended_support and cycles_eoldate.get('extendedSupport') else 'eol'
    eol_date = cycles_eoldate.get(eol_key)

    if eol_date:
        eol_dt = time.timestr2datetime(eol_date, pattern=pattern)
        msg.append(f'EOL {eol_date} {"+" if offset_eol > 0 else ""}{offset_eol}d')
        if now > eol_dt + datetime.timedelta(days=offset_eol):
            state = STATE_WARN
            msg.append(base.state2str(state, prefix=' '))
    else:
        msg.append('EOL unknown')

    try:
        latest_versions = [version(item['latest']) for item in eol]
    except (TypeError, KeyError):
        return state, ' '.join(msg)

    major, minor, patch = installed

    for v_major, v_minor, v_patch in latest_versions:
        if v_major > major:
            msg.append(f', major {v_major}.{v_minor}.{v_patch} available')
            if check_major:
                state = STATE_WARN
            break
        if v_major == major and v_minor > minor:
            msg.append(f', minor {v_major}.{v_minor}.{v_patch} available')
            if check_minor:
                state = STATE_WARN
            break
        if v_major == major and v_minor == minor and v_patch > patch:
            msg.append(f', patch {v_major}.{v_minor}.{v_patch} available')
            if check_patch:
                state = STATE_WARN
            break

    return state, ''.join(msg)


def get_os_info():
    """
    Return OS version information.

    This function reads and returns the operating system name and version by sourcing `/etc/os-release`
    and echoing the `$NAME` and `$VERSION` environment variables.

    ### Parameters
    None

    ### Returns
    - **str**:
      The OS name and version as a string, or an empty string if the command fails.

    ### Example
    >>> get_os_info()
    'Ubuntu 22.04.1 LTS'
    """
    cmd = '. /etc/os-release && echo "$NAME $VERSION"'
    success, result = shell.shell_exec(cmd, shell=True)
    if not success:
        return ''
    
    stdout, _, _ = result
    return stdout.strip()


def version(ver, maxlen=3):
    """
    Parse a version string and return a comparable tuple.

    This function converts a (semantic) version string into a tuple of integers. Non-numeric
    characters (except for `.` and `-`) are ignored. Useful for comparing version numbers.

    ### Parameters
    - **ver** (`str`): A version string (e.g., "v5.13.19-4-pve").
    - **maxlen** (`int`, optional): Desired tuple length. Defaults to `3`.

    ### Returns
    - **tuple**:
      A tuple of integers representing the version, e.g., `(5, 13, 19)`.

    ### Example
    >>> version('1')
    (1, 0, 0)
    >>> version('1.2')
    (1, 2, 0)
    >>> version('v5.13.19-4-pve')
    (5, 13, 19)
    >>> version('v5.13.19-4-pve', maxlen=4)
    (5, 13, 19, 4)
    >>> version('3.0.7') < version('3.0.11')
    True
    >>> version(psutil.__version__) >= version('5.3.0')
    True
    """
    # Clean the version string: keep digits, dots, and dashes
    ver_cleaned = re.sub(r'[^0-9\.-]', '', ver).replace('-', '.')
    parts = [int(p) for p in ver_cleaned.split('.') if p]

    # Pad with zeros or truncate to match maxlen
    if len(parts) < maxlen:
        parts.extend([0] * (maxlen - len(parts)))
    else:
        parts = parts[:maxlen]

    return tuple(parts)


def version2float(ver):
    """
    Convert a version string into a single float value.

    This function parses a version string, removes non-numeric characters except dots, and
    constructs a float for simple comparison purposes. Raises ValueError if no numbers are found.

    ### Parameters
    - **ver** (`str`): A version string, e.g., `"Version v17.3.2.0"`.

    ### Returns
    - **float**:
      Version represented as a float.

    ### Raises
    - **ValueError**:
      If the input does not contain any digits.

    ### Example
    >>> version2float('Version v17.3.2.0')
    17.320
    >>> version2float('Fedora Linux 41 (Workstation Edition)')
    41.0
    >>> version2float('21.60-53-93285')
    21.605393285
    """
    cleaned = re.sub(r'[^0-9.]', '', ver)
    if not re.search(r'\d', cleaned):
        raise ValueError(f'No digits found in version string: {ver}')

    parts = cleaned.split('.')
    major = parts[0]
    minor = ''.join(parts[1:]) if len(parts) > 1 else '0'

    return float(f'{major}.{minor}')
