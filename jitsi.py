#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Jitsi related functions that are
needed by more than one Jitsi plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025041901'

import base64 # pylint: disable=C0413

from . import url


def get_data(args, _type='json'):
    """
    Fetch data from a URL, with optional authentication and content type handling.

    This function calls the provided URL and returns the data in either JSON format (default) or
    raw format, based on the specified type.

    ### Parameters
    - **args** (`object`): An object containing the URL (`args.URL`), username (`args.USERNAME`),
      password (`args.PASSWORD`), and other options (e.g., `TIMEOUT`, `INSECURE`, `NO_PROXY`).
    - **_type** (`str`, optional): The type of data to fetch. If `'json'`, returns the data as JSON.
      Otherwise, returns raw data. Defaults to `'json'`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the fetch was successful, False otherwise.
      - **result** (`dict` or `str`): The fetched data, either as a parsed JSON object or raw data.
      - **False** (`bool`): If the fetch failed, False is returned as the third element.

    ### Example
    >>> get_data(args, _type='json')
    (True, {'key': 'value'})
    """
    header = {}
    if not args.USERNAME is None:
        header['Authorization'] = 'Basic {}'.format(
            base64.b64encode(args.USERNAME + ':' + args.PASSWORD)
        )
    if _type == 'json':
        success, result = url.fetch_json(
            args.URL,
            extended=True,
            header=header,
            insecure=args.INSECURE,
            no_proxy=args.NO_PROXY,
            timeout=args.TIMEOUT,
        )
    else:
        success, result = url.fetch(
            args.URL,
            extended=True,
            header=header,
            insecure=args.INSECURE,
            no_proxy=args.NO_PROXY,
            timeout=args.TIMEOUT,
        )

    if not success:
        return (success, result, False)
    return (True, result)
