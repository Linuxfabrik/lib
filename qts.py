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
__version__ = '2024031501'

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
    Authenticate against the QTS API.
    The auth sid token is required for other API calls.

    API Authentication Documentation: https://download.qnap.com/dev/API_QNAP_QTS_Authentication.pdf

    Parameters
    ----------
    args : dict
        Can usually be directly taken from argparse. Subkeys:

        USERNAME: string
            API Username.
        PASSWORD: string
            API Password.
        URL: string
            API URL.
        INSECURE: bool
            Allow to perform "insecure" SSL connections.
        NO_PROXY: bool
            Do not use a proxy.
        TIMEOUT: int
            Network timeout in seconds.

    Returns
    -------
    tuple: (success, auth_sid)
    """
    if not LIB_XMLTODICT_FOUND:
        return (False, 'Python module "xmltodict" is not installed.')

    api_url = '{}/cgi-bin/authLogin.cgi'.format(args.URL)
    login = {
        'user': args.USERNAME,
        'pwd': txt.to_text(base64.b64encode(txt.to_bytes(args.PASSWORD))),
    }
    result = base.coe(url.fetch(
        api_url,
        data=login,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    ))
    auth_result = xmltodict.parse(result)['QDocRoot']

    auth_passed = auth_result['authPassed']
    if auth_passed is not None and len(auth_passed) == 1 and auth_passed == "0":
        return (False, 'Failed to authenticate.')
    return (True, auth_result['authSid'])
