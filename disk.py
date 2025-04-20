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
__version__ = '2025042001'

import csv
import os
import re
import tempfile

from . import shell


def file_exists(path, allow_empty=False):
    """
    Check if a file exists at the given path, optionally allowing empty files.

    ### Parameters
    - **path** (`str`):
      The path to the file to check.
    - **allow_empty** (`bool`, optional):
      If True, consider empty files as existing.
      If False, empty files are treated as non-existent. Defaults to False.

    ### Returns
    - **bool**:
      True if the file exists (and is non-empty unless `allow_empty` is True), otherwise False.

    ### Example
    >>> file_exists("/path/to/file")
    True
    >>> file_exists("/path/to/empty_file", allow_empty=False)
    False
    >>> file_exists("/path/to/empty_file", allow_empty=True)
    True
    """
    if not os.path.isfile(path):
        return False

    if allow_empty:
        return True

    return os.path.getsize(path) > 0


def get_cwd():
    """
    Get the current working directory.

    ### Parameters
    - None

    ### Returns
    - **str**:
      The absolute path of the current working directory.

    ### Example
    >>> get_cwd()
    '/home/user/project'
    """
    try:
        return os.getcwd()
    except OSError as e:
        # Optional: handle rare cases where the cwd is invalid (e.g., directory was deleted)
        return ''


def bd2dmd(device):
    """
    Retrieve the mapped device name for a device-mapper block device.

    This function reads the sysfs entry directly instead of using `dmsetup ls`, thus avoiding
    elevated privileges. ("bd2dmd" = block device to device-mapper device).

    ### Parameters
    - **device** (`str`):
      The block device name or path (e.g., 'dm-0', '/dev/dm-0').

    ### Returns
    - **str**:
      The full path to the mapped device (e.g., '/dev/mapper/rl_rocky8-root'),
      or an empty string if not a device-mapper device.

    ### Example
    >>> bd2dmd('dm-0')
    '/dev/mapper/rl_rocky8-root'
    >>> bd2dmd('sda')
    ''
    """
    device = os.path.basename(device)
    success, name = read_file(f'/sys/class/block/{device}/dm/name')

    if not success or not name:
        return ''

    mapped_device = f'/dev/mapper/{name.strip()}'
    return mapped_device if os.path.islink(mapped_device) else ''


def get_real_disks():
    """
    Return a list of real local block devices that are mounted and have a filesystem.

    Each device is represented as a dictionary with:
    - 'bd': Block device name (e.g., '/dev/sda1' or '/dev/dm-0').
    - 'dmd': Device-mapper name if available (e.g., '/dev/mapper/rl-root'), otherwise None.
    - 'mp' : Mount point(s), space-separated if mounted in multiple places.

    Devices are discovered by parsing /proc/mounts and resolving device-mapper relationships
    via udevadm. Devices under /dev/loop* (loopback devices) are ignored.

    ### Parameters
    - None

    ### Returns
    - **list of dict**: List of mounted devices and their details.

    ### Example
    >>> get_real_disks()
    [{'bd': '/dev/dm-0', 'dmd': '/dev/mapper/rl-root', 'mp': '/ /home'}]
    """
    success, mounts_content = read_file('/proc/mounts')
    if not success:
        return []

    disks = {}

    for line in mounts_content.splitlines():
        if not line.startswith('/dev/') or line.startswith('/dev/loop'):
            continue

        parts = line.split()
        device_path, mount_point = parts[0], parts[1]

        if device_path.startswith('/dev/mapper/'):
            dmdname = device_path
            bdname = udevadm(dmdname, 'DEVNAME')
        else:
            bdname = device_path
            dmdname = udevadm(bdname, 'DM_NAME')
            if dmdname:
                dmdname = f'/dev/mapper/{dmdname}'

        if bdname not in disks:
            disks[bdname] = {'bd': bdname, 'dmd': dmdname, 'mp': mount_point}
        else:
            disks[bdname]['mp'] += f' {mount_point}'

    return list(disks.values())


def get_tmpdir():
    """
    Return the name of the directory used for temporary files, always without a trailing '/'.

    Searches a standard list of directories to find one in which the calling user can create files.
    The search order is:

    - The directory named by the TMPDIR environment variable.
    - The directory named by the TEMP environment variable.
    - The directory named by the TMP environment variable.
    - A platform-specific default:
        * On Windows: C:\\TEMP, C:\\TMP, \\TEMP, \\TMP (in that order).
        * On other systems: /tmp, /var/tmp, /usr/tmp (in that order).
    - As a last resort, the current working directory.

    ### Parameters
    - None

    ### Returns
    - **str**: The absolute path to the temporary directory.

    ### Example
    >>> get_tmpdir()
    '/tmp'

    >>> get_tmpdir()
    'C:\\Users\\vagrant\\AppData\\Local\\Temp\\2'
    """
    tmpdir = None
    try:
        tmpdir = tempfile.gettempdir()
    except Exception:
        pass

    return tmpdir or '/tmp'


