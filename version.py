#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Provides functions for handling software versions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026100101'

import datetime
import json
import re

from .globals import STATE_OK, STATE_UNKNOWN, STATE_WARN

# The archive suites and components a distribution maintains itself. Backports, Ubuntu's
# universe (maintained by the community, not by Canonical) and third-party repositories
# are left out: their packages do not get the security support of the release.
_DEB_COMPONENTS = {'debian': ('main',), 'ubuntu': ('main', 'restricted')}
_DEB_SUITES = ('{}', '{}-security', '{}-updates')


def _debian_life_cycle(package_path, os_release, timeout, load_eol):
    """
    Return the life cycle Debian or Ubuntu gives the package that installed the file.

    A package from the archive of the release is maintained for as long as the release
    gets security support: on Debian until the end of its LTS, on Ubuntu until the end of
    the standard support of `main` and `restricted`.

    Parameters
    ----------
    package_path : str
        The resolved path of the file the version was read from.
    os_release : dict
        `/etc/os-release` as returned by `_os_release()`.
    timeout : int
        Seconds to wait for `dpkg-query` and `apt-cache`.
    load_eol : callable
        Returns the endoflife.date entries for a product URL, or `None`.

    Returns
    -------
    tuple (str, str) or None
        A description of the life cycle and its end date (`YYYY-MM-DD`), or `None` where
        it does not apply: a file no package owns, a package that does not come from the
        archive of the release, or a release endoflife.date does not list.
    """
    from . import shell

    distro = os_release.get('ID', '')
    codename = os_release.get('VERSION_CODENAME', '')
    version_id = os_release.get('VERSION_ID', '')
    if distro not in _DEB_COMPONENTS or not codename or not version_id:
        return None

    # "python3.10-minimal: /usr/bin/python3.10", or "pkg1, pkg2: path" where several
    # packages ship the same directory. A diversion line names no package.
    success, result = shell.shell_exec(
        ['dpkg-query', '--search', package_path], timeout=timeout
    )
    if not success or result[2] != 0:
        return None
    name = None
    for line in result[0].splitlines():
        owner, sep, path = line.partition(': ')
        if sep and path == package_path and not owner.startswith('diversion '):
            name = owner.split(',')[0].strip().split(':')[0]
            break
    if not name:
        return None

    # The sources of the installed version follow the line `*** <version> <pin>`, one
    # per line, `<pin> <uri> <suite>/<component> <arch> Packages`, until the next version.
    # Verified against apt 2.4 on Ubuntu 22.04 and apt 2.6 on Debian 12.
    success, result = shell.shell_exec(['apt-cache', 'policy', name], timeout=timeout)
    if not success or result[2] != 0:
        return None
    suites = [suite.format(codename) for suite in _DEB_SUITES]
    from_archive = False
    installed = False
    for line in result[0].splitlines():
        if line.startswith(' *** '):
            installed = True
            continue
        if not installed:
            continue
        fields = line.split()
        if len(fields) != 5 or fields[-1] != 'Packages':
            break
        suite, _, component = fields[2].partition('/')
        if suite in suites and component in _DEB_COMPONENTS[distro]:
            from_archive = True
    if not from_archive:
        return None

    cycles = load_eol(f'https://endoflife.date/api/{distro}.json') or []
    for item in cycles:
        if isinstance(item, dict) and str(item.get('cycle')) == version_id:
            eol = item.get('eol')
            if isinstance(eol, str) and eol:
                label = 'Debian' if distro == 'debian' else 'Ubuntu'
                return f'{label} {version_id} package {name}', eol
    return None


