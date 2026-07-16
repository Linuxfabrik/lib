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
__version__ = '2026071601'

import csv
import glob as _glob
import hashlib
import os
import re
import shutil
import tempfile

from . import shell


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


def copy_dir(src, dst):
    """
    Recursively copy a directory tree.

    Wraps `shutil.copytree()` and reports the outcome in the same
    `(success, error)` style as the other disk helpers, so callers do not have to
    handle exceptions themselves.

    ### Parameters
    - **src** (`str`): Source directory.
    - **dst** (`str`): Destination directory (must not exist yet).

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the copy succeeded, otherwise False.
        - tuple[1] (**None or str**): None on success, otherwise an error message.

    ### Example
    >>> copy_dir('/usr/share/lynis', '/tmp/lynis')
    (True, None)
    """
    try:
        shutil.copytree(src, dst)
        return True, None
    except (OSError, shutil.Error) as e:
        return False, f'Error copying directory {src} to {dst}: {e}'
    except Exception as e:
        return False, f'Unknown error copying directory {src} to {dst}: {e}'


def copy_file(src, dst):
    """
    Copy a single file, preserving its metadata.

    Wraps `shutil.copy2()` and reports the outcome in the same `(success, error)`
    style as the other disk helpers.

    ### Parameters
    - **src** (`str`): Source file.
    - **dst** (`str`): Destination file or directory.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the copy succeeded, otherwise False.
        - tuple[1] (**None or str**): None on success, otherwise an error message.

    ### Example
    >>> copy_file('/etc/lynis/default.prf', '/tmp/lynis/default.prf')
    (True, None)
    """
    try:
        shutil.copy2(src, dst)
        return True, None
    except OSError as e:
        return False, f'OS error "{e.strerror}" while copying {src} to {dst}'
    except Exception as e:
        return False, f'Unknown error copying {src} to {dst}: {e}'


def dir_exists(path):
    """
    Check if a directory exists at the given path.

    Use this when you specifically want a directory check. `file_exists()`
    only returns `True` for regular files (it is `os.path.isfile()` under
    the hood), so passing a directory to it always returns `False`.

    ### Parameters
    - **path** (`str`):
      The path to the directory to check.

    ### Returns
    - **bool**:
      `True` if the path exists and is a directory (or a symlink to one),
      `False` otherwise.

    ### Example
    >>> dir_exists('/etc')
    True
    >>> dir_exists('/etc/passwd')
    False
    >>> dir_exists('/path/that/does/not/exist')
    False
    """
    return os.path.isdir(path)


def file_exists(path, allow_empty=False):
    """
    Check if a regular file exists at the given path, optionally allowing
    empty files.

    This wraps `os.path.isfile()`, so it only matches regular files and
    symlinks pointing at regular files. Directories return `False`; use
    `dir_exists()` for directory checks.

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
    >>> file_exists('/path/to/file')
    True
    >>> file_exists('/path/to/empty_file', allow_empty=False)
    False
    >>> file_exists('/path/to/empty_file', allow_empty=True)
    True
    """
    if not os.path.isfile(path):
        return False

    if allow_empty:
        return True

    return os.path.getsize(path) > 0


def is_within(path, roots):
    """
    Return whether `path` resolves inside one of the directories in `roots`.

    Both `path` and each root are canonicalized with `os.path.realpath()` before
    comparison, so symlinks and `..` segments are resolved and cannot be used to
    step outside a root. A caller that must restrict which files it touches (for
    example something running with elevated privileges that should stay inside an
    operator-controlled directory) can use this to reject any path that escapes
    the intended roots. Because symlinks are resolved, a symlink pointing out of
    a root is rejected; to legitimately reach a location stored elsewhere,
    bind-mount it into a root instead of symlinking it.

    ### Parameters
    - **path** (`str`):
      The path to check. It need not exist; only its resolved location matters.
    - **roots** (`iterable` of `str`):
      The directories `path` is allowed to resolve into.

    ### Returns
    - **bool**:
      True if `path` resolves to one of the roots or a location below it,
      otherwise False.

    ### Example
    >>> is_within('/var/log/app/today.log', ['/var/log'])
    True
    >>> is_within('/var/log/../etc/shadow', ['/var/log'])
    False
    """
    # normcase() is a no-op on POSIX but lowercases and normalizes separators on
    # Windows, where paths are case-insensitive; without it the containment check
    # would wrongly reject `C:\Var\Log\...` against a `C:\var\log` root.
    real = os.path.normcase(os.path.realpath(path))
    for root in roots:
        real_root = os.path.normcase(os.path.realpath(root))
        if real == real_root or real.startswith(real_root + os.sep):
            return True
    return False


