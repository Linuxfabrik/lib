#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Wrapper library for functions from psutil."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082601'

import sys
from collections import namedtuple

from .globals import STATE_UNKNOWN

try:
    import psutil
except ImportError:
    print('Python module "psutil" is not installed.')
    sys.exit(STATE_UNKNOWN)


# The fields a caller gets back. psutil's own partition tuple is not reused, because its
# shape moves between releases: psutil 5.9 carries `maxfile` and `maxpath` next to these
# four and psutil 7 does not, so building one from four values raises there.
sdiskpart = namedtuple('sdiskpart', ['device', 'mountpoint', 'fstype', 'opts'])


def get_partitions(ignore=None, include_all=False):
    """
    Return all mounted disk partitions as a list of named tuples, including device, mount point,
    filesystem type and mount options, similar to the `df` command on UNIX.

    Listing the partitions never waits on the filesystems it lists. `psutil.disk_partitions()`
    looks up `os.pathconf()` on every mount point it returns, to fill in the `maxfile` and
    `maxpath` fields, and that lookup blocks on a network filesystem whose server has stopped
    answering: merely asking what is mounted then never comes back. Those two fields are
    dropped here and the lookup with them, so the answer comes from the mount table alone.

    ### Parameters
    - **ignore** (`list`, optional): A list of strings to ignore. Any partition whose mount
      point contains any of the strings in this list will be excluded from the result.
      Defaults to an empty list.
    - **include_all** (`bool`, optional): Return every mounted filesystem instead of the
      physical devices only. The default leaves out the pseudo and memory filesystems, and
      with them the network filesystems, which the kernel also lists as `nodev`.
      Defaults to False.

    ### Returns
    - **list**: A list of named tuples representing the disk partitions, each containing:
      - **device**: The device name (e.g., `/dev/sda1`).
      - **mountpoint**: The mount point (e.g., `/`).
      - **fstype**: The filesystem type (e.g., `ext4`).
      - **opts**: The mount options (e.g., `rw,relatime`).

    ### Example
    >>> get_partitions(['/mnt'])
    [sdiskpart(device='/dev/sda1', mountpoint='/', fstype='ext4', opts='rw,relatime')]
    """
    if ignore is None:
        ignore = []
    ignore = list(filter(None, ignore))

    try:
        # psutil's platform module is not its published interface, so a layout that does
        # not match falls back to the documented function, blocking lookups and all.
        parts = psutil._psplatform.disk_partitions(include_all)
    except Exception:
        parts = psutil.disk_partitions(all=include_all)

    return [
        sdiskpart(part.device, part.mountpoint, part.fstype, part.opts)
        for part in parts
        if not any(item in part.mountpoint for item in ignore)
    ]
