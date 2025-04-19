#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Microsoft PowerShell related functions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025041901'

import subprocess

from . import txt


def run_ps(cmd):
    """
    Run a PowerShell command and return the results.

    This function works cross-platform as long as PowerShell is installed and Python 3.6+ is used.
    It doesn't require any external libraries.

    ### Parameters
    - **cmd** (`str`): The PowerShell command to run.

    ### Returns
    - **dict**: A dictionary containing the following keys:
      - **args** (`list`): The arguments passed to the PowerShell command.
      - **retc** (`int`): The return code of the command. `0` indicates success.
      - **stdout** (`str`): The standard output of the command, converted from byte to Unicode.
      - **stderr** (`str`): The standard error of the command, converted from byte to Unicode.

    ### Example
    >>> run_ps('Get-Process')
    {
        'args': ['powershell', '-Command', 'Get-Process'],
        'retc': 0,
        'stdout': 'List of processes...',
        'stderr': ''
    }
    """
    try:
        result = subprocess.run(['powershell', '-Command', cmd], capture_output=True)
        return {
            'args': result.args,
            'retc': result.returncode,
            'stdout': txt.to_text(result.stdout), # convert from byte to unicode
            'stderr': txt.to_text(result.stderr), # convert from byte to unicode
        }
    except:
        return None
