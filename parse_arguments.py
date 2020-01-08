#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://nagios-plugins.org/doc/guidelines.html

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020010801'


def csv_arg(string):
    return [x for x in string.split(',')]
