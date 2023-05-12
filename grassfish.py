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
__version__ = '2023051201'

from . import url


def fetch_json(token, host, port, uri, version, func):
    """curl --request GET --header 'Accept: application/json' --header 'X-ApiKey: token' 'https://$host:$port/$uri'
    """
    uri = 'https://{}:{}{}/v{}/{}'.format(host, port, uri, version, func)
    success, result = url.fetch_json(
        uri,
        header={'X-ApiKey': token},
    )
    if not success:
        return (success, result)
    if not result:
        return (False, 'There was no result from {}.'.format(uri))

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


def set_player_defaults(item):
    """These attributes are not returned by the API if they do not contain values, so we
    explicitly set them to `None`.
    """
    if 'Address' not in item:
        item['Address'] = None
    if 'BoxId' not in item:
        item['BoxId'] = None
    if 'BoxState' not in item:
        item['BoxState'] = None
    if 'City' not in item:
        item['City'] = None
    if 'ConfigurationGroupId' not in item:
        item['ConfigurationGroupId'] = None
    if 'Country' not in item:
        item['Country'] = None
    if 'Created' not in item:
        item['Created'] = None
    if 'CustomId' not in item:
        item['CustomId'] = None
    if 'EditionId' not in item:
        item['EditionId'] = None
    if 'Email' not in item:
        item['Email'] = None
    if 'FaxNumber' not in item:
        item['FaxNumber'] = None
    if 'Id' not in item:
        item['Id'] = None
    if 'IsInstalled' not in item:
        item['IsInstalled'] = None
    if 'IsLicensed' not in item:
        item['IsLicensed'] = None
    if 'LastAccess' not in item:
        item['LastAccess'] = None
    if 'Latitude' not in item:
        item['Latitude'] = None
    if 'LicenseType' not in item:
        item['LicenseType'] = None
    if 'LocationId' not in item:
        item['LocationId'] = None
    if 'Longitude' not in item:
        item['Longitude'] = None
    if 'Modified' not in item:
        item['Modified'] = None
    if 'Name' not in item:
        item['Name'] = None
    if 'PendingTimezoneId' not in item:
        item['PendingTimezoneId'] = None
    if 'PhoneNumber' not in item:
        item['PhoneNumber'] = None
    if 'PostCode' not in item:
        item['PostCode'] = None
    if 'ProvisioningState' not in item:
        item['ProvisioningState'] = None
    if 'RootPasswordSet' not in item:
        item['RootPasswordSet'] = None
    if 'TemperatureUnit' not in item:
        item['TemperatureUnit'] = None
    if 'TimezoneId' not in item:
        item['TimezoneId'] = None
    if 'TransferStatus' not in item:
        item['TransferStatus'] = None

    return item


def set_screen_defaults(item):
    """These attributes are not returned by the API if they do not contain values, so we
    explicitly set them to `None`.
    """
    if 'DisplayName' not in item:
        item['DisplayName'] = None
    if 'Id' not in item:
        item['Id'] = None
    if 'IsOn' not in item:
        item['IsOn'] = None
    if 'LastStatusChange' not in item:
        item['LastStatusChange'] = None
    if 'LastUpdate' not in item:
        item['LastUpdate'] = None
    if 'Number' not in item:
        item['Number'] = None
    if 'Orientation' not in item:
        item['Orientation'] = None
    if 'PendingOrientation' not in item:
        item['PendingOrientation'] = None
    if 'Status' not in item:
        item['Status'] = None

    return item

