#! /usr/bin/env python2
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
__version__ = '2021112202'

import time

from globals2 import STATE_OK, STATE_UNKNOWN, STATE_WARN, STATE_CRIT

import base2
import cache2
import url2


def get_creds(args):
    # we cache credentials to reuse them until they expire, because logins might be
    # rate-limited for security reasons
    ibasetoken = cache2.get('huawei-{}-ibasetoken'.format(args.DEVICE_ID))
    cookie = cache2.get('huawei-{}-cookie'.format(args.DEVICE_ID))
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
    result = base2.coe(url2.fetch_json(
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
    expire = base2.now() + args.CACHE_EXPIRE*60
    cache2.set('huawei-{}-ibasetoken'.format(args.DEVICE_ID), ibasetoken, expire)
    cache2.set('huawei-{}-cookie'.format(args.DEVICE_ID), cookie, expire)
    return ibasetoken, cookie


def get_data(endpoint, args, params=''):
    # login and get iBaseToken and Cookie
    ibasetoken, cookie = get_creds(args)

    # fetch data
    url = '{}/deviceManager/rest/{}/{}{}'.format(
        args.URL,
        args.DEVICE_ID,
        endpoint,
        params,
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
        result = base2.coe(url2.fetch_json(
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
        return 'Normal (1)'
    if int(hs) == 2:
        return 'Faulty (2)'
    if int(hs) == 3:
        return 'About to fail (3)'
    if int(hs) == 4:
        return 'Partially damaged (4)'
    if int(hs) == 5:
        return 'Degraded (5)'
    if int(hs) == 9:
        return 'Inconsistent (9)'
    if int(hs) == 11:
        return 'No Input (11)'
    if int(hs) == 12:
        return 'Low Battery (12)'
    if int(hs) == 14:
        return 'Invalid (14)'
    if int(hs) == 15:
        return 'Write-protected (15)'
    if int(hs) == 17:
        return 'Single link (17)'
    if int(hs) == 18:
        return 'Offline (18)'
    return 'Unknown'


def get_runlevel(rl):
    if int(rl) == 0:
        return 'low (0)'
    if int(rl) == 1:
        return 'normal (1)'
    if int(rl) == 2:
        return 'high (2)'
    return 'Unknown'


def get_running_status(rs):
    if int(rs) == 1:
        return 'Normal (1)'
    if int(rs) == 2:
        return 'Running (2)'
    if int(rs) == 3:
        return 'Not running (3)'
    if int(rs) == 5:
        return 'Sleep in High Temperature (5)'
    if int(rs) == 12:
        return 'Powering on (12)'
    if int(rs) == 14:
        return 'Pre-Copy (14)'
    if int(rs) == 16:
        return 'Reconstruction (16)'
    if int(rs) == 23:
        return 'Synchronizing (23)'
    if int(rs) == 27:
        return 'Online (27)'
    if int(rs) == 28:
        return 'Offline (28)'
    if int(rs) == 35:
        return 'Invalid (35)'
    if int(rs) == 41:
        return 'Paused (41)'
    if int(rs) == 47:
        return 'Powering off (47)'
    if int(rs) == 51:
        return 'Upgrading (51)'
    if int(rs) == 93:
        return 'Forcibly started (93)'
    if int(rs) == 100:
        return 'To be synchronized (100)'
    if int(rs) == 105:
        return 'Abnormal (105)'
    if int(rs) == 114:
        return 'Erasing (114)'
    if int(rs) == 115:
        return 'Verifying (115)'
    return 'Unknown'


def get_product_mode(pm):
    if int(pm) == 812:
        return 'Dorado 5000 V6 (NVMe) (812)'
    if int(pm) == 813:
        return 'Dorado 6000 V6 (SAS) (813)'
    if int(pm) == 814:
        return 'Dorado 6000 V6 (NVMe) (814)'
    if int(pm) == 815:
        return 'Dorado 8000 V6 (SAS) (815)'
    if int(pm) == 816:
        return 'Dorado 8000 V6 (NVMe) (816)'
    if int(pm) == 817:
        return 'Dorado 18000 V6 (SAS) (817)'
    if int(pm) == 818:
        return 'Dorado 18000 V6 (NVMe) (818)'
    if int(pm) == 819:
        return 'Dorado 3000 V6 (SAS) (819)'
    if int(pm) == 821:
        return 'Dorado 5000 V6 (IP SAS) (821)'
    if int(pm) == 822:
        return 'Dorado 6000 V6 (IP SAS) (822)'
    if int(pm) == 823:
        return 'Dorado 8000 V6 (IP SAS) (823)'
    if int(pm) == 824:
        return 'Dorado 18000 V6 (IP SAS) (824)'
    if int(pm) == 825:
        return 'Dorado 3000 V6  (825)'
    if int(pm) == 826:
        return 'Dorado 5000 V6 (826)'
    if int(pm) == 827:
        return 'Dorado 6000 V6 (827)'
    if int(pm) == 828:
        return 'Dorado 6000 V6 (828)'
    if int(pm) == 829:
        return 'Dorado 8000 V6 (829)'
    if int(pm) == 830:
        return 'Dorado 18000 V6 (830)'
    if int(pm) == 831:
        return 'Dorado 18000 V6 (831)'
    if int(pm) == 832:
        return 'Dorado 18000 V6 (832)'
    return 'Unknown'


def get_enclosure_model(em):
    if int(em) == 39:
        return '4 U 75-slot 3.5-inch 12 Gbit/s SAS disk enclosure'
    if int(em) == 67:
        return '2 U 25-slot 2.5-inch SAS disk enclosure'
    if int(em) == 69:
        return '4 U 24-slot 3.5-inch SAS disk enclosure'
    if int(em) == 112:
        return '4 U 4-controller controller enclosure'
    if int(em) == 113:
        return '2 U 2-controller 25-slot 2.5-inch SAS controller enclosure'
    if int(em) == 114:
        return '2 U 2-controller 12-slot 3.5-inch SAS controller enclosure'
    if int(em) == 115:
        return '2 U 2-controller 36-slot NVMe controller enclosure'
    if int(em) == 116:
        return '2 U 2-controller 25-slot 2.5-inch SAS controller enclosure'
    if int(em) == 117:
        return '2 U 2-controller 12-slot 3.5-inch SAS controller enclosure'
    if int(em) == 118:
        return '2 U 25-slot 2.5-inch smart SAS disk enclosure'
    if int(em) == 119:
        return '2 U 12-slot 3.5-inch smart SAS disk enclosure'
    if int(em) == 120:
        return '2 U 36-slot smart NVMe disk enclosure'
    if int(em) == 122:
        return '2 U 2-controller 25-slot 2.5-inch NVMe controller enclosure'
    return 'Unknown'


def get_logic_type(lt):
    if int(lt) == 0:
        return 'Expansion Enclosure (Disk Enclosure)'
    if int(lt) == 1:
        return 'Controller Enclosure'
    if int(lt) == 2:
        return 'Data Switch'
    if int(lt) == 3:
        return 'Management Switch'
    if int(lt) == 4:
        return 'Management Server'
    return 'Unknown'


def get_switch_status(st):
    if int(st) == 1:
        return 'On'
    if int(st) == 2:
        return 'On'
    return 'Unknown'


def get_controller_model(cm):
    if int(cm) == 4127:
        return 'V6R1C00 2U2C mid-range PALM control board'
    if int(cm) == 4128:
        return 'V6R1C00 2U2C mid-range _SAS control board'
    if int(cm) == 4129:
        return 'V6R1C00 2U2C SAS entry-level control board (Hi1620S)'
    if int(cm) == 4132:
        return 'V6R1C00 4U4C high-end control board'
    if int(cm) == 4135:
        return 'V6R1C00 2U2C mid-range control Board'
    if int(cm) == 4136:
        return 'V6R1C00 2U2C mid-range SAS1711 control board'
    if int(cm) == 4137:
        return 'V6R1C00 2U2C SAS 1711 entry-level control board (Hi1620S)'
    if int(cm) == 4140:
        return 'V6R1C00 4U4C high-end 1711 control board'
    if int(cm) == 4141:
        return 'V6R1C00 2U2C mid-range SAS 1711 control board (100GE extension board)'
    if int(cm) == 4142:
        return 'V6R1C00 2U2C mid-range SAS control board (100GE extension board)'
    if int(cm) == 4144:
        return 'V6R3C00 2U2C low-end NVMe control board'
    return 'Unknown'


def get_role(role):
    if int(role) == 0:
        return 'Member'
    if int(role) == 1:
        return 'Primary'
    if int(role) == 2:
        return 'Secondary'
    return 'Unknown'


def get_host_access_state(has):
    if int(has) == 1:
        return 'Forbidden'
    if int(has) == 2:
        return 'Read-only'
    if int(has) == 3:
        return 'R/W'
    if int(has) == 5:
        return 'Unknown'
    return 'Unknown'


def get_uuid(data):
    """Returns the Universally unique identifier (UUID) of a managed object.
       It is expressed in the format of object type:object ID. For example, if a controller's
       object type number is "207" and the controller ID is "0A", the UUID is "207:0A".

       The UUID is often needed for querying performance statistics, for example.
    """
    return '{}:{}'.format(data['TYPE'], data['ID'])
