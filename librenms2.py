#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some LibreNMS related functions that are
needed by LibreNMS check plugins."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2022021601'

from globals2 import STATE_OK, STATE_UNKNOWN, STATE_WARN, STATE_CRIT

import base2
import url2


def get_data(args, url=''):
    url = args.URL + url
    header = {'X-Auth-Token': args.TOKEN}
    result = base2.coe(url2.fetch_json(
        url, timeout=args.TIMEOUT,
        header=header,
        insecure=args.INSECURE, no_proxy=args.NO_PROXY,
    ))
    if result['status'] != 'ok':
        base2.oao(u'Error fetching data: "{}"'.format(result), STATE_UNKNOWN, always_ok=args.ALWAYS_OK)
    return result


def get_prop(obj, prop, mytype='str'):
    """Get a property of a dict, for example device['uptime'], and handle None-values."""
    if mytype == 'str':
        if prop in obj:
            if obj[prop] is not None:
                return obj[prop].encode('utf-8', 'replace')
        return ''
    if prop in obj:
        if obj[prop] is not None:
            return obj[prop]
    return None


def get_state(librestate):
    if librestate == 'ok':
        return STATE_OK
    if librestate == 'warning':
        return STATE_WARN
    if librestate == 'critical':
        return STATE_CRIT
    return STATE_UNKNOWN
