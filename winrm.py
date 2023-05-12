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
__version__ = '2023051201'

try:
    import winrm
    HAVE_WINRM = True
except ImportError:
    HAVE_WINRM = False

from . import txt


def run_ps(args, cmd):
    """Returns a dict.
    * result.status_code
    * result.std_out
    * result.std_err
    """
    try:
        if args.WINRM_DOMAIN:
            session = winrm.Session(
                args.WINRM_HOSTNAME,
                auth=('{}@{}'.format(args.WINRM_USERNAME,
                args.WINRM_DOMAIN),
                args.WINRM_PASSWORD),
                transport=args.WINRM_TRANSPORT,
            )
        else:
            session = winrm.Session(
                args.WINRM_HOSTNAME,
                auth=(args.WINRM_USERNAME, args.WINRM_PASSWORD),
                transport=args.WINRM_TRANSPORT,
            )
        result = session.run_ps(cmd) # run Powershell block
        return {
            'retc': result.status_code,
            'stdout': txt.to_text(result.std_out), # convert from byte to unicode
            'stderr': txt.to_text(result.std_err), # convert from byte to unicode
        }
    except:
        return None


def run_cmd(args, cmd, params=[]):
    """Returns a dict.
    * result.status_code
    * result.std_out
    * result.std_err
    """
    try:
        if args.WINRM_DOMAIN:
            session = winrm.Session(
                args.WINRM_HOSTNAME,
                auth=('{}@{}'.format(args.WINRM_USERNAME, args.WINRM_DOMAIN), args.WINRM_PASSWORD),
                transport=args.WINRM_TRANSPORT,
            )
        else:
            session = winrm.Session(
                args.WINRM_HOSTNAME,
                auth=(args.WINRM_USERNAME, args.WINRM_PASSWORD),
                transport=args.WINRM_TRANSPORT
            )
        result = session.run_cmd(cmd, params) # run command in cmd.exe
        return {
            'retc': result.status_code,
            'stdout': txt.to_text(result.std_out), # convert from byte to unicode
            'stderr': txt.to_text(result.std_err), # convert from byte to unicode
        }
    except:
        return None
