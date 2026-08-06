#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md


"""Provides information about the Linux distribution it runs on, such as a reliable
machine-readable distro ID and "os_family" (known from Ansible).

Source Code is taken, converted and modified from:
* lib/ansible/module_utils/facts/system/distribution.py

Deliberate differences to Ansible:
* Linux only. Ansible additionally handles AIX, Darwin, DragonFly, FreeBSD, HP-UX,
  NetBSD, OpenBSD and SunOS, all of which require shelling out.
* Purely functional, no classes.
* No external dependencies. Ansible derives its baseline facts from the `distro`
  package; they are read from /etc/os-release, /etc/lsb-release and the distro
  release files directly instead.
* Never shells out. Ansible asks `dpkg` for the release name of pre-8 Debian, and
  reads /etc/lsb-release through the `lsb_release` command. Where that command
  reports a release name the file does not carry, "distribution_release" ends up as
  "NA" here. Gentoo is one such case.
* Adds the "os_info" key, holding NAME plus VERSION from /etc/os-release.
"""

# The module is long because it carries one parser plus its docstring per supported
# distribution family; splitting it would separate the parsers from the table that
# dispatches to them.
# pylint: disable=C0302
# All release file parsers share one signature so that they can be dispatched from a
# single table, which leaves some of them with arguments they do not need.
# pylint: disable=W0613

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026080501'


import os
import platform
import re

# Characters Ansible strips off release file content before parsing it: a quote or
# backslash carries no meaning in any of the formats handled here.
STRIP_QUOTES = r'\'\"\\'


def _file_exists(path, allow_empty=False):
    """
    Check if a file exists and optionally allow empty files.

    This function verifies the existence of a file at the given path. If `allow_empty` is
    `False`, it additionally checks that the file is not empty.

    ### Parameters
    - **path** (`str`):
      Path to the file to check.
    - **allow_empty** (`bool`, optional):
      Whether to allow empty files as valid. Defaults to `False`.

    ### Returns
    - **bool**:
      `True` if the file exists (and is non-empty unless `allow_empty=True`), otherwise
      `False`.

    ### Example
    >>> _file_exists('/etc/os-release')
    True
    """
    if not os.path.isfile(path):
        return False
    if allow_empty:
        return True
    return os.path.getsize(path) > 0


def _get_file_content(path, default=None, strip=True):
    """
    Read the content of a text file, returning a default if that is not possible.

    Mirrors Ansible's `get_file_content`. Reading never raises: containers and jails
    regularly expose release files that look readable but are not.

    ### Parameters
    - **path** (`str`):
      Path to the file to read.
    - **default** (`any type`, optional):
      Value to return if the file cannot be read or is empty. Defaults to `None`.
    - **strip** (`bool`, optional):
      Whether to strip surrounding whitespace. Defaults to `True`.

    ### Returns
    - **str or any type**:
      The file contents, or `default` if the file is missing, unreadable or empty.

    ### Notes
    - Stripping matters for single-value files such as /etc/alpine-release, whose
      content is used as a version verbatim.

    ### Example
    >>> _get_file_content('/etc/alpine-release')
    '3.21.7'
    """
    if not os.path.isfile(path) or not os.access(path, os.R_OK):
        return default
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            data = f.read()
    except OSError:
        return default
    if strip:
        data = data.strip()
    return data if data else default


def _get_file_lines(path):
    """
    Read a text file and return its lines.

    ### Parameters
    - **path** (`str`):
      Path to the file to read.

    ### Returns
    - **list**:
      The lines of the file, or an empty list if it cannot be read.

    ### Example
    >>> _get_file_lines('/etc/debian_version')
    ['12.14']
    """
    data = _get_file_content(path)
    return data.splitlines() if data else []


# /usr/lib/os-release is the vendor copy and the only one present on image based
# distributions such as Clear Linux.
_OS_RELEASE_PATHS = ('/etc/os-release', '/usr/lib/os-release')


def _get_os_release_info():
    """
    Read the first available os-release file into a dictionary.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      The `KEY=value` pairs of the file, with keys lowercased and quotes stripped
      from the values. Empty if no os-release file can be read.

    ### Example
    >>> _get_os_release_info()
    {'name': 'Fedora Linux', 'version': '41 (Workstation Edition)', 'id': 'fedora', ...}
    """
    values = {}
    for path in _OS_RELEASE_PATHS:
        data = _get_file_content(path)
        if not data:
            continue
        for line in data.splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip().lower()] = value.strip().strip(STRIP_QUOTES)
        break
    return values


def _get_lsb_release_info():
    """
    Read /etc/lsb-release into a dictionary.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      The `KEY=value` pairs of the file, with keys lowercased and quotes stripped
      from the values. Empty if the file cannot be read.

    ### Notes
    - Ansible calls `lsb_release` here. Reading the file keeps this module free of
      subprocess calls and yields the same keys on every distribution that ships one.

    ### Example
    >>> _get_lsb_release_info()
    {'distrib_id': 'Ubuntu', 'distrib_release': '24.04', 'distrib_codename': 'noble', ...}
    """
    values = {}
    data = _get_file_content('/etc/lsb-release')
    if not data:
        return values
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip().lower()] = value.strip().strip(STRIP_QUOTES)
    return values


