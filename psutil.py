#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Wrapper library for functions from psutil.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023112901'

import sys

from .globals import STATE_UNKNOWN
try:
    import psutil
except ImportError as e:
    print('Python module "psutil" is not installed.')
    sys.exit(STATE_UNKNOWN)


def get_partitions(ignore=[]):
    """
    Return all mounted disk partitions as a list of named tuples, including device, mount point, 
    and filesystem type, similar to the `df` command on UNIX.

    ### Parameters
    - **ignore** (`list`, optional): A list of strings to ignore. Any partition whose mount
      point contains any of the strings in this list will be excluded from the result.
      Defaults to an empty list.

    ### Returns
    - **list**: A list of named tuples representing the disk partitions, each containing:
      - **device**: The device name (e.g., `/dev/sda1`).
      - **mountpoint**: The mount point (e.g., `/`).
      - **fstype**: The filesystem type (e.g., `ext4`).

    ### Example
    >>> get_partitions(['/mnt'])
    [NamedTuple(device='/dev/sda1', mountpoint='/', fstype='ext4')]
    """
    # remove all empty items from the ignore list, because `'' in 'any_string' == true`
    ignore = list(filter(None, ignore))
    return list(
        filter(
            lambda part: not any(
                ignore_item in part.mountpoint for ignore_item in ignore),
            psutil.disk_partitions(all=False)
        )
    )
