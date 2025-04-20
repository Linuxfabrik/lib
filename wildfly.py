#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some WildFly/JBoss related functions that are
needed by more than one WildFly/JBoss plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

from . import base
from . import url
from .globals import STATE_UNKNOWN


def get_data(args, data, uri=''):
    """
    Fetch data from a management endpoint, with optional domain and instance-specific routing.

    This function fetches data from a server management API, with configurable authentication,
    headers, and error handling.

    ### Parameters
    - **args** (`object`): An object containing the URL (`args.URL`), mode (`args.MODE`),
      node (`args.NODE`), instance (`args.INSTANCE`), username (`args.USERNAME`),
      password (`args.PASSWORD`), and other options
      (e.g., `INSECURE`, `NO_PROXY`, `TIMEOUT`, `ALWAYS_OK`).
    - **data** (`dict`): The data to send in the request body (used for POST requests).
    - **uri** (`str`, optional): The URI to append to the base URL. Defaults to an empty string.

    ### Returns
    - **dict**: The result of the API request, extracted from the 'result' key of the response.

    ### Example
    >>> get_data(args, data={'key': 'value'})
    {'status': 'success', 'data': {'key': 'value'}}
    """
    uri = args.URL.rstrip('/') + '/management' + uri
    if args.MODE == 'domain':
        uri = f'{uri}/host/{args.NODE}/server/{args.INSTANCE}'

    header = {'Content-Type': 'application/json'}

    result = base.coe(url.fetch_json(
        uri,
        data=data,
        digest_auth_password=args.PASSWORD,
        digest_auth_user=args.USERNAME,
        encoding='serialized-json',
        header=header,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    ))

    if result.get('outcome') != 'success':
        base.oao(
            f'Error fetching data: "{result}"',
            STATE_UNKNOWN,
            always_ok=args.ALWAYS_OK,
        )

    return result['result']
