#! /usr/bin/env python3
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
__version__ = '2024020901'

import base64
import json

from .globals import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN

from . import base # pylint: disable=C0413
from . import cache # pylint: disable=C0413
from . import time # pylint: disable=C0413
from . import txt # pylint: disable=C0413
from . import url # pylint: disable=C0413


def get_data(args, uri=''):
    """Fetch JSON data from LibreNMS' REST-API. Cache the results for 60 seconds
    to not overload the server if checking thousands of devices.
    """
    uri = '{}{}'.format(args.URL, uri)
    cache_filename = 'linuxfabrik-lib-librenms-{}.db'.format(
        txt.to_text(base64.urlsafe_b64encode(txt.to_bytes(uri))),
    )
    try:
        cache_table = '-'.join(args.DEVICE_TYPE)
    except:
        cache_table = 'all'

    # gather data - first load from cache
    result = cache.get(
        cache_table,
        filename=cache_filename,
    )
    if result:
        try:
            result = json.loads(result)
        except json.decoder.JSONDecodeError:
            # don't care, we'll fetch new info
            result = False
    if not result:
        # nothing or nothing valid found? load from web
        result = base.coe(url.fetch_json(
            uri,
            header={'X-Auth-Token': args.TOKEN},
            insecure=args.INSECURE,
            no_proxy=args.NO_PROXY,
            timeout=args.TIMEOUT,
        ))
        if result['status'].lower() != 'ok':
            base.oao(
                'Error fetching data: "{}"'.format(result),
                STATE_UNKNOWN,
                always_ok=args.ALWAYS_OK,
            )
        # update the cache with the new info
        retc = cache.set(
            cache_table,
            json.dumps(result),
            expire=time.now() + 60,
            filename=cache_filename,
        )

    return result


def get_prop(obj, prop, mytype='str'):
    """Get a property of a dict, for example device['uptime'], and handle None-values.
    """
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
    """Translate LibreNMS' states into Nagios states.
    """
    if librestate == 'ok':
        return STATE_OK
    if librestate == 'warning':
        return STATE_WARN
    if librestate == 'critical':
        return STATE_CRIT
    return STATE_UNKNOWN
