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
__version__ = '2025041901'

from . import time
from . import txt
from . import url


def delete_alert_contact(params):
    """
    Call the UptimeRobot API to delete an existing alert contact.

    This function filters the input parameters to include only the allowed keys and then calls the
    API to delete the specified alert contact.

    ### Parameters
    - **params** (`dict`): A dictionary containing the parameters to delete the alert contact.
      Only the allowed keys (`'api_key'`, `'id'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the deleted alert contact's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> delete_alert_contact({'api_key': 'your_api_key', 'id': 123456})
    (True, {'id': 123456, 'status': 'deleted'})
    """
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


def delete_monitor(params):
    """
    Call the UptimeRobot API to delete an existing monitor.

    This function filters the input parameters to include only the allowed keys and then calls the
    API to delete the specified monitor.

    ### Parameters
    - **params** (`dict`): A dictionary containing the monitor's parameters. Only the allowed keys
      (`'api_key'`, `'id'`) are included.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the deleted monitor's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> delete_monitor({'api_key': 'your_api_key', 'id': 123456})
    (True, {'id': 123456, 'status': 'deleted'})
    """
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


def delete_mwindow(params):
    """
    Call the UptimeRobot API to delete an existing monitoring window.

    This function filters the input parameters to include only the allowed keys and then calls the
    API to delete the specified monitoring window.

    ### Parameters
    - **params** (`dict`): A dictionary containing the parameters for deleting the monitoring
      window. Only the allowed keys (`'api_key'`, `'id'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the deleted monitoring window's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> delete_mwindow({'api_key': 'your_api_key', 'id': 123456})
    (True, {'id': 123456, 'status': 'deleted'})
    """
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
        'mwindow',
    )


def delete_psp(params):
    """
    Call the UptimeRobot API to delete an existing PSP (public service provider).

    This function filters the input parameters to include only the allowed keys and then calls the
    API to delete the specified PSP.

    ### Parameters
    - **params** (`dict`): A dictionary containing the parameters for deleting the PSP. Only the
      allowed keys (`'api_key'`, `'id'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the deleted PSP's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> delete_psp({'api_key': 'your_api_key', 'id': 123456})
    (True, {'id': 123456, 'status': 'deleted'})
    """
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'id',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    return get_data(
        'https://api.uptimerobot.com/v2/deletePSP',
        params,
        'psp',
    )


def edit_monitor(params):
    """
    Call the UptimeRobot API to edit an existing monitor.

    This function:
    - Filters the input parameters to include only allowed keys.
    - Converts human-readable values (e.g., protocol types, methods, status) to UptimeRobot's
      API-compatible values.

    ### Parameters
    - **params** (`dict`): A dictionary of parameters for editing the monitor. Only the allowed keys
      will be kept and translated accordingly.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the updated monitor's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> edit_monitor({'api_key': 'your_api_key', 'id': 123456, 'friendly_name': 'Updated Monitor', 'status': 'up'})
    (True, {'id': 123456, 'friendly_name': 'Updated Monitor', 'status': 'up', ...})
    """
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
            params[key] = txt.multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/editMonitor',
        params,
        'monitor',
    )


def edit_mwindow(params):
    """
    Call the UptimeRobot API to edit an existing monitoring window.

    This function:
    - Filters the input parameters to include only the allowed keys.
    - Converts human-readable values (e.g., type, value, and status) to UptimeRobot's API-compatible
      values.

    ### Parameters
    - **params** (`dict`): A dictionary of parameters for editing the monitoring window. Only the
      allowed keys (`'api_key'`, `'id'`, `'friendly_name'`, `'type'`, `'value'`, `'start_time'`,
      `'duration'`, `'status'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the edited monitoring window's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> edit_mwindow({'api_key': 'your_api_key', 'id': 123456, 'friendly_name': 'Updated Window', 'status': 'active', 'type': 'daily', 'value': 'mon', 'start_time': '2022-05-01T00:00:00', 'duration': 60})
    (True, {'id': 123456, 'friendly_name': 'Updated Window', 'status': 'active', 'type': 'daily', 'value': 'mon', 'start_time': '2022-05-01T00:00:00', 'duration': 60})
    """
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
            params[key] = txt.multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/editMWindow',
        params,
        'mwindow',
    )


def edit_psp(params):
    """
    Call the UptimeRobot API to edit an existing PSP (public status page).

    This function:
    - Filters the input parameters to include only the allowed keys.
    - Converts human-readable values (e.g., sort and status) to UptimeRobot's API-compatible values.

    ### Parameters
    - **params** (`dict`): A dictionary of parameters for editing the PSP. Only the allowed keys
      (`'api_key'`, `'id'`, `'friendly_name'`, `'monitors'`, `'custom_domain'`, `'password'`,
      `'sort'`, `'hide_url_links'`, `'status'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the edited PSP's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> edit_psp({'api_key': 'your_api_key', 'id': 123456, 'friendly_name': 'Updated PSP', 'status': 'active', 'sort': 'a-z'})
    (True, {'id': 123456, 'friendly_name': 'Updated PSP', 'status': 'active', 'sort': 'a-z', ...})
    """
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'id',  # not documented in the UTR API
        'friendly_name',
        'monitors',
        'custom_domain',
        'password',
        'sort',
        'hide_url_links',
        'status',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    # convert human parameters to uptimerobot
    replace_map = {
        'sort': {
            'a-z': 1,
            'z-a': 2,
            'up-down-paused': 3,
            'down-up-paused': 4,
        },
        'status': {
            'paused': 0,
            'active': 1,
        },
    }
    for key, replacements in replace_map.items():
        if key in params and isinstance(params[key], str):
            params[key] = txt.multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/editPSP',
        params,
        'psp',
    )