def grep_file(filename, pattern):
    """
    Search for a regex pattern in a file, similar to the `grep` command.

    Returns the first match found; if no match is found or an error occurs, returns False.

    ### Parameters
    - **filename** (`str`): Path to the file to search.
    - **pattern** (`str`): A Python regular expression pattern to search for.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the operation succeeded (no I/O or file handling errors),
          otherwise False.
        - tuple[1] (**str**): The string matched by `pattern` (if any), or an error message if
          unsuccessful.

    ### Example
    >>> success, nc_version = grep_file('version.php', r'\\$OC_version=array\\((.*)\\)')
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = f.read()
    except IOError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'

    match = re.search(pattern, data)
    if match:
        return True, match.group(1)
    return True, ''


def read_csv(filename, delimiter=',', quotechar='"', newline='', as_dict=False, skip_empty_rows=False):
    """
    Read a CSV file and return its content as a list or dictionary.

    ### Parameters
    - **filename** (`str`): Path to the CSV file.
    - **delimiter** (`str`, optional): The field delimiter character. Defaults to ','.
    - **quotechar** (`str`, optional): The character used to quote fields. Defaults to '"'.
    - **newline** (`str`, optional): Controls how universal newlines mode works while opening the
      file. Defaults to ''.
    - **as_dict** (`bool`, optional): If True, return each row as a dictionary using the CSV header.
      Defaults to False.
    - **skip_empty_rows** (`bool`, optional): If True, skip rows that contain only empty or
      whitespace fields. Defaults to False.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if reading succeeded, otherwise False.
        - tuple[1] (**list or str**): 
          - If successful, a list of rows (as lists or dicts depending on `as_dict`).
          - If unsuccessful, an error message string.

    ### Example
    >>> success, data = read_csv('data.csv')
    >>> success, data = read_csv('data.csv', as_dict=True, skip_empty_rows=True)
    """
    reader = None
    try:
        with open(filename, 'r', newline=newline, encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter, quotechar=quotechar) if as_dict else csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
            data = [
                row for row in reader
                if not (skip_empty_rows and all(not str(v).strip() for v in (row.values() if isinstance(row, dict) else row)))
            ]
        return True, data
    except csv.Error as e:
        line_num = getattr(reader, 'line_num', 'unknown')
        return False, f'CSV error in file {filename}, line {line_num}: {e}'
    except IOError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'


def read_env(filename, delimiter='='):
    """
    Read a shell script that sets environment variables and return a dictionary with the
    extracted variables.

    Lines starting with '#' are treated as comments and ignored. Only lines that set variables
    (optionally prefixed with 'export') are processed. More complex shell logic (e.g., conditional
    reads) is ignored.

    ### Parameters
    - **filename** (`str`): Path to the environment file to read.
    - **delimiter** (`str`, optional): The character that separates keys and values.
      Defaults to '='.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if reading succeeded, otherwise False.
        - tuple[1] (**dict or str**): 
          - If successful, a dictionary of environment variable names and values.
          - If unsuccessful, an error message string.

    ### Example
    Example shell script 'env.sh':

        export OS_AUTH_URL="https://api/v3"
        export OS_PROJECT_NAME=mypro
        # comment
        OS_PASSWORD='linuxfabrik'
        [ -z "$OS_PASSWORD" ] && read -e -p "Pass: " OS_PASSWORD
        export OS_PASSWORD

    >>> read_env('env.sh')
    {'OS_AUTH_URL': 'https://api/v3', 'OS_PROJECT_NAME': 'mypro', 'OS_PASSWORD': 'linuxfabrik'}
    """
    try:
        with open(filename, mode='r', encoding='utf-8') as envfile:
            data = {}
            for raw_line in envfile:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('export '):
                    line = line[7:]
                if delimiter not in line:
                    continue
                key, value = line.split(delimiter, 1)
                data[key.strip()] = value.strip().strip('\'"')
        return True, data
    except IOError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'


def read_file(filename):
    """
    Read the contents of a file and return it as a string.

    ### Parameters
    - **filename** (`str`): Path to the file to read.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if reading succeeded, otherwise False.
        - tuple[1] (**str**): 
          - If successful, the contents of the file as a string.
          - If unsuccessful, an error message string.

    ### Example
    >>> success, content = read_file('example.txt')
    """
    try:
        with open(filename, mode='r', encoding='utf-8') as f:
            return True, f.read()
    except IOError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'


def rm_file(filename):
    """
    Delete or remove a file.

    ### Parameters
    - **filename** (`str`): Path to the file to delete.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if deletion succeeded, otherwise False.
        - tuple[1] (**None or str**): 
          - None if the file was successfully deleted.
          - An error message string if unsuccessful.

    ### Example
    >>> rm_file('test.txt')
    (True, None)
    """
    try:
        os.remove(filename)
        return True, None
    except OSError as e:
        return False, f'OS error "{e.strerror}" while deleting {filename}'
    except Exception as e:
        return False, f'Unknown error deleting {filename}: {e}'


def udevadm(device, _property):
    """
    Run `udevadm info` and extract a specific property manually.

    To support older systems, the function does not use the `--property=` option 
    and instead parses all properties manually to find the desired one.

    ### Parameters
    - **device** (`str`): Path to the device (e.g., '/dev/dm-0' or '/dev/mapper/rl-root').
    - **_property** (`str`): The property name to retrieve (e.g., 'DEVNAME', 'DM_NAME').

    ### Returns
    - **str**: The value of the requested property if found, otherwise an empty string.

    ### Example
    >>> udevadm('/dev/mapper/rl_rocky8-root', 'DEVNAME')
    '/dev/dm-0'

    >>> udevadm('/dev/dm-0', 'DM_NAME')
    'rl_rocky8-root'

    >>> udevadm('/dev/linuxfabrik', 'DEVNAME')
    ''
    """
    success, result = shell.shell_exec(
        f'udevadm info --query=property --name={device}'
    )
    if not success:
        return ''
    stdout, _, _ = result
    for line in stdout.strip().splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', maxsplit=1)
        if key == _property:
            return value
    return ''


def walk_directory(path, exclude_pattern=r'', include_pattern=r'', relative=True):
    """
    Walk recursively through a directory and create a list of files.

    If an `exclude_pattern` (regex) is specified, files matching this pattern
    are ignored. If an `include_pattern` (regex) is specified, only files matching
    this pattern are included. Exclude filtering is applied before include filtering.

    ### Parameters
    - **path** (`str`): The root directory to walk.
    - **exclude_pattern** (`str`, optional): Regex pattern to exclude files. Defaults to ''.
    - **include_pattern** (`str`, optional): Regex pattern to include files. Defaults to ''.
    - **relative** (`bool`, optional): Return relative paths if True, else absolute.
      Defaults to True.

    ### Returns
    - **list of str**: List of matching file paths.

    ### Example
    >>> walk_directory('/tmp')
    ['cpu-usage.db', 'segv_output.MCiVt9']

    >>> walk_directory('/tmp', exclude_pattern='.*Temp-.*', relative=False)
    ['/tmp/cpu-usage.db', '/tmp/segv_output.MCiVt9']
    """
    if exclude_pattern:
        exclude_pattern = re.compile(exclude_pattern, re.IGNORECASE)
    if include_pattern:
        include_pattern = re.compile(include_pattern, re.IGNORECASE)

    path = path.rstrip('/') + '/'

    result = []
    for current, _, files in os.walk(path):
        for file in files:
            full_path = os.path.join(current, file)
            if exclude_pattern and exclude_pattern.match(full_path):
                continue
            if include_pattern and not include_pattern.match(full_path):
                continue
            result.append(full_path.replace(path, '') if relative else full_path)

    return result


def write_file(filename, content, append=False):
    """
    Write a string to a file.

    If `append` is True, the content is appended to the file instead of overwriting it.

    ### Parameters
    - **filename** (`str`): Path to the file to write to.
    - **content** (`str`): The string content to write into the file.
    - **append** (`bool`, optional): If True, append to the file; if False, overwrite the file. 
      Defaults to False.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if writing succeeded, otherwise False.
        - tuple[1] (**None or str**): 
          - None if the file was written successfully.
          - An error message string if unsuccessful.

    ### Example
    >>> write_file('test.txt', 'First line\\nSecond line')
    (True, None)
    """
    try:
        mode = 'a' if append else 'w'
        with open(filename, mode, encoding='utf-8') as f:
            f.write(content)
        return True, None
    except IOError as e:
        return False, f'I/O error "{e.strerror}" while writing {filename}'
    except Exception as e:
        return False, f'Unknown error writing {filename}: {e}'
