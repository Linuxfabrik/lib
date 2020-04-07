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

import os
try:
    import psutil
except ImportError, e:
    print('Python module "psutil" is not installed.')
    exit(STATE_UNKNOWN)
import re
import tempfile


def get_cwd():
    return os.getcwd()


def get_partitions(ignore=[]):
    # remove all empty items from the ignore list, because `'' in 'any_string' == true`
    ignore = list(filter(None, ignore))
    return list(filter(lambda part: not any(ignore_item in part.mountpoint for ignore_item in ignore), psutil.disk_partitions(all=False)))


def get_tmpdir():
    # always without trailing '/'
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


def walk_directory(path, exclude_pattern='', include_pattern='', relative=True):
    if exclude_pattern:
        exclude_pattern = re.compile(exclude_pattern, re.IGNORECASE)
    if include_pattern:
        include_pattern = re.compile(include_pattern, re.IGNORECASE)
    if not path.endswith('/'):
        path += '/'

    result = []
    for current, dirs, files in os.walk(path):
        for file in files:
            file = os.path.join(current, file)
            if exclude_pattern and exclude_pattern.match(file) is not None:
                continue
            if include_pattern and include_pattern.match(file) is None:
                continue
            if relative:
                result.append(file.replace(path, ''))
            else:
                result.append(file)

    return result