# Basenames that look like a release file but do not identify a distribution. Taken
# from the `distro` package Ansible uses. /etc/system-release is on it because it is
# a symlink whose content repeats the product name, which would otherwise end up
# being reported as the release name of Amazon Linux.
_DISTRO_RELEASE_IGNORE_BASENAMES = (
    'board-release',
    'debian_version',
    'ec2_version',
    'iredmail-release',
    'lsb-release',
    'oem-release',
    'os-release',
    'plesk-release',
    'system-release',
)

_DISTRO_RELEASE_BASENAME_REGEX = re.compile(r'\w+[-_](?:release|version)$')

# "Red Hat Enterprise Linux release 9.7 (Plow)" -> name, version, release name.
_DISTRO_RELEASE_REGEX = re.compile(
    r'^(?P<name>.+?)\s+(?:release|version)\s+'
    r'(?P<version>[\d.+\-a-z]*\d)'
    r'(?:\s+\((?P<codename>.+)\))?'
)


def _get_distro_release_info():
    """
    Extract name, version and release name from the first matching release file in /etc.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      Any of the keys `name`, `version` and `codename` that could be determined.
      Empty if no release file is readable or none of them parses.

    ### Notes
    - Replaces the release file handling of the `distro` package Ansible relies on.
      It is the only source of a release name on the Red Hat family, whose
      /etc/os-release carries no `VERSION_CODENAME`.
    - Candidates are sorted so that the result stays stable where a distribution
      ships several of them, for example Oracle Linux with /etc/oracle-release next
      to /etc/redhat-release.

    ### Example
    >>> _get_distro_release_info()
    {'name': 'Red Hat Enterprise Linux', 'version': '9.7', 'codename': 'Plow'}
    """
    try:
        basenames = sorted(
            basename
            for basename in os.listdir('/etc')
            if basename not in _DISTRO_RELEASE_IGNORE_BASENAMES
            and _DISTRO_RELEASE_BASENAME_REGEX.match(basename)
        )
    except OSError:
        return {}

    for basename in basenames:
        data = _get_file_content(os.path.join('/etc', basename))
        if not data:
            continue
        match = _DISTRO_RELEASE_REGEX.match(data.splitlines()[0])
        if not match:
            continue
        return {k: v for k, v in match.groupdict().items() if v}
    return {}


def _get_best_version(distro_id, version, release_info):
    """
    Refine the version of the two distributions whose os-release is too coarse.

    ### Parameters
    - **distro_id** (`str`):
      The lowercase distribution ID, as found in `ID=` of /etc/os-release.
    - **version** (`str`):
      The version determined so far.
    - **release_info** (`dict`):
      The result of `_get_distro_release_info()`.

    ### Returns
    - **str**:
      The refined version, or the version passed in if no better one is available.

    ### Notes
    - CentOS ships only the major version in /etc/os-release while admins expect
      `7.9`, and Debian omits the minor version there entirely (Debian bug #931197).
      Ansible special-cases exactly these two.

    ### Example
    >>> _get_best_version('debian', '12', {})
    '12.14'
    """
    if distro_id == 'centos':
        best = release_info.get('version', '')
        if best:
            return '.'.join(best.split('.')[:2])
    elif distro_id == 'debian':
        for line in _get_file_lines('/etc/debian_version'):
            # Testing and unstable hold a release name such as 'trixie/sid'.
            if re.match(r'^\d+\.\d+', line.strip()):
                return line.strip()
    return version


def _guess_distribution():
    """
    Provide baseline distribution facts before any release file is parsed.

    Combines /etc/os-release, /etc/lsb-release and the distro release files into the
    same four facts Ansible derives from the `distro` package. The release file
    parsers refine these afterwards.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      `distribution`, `distribution_version`, `distribution_release` and
      `distribution_major_version`. Unknown values are reported as `NA`.

    ### Notes
    - `distribution_release` is the release name (`Plow`, `noble`, `bookworm`), not
      the kernel release.

    ### Example
    >>> _guess_distribution()
    {'distribution': 'Redhat', 'distribution_version': '9.7', 'distribution_release':
    'Plow', 'distribution_major_version': '9'}
    """
    os_release = _get_os_release_info()
    lsb_release = _get_lsb_release_info()
    release_info = _get_distro_release_info()

    distro_id = os_release.get('id') or lsb_release.get('distrib_id', '').lower()

    # Ansible normalises these two so that the OS family map and the release file
    # varieties agree on one spelling.
    distribution = distro_id.capitalize()
    if distribution == 'Amzn':
        distribution = 'Amazon'
    elif distribution == 'Rhel':
        distribution = 'Redhat'
    elif not distribution:
        distribution = 'OtherLinux'

    version = (
        os_release.get('version_id')
        or lsb_release.get('distrib_release')
        or release_info.get('version')
        or ''
    )
    version = _get_best_version(distro_id, version, release_info)

    # Each step only applies if the previous key is absent altogether. An empty
    # VERSION_CODENAME is an answer in itself and has to survive, which is how
    # Fedora ends up with an empty release name instead of the one from
    # /etc/fedora-release.
    codename = os_release.get('version_codename')
    if codename is None:
        codename = os_release.get('ubuntu_codename')
    if codename is None and distro_id == 'ubuntu':
        codename = lsb_release.get('distrib_codename')
    if codename is None:
        codename = release_info.get('codename') or None

    guess = {
        'distribution': distribution,
        'distribution_version': version or 'NA',
        'distribution_release': 'NA' if codename is None else codename,
    }
    guess['distribution_major_version'] = (
        guess['distribution_version'].split('.')[0] or 'NA'
    )
    return guess


