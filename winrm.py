#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Microsoft WinRM related functions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

try:
    import winrm
    HAVE_WINRM = True
except ImportError:
    HAVE_WINRM = False

from . import txt


def run_cmd(args, cmd, params=None):
    """
    Execute a command over WinRM using cmd.exe and return the result.

    This function runs a command remotely on a Windows machine using WinRM via `cmd.exe`.
    It handles authentication with or without a domain and returns the result as a dictionary.

    ### Parameters
    - **args** (object):
      An object containing:
        - `WINRM_HOSTNAME` (`str`): The target hostname or IP.
        - `WINRM_USERNAME` (`str`): WinRM username.
        - `WINRM_PASSWORD` (`str`): WinRM password.
        - `WINRM_DOMAIN` (`str`, optional): Domain name, if applicable.
        - `WINRM_TRANSPORT` (`str`): Transport method (e.g., 'ntlm', 'kerberos').
    - **cmd** (`str`): The command to run (e.g., `ipconfig`).
    - **params** (`list`, optional): List of command-line parameters. Defaults to empty list.

    ### Returns
    - **dict**:
      A dictionary with keys:
        - `retc` (`int`): The status code from the command execution.
        - `stdout` (`str`): The standard output as a string.
        - `stderr` (`str`): The standard error as a string.
    - **None**:
      If the connection or execution fails.

    ### Notes
    - Converts `std_out` and `std_err` from bytes to Unicode text.
    - Uses `winrm.Session().run_cmd()`.

    ### Example
    >>> result = run_cmd(args, 'ipconfig')
    >>> print(result['stdout'])
    """
    try:
        auth = (args.WINRM_USERNAME, args.WINRM_PASSWORD)
        if getattr(args, 'WINRM_DOMAIN', None):
            auth = ('{}@{}'.format(args.WINRM_USERNAME, args.WINRM_DOMAIN), args.WINRM_PASSWORD)

        session = winrm.Session(
            args.WINRM_HOSTNAME,
            auth=auth,
            transport=args.WINRM_TRANSPORT,
        )

        if params is None:
            params = []

        result = session.run_cmd(cmd, params)
        return {
            'retc': result.status_code,
            'stdout': txt.to_text(result.std_out),
            'stderr': txt.to_text(result.std_err),
        }
    except Exception:
        return None


def run_ps(args, cmd):
    """
    Execute a PowerShell command over WinRM and return the result.

    This function runs a PowerShell command remotely on a Windows machine via WinRM.
    It handles authentication with or without a domain and returns the result as a dictionary.

    ### Parameters
    - **args** (object):
      An object containing:
        - `WINRM_HOSTNAME` (`str`): The target hostname or IP.
        - `WINRM_USERNAME` (`str`): WinRM username.
        - `WINRM_PASSWORD` (`str`): WinRM password.
        - `WINRM_DOMAIN` (`str`, optional): Domain name, if applicable.
        - `WINRM_TRANSPORT` (`str`): Transport method (e.g., 'ntlm', 'kerberos').
    - **cmd** (`str`): The PowerShell command to run.

    ### Returns
    - **dict**:
      A dictionary with keys:
        - `retc` (`int`): The status code from the command execution.
        - `stdout` (`str`): The standard output as a string.
        - `stderr` (`str`): The standard error as a string.
    - **None**:
      If the connection or execution fails.

    ### Notes
    - Converts `std_out` and `std_err` from bytes to Unicode text.
    - Uses `winrm.Session().run_ps()`.

    ### Example
    >>> result = run_ps(args, 'Get-Process')
    >>> print(result['stdout'])
    """
    try:
        auth = (args.WINRM_USERNAME, args.WINRM_PASSWORD)
        if args.WINRM_DOMAIN:
            auth = ('{}@{}'.format(args.WINRM_USERNAME, args.WINRM_DOMAIN), args.WINRM_PASSWORD)

        session = winrm.Session(
            args.WINRM_HOSTNAME,
            auth=auth,
            transport=args.WINRM_TRANSPORT,
        )

        result = session.run_ps(cmd)
        return {
            'retc': result.status_code,
            'stdout': txt.to_text(result.std_out),
            'stderr': txt.to_text(result.std_err),
        }
    except Exception:
        return None