# Block-device name prefixes that never carry meaningful I/O for monitoring
# (loopback, RAM disks, compressed RAM, floppy and optical devices). They are
# skipped by get_block_devices().
_PSEUDO_DEVICE_PREFIXES = ('fd', 'loop', 'ram', 'sr', 'zram')


def get_block_devices():
    """
    Return all local block devices that expose I/O counters, mounted or not.

    Unlike `get_real_disks()`, which is limited to block devices that currently have a mounted
    filesystem, this also includes devices without a mounted filesystem, for example raw devices
    backing a database or storage layer, or unmounted multipath/SAN volumes. Devices are
    enumerated from `/proc/diskstats`, so their names line up with the per-device I/O counters
    exposed there.

    Each device is represented as a dictionary with:
    - 'bd' : Block device path (e.g. '/dev/sda' or '/dev/dm-7').
    - 'dmd': Device-mapper path if the device is a device-mapper target (e.g.
      '/dev/mapper/data'), otherwise an empty string.
    - 'mp' : Mount point(s), space-separated if mounted in several places, or an empty string if
      the device is not mounted.

    Pseudo devices that never carry meaningful I/O are skipped by name prefix: loopback (`loop`),
    RAM disks (`ram`), compressed RAM (`zram`), floppy (`fd`) and optical (`sr`) devices.

    ### Parameters
    - None

    ### Returns
    - **list of dict**: One entry per block device, including unmounted ones. Empty list on
      systems without `/proc/diskstats` (e.g. non-Linux).

    ### Example
    >>> get_block_devices()
    [{'bd': '/dev/dm-7', 'dmd': '/dev/mapper/data', 'mp': ''},
     {'bd': '/dev/sda1', 'dmd': '', 'mp': '/boot'}]
    """
    success, diskstats = read_file('/proc/diskstats')
    if not success:
        return []

    # map every mounted block-device path to its mount point(s)
    mountpoints = {}
    mounts_ok, mounts_content = read_file('/proc/mounts')
    if mounts_ok:
        for line in mounts_content.splitlines():
            if not line.startswith('/dev/'):
                continue
            parts = line.split()
            device_path, mount_point = parts[0], parts[1]
            if device_path in mountpoints:
                mountpoints[device_path] += f' {mount_point}'
            else:
                mountpoints[device_path] = mount_point

    disks = []
    for line in diskstats.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[2]
        if name.startswith(_PSEUDO_DEVICE_PREFIXES):
            continue
        bd = f'/dev/{name}'
        dmd = bd2dmd(name)
        # a device can be mounted under its block-device path or its device-mapper path
        mp = mountpoints.get(bd, '') or (mountpoints.get(dmd, '') if dmd else '')
        disks.append({'bd': bd, 'dmd': dmd, 'mp': mp})

    return disks


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
    except OSError:
        # Optional: handle rare cases where the cwd is invalid (e.g., directory was deleted)
        return ''


