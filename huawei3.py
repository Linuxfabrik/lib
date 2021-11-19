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
__version__ = '2021111901'

import time

from .globals3 import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN

from . import base3
from . import cache3
from . import url3


def get_creds(args):
    # we cache credentials to reuse them until they expire, because logins might be
    # rate-limited for security reasons
    ibasetoken = cache3.get('huawei-{}-ibasetoken'.format(args.DEVICE_ID))
    cookie = cache3.get('huawei-{}-cookie'.format(args.DEVICE_ID))
    if ibasetoken:
        return ibasetoken, cookie

    url = '{}/deviceManager/rest/{}/sessions'.format(args.URL, args.DEVICE_ID)
    header = {
        'Content-Type': 'application/json',
    }
    data = {
        'username': args.USERNAME,
        'password': args.PASSWORD,
        'scope': args.SCOPE,
    }
    result = base3.coe(url3.fetch_json(
        url,
        data=data,
        encoding='serialized-json',
        extended=True,
        header=header,
        insecure=True,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    ))
    ibasetoken = result['response_json'].get('data').get('iBaseToken')
    cookie = result['response_header'].getheader('Set-Cookie')
    expire = base3.now() + args.CACHE_EXPIRE*60
    cache3.set('huawei-{}-ibasetoken'.format(args.DEVICE_ID), ibasetoken, expire)
    cache3.set('huawei-{}-cookie'.format(args.DEVICE_ID), cookie, expire)
    return ibasetoken, cookie


def get_data(endpoint, args):
    # login and get iBaseToken and Cookie
    ibasetoken, cookie = get_creds(args)

    # fetch data
    url = '{}/deviceManager/rest/{}/{}'.format(
        args.URL,
        args.DEVICE_ID,
        endpoint,
    )
    header = {
        'Content-Type': 'application/json',
        'iBaseToken' : ibasetoken,
        'Cookie': cookie,
    }

    # Sometimes we get "-401: This operation fails to be performed because of the unauthorized
    # REST.", and shortly after that everything works as expected. Crap. So try to fetch
    # info multiple times, but limit the queries to a certain amount.
    counter = 0
    while True:
        counter += 1
        result = base3.coe(url3.fetch_json(
            url,
            header=header,
            insecure=True,
            no_proxy=args.NO_PROXY,
            timeout=args.TIMEOUT,
        ))
        if result.get('error').get('code') == 0:
            break
        if counter == 9:
            break
        time.sleep(1)
    result['counter'] = counter
    return result


def get_health_status(hs):
    if int(hs) == 1:
        return 'Normal'
    if int(hs) == 2:
        return 'Faulty'
    if int(hs) == 3:
        return 'About to fail'
    if int(hs) == 17:
        return 'Single link'
    return 'Unknown'


def get_running_status(rs):
    if int(rs) == 1:
        return 'Normal'
    if int(rs) == 3:
        return 'Not running'
    if int(rs) == 12:
        return 'Powering on'
    if int(rs) == 14:
        return 'Pre-Copy'
    if int(rs) == 16:
        return 'Reconstruction'
    if int(rs) == 27:
        return 'Online'
    if int(rs) == 28:
        return 'Offline'
    if int(rs) == 47:
        return 'Powering off'
    if int(rs) == 51:
        return 'Upgrading'
    if int(rs) == 114:
        return 'Erasing'
    if int(rs) == 115:
        return 'Verifying'
    return 'Unknown'


def get_product_mode(pm):
    if int(pm) == 812:
        return 'Dorado 5000 V6 (NVMe)'
    if int(pm) == 813:
        return 'Dorado 6000 V6 (SAS)'
    if int(pm) == 814:
        return 'Dorado 6000 V6 (NVMe)'
    if int(pm) == 815:
        return 'Dorado 8000 V6 (SAS)'
    if int(pm) == 816:
        return 'Dorado 8000 V6 (NVMe)'
    if int(pm) == 817:
        return 'Dorado 18000 V6 (SAS)'
    if int(pm) == 818:
        return 'Dorado 18000 V6 (NVMe)'
    if int(pm) == 819:
        return 'Dorado 3000 V6 (SAS)'
    if int(pm) == 821:
        return 'Dorado 5000 V6 (IP SAS)'
    if int(pm) == 822:
        return 'Dorado 6000 V6 (IP SAS)'
    if int(pm) == 823:
        return 'Dorado 8000 V6 (IP SAS)'
    if int(pm) == 824:
        return 'Dorado 18000 V6 (IP SAS)'
    if int(pm) == 825:
        return 'Dorado 3000 V6 '
    if int(pm) == 826:
        return 'Dorado 5000 V6'
    if int(pm) == 827:
        return 'Dorado 6000 V6'
    if int(pm) == 828:
        return 'Dorado 6000 V6'
    if int(pm) == 829:
        return 'Dorado 8000 V6'
    if int(pm) == 830:
        return 'Dorado 18000 V6'
    if int(pm) == 831:
        return 'Dorado 18000 V6'
    if int(pm) == 832:
        return 'Dorado 18000 V6'
    return 'Unknown'

