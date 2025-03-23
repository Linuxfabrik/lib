#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Interacts with the UptimeRobot API."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025032301'

from . import time
from . import url


def get_response_header(uri, data):
    """Call the REST API, including pagination.
    """
    result = []
    data['format'] = 'json'
    success, result = url.fetch_json(
        uri,
        header={
            'Cache-Control': 'no-cache',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data=data,
        timeout=20,
        extended=True,
    )
    if not success:
        return (False, result)
    return (True, result['response_header'])


def get_data(uri, data, result_key):
    """Call the REST API, including pagination.
    """
    offset = 0
    result = []
    data = human2utr(data)
    data['format'] = 'json'
    while True:
        data['offset'] = offset
        success, item = url.fetch_json(
            uri,
            header={
                'Cache-Control': 'no-cache',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data=data,
            timeout=20,
        )
        if not success:
            return (False, item)
        if item['stat'] != 'ok':
            return (False, item['error']['message'])
        if item.get(result_key) is None:
            # status was ok, but response doesn't deliver the result key
            return (True, item['message'])
        if type(item[result_key]) == list:
            result += item[result_key]
        else:
            result = [item[result_key]]
        if 'pagination' not in item:
            # we got just one page
            break
        if offset > item['pagination']['total']:
            # we fetched all pages
            break
        offset += 50
    return (True, result)


def get_account_details(data):
    # https://uptimerobot.com/api/#getAccountDetailsWrap
    success, rl = get_response_header(
        'https://api.uptimerobot.com/v2/getAccountDetails',
        data,
    )
    success, account = get_data(
        'https://api.uptimerobot.com/v2/getAccountDetails',
        data,
        'account',
    )
    return success, account, rl


def get_monitors(data):
    # https://uptimerobot.com/api/#getMonitorsWrap
    if 'alert_contacts' not in data:
        data.update({'alert_contacts': 1})
    if 'auth_type' not in data:
        data.update({'auth_type': 'true'})
    if 'http_request_details' not in data:
        data.update({'http_request_details': 'true'})
    if 'mwindows' not in data:
        data.update({'mwindows': 1})
    if 'ssl' not in data:
        data.update({'ssl': 1})
    return get_data(
        'https://api.uptimerobot.com/v2/getMonitors',
        data,
        'monitors',
    )


def new_monitor(data):
    # https://uptimerobot.com/api/#newMonitorWrap
    return get_data(
        'https://api.uptimerobot.com/v2/newMonitor',
        data,
        'monitor',
    )


def update_monitor(data):
    # https://uptimerobot.com/api/#editMonitorWrap
    return get_data(
        'https://api.uptimerobot.com/v2/editMonitor',
        data,
        'monitor',
    )


def delete_monitor(data):
    # https://uptimerobot.com/api/#deleteMonitorWrap
    return get_data(
        'https://api.uptimerobot.com/v2/deleteMonitor',
        data,
        'monitor',
    )


def get_mwindows(data):
    # https://uptimerobot.com/api/#getMWindowsWrap
    return get_data(
        'https://api.uptimerobot.com/v2/getMWindows',
        data,
        'mwindows',
    )


def new_mwindow(data):
    # https://uptimerobot.com/api/#newMWindowWrap
    return get_data(
        'https://api.uptimerobot.com/v2/newMWindow',
        data,
        'mwindow',
    )


def update_mwindow(data):
    # https://uptimerobot.com/api/#editMWindowWrap
    return get_data(
        'https://api.uptimerobot.com/v2/editMWindow',
        data,
        'mwindow',
    )


def delete_mwindow(data):
    # https://uptimerobot.com/api/#deleteMWindowWrap
    return get_data(
        'https://api.uptimerobot.com/v2/deleteMWindow',
        data,
        'mwindows',
    )


def get_alert_contacts(data):
    # https://uptimerobot.com/api/#getAlertContactsWrap
    return get_data(
        'https://api.uptimerobot.com/v2/getAlertContacts',
        data,
        'alert_contacts',
    )


def new_alertcontact(data):
    # https://uptimerobot.com/api/#newAlertContactWrap
    return get_data(
        'https://api.uptimerobot.com/v2/newAlertContact',
        data,
        'alertcontact',
    )


def update_alertcontact(data):
    # https://uptimerobot.com/api/#editAlertContactWrap
    return get_data(
        'https://api.uptimerobot.com/v2/editAlertContact',
        data,
        'alertcontact',
    )


def delete_alertcontact(data):
    # https://uptimerobot.com/api/#deleteAlertContactWrap
    return get_data(
        'https://api.uptimerobot.com/v2/deleteAlertContact',
        data,
        'alert_contact',
    )


def alertcontacttype2human(_type):
    return {
        1: 'sms',
        2: 'e-mail',
        3: 'twitter',
        5: 'web-hook',
        6: 'pushbullet',
        7: 'zapier',
        8: 'pro-sms',
        9: 'pushover',
        11: 'slack',
        14: 'voice-call',
        15: 'splunk',
        16: 'pagerduty',
        17: 'opsgenie',
        20: 'ms-teams',
        21: 'google-chat',
        23: 'discord',
    }.get(_type, _type)


def alertcontacttype2utr(_type):
    return {
        'sms': 1,
        'e-mail': 2,
        'twitter': 3,
        'web-hook': 5,
        'pushbullet': 6,
        'zapier': 7,
        'pro-sms': 8,
        'pushover': 9,
        'slack': 11,
        'voice-call': 14,
        'splunk': 15,
        'pagerduty': 16,
        'opsgenie': 17,
        'ms-teams': 20,
        'google-chat': 21,
        'discord': 23,
    }.get(_type)


def alert_contactstatus2human(_type):
    return {
        0: 'not activated',
        1: 'paused',
        2: 'active',
    }.get(_type, _type)


def alert_contactstatus2utr(_type):
    return {
        'not activated': 0,
        'paused': 1,
        'active': 2,
    }.get(_type)


def http_auth_type2human(_type):
    return {
        1: 'basic',
        2: 'digest',
    }.get(_type)


def http_auth_type2utr(_type):
    return {
        'basic': 1,
        'digest': 2,
    }.get(_type, _type)  # let utr deal with wrong values


def http_method2human(_method):
    return {
        1: 'head',
        2: 'get',
        3: 'post',
        4: 'put',
        5: 'patch',
        6: 'delete',
        7: 'options',
    }.get(_method)


def http_method2utr(_method):
    return {
        'head': 1,
        'get': 2,
        'post': 3,
        'put': 4,
        'patch': 5,
        'delete': 6,
        'options': 7,
    }.get(_method, _method)


def keywcase2human(_type):
    return {
        0: 'cs',
        1: 'ci',
    }.get(_type)


def keywcase2utr(_type):
    return {
        'cs': 0,
        'ci': 1,
    }.get(_type, _type)


def keywtype2human(_type):
    return {
        1: 'exist',
        2: 'notex',
    }.get(_type, '')


def keywtype2utr(_type):
    return {
        'exist': 1,
        'notex': 2,
    }.get(_type, _type)


def monstatus2human(status):
    return {
        0: 'paused',
        1: 'wait',
        2: 'up',
        8: 'down?',
        9: 'down',
    }.get(status)


def monstatus2utr(status):
    return {
        'paused': 0,
        'wait': 1,
        'up': 2,
        'down?': 8,
        'down': 9,
    }.get(status, status)


def monsetstatus2human(status):
    return {
        0: 'pause',
        1: 'start',
    }.get(status)


def monsetstatus2utr(status):
    return {
        'paused': 0,
        'start': 1,
    }.get(status, status)


def montype2human(_type):
    return {
        1: 'http',
        2: 'keyw',
        3: 'ping',
        4: 'port',
        5: 'beat',
    }.get(_type)


def montype2utr(_type):
    return {
        'http': 1,
        'keyw': 2,
        'ping': 3,
        'port': 4,
        'beat': 5,
    }.get(_type, _type)


def mwinstatus2human(status):
    return {
        0: 'paused',
        1: 'active',
    }.get(status)


def mwinstatus2utr(status):
    return {
        'paused': 0,
        'active': 1,
    }.get(status, status)


def mwintype2human(_type):
    return _type


def mwintype2utr(_type):
    return {
        'once': 1,
        'daily': 2,
        'weekly': 3,
        'monthly': 4,
    }.get(_type, _type)


def mwinvalue2human(value):
    return {
        1: 'mon',
        2: 'tue',
        3: 'wed',
        4: 'thu',
        5: 'fri',
        6: 'sat',
        7: 'sun',
        'mon': 'mon',
        'tue': 'tue',
        'wed': 'wed',
        'thu': 'thu',
        'fri': 'fri',
        'sat': 'sat',
        'sun': 'sun',
    }.get(value, '')


def mwinvalue2utr(value):
    return {
        'mon': 1,
        'tue': 2,
        'wed': 3,
        'thu': 4,
        'fri': 5,
        'sat': 6,
        'sun': 7,
    }.get(value)


def human2utr(item, section='monitors'):
    for key, value in item.items():
        if key == 'http_auth_type':
            item[key] = http_auth_type2utr(value)
        if key == 'http_method':
            item[key] = http_method2utr(value)
        if key == 'keyword_case_type':
            item[key] = keywcase2utr(value)
        if key == 'keyword_type':
            item[key] = keywtype2utr(value)
        if section == 'monitors' and key == 'status':
            item[key] = monstatus2utr(value)
        if section == 'monitors' and key == 'statuses':
            t = []
            for v in value.split('-'):  # keyw-http
                t.append(str(monstatus2utr(v)))
            item[key] = '-'.join(t)
        if section == 'monitors' and key == 'type':
            item[key] = montype2utr(value)
        if section == 'monitors' and key == 'types':
            t = []
            for v in value.split('-'):  # keyw-http
                t.append(str(montype2utr(v)))
            item[key] = '-'.join(t)
        if section == 'mwindows' and key == 'status':
            item[key] = mwinstatus2utr(value)
        if section == 'mwindows' and key == 'type':
            item[key] = mwintype2utr(value)
        if section == 'mwindows' and key == 'value':
            if item['type'] == 1 or item['type'] == 2:
                pass
            else:
                t = []
                for v in value.split('-'):  # mon-tue-fri
                    t.append(str(mwinvalue2utr(v)))
                item[key] = '-'.join(t)
        if section == 'set' and key == 'status':
            item[key] = monsetstatus2utr(value)
    return item


def utr2human(item, section='monitors'):
    for key, value in item.items():
        if key == 'create_datetime':
            item[key] = time.epoch2iso(value)
        if key == 'http_auth_type':
            item[key] = http_auth_type2human(value)
        if key == 'http_method':
            item[key] = http_method2human(value)
        if key == 'keyword_case_type':
            item[key] = keywcase2human(value)
        if key == 'keyword_type':
            item[key] = keywtype2human(value)
        if key == 'ssl':
            item[key]['expires'] = time.epoch2iso(value['expires'])
        if section == 'monitors' and key == 'status':
            item[key] = monstatus2human(value)
        if section == 'monitors' and key == 'type':
            item[key] = montype2human(value)
        if section == 'mwindows' and key == 'status':
            item[key] = mwinstatus2human(value)
        if section == 'mwindows' and key == 'type':
            item[key] = mwintype2human(value)
        if section == 'mwindows' and key == 'value':
            if item['type'] == 'weekly' or item['type'] == 'monthly':
                t = []
                for v in value.split(','):  # 1,2
                    t.append(str(mwinvalue2human(v)))
                item[key] = ', '.join(t)
            else:
                item[key] = ''
        if section == 'alert_contacts' and key == 'type':
            item[key] = alertcontacttype2human(value)
        if section == 'alert_contacts' and key == 'status':
            item[key] = alert_contactstatus2human(value)
    return item
