#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Provides functions to establish native SMB connections."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026092501'


# smbclient and smbprotocol take about 45 ms to import. `_import_smbclient()` loads them on
# the first call, so a consumer that imports this module without touching a share neither
# pays for them nor fails on a host where they are not installed. Verified with
# `python3.9 -X importtime` on Fedora 44, smbprotocol 1.16.1.
_NOT_IMPORTED = object()
smbclient = _NOT_IMPORTED
smbprotocol = _NOT_IMPORTED


def _import_smbclient():
    """Import smbclient and smbprotocol on first use and bind them to this module.
    Returns `None`, or an error message naming the module that is not installed."""
    global smbclient, smbprotocol
    try:
        if smbclient is _NOT_IMPORTED:
            import smbclient
        if smbprotocol is _NOT_IMPORTED:
            import smbprotocol.exceptions
    except ImportError as e:
        return f'Python module "{e.name or "smbprotocol"}" is not installed.'
    return None


def glob(filename, username, password, timeout, pattern='*', encrypt=True):
    """
    List matching files or a single file from an SMB storage device.

    Connects to the SMB server and retrieves file entries matching the given pattern.

    Parameters
    ----------
    filename : str
        Full SMB path to the file or directory.
    username : str
        Username for authentication.
    password : str
        Password for authentication.
    timeout : int
        Connection timeout in seconds.
    pattern : str, optional
        Glob pattern to match files. Default is `'*'`.
    encrypt : bool, optional
        Enable SMB encryption if available. Defaults to `True`.

    Returns
    -------
    tuple (bool, list or str)
        - `True` and a list of file entries if successful.
        - `False` and an error message otherwise.

    Notes
    -----
    - Converts generator from `scandir()` to a list immediately to catch any exceptions early.

    Examples
    --------
    >>> success, files = lib.smb.glob('smb://server/share', 'user', 'pass', timeout=5)
    """
    error = _import_smbclient()
    if error:
        return False, error
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

        files = list(
            smbclient.scandir(
                filename,
                mode='rb',
                username=username,
                password=password,
                connection_timeout=timeout,
                search_pattern=pattern,
                encrypt=encrypt,
            )
        )
        return True, files

    except (
        smbprotocol.exceptions.SMBAuthenticationError,
        smbprotocol.exceptions.LogonFailure,
    ):
        return False, 'Login failed'
    except smbprotocol.exceptions.SMBOSError as e:
        context = getattr(e, '__context__', None)
        if isinstance(context, smbprotocol.exceptions.ObjectNameNotFound):
            return False, 'No such file or directory on the SMB server.'
        if e.strerror == 'No such file or directory':
            return True, []
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}:\n{e}'


def open_file(filename, username, password, timeout, encrypt=True):
    """
    Retrieve the binary content of a file from an SMB storage device.

    This function connects to an SMB server and attempts to open the specified file for reading
    in binary mode.

    Parameters
    ----------
    filename : str
        The full SMB path to the file.
    username : str
        Username for authentication.
    password : str
        Password for authentication.
    timeout : int
        Connection timeout in seconds.
    encrypt : bool, optional
        Enable SMB encryption if available. Defaults to `True`.

    Returns
    -------
    tuple (bool, object or str)
        - `True` and a file descriptor if successful.
        - `False` and an error message otherwise.

    Notes
    -----
    - Wrap the returned file object in a `with` block to ensure it is properly closed.

    Examples
    --------
    >>> with lib.base.coe(
    ...     lib.smb.open_file(url, args.USERNAME, args.PASSWORD, args.TIMEOUT)
    ... ) as fd:
    ...     result = lib.txt.to_text(fd.read())
    """
    error = _import_smbclient()
    if error:
        return False, error
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
    except (
        smbprotocol.exceptions.SMBAuthenticationError,
        smbprotocol.exceptions.LogonFailure,
    ) as e:
        return False, str(e)
    except smbprotocol.exceptions.SMBOSError as e:
        if isinstance(
            getattr(e, '__context__', None), smbprotocol.exceptions.FileIsADirectory
        ):
            return False, 'The file specified is a directory, expected a file.'
        if isinstance(
            getattr(e, '__context__', None), smbprotocol.exceptions.ObjectNameNotFound
        ):
            return False, 'No such file or directory on the SMB server.'
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}:\n{e}'