def _parse_distribution_file_alpine(name, data, path, collected_facts):
    """
    Parse /etc/alpine-release.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Notes
    - The file holds nothing but the version, so there is no marker to check for.

    ### Example
    >>> _parse_distribution_file_alpine('Alpine', '3.21.7', '/etc/alpine-release', {})
    (True, {'distribution': 'Alpine', 'distribution_version': '3.21.7'})
    """
    return True, {'distribution': 'Alpine', 'distribution_version': data}


def _parse_distribution_file_amazon(name, data, path, collected_facts):
    """
    Parse the Amazon Linux release files.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_amazon(
    ...     'Amazon', 'NAME="Amazon Linux"\\nVERSION_ID="2023"', '/etc/os-release', {}
    ... )
    (True, {'distribution': 'Amazon', 'distribution_version': '2023', ...})
    """
    if 'Amazon' not in data:
        return False, {}

    facts = {'distribution': 'Amazon'}
    if path == '/etc/os-release':
        version = re.search(r'VERSION_ID="(.*)"', data)
        if version:
            distribution_version = version.group(1)
            facts['distribution_version'] = distribution_version
            # Ansible unpacks into exactly two parts here and raises on anything
            # else. Slicing keeps a three part version from taking the lib down.
            version_data = distribution_version.split('.')
            facts['distribution_major_version'] = version_data[0]
            facts['distribution_minor_version'] = (
                version_data[1] if len(version_data) > 1 else 'NA'
            )
    else:
        version = [n for n in data.split() if n.isdigit()]
        facts['distribution_version'] = version[0] if version else 'NA'

    return True, facts


def _parse_distribution_file_centos(name, data, path, collected_facts):
    """
    Parse /etc/centos-release.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Notes
    - Plain CentOS reports no match on purpose, so that /etc/redhat-release gets a
      turn and picks the distribution name out of the file content.

    ### Example
    >>> _parse_distribution_file_centos(
    ...     'CentOS', 'CentOS Stream release 9', '/etc/centos-release', {}
    ... )
    (True, {'distribution_release': 'Stream'})
    """
    if 'CentOS Stream' in data:
        return True, {'distribution_release': 'Stream'}

    if 'TencentOS Server' in data:
        return True, {'distribution': 'TencentOS'}

    return False, {}


def _parse_distribution_file_clearlinux(name, data, path, collected_facts):
    """
    Parse the Clear Linux os-release file.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_clearlinux(
    ...     'ClearLinux', 'NAME="Clear Linux OS"', '/usr/lib/os-release', {}
    ... )
    (True, {'distribution': 'Clear Linux OS'})
    """
    if 'clearlinux' not in name.lower():
        return False, {}

    pname = re.search('NAME="(.*)"', data)
    if not pname or 'Clear Linux' not in pname.group(1):
        return False, {}

    facts = {'distribution': pname.group(1)}
    version = re.search('VERSION_ID=(.*)', data)
    if version:
        facts['distribution_major_version'] = version.group(1)
        facts['distribution_version'] = version.group(1)
    release = re.search('ID=(.*)', data)
    if release:
        facts['distribution_release'] = release.group(1)
    return True, facts


def _parse_distribution_file_coreos(name, data, path, collected_facts):
    """
    Parse /etc/coreos/update.conf.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_coreos(
    ...     'Coreos', 'GROUP=stable', '/etc/coreos/update.conf', {}
    ... )
    (True, {'distribution_release': 'stable'})
    """
    if collected_facts.get('distribution', '').lower() != 'coreos':
        return False, {}

    if not data:
        return False, {}

    facts = {}
    release = re.search('^GROUP=(.*)', data)
    if release:
        facts['distribution_release'] = release.group(1).strip('"')
    return True, facts


