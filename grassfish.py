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
__version__ = '2026041201'

from . import url

# curl --header 'Accept: application/json' --header 'X-ApiKey: token' 'https://$host:$port/$uri'


def fetch_json(
    token, host, port, uri, version, func, insecure=False, no_proxy=False, timeout=8
):
    """
    Fetch JSON data from a Grassfish API endpoint.

    This function builds a full API URL, sends an authenticated HTTPS GET request, and parses the
    JSON response. It uses a token for authentication via the `X-ApiKey` header.

    ### Parameters
    - **token** (`str`):
      The API token for authentication (passed as `X-ApiKey` header).
    - **host** (`str`):
      The Grassfish server hostname or IP address.
    - **port** (`int`):
      The port number on which the API is accessible (usually 443 for HTTPS).
    - **uri** (`str`):
      The base URI path before the version number, e.g., `/api`.
    - **version** (`int` or `str`):
      The API version number, without leading 'v'.
    - **func** (`str`):
      The specific API function or endpoint to call.
    - **insecure** (`bool`, optional):
      If `True`, disables SSL verification. Default is `False`.
    - **no_proxy** (`bool`, optional):
      If `True`, bypass system proxy settings. Default is `False`.
    - **timeout** (`int`, optional):
      Request timeout in seconds. Default is `8`.

    ### Returns
    - **tuple**:
      - `(True, dict)`: On success, parsed JSON data.
      - `(False, str)`: On failure, an error message.

    ### Notes
    - The function uses HTTPS by default.
    - If the API response is empty, an error is returned.

    ### Example
    >>> fetch_json(
    ...     token='your-api-token',
    ...     host='api.example.com',
    ...     port=443,
    ...     uri='/api',
    ...     version=1,
    ...     func='devices',
    ... )
    (True, {...})
    """
    full_uri = f'https://{host}:{port}{uri}/v{version}/{func}'
    success, result = url.fetch_json(
        full_uri,
        header={'X-ApiKey': token},
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success:
        return False, result
    if not result:
        return False, f'There was no result from {full_uri}.'

    return True, result


def set_player_defaults(item):
    """
    Ensure all expected player attributes are set, even if missing.

    This function sets any missing expected fields in a player dictionary to `None`, because the
    Grassfish API omits attributes that have no values. It ensures a consistent data structure for
    further processing.

    ### Parameters
    - **item** (`dict`):
      A dictionary representing a player resource from the Grassfish API.

    ### Returns
    - **dict**:
      The modified player dictionary with all expected fields initialized.

    ### Notes
    - If a field like `City`, `Longitude`, `IsInstalled`, etc. is missing, it will be set to `None`.
    - Useful for normalizing API responses before storing, processing, or comparing.

    ### Example
    >>> player = {'Name': 'Player1', 'City': 'Zurich'}
    >>> set_player_defaults(player)
    {
        'Address': None,
        'BoxId': None,
        'BoxState': None,
        'City': 'Zurich',
        'ConfigurationGroupId': None,
        ...
    }
    """
    expected_fields = [
        'Address',
        'BoxId',
        'BoxState',
        'City',
        'ConfigurationGroupId',
        'Country',
        'Created',
        'CustomId',
        'EditionId',
        'Email',
        'FaxNumber',
        'Id',
        'IsInstalled',
        'IsLicensed',
        'LastAccess',
        'Latitude',
        'LicenseType',
        'LocationId',
        'Longitude',
        'Modified',
        'Name',
        'PendingTimezoneId',
        'PhoneNumber',
        'PostCode',
        'ProvisioningState',
        'RootPasswordSet',
        'TemperatureUnit',
        'TimezoneId',
        'TransferStatus',
    ]
    for field in expected_fields:
        item.setdefault(field, None)

    return item


def set_screen_defaults(item):
    """
    Ensure all expected screen attributes are set, even if missing.

    This function sets any missing expected fields in a screen dictionary to `None`, because the
    Grassfish API omits attributes that have no values. It ensures a consistent data structure for
    further processing.

    ### Parameters
    - **item** (`dict`):
      A dictionary representing a screen resource from the Grassfish API.

    ### Returns
    - **dict**:
      The modified screen dictionary with all expected fields initialized.

    ### Notes
    - If a field like `DisplayName`, `Orientation`, or `Status` is missing, it will be set to `None`.
    - Useful for normalizing API responses before storing, processing, or comparing.

    ### Example
    >>> screen = {'DisplayName': 'MainScreen'}
    >>> set_screen_defaults(screen)
    {
        'DisplayName': 'MainScreen',
        'Id': None,
        'IsOn': None,
        'LastStatusChange': None,
        ...
    }
    """
    expected_fields = [
        'DisplayName',
        'Id',
        'IsOn',
        'LastStatusChange',
        'LastUpdate',
        'Number',
        'Orientation',
        'PendingOrientation',
        'Status',
    ]
    for field in expected_fields:
        item.setdefault(field, None)

    return item
