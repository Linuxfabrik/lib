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
__version__ = '2022031401'

from . import url3


BASE_URL = 'https://api.infomaniak.com'


def get_products(account_id, token):
    """Get all Infomaniak Swiss Backup products.
    """
    url = '{}/1/swiss-backup?account_id={}'.format(BASE_URL, account_id)
    success, products =  url3.fetch_json(url, header={'Authorization':'Bearer {}'.format(token)})
    if not success:
        return (success, products)
    if not products:
        return (False, 'There was no result from {}.'.format(url))
    if products.get('result') != 'success':
        return (False, products.get('error').get('description'))
    return (True, products)


def get_slots(account_id, token):
    """Get all devices / slots for each Infomaniak Swiss Backup product.
    """
    success, products = get_products(account_id, token)
    if not success:
        return (success, products)
    slots = []
    for product in products.get('data', {}):
        url = '{}/1/swiss-backup/{}/slot?account_id={}'.format(
            BASE_URL, product.get('id'), account_id
        )
        success, slot = url3.fetch_json(url, header={'Authorization':'Bearer {}'.format(token)})
        if not success:
            return (success, slot)
        if not slot:
            return (False, 'There was no result from {}.'.format(url))
        if slot.get('result') != 'success':
            return (False, slot.get('error').get('description'))
        # append some information from the parent, too:
        slot['product_customer_name'] = product.get('customer_name')
        slot['product_tags'] = product.get('tags')
        slots.append(slot)
    return (True, slots)
