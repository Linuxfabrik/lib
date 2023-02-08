#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides functions using the Grassfish REST-API.
https://ds.example.com/gv2/webservices/API/swagger/ui/index
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023012301'

from . import url3


def fetch_json(token, host, port, uri, version, func):
    """curl --request GET --header 'Accept: application/json' --header 'X-ApiKey: token' 'https://$host:$port/$uri'
    """
    url = 'https://{}:{}{}/v{}/{}'.format(host, port, uri, version, func)
    success, result = url3.fetch_json(
        url,
        header={'X-ApiKey':token},
    )
    if not success:
        return (success, result)
    if not result:
        return (False, 'There was no result from {}.'.format(url))

    return (True, result)


def match(item, _filter):
    """Return `True` if item matches a filter, otherwise `False`.
    """
    if _filter.BOX_STATE:
        if item['BoxState'].lower() not in _filter.BOX_STATE:
            return True
    if _filter.CUSTOM_ID:
        if 'CustomId' not in item:
            return True
        matches = re.search(compiled_custom_id_regex, item['CustomId'])
        if not matches:
            return True
    if _filter.IS_INSTALLED:
        if item['IsInstalled'] and 'yes' not in _filter.IS_INSTALLED:
            return True
        if not item['IsInstalled'] and 'no' not in _filter.IS_INSTALLED:
            return True
    if _filter.IS_LICENSED:
        if item['IsLicensed'] and 'yes' not in _filter.IS_LICENSED:
            return True
        if not item['IsLicensed'] and 'no' not in _filter.IS_LICENSED:
            return True

    # does not match the given filters
    return False


def set_defaults(item):
    """These attributes are not returned by the API if they do not contain values, so we
    explicitly set them to `None`.
    """
    if 'BoxID' not in item:
        item['BoxID'] = None
    if 'ConfigurationGroupId' not in item:
        item['ConfigurationGroupId'] = None
    if 'CustomId' not in item:
        item['CustomId'] = None
    if 'EditionId' not in item:
        item['EditionId'] = None
    if 'IsOn' not in item:
        item['IsOn'] = None
    if 'LastAccess' not in item:
        item['LastAccess'] = None
    if 'LastStatusChange' not in item:
        item['LastStatusChange'] = None
    if 'LastUpdate' not in item:
        item['LastUpdate'] = None
    if 'Status' not in item:
        item['Status'] = None
    if 'TimezoneId' not in item:
        item['TimezoneId'] = None

    return item
