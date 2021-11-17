#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library collects some Microsoft PowerShell related functions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021111701'

import subprocess


def run_ps(cmd):
    """
    You will need PowerShell installed on your system and Python 3.6+.
    This would work cross-platform. No need for external libraries.

    Returns
    * result.args (list)
    * result.returncode: 0 = ok
    * result.stdout: Byte-String
    * result.stderr: Byte-String
    """
    try:
        result = subprocess.run(['powershell', '-Command', cmd], capture_output=True)
        return {
            'args': result.args,
            'retc': result.returncode,
            'stdout': result.stdout.decode(), # convert from byte to unicode
            'stderr': result.stderr.decode(), # convert from byte to unicode
        }
    except:
        return None
