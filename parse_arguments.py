#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://nagios-plugins.org/doc/guidelines.html

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020022101'


def csv(string):
    return [x.strip() for x in string.split(',')]


def int_or_None(input):
    if input is None or str(input) == 'None':
        return None

    return int(input)


def float_or_None(input):
    if input is None or str(input) == 'None':
        return None

    return float(input)


def str_or_None(input):
    if input is None or str(input) == 'None':
        return None

    return str(input)
