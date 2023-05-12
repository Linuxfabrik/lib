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

Source Code is taken, shortened and modified from
* lib/ansible/module_utils/distro/_distro.py
* lib/ansible/module_utils/common/sys_info.py
* lib/ansible/module_utils/facts/system/distribution.py
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'


import platform

from . import disk # pylint: disable=C0413


def get_distribution_facts():
    '''Returns a dict containing
    {
        'distribution': 'Fedora',
        'distribution_release': 'NA',
        'distribution_version': 'NA',
        'distribution_major_version': 'NA',
        'distribution_file_path': '/etc/redhat-release',
        'distribution_file_variety': 'RedHat',
        'distribution_file_parsed': True,
        'os_family': 'RedHat'
    }
    '''

    def get_dist_file_content(path, allow_empty=False):
        # cant find that dist file or it is incorrectly empty
        if not disk.file_exists(path, allow_empty=allow_empty):
            return False, None

        success, data = disk.read_file(path) # pylint: disable=W0612
        return True, data


    def get_distribution():
        '''
        Return the name of the distribution the module is running on.

        :rtype: NativeString or None
        :returns: Name of the distribution the module is running on

        This function attempts to determine what distribution the code is running
        on and return a string representing that value. If the platform is Linux
        and the distribution cannot be determined, it returns ``OtherLinux``.
        '''
        distribution = ''

        if platform.system() == 'Linux':
            if distribution == 'Amzn':
                distribution = 'Amazon'
            elif distribution == 'Rhel':
                distribution = 'Redhat'
            elif not distribution:
                distribution = 'OtherLinux'

        return distribution


    def get_distribution_version():
        return None


    def get_distribution_codename():
        return None


    def guess_distribution():
        # try to find out which linux distribution this is
        dist = (get_distribution(), get_distribution_version(), get_distribution_codename())
        distribution_guess = {
            'distribution': dist[0] or 'NA',
            'distribution_version': dist[1] or 'NA',
            # distribution_release can be the empty string
            'distribution_release': 'NA' if dist[2] is None else dist[2]
        }

        distribution_guess['distribution_major_version'] = distribution_guess['distribution_version'].split('.', maxsplit=1)[0] or 'NA' # pylint: disable=C0301
        return distribution_guess


    def parse_dist_file(_name, dist_file_content):
        search_string = {
            'OracleLinux': 'Oracle Linux',
            'RedHat': 'Red Hat',
            'Altlinux': 'ALT',
            'SMGL': 'Source Mage GNU/Linux',
        }

        # We can't include this in search_string because a name match on its keys
        # causes a fallback to using the first whitespace separated item from the file content
        # as the name. For os-release, that is in form 'NAME=Arch'
        os_release_alias = {
            'Archlinux': 'Arch Linux'
        }

        dist_file_dict = {}
        dist_file_content = dist_file_content.strip(r'\'\"\\')
        if _name in search_string:
            # look for the distribution string in the data and replace according to RELEASE_NAME_MAP
            # only the distribution name is set, the version is assumed to be correct from
            # distro.linux_distribution()
            if search_string[_name] in dist_file_content:
                # this sets distribution=RedHat if 'Red Hat' shows up in data
                dist_file_dict['distribution'] = _name
                dist_file_dict['distribution_file_search_string'] = search_string[_name]
            else:
                # this sets distribution to what's in the data, e.g. CentOS, Scientific, ...
                dist_file_dict['distribution'] = dist_file_content.split()[0]

            return True, dist_file_dict

        if _name in os_release_alias:
            if os_release_alias[_name] in dist_file_content:
                dist_file_dict['distribution'] = _name
                return True, dist_file_dict
            return False, dist_file_dict

        return True, dist_file_dict


    def process_dist_files():
        # do not sort this list
        osdist_list = (
            {'path': '/etc/alpine-release', 'name': 'Alpine'},
            {'path': '/etc/altlinux-release', 'name': 'Altlinux'},
            {'path': '/etc/arch-release', 'name': 'Archlinux', 'allowempty': True},
            {'path': '/etc/centos-release', 'name': 'CentOS'},
            {'path': '/etc/coreos/update.conf', 'name': 'Coreos'},
            {'path': '/etc/flatcar/update.conf', 'name': 'Flatcar'},
            {'path': '/etc/gentoo-release', 'name': 'Gentoo'},
            {'path': '/etc/openwrt_release', 'name': 'OpenWrt'},
            {'path': '/etc/oracle-release', 'name': 'OracleLinux'},
            {'path': '/etc/redhat-release', 'name': 'RedHat'},
            {'path': '/etc/slackware-version', 'name': 'Slackware'},
            {'path': '/etc/sourcemage-release', 'name': 'SMGL'},
            {'path': '/etc/SuSE-release', 'name': 'SUSE'},
            {'path': '/etc/system-release', 'name': 'Amazon'},
            {'path': '/etc/vmware-release', 'name': 'VMwareESX', 'allowempty': True},
            {'path': '/etc/os-release', 'name': 'Debian'},
            {'path': '/etc/os-release', 'name': 'SUSE'},
            {'path': '/etc/os-release', 'name': 'Amazon'},
            {'path': '/etc/os-release', 'name': 'Archlinux'},
            {'path': '/etc/lsb-release', 'name': 'Debian'},
            {'path': '/etc/lsb-release', 'name': 'Mandriva'},
            {'path': '/usr/lib/os-release', 'name': 'ClearLinux'},
            {'path': '/etc/os-release', 'name': 'NA'},
        )

        dist_file_facts = {}

        dist_guess = guess_distribution()
        dist_file_facts.update(dist_guess)

        for ddict in osdist_list:
            _name = ddict['name']
            path = ddict['path']
            allow_empty = ddict.get('allowempty', False)

            has_dist_file, dist_file_content = get_dist_file_content(path, allow_empty=allow_empty)

            # but we allow_empty. For example, ArchLinux with an empty /etc/arch-release and a
            # /etc/os-release with a different name
            if has_dist_file and allow_empty:
                dist_file_facts['distribution'] = _name
                dist_file_facts['distribution_file_path'] = path
                dist_file_facts['distribution_file_variety'] = _name
                break

            if not has_dist_file:
                # keep looking
                continue

            parsed_dist_file, parsed_dist_file_facts = parse_dist_file(_name, dist_file_content)

            # finally found the right os dist file and were able to parse it
            if parsed_dist_file:
                dist_file_facts['distribution'] = _name
                dist_file_facts['distribution_file_path'] = path
                # distribution and file_variety are the same here, but distribution
                # will be changed/mapped to a more specific name.
                # ie, dist=Fedora, file_variety=RedHat
                dist_file_facts['distribution_file_variety'] = _name
                dist_file_facts['distribution_file_parsed'] = parsed_dist_file
                dist_file_facts.update(parsed_dist_file_facts)
                break

        return dist_file_facts

    os_family_map = {'RedHat': ['RedHat', 'RHEL', 'Fedora', 'CentOS', 'Scientific', 'SLC',
                                'Ascendos', 'CloudLinux', 'PSBM', 'OracleLinux', 'OVS',
                                'OEL', 'Amazon', 'Virtuozzo', 'XenServer', 'Alibaba',
                                'EulerOS', 'openEuler', 'AlmaLinux', 'Rocky', 'TencentOS',
                                'EuroLinux'],
                     'Debian': ['Debian', 'Ubuntu', 'Raspbian', 'Neon', 'KDE neon',
                                'Linux Mint', 'SteamOS', 'Devuan', 'Kali', 'Cumulus Linux',
                                'Pop!_OS', 'Parrot', 'Pardus GNU/Linux', 'Uos', 'Deepin'],
                     'Suse': ['SuSE', 'SLES', 'SLED', 'openSUSE', 'openSUSE Tumbleweed',
                              'SLES_SAP', 'SUSE_LINUX', 'openSUSE Leap'],
                     'Archlinux': ['Archlinux', 'Antergos', 'Manjaro'],
                     'Mandrake': ['Mandrake', 'Mandriva'],
                     'Solaris': ['Solaris', 'Nexenta', 'OmniOS', 'OpenIndiana', 'SmartOS'],
                     'Slackware': ['Slackware'],
                     'Altlinux': ['Altlinux'],
                     'SGML': ['SGML'],
                     'Gentoo': ['Gentoo', 'Funtoo'],
                     'Alpine': ['Alpine'],
                     'AIX': ['AIX'],
                     'HP-UX': ['HPUX'],
                     'Darwin': ['MacOSX'],
                     'FreeBSD': ['FreeBSD', 'TrueOS'],
                     'ClearLinux': ['Clear Linux OS', 'Clear Linux Mix'],
                     'DragonFly': ['DragonflyBSD', 'DragonFlyBSD', 'Gentoo/DragonflyBSD',
                                   'Gentoo/DragonFlyBSD'],
                     'NetBSD': ['NetBSD'], }

    os_family = {}
    for family, names in os_family_map.items():
        for name in names:
            os_family[name] = family

    distribution_facts = {}

    # The platform module provides information about the running
    # system/distribution. Use this as a baseline and fix buggy systems
    # afterwards
    system = platform.system()
    distribution_facts['distribution'] = system
    distribution_facts['distribution_release'] = platform.release()
    distribution_facts['distribution_version'] = platform.version()

    systems_implemented = (
        'AIX', 'HP-UX', 'Darwin', 'FreeBSD', 'OpenBSD', 'SunOS', 'DragonFly', 'NetBSD'
    )

    if system in systems_implemented:
        pass
    elif system == 'Linux':
        dist_file_facts = process_dist_files()
        distribution_facts.update(dist_file_facts)
    distro = distribution_facts['distribution']

    # look for a os family alias for the 'distribution', if there isnt one, use 'distribution'
    distribution_facts['os_family'] = os_family.get(distro, None) or distro

    return distribution_facts
