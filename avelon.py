#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides functions using the Avelon Cloud REST-API.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2024062401'

import lib.url

BASE_URL = 'https://avelon.cloud'


def get_token(client_id, client_secret, username, password, insecure=False, no_proxy=False, timeout=8):
    uri = '{}/oauth/token'.format(
        BASE_URL
        )
    header = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "password",
        "username": username,
        "password": password
    }
    success, token = lib.url.fetch_json(
        uri,
        header=header,
        data=data,
        extended=True,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success:
        return (success, token)
    return (True, token['response_json'])


def get_tickets(access_token, insecure=False, no_proxy=False, timeout=8):
    success, devices = _get_devices(access_token, insecure, no_proxy, timeout)
    if not success:
        return (success, devices)
    
    tickets_response = []

    for device in devices:
        tickets_response.extend(_get_ticket_info(access_token, device['clientId'], insecure, no_proxy, timeout))
    
    return tickets_response


def get_data_points(access_token, data_point_id=None, data_point_name=None, insecure=False, no_proxy=False, timeout=8):
    success, devices = _get_devices(access_token, insecure, no_proxy, timeout)
    if not success:
        return (success, devices)
    
    data_points_info = []
    data_points_value = []
    data_points_response = []

    for device in devices:
        success, data_point_info = _get_data_point_info(access_token, device['id'], insecure, no_proxy, timeout)
        data_points_info.extend(data_point_info)

    for data_point in data_points_info:
        if (data_point_id and data_point['id'] in data_point_id) or (data_point_name and data_point['systemName'] in data_point_name):
            success, data_points_value = _get_data_point_value(access_token, data_point['id'], insecure, no_proxy, timeout)
        elif not (data_point_name or data_point_id):
            success, data_points_value = _get_data_point_value(access_token, data_point['id'], insecure, no_proxy, timeout)

        if data_points_value:
            data_points_response.append({**data_point, **data_points_value[0]})
        data_points_value = None

    return data_points_response


def _get_devices(access_token, insecure, no_proxy, timeout):
    uri = '{}/public-api/v1/devices'.format(
        BASE_URL
        )
    header = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    success, devices = lib.url.fetch_json(
        uri,
        header=header,
        extended=True,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not devices['response_json']:
        return (False, 'No devices found. Check if devices under this '
                       'mandate are present in avelon.cloud.')
    return (True, devices['response_json'])


def _get_ticket_info(access_token, client_id, insecure, no_proxy, timeout):
    uri = '{}/public-api/v1/tickets'.format(
        BASE_URL
        )
    header = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "filterScope": "CLIENT",
        "id": client_id
    }
    success, tickets = lib.url.fetch_json(
        uri,
        header=header,
        data = body,
        extended=True,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        encoding = 'serialized-json',
    )
    
    return (True, tickets['response_json'])


def _get_data_point_info(access_token, device_id, insecure, no_proxy, timeout):
    uri = '{}/public-api/v1/data-points?deviceIds={}'.format(
        BASE_URL,
        device_id
        )
    header ={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    success, data_point_info = lib.url.fetch_json(
        uri,
        header=header,
        extended=True,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    return (True, data_point_info['response_json'])

def _get_data_point_value(access_token, data_point_id, insecure, no_proxy, timeout):
    uri = '{}/public-api/v1/data-points/{}/records/latest?limit=1'.format(
        BASE_URL,
        data_point_id
        )
    header = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    success, data_point_value = lib.url.fetch_json(
        uri,
        header=header,
        extended=True,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success:
        return (success, [{'value': data_point_value}])
    return (True, data_point_value['response_json'])