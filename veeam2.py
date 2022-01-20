#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library interacts with the Veeam Enterprise Manager API.
Credits go to https://github.com/surfer190/veeam/blob/master/veeam/client.py."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2022012001'

import base64

import url2


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
    url = args.URL + '/api/sessionMngr/?v=latest'
    header = {}
    # Basic authentication
    header['Authorization'] = u"Basic {}".format(
        base64.b64encode(args.USERNAME + ':' + args.PASSWORD))
    header['Accept'] = 'application/json'
    header['Content-Length'] = 0
    # make this a POST request by filling data with anything
    data = {'make-this': 'a-post-request'}

    success, result = url2.fetch_json(url, header=header, data=data,
        timeout=args.TIMEOUT, insecure=True, extended=True)
    if not success:
        return (success, result)
    if not result:
        return (False, u'There was no result from {}.'.format(url), False)
    if not 'X-RestSvcSessionId' in result:
        return (False, 'Something went wrong, maybe user is unauthorized.', False)
    return (True, result)
