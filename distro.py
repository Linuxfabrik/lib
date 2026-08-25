#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md


"""Provides information about the Linux distribution it runs on, such as a reliable
machine-readable distro ID and "os_family" (known from Ansible).

Source Code is taken, converted and modified from:
* lib/ansible/module_utils/facts/system/distribution.py

Deliberate differences to Ansible:
* Linux only. Ansible additionally handles AIX, Darwin, DragonFly, FreeBSD, HP-UX,
  NetBSD, OpenBSD and SunOS, all of which require shelling out. On anything other
  than Linux this module reports Ansible's bare baseline: "distribution" is what
  platform.system() says, "distribution_release" is the kernel release,
  "distribution_version" is the kernel version, and there is no
  "distribution_major_version" at all.
* Purely functional, no classes.
* No external dependencies. Ansible derives its baseline facts from the `distro`
  package; they are read from /etc/os-release, /etc/lsb-release and the distro
  release files directly instead.
* Never shells out. Ansible asks `dpkg` for the release name of pre-8 Debian, and
  reaches /etc/lsb-release through the `lsb_release` command rather than reading the
  file. That cuts both ways, and it is not only about the release name: Gentoo and
  Arch report "NA" here where the command would say "n/a", and Debian 7 reports the
  version of /etc/os-release where the command would report the more precise one.
  The other way round, Flatcar reports the release name "Oklo" here, which the
  command does not know about because Flatcar does not ship it.
* A release file line naming no "release" keyword only yields a version if that
  version is purely numeric. The `distro` package accepts any lowercase token there
  and consequently reads the version "64-pc-linux-gnu" out of the Source Mage line
  "Source Mage GNU/Linux x86_64-pc-linux-gnu".
* A release file whose first line yields neither a version nor a release name is
  skipped and the next candidate in /etc is tried. The `distro` package takes any
  non-empty first line as the distribution name and stops searching there.
* /etc/debian_version only counts as a version if it holds one. On testing and
  unstable it holds a release name such as "trixie/sid", which the `distro` package
  reports as the version.
* "distribution_major_version" is derived from "distribution_version" where a
  release file parser was the first to find one, as on an Amazon Linux recognised
  through /etc/system-release. Ansible has its major version from the `distro`
  package by then and leaves "NA" standing in that case.
* Never raises where Ansible raises. A three part Amazon VERSION_ID, a non numeric
  SLES VERSION_ID, a Cumulus VERSION_ID that is not exactly three parts, a release
  file holding nothing but whitespace, and an openSUSE that ships /etc/SuSE-release
  without an /etc/os-release each take Ansible down with a ValueError,
  AttributeError, IndexError or TypeError.
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
__version__ = '2026080602'


import os
import platform
import re

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

# Kept apart from SEARCH_STRING: a match on one of its keys falls back to the first
# word of the file, which for an os-release file is the useless 'NAME=Arch'.
OS_RELEASE_ALIAS = {
    'Archlinux': 'Arch Linux',
}

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

# Characters Ansible strips off release file content before parsing it: a quote or
# backslash carries no meaning in any of the formats handled here.
STRIP_QUOTES = r'\'\"\\'

# Basenames that qualify as a release file, such as "rocky-release", "SuSE-release"
# or "slackware-version". The captured word doubles as a distribution ID where no
# other source names one.
_DISTRO_RELEASE_BASENAME_REGEX = re.compile(r'(\w+)[-_](?:release|version)$')

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

# /usr/lib/os-release is the vendor copy and the only one present on image based
# distributions such as Clear Linux.
_OS_RELEASE_PATHS = ('/etc/os-release', '/usr/lib/os-release')

# Release file content naming no "release" keyword, as in "SUSE Linux Enterprise
# Server 11 (x86_64)" or "Ubuntu 20.04.1 LTS". Only a purely numeric version is
# accepted here. The `distro` package allows any lowercase token, which makes it read
# the version "64-pc-linux-gnu" out of "Source Mage GNU/Linux x86_64-pc-linux-gnu".
_RELEASE_CONTENT_NO_KEYWORD_REGEX = re.compile(
    r'^(?P<name>.+?)\s+'
    r'(?P<version>\d+(?:\.\d+)*)'
    r'(?:\s+LTS)?'
    r'(?:\s+\((?P<codename>[^)]*)\))?\s*$'
)

# Release file content naming a "release" or "version" keyword, as in
# "Red Hat Enterprise Linux release 9.7 (Plow)" -> name, version, release name.
_RELEASE_CONTENT_REGEX = re.compile(
    r'^(?P<name>.+?)\s+(?:release|version)\s+'
    r'(?P<version>[\d.+\-a-z]*\d)'
    r'(?:\s+LTS)?'
    r'(?:\s+\((?P<codename>[^)]*)\))?'
)


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


def _get_best_version(distro_id, candidates):
    """
    Pick the most precise version out of the candidates.

    ### Parameters
    - **distro_id** (`str`):
      The lowercase distribution ID, as found in `ID=` of /etc/os-release.
    - **candidates** (`list`):
      The result of `_get_version_candidates()`.

    ### Returns
    - **str**:
      The most precise version, or an empty string if there is no candidate.

    ### Notes
    - CentOS ships only the major version in /etc/os-release while admins expect
      `7.9`, and Debian omits the minor version there entirely (Debian bug #931197).
      Ansible asks the `distro` package for its "best" version for exactly these
      two, which is the candidate carrying the most dots.
    - /etc/debian_version only counts as a candidate if it holds a version. Testing
      and unstable hold a release name such as `trixie/sid` there, which the `distro`
      package happily reports as the version.

    ### Example
    >>> _get_best_version('debian', ['12'])
    '12.14'
    """
    if distro_id == 'debian':
        candidates = candidates + [
            line.strip()
            for line in _get_file_lines('/etc/debian_version')
            if re.match(r'^\d+\.\d+', line.strip())
        ]

    best = ''
    for candidate in candidates:
        if best == '' or candidate.count('.') > best.count('.'):
            best = candidate

    if distro_id == 'centos':
        return '.'.join(best.split('.')[:2])
    return best


def _get_codename(distro_id, os_release, lsb_release, release_info):
    """
    Determine the release name, asking every source in the order Ansible does.

    ### Parameters
    - **distro_id** (`str`):
      The lowercase distribution ID, as found in `ID=` of /etc/os-release.
    - **os_release** (`dict`):
      The result of `_get_os_release_info()`.
    - **lsb_release** (`dict`):
      The result of `_get_lsb_release_info()`.
    - **release_info** (`dict`):
      The result of `_get_distro_release_info()`.

    ### Returns
    - **str or None**:
      The release name, or `None` if no source carries one.

    ### Notes
    - The order is `VERSION_CODENAME`, `UBUNTU_CODENAME`, /etc/lsb-release for
      Ubuntu, whatever `VERSION` of /etc/os-release stands for, /etc/lsb-release for
      everyone else, and finally the release file.
    - An empty release name is an answer in itself and survives the first two steps.

    ### Example
    >>> _get_codename('kali', {}, {'distrib_codename': 'kali-rolling'}, {})
    'kali-rolling'
    """
    codename = os_release.get('version_codename')
    if codename is None:
        codename = os_release.get('ubuntu_codename')
    if codename is None and distro_id == 'ubuntu':
        codename = lsb_release.get('distrib_codename')
    if codename is not None:
        return codename

    codename = _get_os_release_codename(os_release)
    if codename is None:
        codename = (
            lsb_release.get('distrib_codename') or release_info.get('codename') or ''
        )
    return codename or None


# Translation tables the `distro` package applies to the distribution ID, one per
# source it reads the ID from. The lookup key is the value lowercased with blanks
# turned into underscores; anything not listed passes through unchanged.
_NORMALIZED_DISTRO_ID = {
    # RHEL 6 and 7, whose ID is derived from the /etc/redhat-release basename.
    'redhat': 'rhel',
}
_NORMALIZED_LSB_ID = {
    'enterpriseenterpriseas': 'oracle',  # Oracle Enterprise Linux 4
    'enterpriseenterpriseserver': 'oracle',  # Oracle Linux 5
    'redhatenterprisecomputenode': 'rhel',  # RHEL 6 ComputeNode
    'redhatenterpriseserver': 'rhel',  # RHEL 6 and 7 Server
    'redhatenterpriseworkstation': 'rhel',  # RHEL 6 and 7 Workstation
}
_NORMALIZED_OS_ID = {
    'ol': 'oracle',  # Oracle Linux
    'opensuse-leap': 'opensuse',  # Newer openSUSE releases report opensuse-leap
}


def _get_distro_id(os_release, lsb_release, release_info):
    """
    Determine the distribution ID, asking every source in the order Ansible does.

    ### Parameters
    - **os_release** (`dict`):
      The result of `_get_os_release_info()`.
    - **lsb_release** (`dict`):
      The result of `_get_lsb_release_info()`.
    - **release_info** (`dict`):
      The result of `_get_distro_release_info()`.

    ### Returns
    - **str**:
      The lowercase distribution ID, or an empty string if no source names one.

    ### Notes
    - The order is `ID` of /etc/os-release, `DISTRIB_ID` of /etc/lsb-release and the
      basename of the release file. Each source has its own translation table, so
      that a distribution ends up under one ID no matter which of them answered.
    - The release file is what gives RHEL 6, CentOS 6 and SLES 11 an ID at all. None
      of them ships an /etc/os-release.
    - `distro.id()` has a fourth source, `uname -rs`. It is left out, which is no
      difference in practice: the `distro` package discards that output as soon as
      the system name is `Linux`.

    ### Example
    >>> _get_distro_id({}, {}, {'id': 'redhat'})
    'rhel'
    """
    for value, table in (
        (os_release.get('id', ''), _NORMALIZED_OS_ID),
        (lsb_release.get('distrib_id', ''), _NORMALIZED_LSB_ID),
        (release_info.get('id', ''), _NORMALIZED_DISTRO_ID),
    ):
        if value:
            value = value.lower().replace(' ', '_')
            return table.get(value, value)
    return ''


def _get_distro_release_info():
    """
    Extract ID, name, version and release name from the first matching release file.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      Any of the keys `id`, `name`, `version` and `codename` that could be
      determined. Empty if no release file in /etc is readable or none of them
      parses.

    ### Notes
    - Replaces the release file handling of the `distro` package Ansible relies on.
    - Candidates are sorted so that the result stays stable where a distribution
      ships several of them, for example Oracle Linux with /etc/oracle-release next
      to /etc/redhat-release.

    ### Example
    >>> _get_distro_release_info()
    {'name': 'Red Hat Enterprise Linux', 'version': '9.7', 'codename': 'Plow',
    'id': 'redhat'}
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
        # A file carrying no version, such as the os-release formatted
        # /etc/centos-release of TencentOS, states nothing worth reporting.
        info = _parse_release_content(data.splitlines()[0])
        if not info:
            continue
        info['id'] = _DISTRO_RELEASE_BASENAME_REGEX.match(basename).group(1)
        if 'cloudlinux' in info.get('name', '').lower():
            # CloudLinux before 7 names itself in an /etc/redhat-release, which would
            # otherwise leave it with the ID of Red Hat.
            info['id'] = 'cloudlinux'
        return info
    return {}


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
    - Ansible runs `lsb_release -a` here and never looks at the file. Reading the
      file keeps this module free of subprocess calls. The `DISTRIB_` keys stand in
      for the `Distributor ID`, `Release`, `Codename` and `Description` fields of
      the command, which is not the same set of sources: a host can ship one without
      the other. See the module docstring for what that costs and what it gains.

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


def _get_os_release_codename(os_release):
    """
    Determine the release name /etc/os-release stands for.

    ### Parameters
    - **os_release** (`dict`):
      The result of `_get_os_release_info()`.

    ### Returns
    - **str or None**:
      The release name, or `None` if the file carries none.

    ### Notes
    - `VERSION_CODENAME` and `UBUNTU_CODENAME` win over anything derived from
      `VERSION`, even when they are empty: a distribution setting them to nothing
      states that it has no release name. That is how Fedora ends up without one.
    - Deriving the release name from `VERSION` is what makes openEuler report `LTS`
      and AlmaLinux `Purple Manul`, neither of which carries a `VERSION_CODENAME`.

    ### Example
    >>> _get_os_release_codename({'version': '8.3 (Purple Manul)'})
    'Purple Manul'
    """
    if 'version_codename' in os_release:
        return os_release['version_codename']
    if 'ubuntu_codename' in os_release:
        return os_release['ubuntu_codename']

    match = re.search(
        r'\((?P<paren>\D+)\)|,\s*(?P<comma>\D+)', os_release.get('version', '')
    )
    if match:
        return match.group('paren') or match.group('comma')
    return None


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


def _get_version_candidates(os_release, lsb_release, release_info):
    """
    Collect every version the release files offer, in the order Ansible prefers them.

    ### Parameters
    - **os_release** (`dict`):
      The result of `_get_os_release_info()`.
    - **lsb_release** (`dict`):
      The result of `_get_lsb_release_info()`.
    - **release_info** (`dict`):
      The result of `_get_distro_release_info()`.

    ### Returns
    - **list**:
      The candidates, most preferred first. Sources that carry no version are left
      out.

    ### Notes
    - Mirrors the candidate list of `distro.version()`. Its uname candidate is left
      out, which is no difference in practice: the `distro` package discards the
      output of `uname -rs` as soon as the system name is `Linux`, so on Linux that
      candidate is always empty.

    ### Example
    >>> _get_version_candidates({'version_id': '9.7'}, {}, {'version': '9.7'})
    ['9.7', '9.7']
    """
    candidates = [
        os_release.get('version_id', ''),
        lsb_release.get('distrib_release', ''),
        release_info.get('version', ''),
        _parse_release_content(os_release.get('pretty_name', '')).get('version', ''),
        _parse_release_content(lsb_release.get('distrib_description', '')).get(
            'version', ''
        ),
    ]
    return [candidate for candidate in candidates if candidate]


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

    distro_id = _get_distro_id(os_release, lsb_release, release_info)

    # Ansible normalises these two so that the OS family map and the release file
    # varieties agree on one spelling.
    distribution = distro_id.capitalize()
    if distribution == 'Amzn':
        distribution = 'Amazon'
    elif distribution == 'Rhel':
        distribution = 'Redhat'
    elif not distribution:
        distribution = 'OtherLinux'

    candidates = _get_version_candidates(os_release, lsb_release, release_info)
    if distro_id in ('centos', 'debian'):
        # Ansible asks for the most precise version it can get for these two.
        version = _get_best_version(distro_id, candidates)
    else:
        version = candidates[0] if candidates else ''

    codename = _get_codename(distro_id, os_release, lsb_release, release_info)

    guess = {
        'distribution': distribution,
        'distribution_version': version or 'NA',
        'distribution_release': 'NA' if codename is None else codename,
    }
    guess['distribution_major_version'] = (
        guess['distribution_version'].split('.')[0] or 'NA'
    )
    return guess


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
            # Sets distribution to what is in the data, for example CentOS. Ansible
            # indexes unconditionally here, which trips over a release file holding
            # nothing but whitespace.
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
            # Ansible unpacks into exactly three parts here and raises on anything
            # else. Slicing keeps a two part version from taking the lib down.
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
        # Kept in its own name. Ansible rebinds `data` to the line list in the
        # openSUSE branch below and then hands it to the VARIANT_ID re.search at the
        # end of the function, which raises a TypeError. Unreachable in Ansible's own
        # tests because every openSUSE carrying this file also carries an
        # /etc/os-release, which comes first in OSDIST_LIST.
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


# Every name in OSDIST_LIST must either be listed in SEARCH_STRING or
# OS_RELEASE_ALIAS, carry allowempty, or have a parser here. Gentoo is the one
# exception: Ansible has no parser for it either, and it is picked up by the generic
# 'NA' entry at the end of OSDIST_LIST.
# Kept here instead of with the other constants at the top, because it names the
# parsers above and they have to be defined by the time this is read.
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


def _parse_release_content(line):
    """
    Split a release file line into name, version and release name.

    Also used on the `PRETTY_NAME` of /etc/os-release and the `DISTRIB_DESCRIPTION`
    of /etc/lsb-release, both of which carry the same wording.

    ### Parameters
    - **line** (`str`):
      A single line, for example `Red Hat Enterprise Linux release 9.7 (Plow)`.

    ### Returns
    - **dict**:
      Any of the keys `name`, `version` and `codename` that could be determined.
      Empty if the line carries none of them.

    ### Example
    >>> _parse_release_content('Red Hat Enterprise Linux release 9.7 (Plow)')
    {'name': 'Red Hat Enterprise Linux', 'version': '9.7', 'codename': 'Plow'}
    """
    line = (line or '').strip()
    for regex in (_RELEASE_CONTENT_REGEX, _RELEASE_CONTENT_NO_KEYWORD_REGEX):
        match = regex.match(line)
        if match:
            return {k: v for k, v in match.groupdict().items() if v}
    return {}


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

    # A parser may be the first to find a version, for example on an Amazon Linux
    # recognised through /etc/system-release. Ansible has its major version from the
    # `distro` package by then, this module has to derive it.
    if (
        facts['distribution_major_version'] == 'NA'
        and facts['distribution_version'] != 'NA'
    ):
        facts['distribution_major_version'] = (
            facts['distribution_version'].split('.')[0] or 'NA'
        )

    return facts


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
    - `distribution_release` is empty where a distribution states that it has no
      release name, which Fedora does by setting `VERSION_CODENAME=""`. It is `NA`
      where no source carries one at all.
    - On anything other than Linux, only the `platform` module is consulted, and the
      three facts it fills mean something else: `distribution` is the system name,
      `distribution_release` is the kernel release and `distribution_version` is the
      kernel version. `distribution_major_version` is absent there. This is Ansible's
      baseline for a system it has no dedicated code for.

    ### Example
    >>> get_distribution_facts()
    {'distribution': 'Fedora', 'distribution_version': '41', 'distribution_release':
    '', 'distribution_major_version': '41', 'distribution_file_path':
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