# One branch per derivative, mirroring Ansible. Splitting them up would hide the
# order in which the markers are tested, and that order is what tells the
# derivatives apart.
# pylint: disable-next=R0912,R0915
def _parse_distribution_file_debian(name, data, path, collected_facts):
    """
    Parse the release files of the Debian family.

    Covers Debian and its derivatives, all of which are told apart by markers in
    /etc/os-release or /etc/lsb-release rather than by a file of their own.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Notes
    - Reports no match for anything it does not recognise. Without that, every
      os-release based distribution would be classified as Debian.

    ### Example
    >>> _parse_distribution_file_debian(
    ...     'Debian', 'NAME="Ubuntu"', '/etc/os-release', {}
    ... )
    (True, {'distribution': 'Ubuntu'})
    """
    facts = {}
    if any(distro in data for distro in ('Debian', 'Raspbian')):
        facts['distribution'] = 'Debian'
        release = re.search(r'PRETTY_NAME=[^(]+ \(?([^)]+?)\)', data)
        if release:
            facts['distribution_release'] = release.group(1)
        # Ansible falls back to `dpkg --status tzdata` when neither lsb-release nor
        # os-release name the release. Skipped: this module does not shell out, and
        # every Debian since 8 ships VERSION_CODENAME in /etc/os-release.
        for line in _get_file_lines('/etc/debian_version'):
            m = re.search(r'(\d+)\.(\d+)', line.strip())
            if m:
                facts['distribution_minor_version'] = m.group(2)
    elif 'Ubuntu' in data:
        facts['distribution'] = 'Ubuntu'
        # Nothing else to do, Ubuntu names its release in /etc/os-release.
    elif 'SteamOS' in data:
        facts['distribution'] = 'SteamOS'
    elif path in ('/etc/lsb-release', '/etc/os-release') and (
        'Kali' in data or 'Parrot' in data
    ):
        if 'Kali' in data:
            # Kali does not provide /etc/lsb-release anymore.
            facts['distribution'] = 'Kali'
        else:
            facts['distribution'] = 'Parrot'
        release = re.search('DISTRIB_RELEASE=(.*)', data)
        if release:
            facts['distribution_release'] = release.group(1)
    elif 'Devuan' in data:
        facts['distribution'] = 'Devuan'
        release = re.search(r'PRETTY_NAME="?[^("]+ \(?([^) "]+)\)?', data)
        if release:
            facts['distribution_release'] = release.group(1)
        version = re.search(r'VERSION_ID="(.*)"', data)
        if version:
            facts['distribution_version'] = version.group(1)
            facts['distribution_major_version'] = version.group(1)
    elif 'Cumulus' in data:
        facts['distribution'] = 'Cumulus Linux'
        version = re.search(r'VERSION_ID=(.*)', data)
        if version:
            facts['distribution_version'] = version.group(1)
            facts['distribution_major_version'] = version.group(1).split('.')[0]
        release = re.search(r'VERSION="(.*)"', data)
        if release:
            facts['distribution_release'] = release.group(1)
    elif 'Mint' in data:
        facts['distribution'] = 'Linux Mint'
        version = re.search(r'VERSION_ID="(.*)"', data)
        if version:
            facts['distribution_version'] = version.group(1)
            facts['distribution_major_version'] = version.group(1).split('.')[0]
    elif 'UOS' in data or 'Uos' in data or 'uos' in data:
        # The RHEL based UnionTech OS Server variants carry a PLATFORM_ID and are
        # handled by _parse_distribution_file_uniontech. Skipping them here keeps
        # them from being mistaken for the Debian based Uos.
        if re.search(r'PLATFORM_ID="?platform:uel', data):
            return False, facts
        facts['distribution'] = 'Uos'
        release = re.search(r'VERSION_CODENAME="?([^"]+)"?', data)
        if release:
            facts['distribution_release'] = release.group(1)
        version = re.search(r'VERSION_ID="(.*)"', data)
        if version:
            facts['distribution_version'] = version.group(1)
            facts['distribution_major_version'] = version.group(1).split('.')[0]
    elif 'Deepin' in data or 'deepin' in data:
        facts['distribution'] = 'Deepin'
        release = re.search(r'VERSION_CODENAME="?([^"]+)"?', data)
        if release:
            facts['distribution_release'] = release.group(1)
        version = re.search(r'VERSION_ID="(.*)"', data)
        if version:
            facts['distribution_version'] = version.group(1)
            facts['distribution_major_version'] = version.group(1).split('.')[0]
    elif 'LMDE' in data:
        facts['distribution'] = 'Linux Mint Debian Edition'
    else:
        return False, facts

    return True, facts


def _parse_distribution_file_flatcar(name, data, path, collected_facts):
    """
    Parse the Flatcar os-release file.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_flatcar(
    ...     'Flatcar',
    ...     'VERSION="3975.2.0"',
    ...     '/etc/os-release',
    ...     {'distribution': 'Flatcar'},
    ... )
    (True, {'distribution_major_version': '3975', 'distribution_version': '3975.2.0'})
    """
    if collected_facts.get('distribution', '').lower() != 'flatcar':
        return False, {}

    if not data:
        return False, {}

    facts = {}
    version = re.search('VERSION=(.*)', data)
    if version:
        facts['distribution_major_version'] = version.group(1).strip('"').split('.')[0]
        facts['distribution_version'] = version.group(1).strip('"')
    return True, facts


