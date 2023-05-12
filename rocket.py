#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Rocket.Chat related functions that are
needed by more than one Rocket.Chat plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

from . import url


def get_token(rc_url, user, password):
    """Gets an API token from Rocket.Chat, using your credentials.
    Equivalent to:

    $ curl -X "POST" \\
    $      -d "user=admin&password=mypassword" \\
    $      http://localhost:3000/api/v1/login
    """

    if not rc_url.endswith('/login'):
        rc_url += '/login'
    data = {
        'user': user,
        'password': password,
        }

    success, result = url.fetch_json(rc_url, data=data)
    if not success:
        return (success, result)
    if not result:
        return (False, 'There was no result from {}.'.format(rc_url))

    if not 'authToken' in result['data']:
        return (False, 'Something went wrong, maybe user is unauthorized.')
    return (True, result['data']['authToken'] + ':' + result['data']['userId'])


def get_stats(rc_url, auth_token, user_id):
    """Calls api/v1/statistics. You need to get a token using
    `get_token()` first. Equivalent to:

    $ https://rocket.chat/docs/developer-guides/rest-api/miscellaneous/statistics/
    $ curl -H "X-Auth-Token: 8h2mKAwxB3AQrFSjLVKMooJyjdCFaA7W45sWlHP8IzO" \\
    $      -H "X-User-Id: ew28DpvKw3R" \\
    $      http://localhost:3000/api/v1/statistics
    """

    if not rc_url.endswith('/statistics'):
        rc_url += '/statistics'
    header = {
        'X-Auth-Token': auth_token,
        'X-User-Id': user_id,
        }

    success, result = url.fetch_json(rc_url, header=header)
    if not success:
        return (success, result)
    if not result:
        return (False, 'There was no result from {}.'.format(rc_url))

    return (True, result)
