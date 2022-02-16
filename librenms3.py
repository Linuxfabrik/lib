#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library collects some LibreNMS related functions that are
needed by LibreNMS check plugins."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2022021602'

from .globals3 import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN

from . import base3 # pylint: disable=C0413
from . import txt3 # pylint: disable=C0413
from . import url3 # pylint: disable=C0413


def get_data(args, url=''):
    url = '{}{}'.format(args.URL, url)
    header = {'X-Auth-Token': args.TOKEN}
    result = base3.coe(url3.fetch_json(
        url,
        header=header,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    ))
    if result['status'].lower() != 'ok':
        base3.oao(
            'Error fetching data: "{}"'.format(result),
            STATE_UNKNOWN,
            always_ok=args.ALWAYS_OK,
        )
    return result


def get_prop(obj, prop, mytype='str'):
    """Get a property of a dict, for example device['uptime'], and handle None-values."""
    if mytype == 'str':
        if prop in obj:
            if obj[prop] is not None:
                return txt.to_text(obj[prop])
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
