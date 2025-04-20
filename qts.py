#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library assists the communication with QNAP's QTS
operating system via its API.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

import base64

from . import base
from . import txt
from . import url

try:
    import xmltodict
    LIB_XMLTODICT_FOUND = True
except ImportError as e:
    LIB_XMLTODICT_FOUND = False


def get_auth_sid(args):
    """
    Authenticate against the QNAP QTS API.

    This function authenticates against the QNAP QTS API and retrieves an auth SID token needed for
    other API operations.

    ### Parameters
    - **args** (object):
      An argument object containing:
        - `USERNAME` (`str`): API Username.
        - `PASSWORD` (`str`): API Password.
        - `URL` (`str`): API base URL.
        - `INSECURE` (`bool`): Whether to allow insecure SSL connections.
        - `NO_PROXY` (`bool`): Whether to disable proxy usage.
        - `TIMEOUT` (`int`): Request timeout in seconds.

    ### Returns
    - **tuple** (`bool`, `str` or `error`):
      - `True` and the `auth_sid` if authentication succeeds.
      - `False` and an error message if authentication fails.

    ### Notes
    - Requires the `xmltodict` Python library.
    - Refer to API doc: https://download.qnap.com/dev/API_QNAP_QTS_Authentication.pdf

    ### Example
    >>> success, auth_sid = get_auth_sid(args)
    """
    if not LIB_XMLTODICT_FOUND:
        return False, 'Python module "xmltodict" is not installed.'

    api_url = f'{args.URL.rstrip("/")}/cgi-bin/authLogin.cgi'
    login_payload = {
        'user': args.USERNAME,
        'pwd': txt.to_text(base64.b64encode(txt.to_bytes(args.PASSWORD))),
    }
    success, result = url.fetch(
        api_url,
        data=login_payload,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )

    if not success:
        return False, result

    try:
        auth_result = xmltodict.parse(result)['QDocRoot']
    except Exception as e:
        return False, f'Failed to parse XML: {e}'

    if auth_result.get('authPassed') == "0":
        return False, 'Failed to authenticate.'

    return True, auth_result.get('authSid')