def get_fingerprint(filename, length=256):
    """
    Hash a slice of a file, to recognize the file by its content instead of by its metadata.

    Metadata answers few questions about content. Two files of the same size are not
    necessarily the same, and a file that was rewritten in place keeps its inode and can end
    up with the very same size, so nothing the filesystem reports has changed although
    everything in the file has. A hash over the content answers those questions, and hashing
    a fixed-size slice of it keeps the cost independent of the file size.

    Which slice to take depends on the question:

    - The **head** is the part that stays as it is while a file is appended to, which makes it
      an identity marker: it changes when the file has become a different one (rewritten,
      replaced, truncated), not when something was added to it. Use it to tell "still the same
      file I was reading" from "a new file under the same name".
    - The **tail** changes with every write. Use it to tell whether anything was added since
      last time, not to identify the file.
    - The **whole file** is the exact answer to "is this byte-for-byte the same content", and
      the only one that also catches a change in the middle. It costs a full read.

    Compare a fingerprint only against one taken over a slice of the same size and side,
    otherwise a file that has merely grown looks like a different one. Pass the returned byte
    count back as `length` for that, and treat a count below the one requested as "the file no
    longer holds that many bytes", i.e. it was truncated.

    ### Parameters
    - **filename** (`str`):
      Path to the file to fingerprint.
    - **length** (`int`, optional):
      How many bytes to hash, and from which side:
      - `> 0`: the first `length` bytes (the head). Defaults to 256, which is enough to tell
        two lines of text apart.
      - `< 0`: the last `abs(length)` bytes (the tail).
      - `0`: the whole file, read in chunks.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if reading succeeded, otherwise False.
        - tuple[1] (**tuple | str**):
          - If successful, a `(fingerprint, hashed)` tuple: the SHA-256 hexdigest of the
            slice, and the number of bytes it was taken over. `hashed` is less than the
            requested number of bytes if the file is shorter than that.
          - If unsuccessful, an error message string.

    ### Notes
    - A file shorter than the requested slice is hashed as a whole, so head, tail and whole
      file yield the same fingerprint for it.

    ### Example
    >>> success, (fingerprint, hashed) = get_fingerprint('/var/log/messages')
    >>> success, (fingerprint, hashed) = get_fingerprint('/tmp/export', length=-4096)
    >>> success, (fingerprint, hashed) = get_fingerprint('/tmp/export', length=0)
    """
    try:
        with open(filename, mode='rb') as f:
            if length == 0:
                fingerprint = hashlib.sha256()
                hashed = 0
                # Read in chunks: the file is hashed as a whole, but never held
                # as a whole in memory.
                for chunk in iter(lambda: f.read(65536), b''):
                    fingerprint.update(chunk)
                    hashed += len(chunk)
                return True, (fingerprint.hexdigest(), hashed)
            if length < 0:
                # Seek to the start of the tail. Clamped to 0, so a file shorter
                # than the tail is read from its beginning instead of raising.
                f.seek(max(0, os.fstat(f.fileno()).st_size + length))
            data = f.read(abs(length))
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'
    return True, (hashlib.sha256(data).hexdigest(), len(data))


def get_owner(file):
    """
    Get the numeric user ID (UID) of the owner of a filesystem entry.

    ### Parameters
    - **file** *(str | os.PathLike)*:
      Path to the file or directory whose owner UID should be retrieved.

    ### Returns
    - **int**:
      The owner's UID if available; `-1` if the call fails or ownership cannot be determined.

    ### Notes
    - This function is POSIX-oriented. On Windows, `st_uid` may be `0` for all files
      and not reflect the real owner. If you need the account name on Windows,
      consider platform-specific APIs (e.g., `win32security`).
    - All exceptions are caught and result in `-1`.

    ### Example
    >>> get_owner('/etc/passwd')  # doctest: +SKIP (system-dependent)
    0
    >>> get_owner('/path/does/not/exist')
    -1
    """
    try:
        return os.stat(file).st_uid
    except OSError:
        return -1


def stat(file):
    """
    Return the `os.stat()` result for a filesystem entry, or `None` on failure.

    A single stat() syscall exposes every field (size, modification time, mode,
    owner, ...), so a caller that needs more than one of them should use this
    instead of calling `get_size()`, `get_owner()` etc. separately. The common
    fields (`st_size`, `st_mtime`, `st_mode`, `st_uid`) are available on every
    supported platform, including Windows.

    ### Parameters
    - **file** *(str | os.PathLike)*:
      Path to stat.

    ### Returns
    - **os.stat_result | None**:
      The stat result on success; `None` if the call fails (for example the path
      does not exist or is not accessible).

    ### Example
    >>> stat('/path/does/not/exist') is None
    True
    """
    try:
        return os.stat(file)
    except OSError:
        return None


