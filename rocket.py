#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020040601'

import url

import json


def get_stats(rc_url, authToken, userId):
    # https://rocket.chat/docs/developer-guides/rest-api/miscellaneous/statistics/
    # curl -H "X-Auth-Token: 8h2mKAwxB3AQrFSjLVKMooJyjdCFaA7W45sWlHP8IzO" \
    #      -H "X-User-Id: ew28DpvKw3R" \
    #      http://localhost:3000/api/v1/statistics
    if not rc_url.endswith('/statistics'):
    	rc_url += '/statistics'
    header = {
        'X-Auth-Token': authToken,
        'X-User-Id': userId,
        }

    success, result = url.fetch(rc_url, header=header)
    if not success:
    	return (success, result)
    if not result:
        return (False, 'There was no result from {}.'.format(rc_url))

    return (True, json.loads(result))


# get token from Rocket.Chat after login
def get_token(rc_url, user, password):
    # curl -X "POST" \
    #      -d "user=admin&password=mypassword" \
    #      http://localhost:3000/api/v1/login
    if not rc_url.endswith('/login'):
    	rc_url += '/login'
    data = {
        'user': user,
        'password': password,
        }

    success, result = url.fetch(rc_url, data=data)
    if not success:
    	return (success, result)
    if not result:
        return (False, 'There was no result from {}.'.format(rc_url))

    try:
    	result = json.loads(result)
    except:
    	return (False, 'No JSON object could be decoded')
    else:
	    if not 'authToken' in result['data']:
	        return (False, 'Something went wrong, maybe user is unauthorized.')
	    return (True, result['data']['authToken'] + ':' + result['data']['userId'])
