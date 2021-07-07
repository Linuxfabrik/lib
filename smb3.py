#! /usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Provides functions to establish SMB connections.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021021501'

import os.path

missing_smb_lib = False
try:
    import smbclient
    import smbprotocol.exceptions
except ImportError as e:
    missing_smb_lib = 'smbclient'


def open_file(path, username, password, timeout, encrypt=True):
    if missing_smb_lib:
        return (False, f'Python module "{missing_smb_lib}" is not installed.')
    try:
        return (True, smbclient.open_file(
                path,
                mode='rb',
                username=username,
                password=password,
                connection_timeout=timeout,
                encrypt=encrypt,
            ))
    except (smbprotocol.exceptions.SMBAuthenticationError, smbprotocol.exceptions.LogonFailure):
        return (False, 'Login failed')
    except smbprotocol.exceptions.SMBOSError as e:
        if isinstance(e.__context__, smbprotocol.exceptions.FileIsADirectory):
            return (False, 'The file that was specified as a target is a directory, should be a file.')
        if isinstance(e.__context__, smbprotocol.exceptions.ObjectNameNotFound):
            return (False, 'No such file or directory on the smb server.')
        return (False, f'I/O error "{e.strerror}" while opening or reading {path}')
    except Exception as e:
        return (False, f'Unknown error opening or reading {path}:\n{e}')


def glob(path, username, password, timeout, pattern='*', encrypt=True):
    if missing_smb_lib:
        return (False, f'Python module "{missing_smb_lib}" is not installed.')
    try:
        file_entry = smbclient._os.SMBDirEntry.from_path(
                path,
                username=username,
                password=password,
                connection_timeout=timeout,
                encrypt=encrypt,
            )

        if file_entry.is_file():
            return (True, [file_entry])

        # converting generator to list here to trigger any exception when accessing files now. this could probably be improved
        return (True, list(smbclient.scandir(
                path,
                mode='rb',
                username=username,
                password=password,
                connection_timeout=timeout,
                search_pattern=pattern,
                encrypt=encrypt,
            )))
    except (smbprotocol.exceptions.SMBAuthenticationError, smbprotocol.exceptions.LogonFailure):
        return (False, 'Login failed')
    except smbprotocol.exceptions.SMBOSError as e:
        if isinstance(e.__context__, smbprotocol.exceptions.ObjectNameNotFound):
            return (False, 'No such file or directory on the smb server.')
        if e.strerror == 'No such file or directory':
            return (True, [])
        return (False, f'I/O error "{e.strerror}" while opening or reading {path}')
    except Exception as e:
        return (False, f'Unknown error opening or reading {path}:\n{e}')
