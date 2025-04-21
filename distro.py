#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst


"""Provides information about the Linux distribution it runs on, such as a reliable
machine-readable distro ID and "os_family" (known from Ansible).

Source Code is taken, converted, shortened and modified from:
* lib/ansible/module_utils/facts/system/distribution.py
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042002'


import os
import platform
import re

from . import shell
 
# --- Static mappings ---

OSDIST_LIST = (
    {'path': '/etc/alpine-release', 'name': 'Alpine'},
    {'path': '/etc/arch-release', 'name': 'Archlinux', 'allowempty': True},
    {'path': '/etc/centos-release', 'name': 'CentOS'},
    {'path': '/etc/redhat-release', 'name': 'RedHat'},
    {'path': '/etc/oracle-release', 'name': 'OracleLinux'},
    {'path': '/etc/gentoo-release', 'name': 'Gentoo'},
    {'path': '/etc/os-release', 'name': 'Debian'},
    {'path': '/etc/os-release', 'name': 'Ubuntu'},
    {'path': '/etc/os-release', 'name': 'Amazon'},
    {'path': '/usr/lib/os-release', 'name': 'ClearLinux'},
    {'path': '/etc/lsb-release', 'name': 'Debian'},  # fallback
)

SEARCH_STRING = {
    'OracleLinux': 'Oracle Linux',
    'RedHat': 'Red Hat',
    'Altlinux': 'ALT',
    'SMGL': 'Source Mage GNU/Linux',
}

OS_FAMILY_MAP = {
    'RedHat': ['RedHat', 'RHEL', 'CentOS', 'Scientific', 'OracleLinux', 'Fedora', 'AlmaLinux', 'Rocky'],
    'Debian': ['Debian', 'Debian GNU/Linux', 'Ubuntu', 'Raspbian', 'Pop!_OS', 'Kali', 'Parrot', 'Devuan', 'Deepin', 'Mint'],
    'Suse': ['SUSE', 'openSUSE', 'SLES', 'SLED'],
    'Archlinux': ['Archlinux', 'Manjaro', 'Antergos'],
    'Gentoo': ['Gentoo', 'Funtoo'],
    'Alpine': ['Alpine'],
    'ClearLinux': ['ClearLinux'],
}

STRIP_QUOTES = r'\'\"\\'


def _file_exists(path, allow_empty=False):
    """
    Check if a file exists and optionally allow empty files.

    This function verifies the existence of a file at the given path. If `allow_empty` is `False`,
    it additionally checks that the file is not empty.

    ### Parameters
    - **path** (`str`):
      Path to the file to check.
    - **allow_empty** (`bool`, optional):
      Whether to allow empty files as valid. Defaults to `False`.

    ### Returns
    - **bool**:
      `True` if the file exists (and is non-empty unless `allow_empty=True`), otherwise `False`.

    ### Notes
    - Useful to validate configuration or system files before parsing.

    ### Example
    >>> _file_exists('/etc/os-release')
    True
    """
    if not os.path.isfile(path):
        return False
    if allow_empty:
        return True
    return os.path.getsize(path) > 0


def _get_file_content(path):
    """
    Read the content of a text file.

    Opens and reads the entire content of a UTF-8 encoded text file at the specified path.

    ### Parameters
    - **path** (`str`):
      Path to the file to read.

    ### Returns
    - **str**:
      The complete contents of the file as a string.

    ### Notes
    - Raises an exception if the file cannot be opened.

    ### Example
    >>> _get_file_content('/etc/os-release')
    'NAME="Ubuntu"\nVERSION="22.04.2 LTS (Jammy Jellyfish)"\n...'
    """
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _guess_linux_distribution():
    """
    Provide basic distribution facts based on platform module.

    Returns baseline information using the `platform` module, including distribution name,
    kernel version, and major version.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      A dictionary containing `distribution`, `distribution_version`, `distribution_release`, and `distribution_major_version`.

    ### Notes
    - Serves as a fallback if no release file parsing succeeds.

    ### Example
    >>> _guess_linux_distribution()
    {'distribution': 'Linux', 'distribution_version': '#1 SMP...', 'distribution_release': '5.15.0-86-generic', 'distribution_major_version': '5'}
    """
    system = platform.system()
    return {
        'distribution': system if system else 'NA',
        'distribution_version': platform.version() if system else 'NA',
        'distribution_release': platform.release() if system else 'NA',
        'distribution_major_version': platform.version().split('.')[0] if '.' in platform.version() else 'NA',
    }


def _parse_distribution_file(name, data):
    """
    Parse distribution information from release file content.

    This function interprets known distro-specific patterns from given release file content
    and extracts the distribution name if recognized.

    ### Parameters
    - **name** (`str`):
      The expected distribution name or file variety.
    - **data** (`str`):
      The contents of the release file.

    ### Returns
    - **tuple** (`bool`, `dict`):
      - First element: `True` if parsing succeeded, `False` otherwise.
      - Second element: A dictionary of parsed distribution facts.

    ### Notes
    - Handles special parsing for Archlinux, Debian, Ubuntu, Amazon, ClearLinux, Alpine.

    ### Example
    >>> _parse_distribution_file('RedHat', 'Red Hat Enterprise Linux release 8.5...')
    (True, {'distribution': 'RedHat'})
    """
    dist_facts = {}
    data = data.strip(STRIP_QUOTES)

    if name in SEARCH_STRING:
        if SEARCH_STRING[name] in data:
            dist_facts['distribution'] = name
        else:
            dist_facts['distribution'] = data.split()[0]
        return True, dist_facts

    if name == 'Archlinux':
        if 'Arch Linux' in data:
            dist_facts['distribution'] = 'Archlinux'
            return True, dist_facts
        return False, {}

    if name in ('Debian', 'Ubuntu', 'Amazon', 'ClearLinux'):
        if 'PRETTY_NAME' in data or 'NAME=' in data:
            m = re.search(r'^NAME="?([^"\n]*)"?', data, re.M)
            if m:
                dist_facts['distribution'] = m.group(1)
        return True, dist_facts

    if name == 'Alpine':
        if 'Alpine' in data:
            dist_facts['distribution'] = 'Alpine'
            return True, dist_facts
        return False, {}

    return True, dist_facts


def _parse_os_release(path):
    """
    Parse `/etc/os-release` for version information.

    Reads the standard `os-release` file and extracts the version ID and major version.

    ### Parameters
    - **path** (`str`):
      Path to the `os-release` file.

    ### Returns
    - **dict**:
      Parsed facts: `distribution_version` and `distribution_major_version` if found.

    ### Notes
    - Silent if file does not exist or parsing fails.

    ### Example
    >>> _parse_os_release('/etc/os-release')
    {'distribution_version': '22.04', 'distribution_major_version': '22'}
    """
    facts = {}
    if not _file_exists(path):
        return facts

    try:
        data = _get_file_content(path)
    except Exception:
        return facts

    m_version = re.search(r'^VERSION_ID="?([^"\n]*)"?', data, re.M)
    if m_version:
        facts['distribution_version'] = m_version.group(1)
        facts['distribution_major_version'] = m_version.group(1).split('.')[0]
    return facts


def _parse_lsb_release(path):
    """
    Parse `/etc/lsb-release` for version information.

    Reads the `lsb-release` file and extracts the release and major version if available.

    ### Parameters
    - **path** (`str`):
      Path to the `lsb-release` file.

    ### Returns
    - **dict**:
      Parsed facts: `distribution_version` and `distribution_major_version` if found.

    ### Notes
    - Useful fallback for Debian-based systems when `os-release` is incomplete.

    ### Example
    >>> _parse_lsb_release('/etc/lsb-release')
    {'distribution_version': '20.04', 'distribution_major_version': '20'}
    """
    facts = {}
    if not _file_exists(path):
        return facts

    try:
        data = _get_file_content(path)
    except Exception:
        return facts

    m_version = re.search(r'^DISTRIB_RELEASE="?([^"\n]*)"?', data, re.M)
    if m_version:
        facts['distribution_version'] = m_version.group(1)
        facts['distribution_major_version'] = m_version.group(1).split('.')[0]
    return facts


def _process_dist_files():
    """
    Process distribution-specific files to determine system identity.

    Sequentially checks known distribution marker files and parses them to
    extract distribution facts. Improves the guessed facts with better data
    from `/etc/os-release` and `/etc/lsb-release` if available.

    ### Parameters
    - *None*

    ### Returns
    - **dict**:
      Collected facts including distribution, version, major version, and parsing flags.

    ### Notes
    - Stops at the first successful parsing.

    ### Example
    >>> _process_dist_files()
    {'distribution': 'Ubuntu', 'distribution_version': '22.04', 'distribution_major_version': '22', ...}
    """
    facts = _guess_linux_distribution()

    for entry in OSDIST_LIST:
        name = entry['name']
        path = entry['path']
        allow_empty = entry.get('allowempty', False)

        if not _file_exists(path, allow_empty=allow_empty):
            continue

        try:
            data = _get_file_content(path)
        except Exception:
            continue

        if allow_empty:
            facts.update({
                'distribution': name,
                'distribution_file_path': path,
                'distribution_file_variety': name,
            })
            break

        parsed, parsed_facts = _parse_distribution_file(name, data)

        if parsed:
            facts.update({
                'distribution': name,
                'distribution_file_path': path,
                'distribution_file_variety': name,
                'distribution_file_parsed': True,
            })
            facts.update(parsed_facts)
            break

    # Improve facts from os-release or lsb-release
    if '/etc/os-release' in [e['path'] for e in OSDIST_LIST]:
        facts.update(_parse_os_release('/etc/os-release'))
    if '/etc/lsb-release' in [e['path'] for e in OSDIST_LIST]:
        facts.update(_parse_lsb_release('/etc/lsb-release'))

    return facts


def _map_os_family(distribution):
    """
    Map a detected distribution to its OS family.

    Returns a broader OS family (like `RedHat`, `Debian`, etc.) based on the distribution name.

    ### Parameters
    - **distribution** (`str`):
      The detected distribution name.

    ### Returns
    - **str**:
      The mapped OS family name, or the original distribution if no mapping exists.

    ### Notes
    - Helps categorize distributions consistently.

    ### Example
    >>> _map_os_family('Fedora')
    'RedHat'
    """
    for family, members in OS_FAMILY_MAP.items():
        if distribution in members:
            return family
    return distribution


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
      - `distribution_file_path`
      - `distribution_file_variety`
      - `distribution_file_parsed`
      - `os_family`

    ### Example
    >>> get_distribution_facts()
    {'distribution': 'Fedora', 'distribution_version': '41', 'distribution_release': '6.13.10-200.fc41.x86_64', 'distribution_major_version': '41', 'distribution_file_path': '/etc/redhat-release', 'distribution_file_variety': 'RedHat', 'distribution_file_parsed': True, 'os_family': 'RedHat'}
    """
    facts = _process_dist_files()

    distro = facts.get('distribution', 'NA')
    facts['os_family'] = _map_os_family(distro)  # returns 'RedHat', for example

    cmd = '. /etc/os-release && echo "$NAME $VERSION"'
    success, result = shell.shell_exec(cmd, shell=True)
    if not success:
        return facts

    stdout, _, _ = result
    facts['os_info'] = stdout.strip()  # returns 'Fedora Linux 41 (Workstation Edition)', for example

    return facts