def get_account_details(data):
    """
    Call the UptimeRobot API to retrieve account details.

    Filters the input data to include only allowed keys before making the request.

    ### Parameters
    - **data** (`dict`): A dictionary containing API parameters.  
      Only keys listed in `allowed_keys` (e.g., `'api_key'`) are kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **account** (`dict` or `str`): The account details if successful, or an error message.
      - **rl** (`dict`): The response headers from the API call.

    ### Example
    >>> get_account_details({'api_key': 'your_api_key_here', 'extra_key': 'ignored'})
    (True, {'email': 'user@example.com', 'monitor_limit': 50, ...}, {'Content-Type': 'application/json', ...})
    """
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


def get_alert_contacts(params):
    """
    Call the UptimeRobot API to retrieve alert contacts.

    This function:
    - Filters the input parameters to include only the allowed keys.
    - Retrieves the alert contacts, then converts UptimeRobot's status and type values to
      human-readable formats.

    ### Parameters
    - **params** (`dict`): A dictionary containing parameters to filter the alert contacts. Only
      the allowed keys (`'api_key'`, `'alert_contacts'`, `'offset'`, `'limit'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`list` or `str`): 
        - A list of alert contact dictionaries if successful.
        - An error message string if the API call failed.

    ### Example
    >>> get_alert_contacts({'api_key': 'your_api_key', 'limit': 10})
    (True, [{'id': 1, 'status': 'active', 'type': 'sms', ...}, ...])
    """
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


def get_data(uri, data, result_key):
    """
    Call a REST API and retrieve paginated results.

    Automatically handles offset-based pagination by requesting subsequent pages until all data is
    fetched.

    ### Parameters
    - **uri** (`str`): The URI of the REST API endpoint.
    - **data** (`dict`): A dictionary of parameters to send with the request.  
      `'format': 'json'` will be automatically added.
    - **result_key** (`str`): The key under which the desired data is stored in the API response.

    ### Returns
    - **tuple**:
      - On success: (True, list_of_results)
      - On failure: (False, error_message)

    ### Example
    >>> get_data('https://example.com/api', {'key': 'value'}, 'items')
    (True, [{'id': 1, 'name': 'A'}, {'id': 2, 'name': 'B'}, ...])
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


def get_monitors(params):
    """
    Call the UptimeRobot API to retrieve monitor information, including optional translation of
    statuses and types.

    This function:
    - Filters allowed parameters according to UptimeRobot API documentation.
    - Converts human-readable parameters into API-compatible values before sending.
    - Converts API results back into human-readable values after retrieval.

    ### Parameters
    - **params** (`dict`): 
      Parameters to send to the API.  
      Only allowed keys will be kept, and certain fields will be auto-translated (e.g., status
      names to numbers).

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`list` or `str`): 
        - A list of monitor dictionaries if successful.
        - An error message string if failed.

    ### Example
    >>> get_monitors({'api_key': 'your_api_key', 'statuses': 'up', 'types': 'http'})
    (True, [{'id': 12345, 'status': 'up', 'type': 'http', ...}, ...])
    """
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
            params[key] = txt.multi_replace(params[key], replacements)

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


def get_mwindows(params):
    """
    Call the UptimeRobot API to retrieve monitoring windows (mwindows).

    This function:
    - Filters the input parameters to include only the allowed keys.
    - Retrieves the monitoring windows, then converts UptimeRobot's status values to human-readable
      formats.

    ### Parameters
    - **params** (`dict`): A dictionary containing parameters to filter the monitoring windows.
      Only the allowed keys (`'api_key'`, `'mwindows'`, `'offset'`, `'limit'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`list` or `str`): 
        - A list of monitoring window dictionaries if successful.
        - An error message string if the API call failed.

    ### Example
    >>> get_mwindows({'api_key': 'your_api_key', 'limit': 10})
    (True, [{'id': 1, 'status': 'active', 'start_date': '2022-01-01', ...}, ...])
    """
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


def get_psps(params):
    """
    Call the UptimeRobot API to retrieve PSPs (public service providers).

    This function:
    - Filters the input parameters to include only the allowed keys.
    - Retrieves the PSPs, then converts UptimeRobot's status and sort values to human-readable
      formats.

    ### Parameters
    - **params** (`dict`): A dictionary containing parameters to filter the PSPs. Only the allowed
      keys (`'api_key'`, `'psps'`, `'offset'`, `'limit'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`list` or `str`): 
        - A list of PSP dictionaries if successful.
        - An error message string if the API call failed.

    ### Example
    >>> get_psps({'api_key': 'your_api_key', 'limit': 10})
    (True, [{'id': 12345, 'sort': 'a-z', 'status': 'active', ...}, ...])
    """
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'psps',
        'offset',
        'limit',
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    success, result = get_data(
        'https://api.uptimerobot.com/v2/getPSPs',
        params,
        'psps',
    )
    if not success:
        return success, result

    # convert uptimerobot result values to human
    replace_map = {
        'sort': {
            1: 'a-z',
            2: 'z-a',
            3: 'up-down-paused',
            4: 'down-up-paused',
        },
        'status': {
            0: 'paused',
            1: 'active',
        },
    }

    def replace_values(item):
        # replace values for top-level keys
        if 'sort' in item:
            item['sort'] = replace_map['sort'].get(
                item['sort'],
                'None',
            )
        if 'status' in item:
            item['status'] = replace_map['status'].get(
                item['status'],
                'None',
            )
        return item

    # Process each dictionary in your result list
    result = [replace_values(item) for item in result]

    return success, result


def get_response_header(uri, data):
    """
    Call a REST API and return only the response headers.

    Sends a request with specific headers and optional form data, expecting a JSON-formatted
    response.

    ### Parameters
    - **uri** (`str`): The URI of the REST API endpoint.
    - **data** (`dict`): A dictionary of data to send in the request body.  
      `'format': 'json'` will be automatically added.

    ### Returns
    - **tuple**:
      - On success: (True, response_headers)
      - On failure: (False, error_message)

    ### Example
    >>> get_response_header('https://example.com/api', {'key': 'value'})
    (True, {'Content-Type': 'application/json', 'Content-Length': '123', ...})
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


