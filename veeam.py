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
__version__ = '2023051201'

import base64

from . import txt
from . import url


def get_token(args):
    """Login like
          `curl --request POST
                --header "Authorization: Basic $(echo -n 'user:password' | base64)"
                --header "Accept: application/json"
                --header "Content-Length: 0"
                https://veeam:9398/api/sessionMngr/?v=latest`
    and return allowed methods and the `X-RestSvcSessionId` token
    (looks like `ZWIwMDkzODMtM2YzNy00MDJjLThlNzMtZDEwY2E4ZmU5MzYx`).
    """
    uri = args.URL + '/api/sessionMngr/?v=latest'
    header = {}
    # Basic authentication
    auth = '{}:{}'.format(args.USERNAME, args.PASSWORD)
    encoded_auth = txt.to_text(base64.b64encode(txt.to_bytes(auth)))
    header['Authorization'] = 'Basic {}'.format(encoded_auth)
    header['Accept'] = 'application/json'
    header['Content-Length'] = 0
    # make this a POST request by filling data with anything
    data = {'make-this': 'a-post-request'}
    success, result = url.fetch_json(
        uri,
        header=header,
        data=data,
        timeout=args.TIMEOUT,
        insecure=True,
        extended=True,
    )
    if not success:
        return (success, result)
    if not result:
        return (False, 'There was no result from {}.'.format(uri))
    # In Python 3, getheader() should be get()
    result['X-RestSvcSessionId'] = result.get('response_header').get('X-RestSvcSessionId')
    if not result['X-RestSvcSessionId']:
        return (False, 'Something went wrong, maybe user is unauthorized.')
    return (True, result)
