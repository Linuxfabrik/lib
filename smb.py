#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides functions to establish native SMB connections.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

import sys

from .globals import STATE_UNKNOWN
import smbclient
import smbprotocol.exceptions


def glob(filename, username, password, timeout, pattern='*', encrypt=True):
    """
    List matching files or a single file from an SMB storage device.

    Connects to the SMB server and retrieves file entries matching the given pattern.

    ### Parameters
    - **filename** (`str`): Full SMB path to the file or directory.
    - **username** (`str`): Username for authentication.
    - **password** (`str`): Password for authentication.
    - **timeout** (`int`): Connection timeout in seconds.
    - **pattern** (`str`, optional): Glob pattern to match files. Default is `'*'`.
    - **encrypt** (`bool`, optional): Enable SMB encryption if available. Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `list` or `str`):
      - `True` and a list of file entries if successful.
      - `False` and an error message otherwise.

    ### Notes
    - Converts generator from `scandir()` to a list immediately to catch any exceptions early.

    ### Example
    >>> success, files = lib.smb.glob('smb://server/share', 'user', 'pass', timeout=5)
    """
    try:
        file_entry = smbclient._os.SMBDirEntry.from_path(
            filename,
            username=username,
            password=password,
            connection_timeout=timeout,
            encrypt=encrypt,
        )
        if file_entry.is_file():
            return True, [file_entry]

        files = list(smbclient.scandir(
            filename,
            mode='rb',
            username=username,
            password=password,
            connection_timeout=timeout,
            search_pattern=pattern,
            encrypt=encrypt,
        ))
        return True, files

    except (smbprotocol.exceptions.SMBAuthenticationError, smbprotocol.exceptions.LogonFailure):
        return False, 'Login failed'
    except smbprotocol.exceptions.SMBOSError as e:
        context = getattr(e, '__context__', None)
        if isinstance(context, smbprotocol.exceptions.ObjectNameNotFound):
            return False, 'No such file or directory on the SMB server.'
        if e.strerror == 'No such file or directory':
            return True, []
        return False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename)
    except Exception as e:
        return False, 'Unknown error opening or reading {}:\n{}'.format(filename, e)


def open_file(filename, username, password, timeout, encrypt=True):
    """
    Retrieve the binary content of a file from an SMB storage device.

    This function connects to an SMB server and attempts to open the specified file for reading
    in binary mode.

    ### Parameters
    - **filename** (`str`): The full SMB path to the file.
    - **username** (`str`): Username for authentication.
    - **password** (`str`): Password for authentication.
    - **timeout** (`int`): Connection timeout in seconds.
    - **encrypt** (`bool`, optional): Enable SMB encryption if available. Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `object` or `str`):
      - `True` and a file descriptor if successful.
      - `False` and an error message otherwise.

    ### Notes
    - Wrap the returned file object in a `with` block to ensure it is properly closed.

    ### Example
    >>> with lib.base.coe(lib.smb.open_file(url, args.USERNAME, args.PASSWORD, args.TIMEOUT)) as fd:
    >>>     result = lib.txt.to_text(fd.read())
    """
    try:
        file_obj = smbclient.open_file(
            filename,
            mode='rb',
            username=username,
            password=password,
            connection_timeout=timeout,
            encrypt=encrypt,
        )
        return True, file_obj
    except (smbprotocol.exceptions.SMBAuthenticationError, smbprotocol.exceptions.LogonFailure) as e:
        return False, str(e)
    except smbprotocol.exceptions.SMBOSError as e:
        if isinstance(getattr(e, '__context__', None), smbprotocol.exceptions.FileIsADirectory):
            return False, 'The file specified is a directory, expected a file.'
        if isinstance(getattr(e, '__context__', None), smbprotocol.exceptions.ObjectNameNotFound):
            return False, 'No such file or directory on the SMB server.'
        return False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename)
    except Exception as e:
        return False, 'Unknown error opening or reading {}:\n{}'.format(filename, e)
