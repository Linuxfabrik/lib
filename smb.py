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
__version__ = '2023051201'

import sys

from .globals import STATE_UNKNOWN
import smbclient
import smbprotocol.exceptions

def open_file(filename, username, password, timeout, encrypt=True):
    """Returns the binary-encoded contents of a file from an SMB storage device.

    >>> with lib.base.coe(lib.smb.open_file(url, args.USERNAME, args.PASSWORD, args.TIMEOUT)) as fd:
    >>>     result = lib.txt.to_text(fd.read())
    """
    try:
        return (
            True,
            smbclient.open_file(
                filename,
                mode='rb',
                username=username,
                password=password,
                connection_timeout=timeout,
                encrypt=encrypt,
            )
        )
    except (smbprotocol.exceptions.SMBAuthenticationError, smbprotocol.exceptions.LogonFailure) as e:
        return (False, e)
    except smbprotocol.exceptions.SMBOSError as e:
        if isinstance(e.__context__, smbprotocol.exceptions.FileIsADirectory):
            return (False, 'The file that was specified as a target is a directory, should be a file.')
        if isinstance(e.__context__, smbprotocol.exceptions.ObjectNameNotFound):
            return (False, 'No such file or directory on the smb server.')
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except Exception as e:
        return (False, 'Unknown error opening or reading {}:\n{}'.format(filename, e))


def glob(filename, username, password, timeout, pattern='*', encrypt=True):
    try:
        file_entry = smbclient._os.SMBDirEntry.from_path(
            filename,
            username=username,
            password=password,
            connection_timeout=timeout,
            encrypt=encrypt,
        )

        if file_entry.is_file():
            return (True, [file_entry])

        # converting generator to list here to trigger any exception when accessing files now. this could probably be improved
        return (True, list(smbclient.scandir(
            filename,
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
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except Exception as e:
        return (False, 'Unknown error opening or reading {}:\n{}'.format(filename, e))
