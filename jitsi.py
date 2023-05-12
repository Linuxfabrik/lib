#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Jitsi related functions that are
needed by more than one Jitsi plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

import base64 # pylint: disable=C0413

from . import url


def get_data(args, _type='json'):
    """Calls args.URL, optionally using args.USERNAME and args.PASSWORD,
    taking args.TIMEOUT into account, returning JSON (`type='json'`) or raw data (else).
    """
    header = {}
    if not args.USERNAME is None:
        header['Authorization'] = 'Basic {}'.format(
            base64.b64encode(args.USERNAME + ':' + args.PASSWORD)
        )
    if _type == 'json':
        success, result = url.fetch_json(
            args.URL,
            extended=True,
            header=header,
            insecure=True,
            timeout=args.TIMEOUT,
        )
    else:
        success, result = url.fetch(
            args.URL,
            extended=True,
            header=header,
            insecure=True,
            timeout=args.TIMEOUT,
        )

    if not success:
        return (success, result, False)
    return (True, result)