def glob(pattern, recursive=True):
    """
    Return a sorted list of paths matching a shell glob pattern.

    Wraps the standard-library glob with `recursive=True` by default, so a `**`
    segment spans directories. Absolute and relative patterns both work. A
    pattern that matches nothing yields an empty list; the call never raises for
    a non-matching pattern.

    ### Parameters
    - **pattern** *(str)*:
      The glob pattern, e.g. `/var/log/**/*.log` or `*.txt`.
    - **recursive** *(bool, optional)*:
      Whether `**` should match across directory boundaries. Defaults to True.

    ### Returns
    - **list**:
      The matching paths, sorted for a deterministic order.

    ### Example
    >>> glob('/path/does/not/exist/*')
    []
    """
    return sorted(_glob.glob(pattern, recursive=recursive))


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
    Return the absolute path of the directory used for temporary files, without a trailing '/'.

    Thin wrapper around `tempfile.gettempdir()`, which picks a usable temporary directory by
    trying to create, write and delete a test file in each candidate and returning the first one
    that works. The candidates are tried in this order:

    - The directories named by the `TMPDIR`, `TEMP` and `TMP` environment variables.
    - Platform-specific defaults: on Windows `~\\AppData\\Local\\Temp`, `%SYSTEMROOT%\\Temp`,
      `c:\\temp`, `c:\\tmp`, `\\temp`, `\\tmp`; on other systems `/tmp`, `/var/tmp`, `/usr/tmp`.
    - As a last resort, the current working directory.

    The literal `/tmp` is only returned as a fallback if `tempfile.gettempdir()` itself raises.

    ### Parameters
    - None

    ### Returns
    - **str**: The absolute path to the temporary directory.

    ### Notes
    - `tempfile.gettempdir()` computes the result once and caches it; changing `TMPDIR` and
      friends afterwards has no effect for the rest of the process.
    - The path is made absolute but not symlink-resolved (`os.path.abspath`, not
      `os.path.realpath`), so a caller that needs a trusted location must validate the final path
      itself.

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

    return tmpdir or '/tmp'  # nosec B108 - fallback when tempfile.gettempdir() fails


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
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'

    match = re.search(pattern, data)
    if match:
        return True, match.group(1)
    return True, ''


def make_temp_dir(prefix=''):
    """
    Create a unique temporary directory and return its path.

    Wraps `tempfile.mkdtemp()` and reports the outcome in the same
    `(success, result)` style as the other disk helpers.

    ### Parameters
    - **prefix** (`str`, optional): Prefix for the directory name. Defaults to ''.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**str**): The created directory path on success, otherwise an
          error message.

    ### Example
    >>> make_temp_dir(prefix='myapp-')
    (True, '/tmp/myapp-abcd1234')
    """
    try:
        return True, tempfile.mkdtemp(prefix=prefix)
    except OSError as e:
        return False, f'OS error "{e.strerror}" while creating a temporary directory'
    except Exception as e:
        return False, f'Unknown error creating a temporary directory: {e}'


def mkdir(path, mode=0o755, exist_ok=True):
    """
    Create a directory, including any missing parent directories.

    Wraps `os.makedirs()` and reports the outcome in the same `(success, error)`
    style as the other disk helpers, so callers do not have to handle exceptions
    themselves.

    ### Parameters
    - **path** (`str`): Directory path to create.
    - **mode** (`int`, optional): Permission bits for newly created directories.
      Defaults to `0o755`.
    - **exist_ok** (`bool`, optional): If `True`, an already existing directory is
      not an error. Defaults to `True`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the directory exists afterwards, else False.
        - tuple[1] (**None or str**): None on success, otherwise an error message.

    ### Example
    >>> mkdir('/tmp/example/sub')
    (True, None)
    """
    try:
        os.makedirs(path, mode=mode, exist_ok=exist_ok)
        return True, None
    except OSError as e:
        return False, f'OS error "{e.strerror}" while creating {path}'
    except Exception as e:
        return False, f'Unknown error creating {path}: {e}'


