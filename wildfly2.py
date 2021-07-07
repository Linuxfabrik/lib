#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library collects some WildFly/JBoss related functions that are
needed by more than one WildFly/JBoss plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021041901'

import base2
import url2


def get_data(args, data, url=''):
    url = args.URL + '/management' + url
    if args.MODE == 'domain':
        url = '/host/{}/server/{}'.format(args.NODE, args.INSTANCE) + url
    header = {'Content-Type': 'application/json'}
    result = base2.coe(url2.fetch_json(
        url, timeout=args.TIMEOUT,
        header=header, data=data,
        digest_auth_user=args.USERNAME, digest_auth_password=args.PASSWORD,
        encoding='serialized-json'
        ))
    if result['outcome'] != 'success':
        base2.oao('Error fetching data: "{}"'.format(res), STATE_UNKNOWN, perfdata, always_ok=args.ALWAYS_OK)
    return result['result']



