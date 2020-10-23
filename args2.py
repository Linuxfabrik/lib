#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Extends argparse by new input argument data types on demand.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020043001'


def csv(arg):
    """Returns a list from a `csv` input argument.
    """

    return [x.strip() for x in arg.split(',')]


def float_or_none(arg):
    """Returns None or float from a `float_or_none` input argument.
    """

    if arg is None or str(arg.lower()) == 'none':
        return None
    return float(arg)


def int_or_none(arg):
    """Returns None or int from a `int_or_none` input argument.
    """

    if arg is None or str(arg.lower()) == 'none':
        return None
    return int(arg)


def range_or_none(arg):
    """Returns None or range from a `range_or_none` input argument.
    """

    return str_or_none(arg)


def str_or_none(arg):
    """Returns None or str from a `str_or_none` input argument.
    """

    if arg is None or str(arg.lower()) == 'none':
        return None
    return str(arg)
