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
__version__ = '2025042001'

import base64 # pylint: disable=C0413

from . import url


def get_data(args, _type='json'):
    """
    Fetch data from a URL, with optional authentication and content type handling.

    This function calls the provided URL and returns the data in either JSON format (default) or
    raw format, based on the specified type.

    ### Parameters
    - **args** (`object`):
      An object containing:
        - `URL` (`str`): URL to fetch.
        - `USERNAME` (`str`): Username for Basic Auth (optional).
        - `PASSWORD` (`str`): Password for Basic Auth (optional).
        - `TIMEOUT` (`int`): Request timeout in seconds.
        - `INSECURE` (`bool`): Disable SSL verification.
        - `NO_PROXY` (`bool`): Ignore proxy settings.
    - **_type** (`str`, optional):
      Either `'json'` for JSON parsing or anything else for raw fetch. Defaults to `'json'`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): Whether the request succeeded.
      - **result** (`dict` or `str`): Parsed JSON or raw response.
      - **False** (`bool`): False if fetch failed.

    ### Example
    >>> success, result = get_data(args, _type='json')
    >>> print(result)
    """
    headers = {}
    if args.USERNAME:
        auth = f"{args.USERNAME}:{args.PASSWORD}"
        headers['Authorization'] = f"Basic {base64.b64encode(auth.encode()).decode()}"

    fetch_func = url.fetch_json if _type == 'json' else url.fetch
    success, result = fetch_func(
        args.URL,
        extended=True,
        header=headers,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )

    if not success:
        return (success, result, False)

    return (True, result)
