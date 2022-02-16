#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library collects some Jitsi related functions that are
needed by more than one Jitsi plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2022021601'

import base64 # pylint: disable=C0413

from . import url3


def get_data(args, _type='json'):
    """Calls args.URL, optionally using args.USERNAME and args.PASSWORD,
    taking args.TIMEOUT into account, returning JSON (`type='json'`) or raw data (else).
    """
    if args.USERNAME is None:
        if _type == 'json':
            success, result = url3.fetch_json(args.URL, timeout=args.TIMEOUT, insecure=True)
        else:
            success, result = url3.fetch(args.URL, timeout=args.TIMEOUT, insecure=True, extended=True)
    else:
        header = {}
        header['Authorization'] = 'Basic {}'.format(base64.b64encode(args.USERNAME + ':' + args.PASSWORD))
        if _type == 'json':
            success, result = url3.fetch_json(args.URL, header=header, timeout=args.TIMEOUT, insecure=True)
        else:
            success, result = url3.fetch(args.URL, header=header, timeout=args.TIMEOUT, insecure=True, extended=True)

    if not success:
        return (success, result, False)
    return (True, result)
