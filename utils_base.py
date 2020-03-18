#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020031801'

import re
import tempfile
import time


def continue_or_exit(result, state=3):
    if (result[0]):
        # if return code of a function's result is true
        # return its result set/data, and you can continue your code
        return result[1]
    else:
        # print the error message instead and exit with STATE_UNKOWN (3)
        print(result[1])
        exit(state)


def get_tmpdir():
    try:
        return tempfile.gettempdir()   
    except:
        return '/tmp'


def grep_file(filename, pattern):
    try:
        with open(filename, 'r') as f:
            data = f.read()
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error opening or reading {}'.format(filename))
    else:
        match = re.search(pattern, data).group(1)
        if match:
            return (True, match)
        else:
            # function was successful in opening and reading the file, but no match found
            return (True, False)


def now():
    return int(time.time())