def _parse_distribution_file_mandriva(name, data, path, collected_facts):
    """
    Parse the Mandriva lsb-release file.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_mandriva(
    ...     'Mandriva', 'DISTRIB_ID=Mandriva', '/etc/lsb-release', {}
    ... )
    (True, {'distribution': 'Mandriva'})
    """
    if 'Mandriva' not in data:
        return False, {}

    facts = {'distribution': name}
    version = re.search('DISTRIB_RELEASE="(.*)"', data)
    if version:
        facts['distribution_version'] = version.group(1)
    release = re.search('DISTRIB_CODENAME="(.*)"', data)
    if release:
        facts['distribution_release'] = release.group(1)
    return True, facts


def _parse_distribution_file_na(name, data, path, collected_facts):
    """
    Parse an os-release file of a distribution without dedicated handling.

    This is the generic fallback at the end of `OSDIST_LIST`. It takes the
    distribution name from `NAME=` and, if nothing better was found, the version
    from `VERSION=`.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_na(
    ...     'NA', 'NAME="Gentoo"', '/etc/os-release', {'distribution_version': 'NA'}
    ... )
    (True, {'distribution': 'Gentoo'})
    """
    facts = {}
    for line in data.splitlines():
        distribution = re.search('^NAME=(.*)', line)
        if distribution and name == 'NA':
            facts['distribution'] = distribution.group(1).strip(STRIP_QUOTES)
        version = re.search('^VERSION=(.*)', line)
        if version and collected_facts.get('distribution_version') == 'NA':
            facts['distribution_version'] = version.group(1).strip(STRIP_QUOTES)
    return True, facts


def _parse_distribution_file_openwrt(name, data, path, collected_facts):
    """
    Parse /etc/openwrt_release.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_openwrt(
    ...     'OpenWrt', 'DISTRIB_RELEASE="23.05.5"', '/etc/openwrt_release', {}
    ... )
    (True, {'distribution': 'OpenWrt', 'distribution_version': '23.05.5'})
    """
    if 'OpenWrt' not in data:
        return False, {}

    facts = {'distribution': name}
    version = re.search('DISTRIB_RELEASE="(.*)"', data)
    if version:
        facts['distribution_version'] = version.group(1)
    release = re.search('DISTRIB_CODENAME="(.*)"', data)
    if release:
        facts['distribution_release'] = release.group(1)
    return True, facts


def _parse_distribution_file_slackware(name, data, path, collected_facts):
    """
    Parse /etc/slackware-version.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_slackware(
    ...     'Slackware', 'Slackware 15.0', '/etc/slackware-version', {}
    ... )
    (True, {'distribution': 'Slackware', 'distribution_version': '15.0'})
    """
    if 'Slackware' not in data:
        return False, {}

    facts = {'distribution': name}
    version = re.findall(r'\w+[.]\w+\+?', data)
    if version:
        facts['distribution_version'] = version[0]
    return True, facts


