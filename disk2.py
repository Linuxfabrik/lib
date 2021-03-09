#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Offers file and disk related functions, like getting a list of
partitions, grepping a file, etc.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021030901'

import csv
import os
import re
import sys
import tempfile

from lib.globals2 import STATE_UNKNOWN
try:
    import psutil
except ImportError as e:
    print('Python module "psutil" is not installed.')
    sys.exit(STATE_UNKNOWN)


def get_cwd():
    """Gets the current working directory.
    """

    return os.getcwd()


def get_partitions(ignore=[]):
    """Return all mounted disk partitions as a list of named tuples
    including device, mount point and filesystem type, similarly to
    `df` command on UNIX.
    """

    # remove all empty items from the ignore list, because `'' in 'any_string' == true`
    ignore = list(filter(None, ignore))
    return list(
        filter(
            lambda part: not any(
                ignore_item in part.mountpoint for ignore_item in ignore),
            psutil.disk_partitions(all=False)
            )
        )


def get_tmpdir():
    """ Return the name of the directory used for temporary files, always
    without trailing '/'.

    Searches a standard list of directories to find one which the calling user
    can create files in. The list is:

    * The directory named by the TMPDIR environment variable.
    * The directory named by the TEMP environment variable.
    * The directory named by the TMP environment variable.
    * A platform-specific location:
      - On Windows, the directories C:\\TEMP, C:\\TMP, \\TEMP, and \\TMP,
        in that order.
      - On all other platforms, the directories /tmp, /var/tmp, and /usr/tmp,
        in that order.
    * As a last resort, the current working directory.
    """

    try:
        return tempfile.gettempdir()
    except:
        return '/tmp'


def grep_file(filename, pattern):
    """Like `grep` searches for `pattern` in `filename`. Returns the
    match, otherwise `False`.

    >>> success, nc_version=lib.disk2.grep_file('version.php', r'\\$OC_version=array\\((.*)\\)')

    Parameters
    ----------
    filename : str
        The file.
    pattern : str
        A Python regular expression.

    Returns
    -------
    tuple
        tuple[0]: bool: if successful (no I/O or file handling errors) or not
        tuple[1]: str: the string matched by `pattern` (if any)
    """

    try:
        with open(filename, 'r') as file:
            data = file.read()
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error opening or reading {}'.format(filename))
    else:
        match = re.search(pattern, data).group(1)
        return (True, match)


def read_csv(filename, delimiter=',', quotechar='"', newline='', as_dict=False):
    """Reads a CSV file, and returns a list or a dict.

    """

    try:
        with open(filename, newline=newline) as csvfile:
            if not as_dict:
                reader = csv.reader(csvfile, delimiter=',', quotechar='"')
            else:
                reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
            data = []
            is_header_row = True
            for row in reader:
                data.append(row)
    except csv.Error as e:
        return (False, 'CSV error in file {}, line {}: {}'.format(filename, reader.line_num, e))
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error opening or reading {}'.format(filename))
    return (True, data)


def read_file(filename):
    """Reads a file.

    """

    try:
        f = open(filename, 'r')
        data = f.read()
        f.close()
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error opening or reading {}'.format(filename))
    return (True, data)


def walk_directory(path, exclude_pattern=r'', include_pattern=r'', relative=True):
    """Walks recursively through a directory and creates a list of files.
    If an exclude_pattern (regex) is specified, files matching this pattern
    are ignored. If an include_pattern (regex) is specified, only files matching
    this pattern are put on the list (in this particular order).

    >>> lib.disk2.walk_directory('/tmp')
    ['cpu-usage.db', 'segv_output.MCiVt9']
    >>> lib.disk2.walk_directory('/tmp', exclude_pattern='.*Temp-.*', relative=False)
    ['/tmp/cpu-usage.db', '/tmp/segv_output.MCiVt9']
    """

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