def read_csv(
    filename,
    delimiter=',',
    quotechar='"',
    newline='',
    as_dict=False,
    skip_empty_rows=False,
):
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
            reader = (
                csv.DictReader(csvfile, delimiter=delimiter, quotechar=quotechar)
                if as_dict
                else csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
            )
            data = [
                row
                for row in reader
                if not (
                    skip_empty_rows
                    and all(
                        not str(v).strip()
                        for v in (row.values() if isinstance(row, dict) else row)
                    )
                )
            ]
        return True, data
    except csv.Error as e:
        line_num = getattr(reader, 'line_num', 'unknown')
        return False, f'CSV error in file {filename}, line {line_num}: {e}'
    except OSError as e:
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
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'


def read_file(filename, binary=False):
    """
    Read the contents of a file and return them.

    ### Parameters
    - **filename** (`str`): Path to the file to read.
    - **binary** (`bool`, optional): If True, read in binary mode and return the
      contents as `bytes`; otherwise decode as UTF-8 text. Defaults to False.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if reading succeeded, otherwise False.
        - tuple[1] (**str | bytes**):
          - If successful, the contents of the file (`str`, or `bytes` when
            `binary` is True).
          - If unsuccessful, an error message string.

    ### Example
    >>> success, content = read_file('example.txt')
    >>> success, raw = read_file('cert.der', binary=True)
    """
    try:
        if binary:
            with open(filename, mode='rb') as f:
                return True, f.read()
        with open(filename, mode='r', encoding='utf-8') as f:
            return True, f.read()
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}: {e}'


def rm_dir(path):
    """
    Recursively delete a directory tree.

    Wraps `shutil.rmtree()` and reports the outcome in the same `(success, error)`
    style as `rm_file()`.

    ### Parameters
    - **path** (`str`): Directory tree to delete.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if deletion succeeded, otherwise False.
        - tuple[1] (**None or str**): None on success, otherwise an error message.

    ### Example
    >>> rm_dir('/tmp/lynis')
    (True, None)
    """
    try:
        shutil.rmtree(path)
        return True, None
    except OSError as e:
        return False, f'OS error "{e.strerror}" while deleting {path}'
    except Exception as e:
        return False, f'Unknown error deleting {path}: {e}'


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


def shorten_path(path):
    """
    Shorten a path for display.

    Abbreviate a slash-separated path by reducing every component except the last one to its
    first character, the way the zsh prompt shortens a long working directory. The last
    component is kept in full because it usually carries the identifying information. This is
    a pure string transformation; the path is not resolved and the filesystem is not touched.

    ### Parameters
    - **path** (`str`): A slash-separated path, for example `/etc/pki/tls/certs/002c0b4f.0`.

    ### Returns
    - **str**: The abbreviated path, for example `/e/p/t/c/002c0b4f.0`. A value without a
      slash (a bare basename, an empty string, a sentinel like `-`) is returned unchanged.

    ### Example
    >>> shorten_path('/etc/pki/tls/certs/002c0b4f.0')
    '/e/p/t/c/002c0b4f.0'

    >>> shorten_path('index.php')
    'index.php'
    """
    if not path or '/' not in path:
        return path
    head, _, tail = path.rpartition('/')
    abbrev = '/'.join(part[:1] for part in head.split('/'))
    return f'{abbrev}/{tail}'


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
    # Only query real device nodes under /dev. Resolving the path first defends
    # against a crafted `device` that points elsewhere or smuggles arguments.
    device = os.path.realpath(device)
    if not device.startswith('/dev/'):
        return ''
    success, result = shell.shell_exec(
        ['udevadm', 'info', '--query=property', f'--name={device}']
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
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while writing {filename}'
    except Exception as e:
        return False, f'Unknown error writing {filename}: {e}'
