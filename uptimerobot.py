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
__version__ = '2025032701'

from . import time
from . import url


def get_response_header(uri, data):
    """Call the REST API, but just return the response headers.
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
        timeout=10,
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
            return (False, f"{item['error']['type']}: {item['error']['message']}")
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


def multi_replace(text, repl_map):
    """Replace all occurrences based on the provided mapping."""
    for old, new in repl_map.items():
        text = text.replace(old, str(new))
    return text


def get_account_details(data):
    # https://uptimerobot.com/api
    # remove unwanted keys (copied 1:1 from documentation)
    allowed_keys = {
        'api_key',
    }
    for key in list(data.keys()):
        if key not in allowed_keys:
            data.pop(key)

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


def get_monitors(params):
    # https://uptimerobot.com/api
    # remove unwanted keys (copied 1:1 from documentation)
    # and translate human2uptimerobot and vice versa
    allowed_keys = {
        'api_key',
        'monitors',
        'types',
        'statuses',
        'custom_uptime_ratios',
        'custom_down_durations',
        'custom_uptime_ranges',
        'all_time_uptime_ratio',
        'all_time_uptime_durations',
        'logs',
        'logs_start_date',
        'logs_end_date',
        'log_types',
        'logs_limit',
        'response_times',
        'response_times_limit',
        'response_times_average',
        'response_times_start_date',
        'response_times_end_date',
        'alert_contacts',
        'mwindows',
        'ssl',
        'custom_http_headers',
        'custom_http_statuses',
        'http_request_details',
        'auth_type',
        'timezone',
        'offset',
        'limit',
        'search',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    # convert human parameters to uptimerobot
    replace_map = {
        'statuses': {
            'paused': '0',
            'wait': '1',
            'up': '2',
            'seems_down': '8',
            'down': '9',
        },
        'types': {
            'http': '1',
            'keyw': '2',
            'ping': '3',
            'port': '4',
            'beat': '5',
        },
    }
    for key, replacements in replace_map.items():
        if key in params and isinstance(params[key], str):
            params[key] = multi_replace(params[key], replacements)

    success, result = get_data(
        'https://api.uptimerobot.com/v2/getMonitors',
        params,
        'monitors',
    )
    if not success:
        return success, result

    # convert uptimerobot result values to human
    replace_map = {
        'alert_contacts_type': {
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
        },
        'auth_type': {
            1: 'basic',
            2: 'digest',
        },
        'http_method': {
            1: 'head',
            2: 'get',
            3: 'post',
            4: 'put',
            5: 'patch',
            6: 'delete',
            7: 'options',
        },
        'keyword_case_type': {
            0: 'cs',
            1: 'ci',
        },
        'keyword_type': {
            1: 'exist',
            2: 'notex',
        },
        'status': {
            0: 'paused',
            1: 'wait',
            2: 'up',
            8: 'seems_down',
            9: 'down',
        },
        'type': {
            1: 'http',
            2: 'keyw',
            3: 'ping',
            4: 'port',
            5: 'beat',
        },
    }

    def replace_values(item):
        # replace the nested alert_contacts 'type' value
        for contact in item.get('alert_contacts', []):
            if 'type' in contact:
                contact['type'] = replace_map['alert_contacts_type'].get(
                    contact['type'],
                    contact['type'],
                )
        # replace values for top-level keys
        if 'auth_type' in item:
            item['auth_type'] = replace_map['auth_type'].get(
                item['auth_type'],
                'None',
            )
        if 'http_method' in item:
            item['http_method'] = replace_map['http_method'].get(
                item['http_method'],
                item['http_method'],
            )
        if 'keyword_case_type' in item:
            item['keyword_case_type'] = replace_map['keyword_case_type'].get(
                item['keyword_case_type'],
                item['keyword_case_type'],
            )
        if 'keyword_type' in item:
            item['keyword_type'] = replace_map['keyword_type'].get(
                item['keyword_type'],
                'None',
            )
        if 'status' in item:
            item['status'] = replace_map['status'].get(
                item['status'],
                item['status'],
            )
        if 'type' in item:
            item['type'] = replace_map['type'].get(
                item['type'],
                item['type'],
            )

        return item

    # Process each dictionary in your result list
    result = [replace_values(item) for item in result]

    return success, result


def new_monitor(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'friendly_name',
        'url',
        'type',
        'sub_type',
        'port',
        'keyword_type',
        'keyword_case_type',
        'keyword_value',
        'interval',
        'timeout',
        'http_username',
        'http_password',
        'http_auth_type',
        'post_type',
        'post_value',
        'http_method',
        'post_content_type',
        'alert_contacts',
        'mwindows',
        'custom_http_headers',
        'custom_http_statuses',
        'ignore_ssl_errors',
        'disable_domain_expire_notifications',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    # convert human parameters to uptimerobot
    replace_map = {
        'type': {
            'http': '1',
            'keyw': '2',
            'ping': '3',
            'port': '4',
            'beat': '5',
        },
        'sub_type': {
            'http': '1',
            'https': '443',
            'ftp': '21',
            'smtp': '25',
            'pop3': '110',
            'imap': '143',
            'custom': '99',
        },
        'keyword_type': {
            'exist': '1',
            'notex': '2',
        },
        'keyword_case_type': {
            'cs': '0',
            'ci': '1',
        },
        'auth_type': {
            'basic': '1',
            'digest': '2',
        },
        'http_auth_type': {
            'basic': '1',
            'digest': '2',
        },
        'post_type': {
            'key-value': '1',
            'raw data': '2',
        },
        'http_method': {
            'head': 1,
            'get': 2,
            'post': 3,
            'put': 4,
            'patch': 5,
            'delete': 6,
            'options': 7,
        },
        'post_content_type': {
            'text/html': '0',
            'content/json': '1',
        },
        'disable_domain_expire_notifications': {
            'enable': '0',
            'disable': '1',
        },
    }
    for key, replacements in replace_map.items():
        if key in params and isinstance(params[key], str):
            params[key] = multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/newMonitor',
        params,
        'monitor',
    )


def edit_monitor(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'id',
        'friendly_name',
        'url',
        'sub_type',
        'port',
        'keyword_type',
        'keyword_case_type',
        'keyword_value',
        'interval',
        'timeout',
        'status',
        'http_username',
        'http_password',
        'http_auth_type',
        'http_method',
        'post_type',
        'post_value',
        'post_content_type',
        'alert_contacts',
        'mwindows',
        'custom_http_headers',
        'custom_http_statuses',
        'ignore_ssl_errors',
        'disable_domain_expire_notifications',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    # convert human parameters to uptimerobot
    replace_map = {
        'sub_type': {
            'http': '1',
            'https': '443',
            'ftp': '21',
            'smtp': '25',
            'pop3': '110',
            'imap': '143',
            'custom': '99',
        },
        'keyword_type': {
            'exist': '1',
            'notex': '2',
        },
        'keyword_case_type': {
            'cs': '0',
            'ci': '1',
        },
        'status': {
            'paused': 0,
            'up': 1,
        },
        'auth_type': {
            'basic': '1',
            'digest': '2',
        },
        'http_auth_type': {
            'basic': '1',
            'digest': '2',
        },
        'http_method': {
            'head': 1,
            'get': 2,
            'post': 3,
            'put': 4,
            'patch': 5,
            'delete': 6,
            'options': 7,
        },
        'post_type': {
            'key-value': '1',
            'raw data': '2',
        },
        'post_content_type': {
            'text/html': '0',
            'content/json': '1',
        },
        'disable_domain_expire_notifications': {
            'enable': '0',
            'disable': '1',
        },
    }
    for key, replacements in replace_map.items():
        if key in params and isinstance(params[key], str):
            params[key] = multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/editMonitor',
        params,
        'monitor',
    )


def delete_monitor(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'id',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}
    
    return get_data(
        'https://api.uptimerobot.com/v2/deleteMonitor',
        params,
        'monitor',
    )


def get_alert_contacts(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'alert_contacts',
        'offset',
        'limit',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    success, result = get_data(
        'https://api.uptimerobot.com/v2/getAlertContacts',
        params,
        'alert_contacts',
    )
    if not success:
        return success, result

    # convert uptimerobot result values to human
    replace_map = {
        'status': {
            0: 'not activated',
            1: 'paused',
            2: 'active',
        },
        'type': {
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
        },
    }

    def replace_values(item):
        # replace values for top-level keys
        if 'status' in item:
            item['status'] = replace_map['status'].get(
                item['status'],
                'None',
            )
        if 'type' in item:
            item['type'] = replace_map['type'].get(
                item['type'],
                'None',
            )
        return item

    # Process each dictionary in your result list
    result = [replace_values(item) for item in result]

    return success, result


def delete_alert_contact(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'id',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}
    
    return get_data(
        'https://api.uptimerobot.com/v2/deleteAlertContact',
        params,
        'alert_contact',
    )


def get_mwindows(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'mwindows',
        'offset',
        'limit',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    success, result = get_data(
        'https://api.uptimerobot.com/v2/getMWindows',
        params,
        'mwindows',
    )
    if not success:
        return success, result

    # convert uptimerobot result values to human
    replace_map = {
        'status': {
            0: 'paused',
            1: 'active',
        },
    }

    def replace_values(item):
        # replace values for top-level keys
        if 'status' in item:
            item['status'] = replace_map['status'].get(
                item['status'],
                'None',
            )
        return item

    # Process each dictionary in your result list
    result = [replace_values(item) for item in result]

    return success, result


def new_mwindow(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'friendly_name',
        'type',
        'value',
        'start_time',
        'duration',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    # convert human parameters to uptimerobot
    replace_map = {
        'type': {
            'once': 1,
            'daily': 2,
            'weekly': 3,
            'monthly': 4,
        },
        'value': {
            'mon': 1,
            'tue': 2,
            'wed': 3,
            'thu': 4,
            'fri': 5,
            'sat': 6,
            'sun': 7,
        },
    }
    for key, replacements in replace_map.items():
        if key in params and isinstance(params[key], str):
            params[key] = multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/newMWindow',
        params,
        'mwindow',
    )


def edit_mwindow(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'id',  # not documented
        'friendly_name',
        'type',
        'value',
        'start_time',
        'duration',
        'status',  # not documented
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    # convert human parameters to uptimerobot
    replace_map = {
        'status': {
            'paused': 0,
            'active': 1,
        },
        'type': {
            'once': 1,
            'daily': 2,
            'weekly': 3,
            'monthly': 4,
        },
        'value': {
            'mon': 1,
            'tue': 2,
            'wed': 3,
            'thu': 4,
            'fri': 5,
            'sat': 6,
            'sun': 7,
        },
    }
    for key, replacements in replace_map.items():
        if key in params and isinstance(params[key], str):
            params[key] = multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/editMWindow',
        params,
        'mwindow',
    )


def delete_mwindow(params):
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'id',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    return get_data(
        'https://api.uptimerobot.com/v2/deleteMWindow',
        params,
        'mwindows',
    )