def _load_eol(product, insecure, no_proxy, proxy, timeout):
    """
    Return the endoflife.date entries of a product: cached, online or bundled.

    Returns
    -------
    tuple (list or None, bool, bool)
        The entries, whether they come from the bundled offline snapshot, and whether
        that is because the Python running the consumer lacks httpx. `None` if the
        product is unknown everywhere.

    Notes
    -----
    - A successful online lookup is cached locally for 24 hours. The bundled snapshot is
      not cached, so the next call retries the online source instead of masking a
      persistent outage.
    """
    from . import cache, time, url

    try:
        eol_data = cache.get(product, filename='linuxfabrik-lib-version.db')
        eol = json.loads(eol_data) if eol_data else None
    except (json.JSONDecodeError, TypeError):
        eol = None
    if eol:
        return eol, False, False

    success, eol = url.fetch_json(
        product, insecure=insecure, no_proxy=no_proxy, proxy=proxy, timeout=timeout
    )
    if success and eol:
        cache.set(
            product,
            json.dumps(eol),
            expire=time.now() + 86400,
            filename='linuxfabrik-lib-version.db',
        )
        return eol, False, False

    # endoflife.date is unreachable, or could not be asked at all because the Python
    # running the consumer lacks httpx (a plugin started with the system Python instead
    # of the one of its venv). The caller tells the two apart in its message: they are
    # fixed in different places.
    try:
        from . import endoflifedate

        return endoflifedate.ENDOFLIFE_DATE[product], True, url.httpx is None
    except (ImportError, KeyError):
        return None, False, False


def _os_release():
    """Return `ID`, `ID_LIKE` (a list), `VERSION_CODENAME` and `VERSION_ID`."""
    from . import disk

    success, content = disk.read_file('/etc/os-release')
    if not success:
        return {}
    result = {}
    for line in content.splitlines():
        key, _, value = line.partition('=')
        if key in ('ID', 'ID_LIKE', 'VERSION_CODENAME', 'VERSION_ID'):
            result[key] = value.strip().strip('"\'')
    result['ID_LIKE'] = result.get('ID_LIKE', '').split()
    return result


# The vendor of a rebuild is whatever its packages say ("Red Hat, Inc.", "Rocky",
# "AlmaLinux"), so it is never compared against a list. A package counts as the
# distribution's own if it carries the vendor of the package that installed
# /etc/os-release. EPEL ("Fedora Project") and third-party repositories do not.
_RPM_QUERY_FORMAT = '%{NAME}\\t%{VENDOR}\\t%{VERSION}\\t%{MODULARITYLABEL}\\n'


def _rhel_life_cycle(package_path, timeout):
    """
    Return the life cycle Red Hat gives the package that installed the file.

    Red Hat maintains the software it ships for a fixed time that has nothing to do with
    the end of life upstream announces: Python 3.9 is supported on RHEL 9 until 2032,
    years after python.org dropped it.

    Parameters
    ----------
    package_path : str
        The resolved path of the file the version was read from.
    timeout : int
        Seconds to wait for `rpm`.

    Returns
    -------
    tuple (str, str) or None
        A description of the life cycle and its end date (`YYYY-MM-DD`), or `None` where
        it does not apply: no `rpm`, a file no package owns, a package from another
        vendor, or a module stream Red Hat's data does not list.

    Notes
    -----
    - The data comes from `rhelappstreams.py`, generated from what Red Hat publishes
      for its Application Streams life cycle API.
    - A package of the distribution vendor that Red Hat lists with no end date of its
      own, or does not list at all, is maintained for the life of the major release.
      That is the case for everything in BaseOS, Postfix for example.
    """
    from . import shell

    packages = []
    for path in ('/etc/os-release', package_path):
        success, result = shell.shell_exec(
            ['rpm', '--query', f'--queryformat={_RPM_QUERY_FORMAT}', '--file', path],
            timeout=timeout,
        )
        if not success:
            return None
        stdout, _, retc = result
        fields = stdout.splitlines()[0].split('\t') if stdout else []
        if retc != 0 or len(fields) != 4:
            return None
        packages.append(fields)
    (_, os_vendor, os_version, _), (name, vendor, _, modularity) = packages
    if vendor != os_vendor:
        return None

    try:
        from . import rhelappstreams

        major = int(os_version.split('.')[0])
        release = rhelappstreams.RHEL_APP_STREAMS[major]
    except (ImportError, KeyError, ValueError):
        return None

    if modularity and modularity != '(none)':
        # "python39:3.9:8100020251218081213:e3a3f2fc" is module, stream, version and
        # context, the life cycle belongs to module and stream.
        stream = release['modules'].get(':'.join(modularity.split(':')[:2]))
        if stream is None:
            return None
    else:
        stream = release['packages'].get(name)
    if stream is None or stream[1] is None:
        return f'RHEL {major} package {name}', release['eol']
    return f'RHEL {major} Application Stream {stream[0]}', stream[1]


