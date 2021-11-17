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
__version__ = '2021111702'

try:
    import winrm
except ImportError as e:
    winrm_found = False
else:
    winrm_found = True


def run_ps(args, cmd):
    """Returns a winrm object.
    * result.status_code
    * result.std_out
    * result.std_err
    """
    try:
        if args.WINRM_DOMAIN:
            session = winrm.Session(args.WINRM_HOSTNAME, auth=('{}@{}'.format(args.WINRM_USERNAME, args.WINRM_DOMAIN), args.WINRM_PASSWORD), transport=args.WINRM_TRANSPORT)
        else:
            session = winrm.Session(args.WINRM_HOSTNAME, auth=(args.WINRM_USERNAME, args.WINRM_PASSWORD), transport=args.WINRM_TRANSPORT)
        result = session.run_ps(cmd) # run Powershell block
        return {
            'retc': result.status_code,
            'stdout': result.std_out.decode(), # convert from byte to unicode
            'stderr': result.std_err.decode(), # convert from byte to unicode
        }
    except:
        return None


def run_cmd(args, cmd, params=[]):
    """Returns a winrm object.
    * result.status_code
    * result.std_out
    * result.std_err
    """
    try:
        if args.WINRM_DOMAIN:
            session = winrm.Session(args.WINRM_HOSTNAME, auth=('{}@{}'.format(args.WINRM_USERNAME, args.WINRM_DOMAIN), args.WINRM_PASSWORD), transport=args.WINRM_TRANSPORT)
        else:
            session = winrm.Session(args.WINRM_HOSTNAME, auth=(args.WINRM_USERNAME, args.WINRM_PASSWORD), transport=args.WINRM_TRANSPORT)
        result = session.run_cmd(cmd, params) # run command in cmd.exe
        return {
            'retc': result.status_code,
            'stdout': result.std_out.decode(), # convert from byte to unicode
            'stderr': result.std_err.decode(), # convert from byte to unicode
        }
    except:
        return None