# Two file formats and three variant detections in one function, mirroring Ansible.
# pylint: disable-next=R0912
def _parse_distribution_file_suse(name, data, path, collected_facts):
    """
    Parse the release files of the SUSE family.

    Handles both the modern /etc/os-release and the /etc/SuSE-release of SLES 11 and
    older, and recognises the SLES for SAP and SUSE Linux Micro variants.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Example
    >>> _parse_distribution_file_suse(
    ...     'SUSE', 'NAME="openSUSE Leap"\\nVERSION_ID="16.0"', '/etc/os-release', {}
    ... )
    (True, {'distribution': 'openSUSE Leap', 'distribution_version': '16.0', ...})
    """
    if 'suse' not in data.lower():
        return False, {}

    facts = {}
    if path == '/etc/os-release':
        for line in data.splitlines():
            distribution = re.search('^NAME=(.*)', line)
            if distribution:
                facts['distribution'] = distribution.group(1).strip('"')
            # Example patterns are 13.04, 13.0 and 13.
            version = re.search(r'^VERSION_ID="?([0-9]+\.?[0-9]*)"?', line)
            if version:
                facts['distribution_version'] = version.group(1)
                facts['distribution_major_version'] = version.group(1).split('.')[0]
            if 'open' in data.lower():
                release = re.search(r'^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                if release:
                    facts['distribution_release'] = release.group(1)
            elif 'enterprise' in data.lower() and 'VERSION_ID' in line:
                # SLES has no release names, so the minor version stands in for one.
                release = re.search(r'^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                # Ansible dereferences the match unconditionally here, which trips
                # over a non numeric VERSION_ID.
                if release and release.group(1):
                    facts['distribution_release'] = release.group(1)
                else:
                    facts['distribution_release'] = '0'
    elif path == '/etc/SuSE-release':
        lines = data.splitlines()
        if 'open' in data.lower():
            facts['distribution'] = lines[0].split()[0]
            for line in lines:
                release = re.search('CODENAME *= *([^\n]+)', line)
                if release:
                    facts['distribution_release'] = release.group(1).strip()
        elif 'enterprise' in data.lower():
            if 'Server' in data:
                facts['distribution'] = 'SLES'
            elif 'Desktop' in data:
                facts['distribution'] = 'SLED'
            for line in lines:
                release = re.search('PATCHLEVEL = ([0-9]+)', line)
                if release:
                    facts['distribution_release'] = release.group(1)
                    facts['distribution_version'] = (
                        collected_facts.get('distribution_version', 'NA')
                        + '.'
                        + release.group(1)
                    )

    # VARIANT_ID marks SLES for SAP and SUSE Linux Micro.
    variant_id_match = re.search(r'^VARIANT_ID="?([^"\n]*)"?', data, re.MULTILINE)
    if variant_id_match:
        variant_id = variant_id_match.group(1)
        if variant_id in ('server-sap', 'sles-sap'):
            facts['distribution'] = 'SLES_SAP'
        elif variant_id == 'transactional':
            facts['distribution'] = 'SL-Micro'
    elif os.path.islink('/etc/products.d/baseproduct'):
        # Older SLES 15 has no VARIANT_ID and is told apart by the baseproduct link.
        resolved = os.path.realpath('/etc/products.d/baseproduct')
        if resolved.endswith('SLES_SAP.prod'):
            facts['distribution'] = 'SLES_SAP'
        elif resolved.endswith('SL-Micro.prod'):
            facts['distribution'] = 'SL-Micro'

    return True, facts


def _parse_distribution_file_uniontech(name, data, path, collected_facts):
    """
    Parse the release files of UnionTech OS Server.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`): Whether the file was parsed, plus the parsed facts.

    ### Notes
    - Only the RHEL based UOS Server is claimed here. The Debian based UOS Desktop
      carries no `PLATFORM_ID` and is left to `_parse_distribution_file_debian`.

    ### Example
    >>> _parse_distribution_file_uniontech(
    ...     'UnionTech',
    ...     'UnionTech OS Server release 20 (kongzi)',
    ...     '/etc/redhat-release',
    ...     {},
    ... )
    (True, {'distribution': 'UnionTech', 'distribution_release': 'kongzi', ...})
    """
    is_uos_release_file = bool(
        re.search(r'(UnionTech OS Server|UOS Server) release', data)
    )
    has_uel_platform_id = bool(re.search(r'PLATFORM_ID="?platform:uel', data))
    if not (is_uos_release_file or has_uel_platform_id):
        return False, {}

    facts = {'distribution': 'UnionTech'}
    release = re.search(r'VERSION_CODENAME="?([^"\n]+)"?', data)
    if release:
        facts['distribution_release'] = release.group(1)
    else:
        # /etc/redhat-release style: "UnionTech OS Server release 20 (kongzi)".
        release = re.search(r'release\s+\S+\s+\(([^)]+)\)', data)
        if release:
            facts['distribution_release'] = release.group(1)

    version = re.search(r'VERSION_ID="?([^"\n]+)"?', data)
    if not version:
        version = re.search(r'release\s+(\S+)', data)
    if version:
        facts['distribution_version'] = version.group(1)
        facts['distribution_major_version'] = version.group(1).split('.')[0]
    return True, facts


# Distributions whose release file is recognised by a marker string rather than by a
# parser. If the marker is absent, the first word of the file becomes the
# distribution name, which is how Scientific Linux and friends are picked up from
# /etc/redhat-release.
SEARCH_STRING = {
    'Altlinux': 'ALT',
    'OracleLinux': 'Oracle Linux',
    'RedHat': 'Red Hat',
    'SMGL': 'Source Mage GNU/Linux',
}

# Kept apart from SEARCH_STRING: a match on one of its keys falls back to the first
# word of the file, which for an os-release file is the useless 'NAME=Arch'.
OS_RELEASE_ALIAS = {
    'Archlinux': 'Arch Linux',
}

# Every name in OSDIST_LIST must either be listed in SEARCH_STRING or
# OS_RELEASE_ALIAS, carry allowempty, or have a parser here. Gentoo is the one
# exception: Ansible has no parser for it either, and it is picked up by the generic
# 'NA' entry at the end of OSDIST_LIST.
_DIST_FILE_PARSERS = {
    'Alpine': _parse_distribution_file_alpine,
    'Amazon': _parse_distribution_file_amazon,
    'CentOS': _parse_distribution_file_centos,
    'ClearLinux': _parse_distribution_file_clearlinux,
    'Coreos': _parse_distribution_file_coreos,
    'Debian': _parse_distribution_file_debian,
    'Flatcar': _parse_distribution_file_flatcar,
    'Mandriva': _parse_distribution_file_mandriva,
    'NA': _parse_distribution_file_na,
    'OpenWrt': _parse_distribution_file_openwrt,
    'SUSE': _parse_distribution_file_suse,
    'Slackware': _parse_distribution_file_slackware,
    'UnionTech': _parse_distribution_file_uniontech,
}


def _parse_dist_file(name, data, path, collected_facts):
    """
    Dispatch a release file to the parser responsible for it.

    ### Parameters
    - **name** (`str`):
      The variety name from `OSDIST_LIST`.
    - **data** (`str`):
      The contents of the release file.
    - **path** (`str`):
      The path the content was read from.
    - **collected_facts** (`dict`):
      The facts gathered so far.

    ### Returns
    - **tuple** (`bool`, `dict`):
      - First element: `True` if the file belongs to this variety, `False` otherwise.
      - Second element: The parsed facts.

    ### Notes
    - A variety without a parser reports no match, which lets `_process_dist_files`
      move on to the next candidate.

    ### Example
    >>> _parse_dist_file(
    ...     'RedHat',
    ...     'Red Hat Enterprise Linux release 9.7 (Plow)',
    ...     '/etc/redhat-release',
    ...     {},
    ... )
    (True, {'distribution': 'RedHat', 'distribution_file_search_string': 'Red Hat'})
    """
    facts = {}
    data = data.strip(STRIP_QUOTES)

    if name in SEARCH_STRING:
        if SEARCH_STRING[name] in data:
            # Sets distribution=RedHat if 'Red Hat' shows up in the data.
            facts['distribution'] = name
            facts['distribution_file_search_string'] = SEARCH_STRING[name]
        elif data.split():
            # Sets distribution to what is in the data, for example CentOS.
            facts['distribution'] = data.split()[0]
        return True, facts

    if name in OS_RELEASE_ALIAS:
        if OS_RELEASE_ALIAS[name] in data:
            facts['distribution'] = name
            return True, facts
        return False, facts

    parser = _DIST_FILE_PARSERS.get(name)
    if parser is None:
        return False, facts
    return parser(name, data, path, collected_facts)


# Order matters and is not alphabetical: the first entry that parses wins. Oracle
# Linux has to come before Red Hat because it ships a /etc/redhat-release naming Red
# Hat, and UnionTech before Red Hat because its A-version symlinks redhat-release to
# uos-release. The generic 'NA' entry has to stay last.
OSDIST_LIST = (
    {'path': '/etc/altlinux-release', 'name': 'Altlinux'},
    {'path': '/etc/oracle-release', 'name': 'OracleLinux'},
    {'path': '/etc/slackware-version', 'name': 'Slackware'},
    {'path': '/etc/centos-release', 'name': 'CentOS'},
    {'path': '/etc/redhat-release', 'name': 'UnionTech'},
    {'path': '/etc/redhat-release', 'name': 'RedHat'},
    {'path': '/etc/vmware-release', 'name': 'VMwareESX', 'allowempty': True},
    {'path': '/etc/openwrt_release', 'name': 'OpenWrt'},
    {'path': '/etc/os-release', 'name': 'Amazon'},
    {'path': '/etc/system-release', 'name': 'Amazon'},
    {'path': '/etc/alpine-release', 'name': 'Alpine'},
    {'path': '/etc/arch-release', 'name': 'Archlinux', 'allowempty': True},
    {'path': '/etc/os-release', 'name': 'Archlinux'},
    {'path': '/etc/os-release', 'name': 'SUSE'},
    {'path': '/etc/SuSE-release', 'name': 'SUSE'},
    {'path': '/etc/gentoo-release', 'name': 'Gentoo'},
    {'path': '/etc/os-release', 'name': 'UnionTech'},
    {'path': '/etc/os-release', 'name': 'Debian'},
    {'path': '/etc/lsb-release', 'name': 'Debian'},
    {'path': '/etc/lsb-release', 'name': 'Mandriva'},
    {'path': '/etc/sourcemage-release', 'name': 'SMGL'},
    {'path': '/usr/lib/os-release', 'name': 'ClearLinux'},
    {'path': '/etc/coreos/update.conf', 'name': 'Coreos'},
    {'path': '/etc/os-release', 'name': 'Flatcar'},
    {'path': '/etc/os-release', 'name': 'NA'},
)


def _process_dist_files():
    """
    Walk the known release files and collect distribution facts from the first match.

    Starts from the baseline facts of `_guess_distribution()` and refines them with
    whatever the matching release file parser reports.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      The collected facts, including `distribution_file_path` and
      `distribution_file_variety` if a release file matched.

    ### Example
    >>> _process_dist_files()
    {'distribution': 'RedHat', 'distribution_version': '9.7', 'distribution_release':
    'Plow', 'distribution_major_version': '9', 'distribution_file_path':
    '/etc/redhat-release', 'distribution_file_variety': 'RedHat', ...}
    """
    facts = _guess_distribution()

    for entry in OSDIST_LIST:
        name = entry['name']
        path = entry['path']
        allow_empty = entry.get('allowempty', False)

        if not _file_exists(path, allow_empty=allow_empty):
            continue

        # An empty file is a marker in itself, for example an Archlinux with an
        # empty /etc/arch-release next to an /etc/os-release naming something else.
        if allow_empty:
            facts['distribution'] = name
            facts['distribution_file_path'] = path
            facts['distribution_file_variety'] = name
            break

        data = _get_file_content(path)
        if data is None:
            continue

        parsed, parsed_facts = _parse_dist_file(name, data, path, facts)
        if not parsed:
            continue

        facts['distribution'] = name
        facts['distribution_file_path'] = path
        # distribution and file variety are the same here, but the parsers below
        # may replace distribution with a more specific name, for example
        # distribution=Fedora with distribution_file_variety=RedHat.
        facts['distribution_file_variety'] = name
        facts['distribution_file_parsed'] = parsed
        facts.update(parsed_facts)
        break

    return facts


# Keys and members are kept in sync with the Ansible Conditionals documentation, so
# that "os_family" means the same thing here as in a playbook. Non-Linux families are
# left out because this module never reports them.
OS_FAMILY_MAP = {
    'Alpine': ['Alpine'],
    'Altlinux': ['Altlinux'],
    'Archlinux': ['Antergos', 'Archlinux', 'Manjaro'],
    'ClearLinux': ['Clear Linux Mix', 'Clear Linux OS'],
    'Debian': [
        'Cumulus Linux',
        'Debian',
        'Deepin',
        'Devuan',
        'KDE neon',
        'Kali',
        'Linux Mint',
        'Linux Mint Debian Edition',
        'Neon',
        'OSMC',
        'Pardus GNU/Linux',
        'Parrot',
        'Pop!_OS',
        'Raspbian',
        'SteamOS',
        'Ubuntu',
        'Univention Corporate Server',
        'Uos',
    ],
    'Gentoo': ['Funtoo', 'Gentoo'],
    'Mandrake': ['Mandrake', 'Mandriva'],
    'RedHat': [
        'Alibaba',
        'AlmaLinux',
        'Amazon',
        'Amzn',
        'Ascendos',
        'CentOS',
        'CloudLinux',
        'EuroLinux',
        'EulerOS',
        'Fedora',
        'Kylin Linux Advanced Server',
        'MIRACLE',
        'OEL',
        'OVS',
        'OracleLinux',
        'PSBM',
        'RHEL',
        'RedHat',
        'Rocky',
        'SLC',
        'Scientific',
        'TencentOS',
        'UnionTech',
        'Virtuozzo',
        'XenServer',
        'openEuler',
    ],
    'SMGL': ['SMGL'],
    'Slackware': ['Slackware'],
    'Suse': [
        'ALP-Dolomite',
        'SLED',
        'SLES',
        'SLES_SAP',
        'SL-Micro',
        'SUSE_LINUX',
        'SuSE',
        'openSUSE',
        'openSUSE Leap',
        'openSUSE MicroOS',
        'openSUSE Tumbleweed',
    ],
}

# Flattened for lookup. No distribution appears in more than one family.
_OS_FAMILY = {
    member: family for family, members in OS_FAMILY_MAP.items() for member in members
}


def _map_os_family(distribution):
    """
    Map a detected distribution to its OS family.

    ### Parameters
    - **distribution** (`str`):
      The detected distribution name.

    ### Returns
    - **str**:
      The mapped OS family name, or the distribution itself if it has no family.

    ### Example
    >>> _map_os_family('Fedora')
    'RedHat'
    """
    return _OS_FAMILY.get(distribution) or distribution


def get_distribution_facts():
    """
    Detect the Linux distribution and return normalized facts.

    Collects detailed information about the Linux distribution based on release files,
    and assigns a standardized OS family name.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      Dictionary of collected distribution facts:
      - `distribution`
      - `distribution_version`
      - `distribution_release`
      - `distribution_major_version`
      - `distribution_minor_version` (only for some distributions)
      - `distribution_file_path` (only if a release file matched)
      - `distribution_file_variety` (only if a release file matched)
      - `distribution_file_search_string` (only if a marker string matched)
      - `distribution_file_parsed` (only if a release file matched)
      - `os_family`
      - `os_info` (only if /etc/os-release is readable)

    ### Notes
    - All keys except `os_info` carry the same meaning as the `ansible_facts` of the
      same name. In particular, `distribution_release` is the release name such as
      `Plow` or `noble`, not the kernel release.
    - On anything other than Linux, only the `platform` module is consulted.

    ### Example
    >>> get_distribution_facts()
    {'distribution': 'Fedora', 'distribution_version': '41', 'distribution_release':
    'NA', 'distribution_major_version': '41', 'distribution_file_path':
    '/etc/redhat-release', 'distribution_file_variety': 'RedHat',
    'distribution_file_parsed': True, 'os_family': 'RedHat', 'os_info':
    'Fedora Linux 41 (Workstation Edition)'}
    """
    # The platform module provides a baseline for systems this module does not
    # otherwise know about.
    system = platform.system()
    facts = {
        'distribution': system,
        'distribution_release': platform.release(),
        'distribution_version': platform.version(),
    }

    if system == 'Linux':
        facts.update(_process_dist_files())

    facts['os_family'] = _map_os_family(facts['distribution'])

    # Not an Ansible fact: a human readable name, for example
    # 'Fedora Linux 41 (Workstation Edition)'.
    values = _get_os_release_info()
    os_info = ' '.join(
        part for part in (values.get('name'), values.get('version')) if part
    )
    if os_info:
        facts['os_info'] = os_info

    return facts