def _vendor_life_cycle(package_path, timeout, load_eol):
    """
    Return the life cycle the distribution gives the package that installed a file.

    Distributions maintain the software they ship for as long as they support the
    release or the stream, which has nothing to do with the end of life upstream
    announces. Supported are the rebuilds of Red Hat Enterprise Linux, Debian and Ubuntu.

    Parameters
    ----------
    package_path : str
        The file the version was read from, a binary for example. A bare command name is
        looked up in `PATH`, and symlinks are resolved, so `/usr/bin/python3` finds the
        package of the interpreter it points to.
    timeout : int
        Seconds to wait for each package manager query.
    load_eol : callable
        Returns the endoflife.date entries for a product URL, or `None`.

    Returns
    -------
    tuple (str, str) or None
        A description of the life cycle and its end date (`YYYY-MM-DD`), or `None` where
        the upstream end of life applies.
    """
    import os
    import shutil

    if not isinstance(package_path, str) or not package_path:
        return None
    if os.sep not in package_path:
        package_path = shutil.which(package_path)
        if not package_path:
            return None
    package_path = os.path.realpath(package_path)

    os_release = _os_release()
    distro = os_release.get('ID', '')
    if distro in _DEB_COMPONENTS:
        return _debian_life_cycle(package_path, os_release, timeout, load_eol)
    # CentOS Stream calls itself "centos" and carries ID_LIKE="rhel fedora", but runs
    # ahead of RHEL with a shorter life, so only the rebuilds of RHEL itself count.
    if distro != 'centos' and 'rhel' in [distro, *os_release.get('ID_LIKE', [])]:
        return _rhel_life_cycle(package_path, timeout)
    return None


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
    proxy=None,
    timeout=8,
    unreachable_severity='ok',
    cycle=None,
    package_path=None,
):
    """
    Check if a software version is End of Life (EOL) by comparing it to endoflife.date data.

    This function checks the EOL status based on local cache, online API or bundled definitions.
    It reports whether the installed version is outdated, nearing EOL, or fully supported.

    Parameters
    ----------
    product : str
        Product name or endoflife.date JSON URL.
    version_string : str
        The version string of the installed software.
    offset_eol : int, optional
        Days before EOL to trigger a warning. Default: `-30`.
    check_major : bool, optional
        Warn if a newer major version exists.
    check_minor : bool, optional
        Warn if a newer minor version exists.
    check_patch : bool, optional
        Warn if a newer patch version exists.
    pattern : str, optional
        Datetime parsing pattern. Default: `'%Y-%m-%d'`.
    extended_support : bool, optional
        Check extended support EOL if available.
    insecure : bool, optional
        Disable SSL certificate verification.
    no_proxy : bool, optional
        Ignore proxy settings.
    proxy : str, optional
        Proxy to reach the endoflife.date API through, overriding the one the
        environment names. Defaults to `None`, which leaves the choice to the
        environment.
    timeout : int, optional
        Network timeout in seconds. Default: `8`.
    unreachable_severity : str, optional
        State to report when endoflife.date is
        unreachable and the lookup falls back to the bundled offline data. One of `'ok'`, `'warn'`,
        `'crit'` or `'unknown'`. Default: `'ok'`.
    cycle : str or list of str, optional
        The endoflife.date cycle to evaluate, for products whose cycles are not named
        after a version number (`'11-24h2-e'`, `'2012-r2'`). A list names candidates
        from the most to the least specific, and the first one the data lists is used.
        `version_string` then only appears in the message, and neither the newer
        release check nor the placement of an unlisted version above or below the
        listed cycles takes place. Default: `None`, which derives the cycle from
        `version_string`.
    package_path : str, optional
        The file the version was read from, a binary for example. Where that file comes
        from a package the distribution maintains itself, the end of life is the one
        the distribution gives it rather than the one upstream announces, and the
        message names it: Red Hat's for a package or Application Stream on a rebuild of
        Red Hat Enterprise Linux, the end of security support (LTS included) of the
        release on Debian, and of the standard support of `main` and `restricted` on
        Ubuntu. The newer release check still compares against upstream. Default:
        `None`, which always uses the upstream end of life.

    Returns
    -------
    tuple (int, str)
        Nagios state and a descriptive status message.

    Notes
    -----
    - A successful online lookup is cached locally for 24 hours. The bundled offline fallback is
      not cached, so the next call retries the online source instead of masking a persistent
      outage from `unreachable_severity`.

    Examples
    --------
    >>> check_eol('https://endoflife.date/api/python.json', '3.10')
    (1, 'EOL 2026-10-01')
    """
    # Imported here, not at module level: `check_eol()` is the only consumer of
    # these, and importing them eagerly would pull cache, db_sqlite and url into
    # every module that only wants the pure `version()` / `version2float()`
    # parsers below.
    from . import base, time

    now = time.now(as_type='datetime')

    eol, used_fallback, missing_httpx = _load_eol(
        product, insecure, no_proxy, proxy, timeout
    )
    if eol is None:
        return STATE_UNKNOWN, f'product {product} unknown'

    unreachable_state = (
        base.str2state(unreachable_severity) if used_fallback else STATE_OK
    )
    unreachable_note = ''
    if used_fallback:
        unreachable_note = (
            ', Python module "httpx" is not installed, using bundled data'
            if missing_httpx
            else ', endoflife.date unreachable, using bundled data'
        )

    installed = version(version_string)

    cycles_eoldate = None
    if cycle is not None:
        # Some products name their cycles after an edition or a servicing channel
        # ("11-24h2-e", "23h2-ac") rather than after a version, so no prefix of the
        # version string finds them. The caller knows which cycle applies.
        for candidate in [cycle] if isinstance(cycle, str) else cycle:
            _, cycles_eoldate = base.lookup_lod(eol, 'cycle', candidate)
            if cycles_eoldate:
                break
    else:
        for i in range(1, len(installed) + 1):
            lookup = '.'.join(map(str, installed[:i]))
            _, cycles_eoldate = base.lookup_lod(eol, 'cycle', lookup)
            if cycles_eoldate:
                break

    msg = []
    state = STATE_OK

    vendor_life_cycle = None
    if package_path:
        vendor_life_cycle = _vendor_life_cycle(
            package_path,
            timeout,
            lambda distro_product: _load_eol(
                distro_product, insecure, no_proxy, proxy, timeout
            )[0],
        )
    if vendor_life_cycle:
        # The distribution maintains this build itself, so its date is the one that
        # counts, whether or not upstream still lists the cycle.
        label, eol_date = vendor_life_cycle
        eol_dt = time.timestr2datetime(eol_date, pattern='%Y-%m-%d')
        msg.append(
            f'{label}, EOL {eol_date} {"+" if offset_eol > 0 else ""}{offset_eol}d'
        )
        if now > eol_dt + datetime.timedelta(days=offset_eol):
            state = STATE_WARN
            msg.append(base.state2str(state, prefix=' '))
    elif not cycles_eoldate:
        # endoflife.date lists the product but not this cycle, and where the installed
        # version falls relative to what is listed says what that means. A version above
        # everything listed is a host that upstream has not catalogued yet, which nobody
        # can act on; one below everything listed is older than the oldest cycle upstream
        # still records, and therefore out of support for certain. Only a gap between the
        # two is genuinely unknown. Cycles named by the caller have no such order.
        oldest, newest = (None, None) if cycle is not None else cycle_bounds(eol)
        if newest is not None and installed > newest:
            msg.append('newer than anything endoflife.date lists')
        elif oldest is not None and installed < oldest:
            state = STATE_WARN
            msg.append('older than anything endoflife.date lists')
            msg.append(base.state2str(state, prefix=' '))
        else:
            state = STATE_UNKNOWN
            msg.append(f'version {version_string} unknown')
    else:
        eol_key = (
            'extendedSupport'
            if extended_support and cycles_eoldate.get('extendedSupport')
            else 'eol'
        )
        eol_date = cycles_eoldate.get(eol_key)

        # Where full support ends on the day of the end of life (Windows 10 22H2 without
        # Extended Security Updates, for example), the EOL below says it all.
        support = cycles_eoldate.get('support')
        if support and isinstance(support, str) and support != eol_date:
            if now > time.timestr2datetime(support, pattern=pattern):
                msg.append(f'full support ended on {support}; ')

        # The API answers this field in three shapes and they are not interchangeable:
        # a date string, `true` (end of life reached, no date given) and `false` (no end
        # announced). Reading either boolean as a date is what used to raise a TypeError
        # here, and reading `false` as a missing date reported the healthiest answer the
        # API gives as a gap in our knowledge.
        if isinstance(eol_date, str) and eol_date:
            eol_dt = time.timestr2datetime(eol_date, pattern=pattern)
            msg.append(f'EOL {eol_date} {"+" if offset_eol > 0 else ""}{offset_eol}d')
            if now > eol_dt + datetime.timedelta(days=offset_eol):
                state = STATE_WARN
                msg.append(base.state2str(state, prefix=' '))
        elif eol_date is True:
            state = STATE_WARN
            msg.append('EOL, no date announced')
            msg.append(base.state2str(state, prefix=' '))
        else:
            msg.append('no EOL announced')

    # The `latest` of a named cycle is not comparable to the version string: Windows
    # reports the same build number there for every edition of a feature release.
    if cycle is not None:
        state = base.get_worst(state, unreachable_state)
        return state, ''.join(msg) + unreachable_note

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


