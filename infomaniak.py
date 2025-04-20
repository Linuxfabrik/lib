#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides functions using the Infomanik REST-API.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

from . import url


BASE_URL = 'https://api.infomaniak.com'


def get_events(token, insecure=False, no_proxy=False, timeout=8):
    """
    Get all Infomaniak Events.

    This function queries the Infomaniak API to retrieve all available events. Requires an
    OAuth Bearer token for authentication.

    ### Parameters
    - **token** (`str`):
      OAuth2 Bearer token used for authentication.
    - **insecure** (`bool`, optional):
      Disable SSL verification. Default is `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Default is `False`.
    - **timeout** (`int`, optional):
      Timeout for the request in seconds. Default is 8.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - If successful, returns `(True, events dictionary)`.
      - If failed, returns `(False, error message)`.

    ### Notes
    - API documentation: https://developer.infomaniak.com/docs/api/get/2/events

    ### Example
    >>> success, events = get_events(token)
    >>> if success:
    >>>     print(events)
    """
    uri = f'{BASE_URL}/2/events?locale=en'
    headers = {'Authorization': f'Bearer {token}'}
    success, events = url.fetch_json(
        uri,
        header=headers,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success:
        return success, events
    if not events:
        return False, f'There was no result from {uri}.'
    if events.get('result') != 'success':
        return False, events.get('error', {}).get('description', 'Unknown error')

    return True, events


def get_swiss_backup_products(account_id, token, insecure=False, no_proxy=False, timeout=8):
    """
    Get all Infomaniak Swiss Backup products.

    This function queries the Infomaniak API to retrieve all Swiss Backup products for a given
    account ID. Requires an OAuth Bearer token for authentication.

    ### Parameters
    - **account_id** (`str`):
      ID of the Infomaniak account.
    - **token** (`str`):
      OAuth2 Bearer token used for authentication.
    - **insecure** (`bool`, optional):
      Disable SSL verification. Default is `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Default is `False`.
    - **timeout** (`int`, optional):
      Timeout for the request in seconds. Default is 8.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - If successful, returns `(True, products dictionary)`.
      - If failed, returns `(False, error message)`.

    ### Notes
    - API documentation: https://developer.infomaniak.com/docs/api/get/1/swiss_backups

    ### Example
    >>> success, products = get_swiss_backup_products(account_id, token)
    >>> if success:
    >>>     print(products)
    """
    uri = f'{BASE_URL}/1/swiss_backups?account_id={account_id}'
    headers = {'Authorization': f'Bearer {token}'}
    success, products = url.fetch_json(
        uri,
        header=headers,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success:
        return success, products
    if not products:
        return False, f'There was no result from {uri}.'
    if products.get('result') != 'success':
        return False, products.get('error', {}).get('description', 'Unknown error')

    return True, products


def get_swiss_backup_slots(account_id, token, insecure=False, no_proxy=False, timeout=8):
    """
    Get all devices/slots for each Infomaniak Swiss Backup product.

    This function retrieves all devices (slots) for every Swiss Backup product under a specific
    Infomaniak account.

    ### Parameters
    - **account_id** (`str`):
      ID of the Infomaniak account.
    - **token** (`str`):
      OAuth2 Bearer token used for authentication.
    - **insecure** (`bool`, optional):
      Disable SSL verification. Default is `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Default is `False`.
    - **timeout** (`int`, optional):
      Timeout for the request in seconds. Default is 8.

    ### Returns
    - **tuple** (`bool`, `list` or `str`):
      - If successful, returns `(True, list of slots with additional info)`.
      - If failed, returns `(False, error message)`.

    ### Notes
    - API documentation:
      https://developer.infomaniak.com/docs/api/get/1/swiss_backups/{swiss_backup_id}/slots/{slot_id}

    ### Example
    >>> success, slots = get_swiss_backup_slots(account_id, token)
    >>> if success:
    >>>     print(slots)
    """
    success, products = get_swiss_backup_products(account_id, token)
    if not success:
        return success, products

    slots = []
    for product in products.get('data', []):
        uri = f'{BASE_URL}/1/swiss_backups/{product.get("id")}/slots'
        headers = {'Authorization': f'Bearer {token}'}
        success, slot = url.fetch_json(
            uri,
            header=headers,
            insecure=insecure,
            no_proxy=no_proxy,
            timeout=timeout,
        )
        if not success:
            return success, slot
        if not slot:
            return False, f'There was no result from {uri}.'
        if slot.get('result') != 'success':
            return False, slot.get('error', {}).get('description', 'Unknown error')

        slot['product_customer_name'] = product.get('customer_name')
        slot['product_tags'] = product.get('tags')
        slots.append(slot)

    return True, slots
