#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides functions for handling software versions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026070901'

import datetime
import json
import re

from .globals import STATE_OK, STATE_UNKNOWN, STATE_WARN


def check_eol(
    product,
    version_string,
    offset_eol=-30,
    check_major=False,
    check_minor=False,
    check_patch=False,
    pattern='%Y-%m-%d',
    extended_support=False,
    insecure=False,
    no_proxy=False,
    timeout=8,
    unreachable_severity='ok',
):
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
    - **unreachable_severity** (`str`, optional): State to report when endoflife.date is
      unreachable and the check falls back to the bundled offline data. One of `'ok'`, `'warn'`,
      `'crit'` or `'unknown'`. Default: `'ok'`.

    ### Returns
    - **tuple** (`int`, `str`):
      Nagios state and a descriptive status message.

    ### Notes
    - A successful online lookup is cached locally for 24 hours. The bundled offline fallback is
      not cached, so the next call retries the online source instead of masking a persistent
      outage from `unreachable_severity`.

    ### Example
    >>> check_eol('https://endoflife.date/api/python.json', '3.10')
    (STATE_WARN, 'EOL 2026-10-01')
    """
    # Imported here, not at module level: `check_eol()` is the only consumer of
    # these, and importing them eagerly would pull cache, db_sqlite and url into
    # every module that only wants the pure `version()` / `version2float()`
    # parsers below.
    from . import base, cache, time, url

    now = time.now(as_type='datetime')

    try:
        eol_data = cache.get(product, filename='linuxfabrik-lib-version.db')
        eol = json.loads(eol_data) if eol_data else None
    except (json.JSONDecodeError, TypeError):
        eol = None

    used_fallback = False
    if not eol:
        success, eol = url.fetch_json(
            product, insecure=insecure, no_proxy=no_proxy, timeout=timeout
        )
        if not success or not eol:
            # endoflife.date is unreachable. Fall back to the bundled offline snapshot.
            try:
                from . import endoflifedate

                eol = endoflifedate.ENDOFLIFE_DATE[product]
                used_fallback = True
            except (ImportError, KeyError):
                return STATE_UNKNOWN, f'product {product} unknown'
        else:
            # Only cache genuine online responses. The bundled snapshot is static, so caching it
            # would just suppress the retry against the online source for 24 hours.
            cache.set(
                product,
                json.dumps(eol),
                expire=time.now() + 86400,
                filename='linuxfabrik-lib-version.db',
            )

    unreachable_state = (
        base.str2state(unreachable_severity) if used_fallback else STATE_OK
    )
    unreachable_note = (
        ', endoflife.date unreachable, using bundled data' if used_fallback else ''
    )

    installed = version(version_string)

    cycles_eoldate = None
    for i in range(1, len(installed) + 1):
        lookup = '.'.join(map(str, installed[:i]))
        _, cycles_eoldate = base.lookup_lod(eol, 'cycle', lookup)
        if cycles_eoldate:
            break

    if not cycles_eoldate:
        return (
            base.get_worst(STATE_UNKNOWN, unreachable_state),
            f'version {version_string} unknown{unreachable_note}',
        )

    msg = []
    state = STATE_OK

    support = cycles_eoldate.get('support')
    if support and isinstance(support, str):
        if now > time.timestr2datetime(support, pattern=pattern):
            msg.append(f'full support ended on {support}; ')

    eol_key = (
        'extendedSupport'
        if extended_support and cycles_eoldate.get('extendedSupport')
        else 'eol'
    )
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
        state = base.get_worst(state, unreachable_state)
        return state, ' '.join(msg) + unreachable_note

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

    state = base.get_worst(state, unreachable_state)
    return state, ''.join(msg) + unreachable_note


def get_os_info():
    """
    Return OS version information.

    This function reads the operating system name and version from the `NAME` and `VERSION`
    fields of `/etc/os-release`.

    ### Parameters
    None

    ### Returns
    - **str**:
      The OS name and version as a string, or an empty string if `/etc/os-release` cannot be read.

    ### Example
    >>> get_os_info()
    'Ubuntu 22.04.1 LTS'
    """
    values = {}
    try:
        with open('/etc/os-release', encoding='utf-8') as os_release:
            for line in os_release:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                values[key] = value.strip().strip('"').strip("'")
    except OSError:
        return ''

    return ' '.join(
        part for part in (values.get('NAME'), values.get('VERSION')) if part
    )


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