def cycle_bounds(eol):
    """
    Return the lowest and highest release cycle a set of endoflife.date entries names.

    Used to place a version that has no cycle of its own: above the highest cycle the
    data has simply not caught up yet, below the lowest it is older than anything
    upstream still records.

    Parameters
    ----------
    eol : list
        endoflife.date entries, each a dict that may carry a `cycle` key.

    Returns
    -------
    tuple (tuple or None, tuple or None)
        The lowest and the highest cycle as comparable version tuples, or `(None, None)`
        when no entry names a parsable cycle.

    Examples
    --------
    >>> cycle_bounds([{'cycle': '8.4'}, {'cycle': '5.7'}])
    ((5, 7, 0), (8, 4, 0))
    """
    cycles = []
    for item in eol:
        if not isinstance(item, dict) or item.get('cycle') is None:
            continue
        cycle = str(item['cycle'])
        # endoflife.date names 166 of its 8444 cycles without a single digit
        # ("current", "subscription", "nodejs", ...). `version()` turns those into
        # (0, 0, 0) rather than raising, which would drag the lower bound to zero and
        # silently disable the "older than anything listed" verdict for that product.
        if not any(char.isdigit() for char in cycle):
            continue
        try:
            cycles.append(version(cycle))
        except (TypeError, ValueError):
            continue
    if not cycles:
        return None, None
    return min(cycles), max(cycles)


def version(ver, maxlen=3):
    """
    Parse a version string and return a comparable tuple.

    This function converts a (semantic) version string into a tuple of integers. Non-numeric
    characters (except for `.` and `-`) are ignored. Useful for comparing version numbers.

    Parameters
    ----------
    ver : str
        A version string (e.g., "v5.13.19-4-pve").
    maxlen : int, optional
        Desired tuple length. Defaults to `3`.

    Returns
    -------
    tuple
        A tuple of integers representing the version, e.g., `(5, 13, 19)`.

    Examples
    --------
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

    Parameters
    ----------
    ver : str
        A version string, e.g., `"Version v17.3.2.0"`.

    Returns
    -------
    float
        Version represented as a float.

    Raises
    ------
    ValueError
        If the input does not contain any digits.

    Examples
    --------
    >>> version2float('Version v17.3.2.0')
    17.32
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
