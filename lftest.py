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
__version__ = '2025041901'


def test(args):
    """
    Returns the content of two files and the provided return code. The first file represents STDOUT, 
    and the second represents STDERR. This function is useful for enabling unit tests.

    ### Parameters
    - **args** (`list`): A list containing:
      - The path to the file representing STDOUT or the string to be used as STDOUT.
      - The path to the file representing STDERR or the string to be used as STDERR.
      - The return code (integer or string). Defaults to 0 if not provided.

    ### Returns
    - **tuple**:
      - **stdout** (`str`): The content of the first file or the provided STDOUT string.
      - **stderr** (`str`): The content of the second file or the provided STDERR string.
      - **retc** (`int`): The return code, either from the provided value or defaulted to 0.

    ### Example
    >>> test('path/to/stdout.txt', 'path/to/stderr.txt', 128)
    ('This is stdout content', 'This is stderr content', 128)
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