def new_monitor(params):
    """
    Call the UptimeRobot API to create a new monitor.

    This function:
    - Filters the input parameters to include only allowed keys.
    - Converts human-readable values (e.g., protocol types, methods) to UptimeRobot's API-compatible
      values.

    ### Parameters
    - **params** (`dict`): A dictionary of parameters for the new monitor. Only the allowed keys
      will be kept and translated accordingly.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the created monitor's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> new_monitor({'api_key': 'your_api_key', 'friendly_name': 'My Monitor', 'url': 'https://example.com', 'type': 'http'})
    (True, {'id': 123456, 'friendly_name': 'My Monitor', 'url': 'https://example.com', 'status': 'up', ...})
    """
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
            params[key] = txt.multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/newMonitor',
        params,
        'monitor',
    )


def new_mwindow(params):
    """
    Call the UptimeRobot API to create a new monitoring window.

    This function:
    - Filters the input parameters to include only the allowed keys.
    - Converts human-readable values (e.g., type and value) to UptimeRobot's API-compatible values.

    ### Parameters
    - **params** (`dict`): A dictionary of parameters for the new monitoring window. Only the
      allowed keys (`'api_key'`, `'friendly_name'`, `'type'`, `'value'`, `'start_time'`, 
      `'duration'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the created monitoring window's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> new_mwindow({'api_key': 'your_api_key', 'friendly_name': 'Maintenance Window', 'type': 'once', 'value': 'mon', 'start_time': '2022-05-01T00:00:00', 'duration': 60})
    (True, {'id': 1, 'friendly_name': 'Maintenance Window', 'status': 'active', ...})
    """
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
            params[key] = txt.multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/newMWindow',
        params,
        'mwindow',
    )


def new_psp(params):
    """
    Call the UptimeRobot API to create a new PSP (public service provider).

    This function:
    - Filters the input parameters to include only the allowed keys.
    - Converts human-readable values (e.g., sort and status) to UptimeRobot's API-compatible values.

    ### Parameters
    - **params** (`dict`): A dictionary of parameters for the new PSP. Only the allowed keys
      (`'api_key'`, `'friendly_name'`, `'monitors'`, `'custom_domain'`, `'password'`, `'sort'`,
      `'hide_url_links'`) will be kept.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the created PSP's details if successful.
        - An error message string if the API call failed.

    ### Example
    >>> new_psp({'api_key': 'your_api_key', 'friendly_name': 'New PSP', 'monitors': '12345,67890', 'sort': 'a-z'})
    (True, {'id': 123456, 'friendly_name': 'New PSP', 'status': 'active', ...})
    """
    # https://uptimerobot.com/api
    allowed_keys = {
        'api_key',
        'friendly_name',
        'monitors',
        'custom_domain',
        'password',
        'sort',
        'hide_url_links',
        # 'status',  # not allowed for creation
    }
    # Keep only allowed parameters
    params = {k: v for k, v in params.items() if k in allowed_keys}

    # convert human parameters to uptimerobot
    replace_map = {
        'sort': {
            'a-z': 1,
            'z-a': 2,
            'up-down-paused': 3,
            'down-up-paused': 4,
        },
        'status': {
            'paused': 0,
            'active': 1,
        },
    }
    for key, replacements in replace_map.items():
        if key in params and isinstance(params[key], str):
            params[key] = txt.multi_replace(params[key], replacements)

    return get_data(
        'https://api.uptimerobot.com/v2/newPSP',
        params,
        'psp',
    )
