#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020040301'

import datetime
import hashlib
import time


def continue_or_exit(result, state=3):
    if (result[0]):
        # if return code of a more complex function's result is true (= no exception)
        # return its result set/data, and you can continue your code
        return result[1]
    else:
        # print the error message instead and exit with STATE_UNKOWN (3)
        print(result[1])
        exit(state)


def md5sum(data):
    return hashlib.md5(data).hexdigest()


def now(as_datetime=False):
    if as_datetime:
        return datetime.datetime.now()
    else:
        return int(time.time())


def oao(msg, state, perfdata='', always_ok=False):
    '''Over and Out'''
    if perfdata:
        print(msg.strip() + '|' + perfdata.strip())
    else:
        print(msg.strip())
    if always_ok:
        exit(0)
    exit(state)


def pluralize(noun, value, suffix='s'):
    """Returns a plural suffix if the value is not 1. By default, 's' is used as the suffix.
    If value is 0, pluralize('vote', value) displays "0 votes".
    If value is 1, pluralize('vote', value) displays "1 vote".
    If value is 2, pluralize('vote', value) displays "2 votes".

    If an argument is provided, that string is used instead:

    If value is 0, pluralize('class', value, 'es') displays "0 classes".
    If value is 1, pluralize('class', value, 'es') displays "1 class".
    If value is 2, pluralize('class', value, 'es') displays "2 classes".

    If the provided argument contains a comma, the text before the comma is used for the singular case and the text after the comma is used for the plural case:

    If value is 0, pluralize('cand', value, 'y,ies) displays "0 candies".
    If value is 1, pluralize('cand', value, 'y,ies) displays "1 candy".
    If value is 2, pluralize('cand', value, 'y,ies) displays "2 candies".

    From https://kite.com/python/docs/django.template.defaultfilters.pluralize
    """
    if ',' in suffix:
        singular, plural = suffix.split(',')
    else:
        singular, plural = '', suffix
    if int(value) == 1:
        return noun + singular
    else:
        return noun + plural


def smartcast(value):
    # returns value converted to float if possible, else string, else the uncasted value
    for test in [float, str]:
        try:
            return test(value)
        except ValueError:
            continue
            # No match
    return value


def today():
    return datetime.datetime.today()


def version(v):
    """Use this to compare numerical version numbers.
    True: version('3.0.7') < version('3.0.11')
    False: '3.0.7' < '3.0.11'
    """
    return tuple(map(int, (v.split("."))))
