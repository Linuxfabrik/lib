#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Extends argparse by new input argument data types on demand.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021082501'


def csv(arg):
    """Returns a list from a `csv` input argument.
    """
    return [x.strip() for x in arg.split(',')]


def float_or_none(arg):
    """Returns None or float from a `float_or_none` input argument.
    """
    if arg is None or str(arg).lower() == 'none':
        return None
    return float(arg)


def int_or_none(arg):
    """Returns None or int from a `int_or_none` input argument.
    """
    if arg is None or str(arg).lower() == 'none':
        return None
    return int(arg)


def range_or_none(arg):
    """Returns None or range from a `range_or_none` input argument.
    """
    return str_or_none(arg)


def str_or_none(arg):
    """Returns None or str from a `str_or_none` input argument.
    """
    if arg is None or str(arg).lower() == 'none':
        return None
    return str(arg)
