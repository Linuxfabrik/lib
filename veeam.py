#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library interacts with the Veeam Enterprise Manager API.
Credits go to https://github.com/surfer190/veeam/blob/master/veeam/client.py."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

import base64

from . import txt
from . import url


def get_token(args):
    """
    Authenticate against the Veeam API and retrieve a session token.

    This function logs into the Veeam Backup REST API by sending a POST request with basic
    authentication. It returns allowed methods and the `X-RestSvcSessionId` token used for further
    API requests.

    ### Parameters
    - **args** (object):
      An argument object containing:
        - `URL` (`str`): Base URL of the Veeam API.
        - `USERNAME` (`str`): API Username.
        - `PASSWORD` (`str`): API Password.
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - `success` (`bool`): Whether authentication was successful.
      - `result` (`dict`): Result dictionary containing session token on success, error otherwise.

    ### Notes
    - The session token `X-RestSvcSessionId` is extracted from the HTTP response headers.
    - If authentication fails or no token is found, returns an error message.

    ### Example
    >>> get_token(args)
    (True, {'X-RestSvcSessionId': 'zwiw....'})
    """

    uri = f"{args.URL.rstrip('/')}/api/sessionMngr/?v=latest"
    auth = f"{args.USERNAME}:{args.PASSWORD}"
    encoded_auth = txt.to_text(base64.b64encode(txt.to_bytes(auth)))

    headers = {
        'Authorization': f"Basic {encoded_auth}",
        'Accept': 'application/json',
        'Content-Length': '0',
    }

    data = {'make-this': 'a-post-request'}
    success, result = url.fetch_json(
        uri,
        header=headers,
        data=data,
        extended=True,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )

    if not success:
        return success, result

    if not result:
        return False, f'There was no result from {uri}.'

    token = result.get('response_header', {}).get('X-RestSvcSessionId')
    if not token:
        return False, 'Something went wrong, maybe user is unauthorized.'

    result['X-RestSvcSessionId'] = token
    return True, result
