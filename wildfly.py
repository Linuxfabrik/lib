#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some WildFly/JBoss related functions that are
needed by more than one WildFly/JBoss plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

from . import base
from . import url
from .globals import STATE_UNKNOWN


def get_data(args, data, uri=''):
    uri = args.URL + '/management' + uri
    if args.MODE == 'domain':
        uri = '{}/host/{}/server/{}'.format(uri, args.NODE, args.INSTANCE)
    header = {'Content-Type': 'application/json'}
    result = base.coe(url.fetch_json(
        uri, timeout=args.TIMEOUT,
        header=header, data=data,
        digest_auth_user=args.USERNAME, digest_auth_password=args.PASSWORD,
        encoding='serialized-json'
    ))
    if result['outcome'] != 'success':
        base.oao('Error fetching data: "{}"'.format(result), STATE_UNKNOWN, always_ok=args.ALWAYS_OK)
    return result['result']
