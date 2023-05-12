#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides test functions for unit tests.
"""

import os

from . import disk


__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'


def test(args):
    """Returns the content of two files as well as the provided return code. The first file stands
    for STDOUT, the second for STDERR. The function can be used to enable unit tests.

    >>> test('path/to/stdout.txt', 'path/to/stderr.txt', 128)
    """
    if args[0] and os.path.isfile(args[0]):
        success, stdout = disk.read_file(args[0])
    else:
        stdout = args[0]
    if args[1] and os.path.isfile(args[1]):
        success, stderr = disk.read_file(args[1])
    else:
        stderr = args[1]
    if args[2] == '':
        retc = 0
    else:
        retc = int(args[2])

    return stdout, stderr, retc
