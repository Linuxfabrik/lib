#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020033101'

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


def now():
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