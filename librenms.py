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
__version__ = '2025042001'

from .globals import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN

from . import base # pylint: disable=C0413
from . import txt # pylint: disable=C0413
from . import url # pylint: disable=C0413


def get_data(args, uri=''):
    """
    Fetch data from the LibreNMS API.

    This function builds the API URL using the base URL and endpoint URI. It authenticates using
    the provided token and fetches the data. If the API returns an error status, it exits or
    handles the error appropriately.

    ### Parameters
    - **args** (object):
      An object containing:
        - `URL` (`str`): Base URL of the LibreNMS API.
        - `TOKEN` (`str`): API authentication token.
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.
        - `ALWAYS_OK` (`bool`): Whether to always exit cleanly even on errors.

    - **uri** (`str`, optional):
      Endpoint URI to append to the base URL. Defaults to `''`.

    ### Returns
    - **dict**:
      The fetched data as a parsed JSON dictionary.

    ### Notes
    - Automatically ensures correct URL formatting.
    - If the response status is not `ok`, the function exits or handles the error.

    ### Example
    >>> result = get_data(args, uri='/api/v0/devices')
    """

    url_base = args.URL.rstrip('/')
    endpoint = f'/{uri.lstrip("/")}'
    full_url = f'{url_base}{endpoint}'
    headers = {'X-Auth-Token': args.TOKEN}

    result = base.coe(url.fetch_json(
        full_url,
        header=headers,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    ))

    if result.get('status', '').lower() != 'ok':
        base.oao(
            f'Error fetching data: "{result}"',
            STATE_UNKNOWN,
            always_ok=args.ALWAYS_OK,
        )

    return result


def get_prop(obj, prop, mytype='str'):
    """
    Retrieve a property from a dictionary with safe type handling.

    This function fetches a specific property from a dictionary and handles cases where the property
    might not exist or be `None`. For string types, it returns an empty string if missing; otherwise,
    it returns `None`.

    ### Parameters
    - **obj** (`dict`): 
      The dictionary object to query.
    - **prop** (`str`): 
      The property name to retrieve.
    - **mytype** (`str`, optional): 
      Expected type of the property. `'str'` ensures text formatting. Defaults to `'str'`.

    ### Returns
    - **str** or **any**:
      - If `mytype` is `'str'`, returns a string.
      - Otherwise, returns the original value or `None` if not found.

    ### Notes
    - Helps avoid KeyErrors and NoneType issues in chained lookups.
    - Useful for safely accessing fields in API responses.

    ### Example
    >>> get_prop(device, 'uptime')
    '3600'
    >>> get_prop(device, 'cpu_usage', mytype='int')
    15
    """

    value = obj.get(prop)

    if mytype == 'str':
        return txt.to_text(value) if value is not None else ''
    
    return value if value is not None else None


def get_state(librestate, severity='crit'):
    """
    Translate LibreNMS service state to a Nagios-compatible state.

    LibreNMS returns a custom service state where:
      - 0 = OK
      - 1 = Alert
      - 2 = Acknowledged

    This function maps these LibreNMS states to Nagios exit codes.

    ### Parameters
    - **librestate** (`int`):
      The LibreNMS state code to translate.
    - **severity** (`str`, optional):
      If `crit`, maps alert states to critical. Otherwise, maps to warning.

    ### Returns
    - **int**:
      Nagios-compatible state code:
        - 0 = OK
        - 1 = WARNING
        - 2 = CRITICAL

    ### Notes
    - Assumes STATE_OK, STATE_WARN, and STATE_CRIT constants are defined.

    ### Example
    >>> get_state(0)
    0
    >>> get_state(1, severity='warn')
    1
    >>> get_state(1, severity='crit')
    2
    """

    if librestate != 1:
        return STATE_OK
    return STATE_CRIT if severity == 'crit' else STATE_WARN

