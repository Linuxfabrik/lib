#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Offers file and disk related functions, like getting a list of
partitions, grepping a file, etc.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2024033101'

import csv
import os
import re
import tempfile

from . import shell


def file_exists(path, allow_empty=False):
    # not finding the file, exit early
    if not os.path.exists(path):
        return False

    # if just the path needs to exists (ie, it can be empty) we are done
    if allow_empty:
        return True

    # file exists but is empty and we dont allow_empty
    if os.path.getsize(path) == 0:
        return False

    # file exists with some content
    return True


def get_cwd():
    """Gets the current working directory.
    """
    return os.getcwd()


def get_dm_name(dm_device):
    """Get the name of a device mapper device. Instead of using `dmsetup ls`, this solution does 
    not need sudo-permissions and is straight to the point.

    >>> get_dm_name('dm-0')
    rl_rocky8-root
    """
    success, result = read_file('/sys/class/block/{}/dm/name'.format(dm_device))
    if not success:
        return dm_device
    if not result:
        return dm_device
    return result


def get_real_disks():
    """Get a list of local devices and their mountpoints.
    Simply use `df` for that.

    >>> get_real_disks()
    [['/dev/dm-0', '/'], ['devtmpfs', '/dev'], ['tmpfs', '/dev/shm'], ['/dev/dm-0', '/home'], ['/dev/nvme0n1p2', '/boot'], ['/dev/nvme0n1p1', '/boot/efi'], ['tmpfs', '/tmp'], ['tmpfs', '/run/user/1000']]
    """
    success, result = shell.shell_exec('df --local --output=source,target')
    disks = []
    if not success:
        return disks
    disks, _, _ = result
    if not disks:
        return disks
    disks = disks.strip().splitlines()
    disks = [disk.split() for disk in disks][1:] # remove header line from `df`
    disks = [disk[0] for disk in disks]
    return list(set(disks)) # get the unique values from the list


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

    >>> success, nc_version=lib.disk.grep_file('version.php', r'\\$OC_version=array\\((.*)\\)')

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


def read_csv(filename, delimiter=',', quotechar='"', newline='', as_dict=False, skip_empty_rows=False):
    """Reads a CSV file, and returns a list or a dict.
    """
    try:
        with open(filename, newline=newline) as csvfile:
            if not as_dict:
                reader = csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
            else:
                reader = csv.DictReader(csvfile, delimiter=delimiter, quotechar=quotechar)
            data = []
            for row in reader:
                # check if the list contains empty strings only
                if skip_empty_rows and all(s == '' or s.isspace() for s in row):
                    continue
                data.append(row)
        return (True, data)
    except csv.Error as e:
        return (False, 'CSV error in file {}, line {}: {}'.format(filename, reader.line_num, e))
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error opening or reading {}'.format(filename))


def read_env(filename, delimiter='='):
    """Reads an shell script for setting environment variables,
    and returns a dict with all of them.

    Example shell script:

        export OS_AUTH_URL="https://api/v3"
        export OS_PROJECT_NAME=myproject
        # comment
        OS_PASSWORD='linuxfabrik'
        [ -z "$OS_PASSWORD" ] && read -e -p "Pass: " OS_PASSWORD
        export OS_PASSWORD

    >>> read_env(filename)
    {'OS_AUTH_URL': 'https://api/v3', 'OS_PROJECT_NAME': 'myproject', 'OS_PASSWORD': 'linuxfabrik'}
    """
    try:
        with open(filename) as envfile:
            data = {}
            for line in envfile.readlines():
                line = line.strip().split(delimiter)
                try:
                    if not line[0].startswith('#'):
                        data[line[0].replace('export ', '')] = line[1].replace("'", '').replace('"', '')
                except:
                    continue
        return (True, data)
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error opening or reading {}'.format(filename))


def read_file(filename):
    """Reads a file.
    """
    try:
        with open(filename, 'r') as f:
            data = f.read()
        return (True, data)
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error opening or reading {}'.format(filename))


def rm_file(filename):
    """Deletes/Removes a file.

    >>> rm_file('test.txt')
    (True, None)
    """
    try:
        os.remove(filename)
        return (True, None)
    except OSError as e:
        return (False, 'OS error "{}" while deleting {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error deleting {}'.format(filename))


def walk_directory(path, exclude_pattern=r'', include_pattern=r'', relative=True):
    """Walks recursively through a directory and creates a list of files.
    If an exclude_pattern (regex) is specified, files matching this pattern
    are ignored. If an include_pattern (regex) is specified, only files matching
    this pattern are put on the list (in this particular order).

    >>> walk_directory('/tmp')
    ['cpu-usage.db', 'segv_output.MCiVt9']
    >>> walk_directory('/tmp', exclude_pattern='.*Temp-.*', relative=False)
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


def write_file(filename, content, append=False):
    """Writes a string to a file.

    >>> write_file('test.txt', 'First line\nSecond line')
    (True, None)
    """
    try:
        with open(filename, 'w' if not append else 'a') as f:
            f.write(content)
        f.close()
        return (True, None)
    except IOError as e:
        return (False, 'I/O error "{}" while writing {}'.format(e.strerror, filename))
    except:
        return (False, 'Unknown error writing {}, or content is not a string'.format(filename))
