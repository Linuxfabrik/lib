#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides functions using the Avelon REST-API.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2024061201'

import requests # type: ignore
import json

BASE_URL = 'https://avelon.cloud'

def get_token(client_id, client_secret, username, password, verify=True, proxies={}, timeout=8):
    url = '{}/oauth/token'.format(
        BASE_URL
        )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "password",
        "username": username,
        "password": password
    }

    try:
        response = requests.post(url, headers=headers, data=data, verify=verify, proxies=proxies, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        try:
            message = e.response.json().get("message", "An error occurred")
        except (ValueError, AttributeError):
            message = str(e)
        return {
            "status_code": getattr(e.response, 'status_code', 'N/A'),
            "message": message
        }

def get_tickets(access_token, verify=True, proxies={}, timeout=8):
    devices = _get_devices(access_token)
    tickets_response = []

    for device in devices:
        tickets_response.extend(_get_ticket_info(access_token, device['clientId']))
    
    return tickets_response

def get_data_points(access_token, data_point_id=None, data_point_name=None, verify=True, proxies={}, timeout=8):
    devices  = _get_devices(access_token)
    data_points_info = []
    data_points_value = []
    data_points_response = []

    for device in devices:
        data_points_info.extend(_get_data_point_info(access_token, device['id']))

    for data_point in data_points_info:
        if not (data_point_name or data_point_id):
            data_points_value = _get_data_point_value(access_token, data_point['id'])
        elif data_point_id and data_point['id'] in data_point_id:
            data_points_value = _get_data_point_value(access_token, data_point['id'])
        elif data_point_name and data_point['systemName'] in data_point_name:
            data_points_value = _get_data_point_value(access_token, data_point['id'])

        if data_points_value:
            data_points_response.append({**data_point, **data_points_value[0]})

        data_points_value = None

    return data_points_response



def _get_devices(access_token, verify=True, proxies={}, timeout=8):
    url = '{}/public-api/v1/devices'.format(
        BASE_URL
        )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers, verify=verify, proxies=proxies, timeout=timeout)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "status_code": response.status_code,
            "message": response.json().get("message", "An error occurred")
        }


def _get_ticket_info(access_token, client_id, verify=True, proxies={}, timeout=8):
    url = '{}/public-api/v1/tickets'.format(
        BASE_URL
        )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "filterScope": "CLIENT",
        "id": client_id
    }

    response = requests.post(url, headers=headers, data=json.dumps(body), verify=verify, proxies=proxies, timeout=timeout)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "status_code": response.status_code,
            "message": response.json().get("message", "An error occurred")
        }


def _get_data_point_info(access_token, device_id, verify=True, proxies={}, timeout=8):
    url = '{}/public-api/v1/data-points?deviceIds={}'.format(
        BASE_URL,
        device_id
        )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers, verify=verify, proxies=proxies, timeout=timeout)

    if response.status_code == 200:
        return response.json()
    else:
        return {
            "status_code": response.status_code,
            "message": response.json().get("message", "An error occurred")
        }

def _get_data_point_value(access_token, data_point_id, verify=True, proxies={}, timeout=8):
    url = '{}/public-api/v1/data-points/{}/records/latest?limit=1'.format(
        BASE_URL,
        data_point_id
        )
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers, verify=verify, proxies=proxies, timeout=timeout)

    if response.status_code == 200:
        return response.json()
    else:
        return [response.json()]