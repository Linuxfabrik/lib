#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some NodeBB related functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

from . import base
from . import url


def get_data(args, uri=''):
    """
    Fetch JSON data from the NodeBB API using a user token.

    This function makes a request to the NodeBB API with the provided user token and returns the
    JSON response.

    ### Parameters
    - **args** (`object`): An object containing the URL (`args.URL`), token (`args.TOKEN`), and 
      other options (e.g., `INSECURE`, `NO_PROXY`, `TIMEOUT`).
    - **uri** (`str`, optional): The specific URI to append to the base URL. Defaults to an
      empty string.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the API call succeeded, False otherwise.
      - **result** (`dict` or `str`): 
        - A dictionary containing the API response if successful.
        - An error message string if the API call failed.

    ### Example
    >>> get_data(args, uri='/api/v1/posts')
    (True, {'posts': [...], 'total': 100})
    """
    return base.coe(url.fetch_json(
        f'{args.URL.rstrip("/")}{uri}',
        header={
            'Accept': 'application/json',
            'Authorization': f'Bearer {args.TOKEN}',
        },
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    ))
