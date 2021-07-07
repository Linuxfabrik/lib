#! /usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Wrapper library for functions from psutil.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021050301'

import sys

from .globals3 import STATE_UNKNOWN
try:
    import psutil
except ImportError as e:
    print('Python module "psutil" is not installed.')
    sys.exit(STATE_UNKNOWN)


def get_partitions(ignore=[]):
    """Return all mounted disk partitions as a list of named tuples
    including device, mount point and filesystem type, similarly to
    `df` command on UNIX.
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
