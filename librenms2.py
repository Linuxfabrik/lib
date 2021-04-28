#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library collects some LibreNMS related functions that are
needed by LibreNMS check plugins."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021042801'

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
        base2.oao('Error fetching data: "{}"'.format(res), STATE_UNKNOWN, perfdata, always_ok=args.ALWAYS_OK)
    return result



