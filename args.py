#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020040701'


def csv(string):
    return [x.strip() for x in string.split(',')]


def float_or_none(input):
    if input is None or str(input.lower()) == 'none':
        return None
    return float(input)


def int_or_none(input):
    if input is None or str(input.lower()) == 'none':
        return None
    return int(input)


def range_or_none(input):
    return str_or_none(input)


def str_or_none(input):
    if input is None or str(input.lower()) == 'none':
        return None
    return str(input)

