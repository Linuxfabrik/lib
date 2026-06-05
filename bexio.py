#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This module tries to make accessing the Bexio API easier."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026060501'

import urllib
import urllib.parse

from . import url

# https://docs.bexio.com/
BEXIO_API_BASE_URL = 'https://api.bexio.com'
BEXIO_API_CONTACT_TYPE_COMPANY = 1
BEXIO_API_CONTACT_TYPE_PERSON = 2
BEXIO_API_ACCOUNT_URL = '/2.0/accounts'
BEXIO_API_BANK_ACCOUNT_URL = '/3.0/banking/accounts'
# API endpoint still uses an old name in the URL for "business activities"
BEXIO_API_BUSINESS_ACTIVITY_URL = '/2.0/client_service'
BEXIO_API_CONTACT_URL = '/2.0/contact'
BEXIO_API_CONTACT_GROUP_URL = '/2.0/contact_group'
BEXIO_API_CONTACT_RELATION_URL = '/2.0/contact_relation'
# API endpoint still uses an old name in the URL for "contact sectors"
BEXIO_API_CONTACT_SECTOR_URL = '/2.0/contact_branch'
BEXIO_API_COUNTRY_URL = '/2.0/country'
BEXIO_API_CURRENCY_URL = '/3.0/currencies'
BEXIO_API_DEFAULT_API_CALL_TIMEOUT = 20
BEXIO_API_INVOICE_URL = '/2.0/kb_invoice'
BEXIO_API_ITEM_URL = '/2.0/article'  # API endpoint uses a different name in the URL
BEXIO_API_LANGUAGE_URL = '/2.0/language'
BEXIO_API_SALUTATION_URL = '/2.0/salutation'
BEXIO_API_PAYMENT_TYPE_URL = '/2.0/payment_type'
BEXIO_API_PROJECT_STATUS_URL = '/2.0/pr_project_state'
BEXIO_API_PROJECT_TYPE_URL = '/2.0/pr_project_type'
BEXIO_API_PROJECT_URL = '/2.0/pr_project'
BEXIO_API_STOCK_AREA_URL = '/2.0/stock_place'
BEXIO_API_STOCK_LOCATION_URL = '/2.0/stock'
BEXIO_API_TAX_URL = '/3.0/taxes'
BEXIO_API_TIMESHEET_URL = '/2.0/timesheet'
BEXIO_API_TIMESHEET_STATUS_URL = '/2.0/timesheet_status'
BEXIO_API_TITLE_URL = '/2.0/title'
BEXIO_API_UNIT_URL = '/2.0/unit'
BEXIO_API_USER_URL = '/3.0/users'


def call_api(api_token, path, data=None, method=None):
    """
    Makes an HTTP GET or POST call against the Bexio API and returns the parsed JSON.

    ### Parameters
    - **api_token** (`str`)
        Bexio API Token. Create at https://developer.bexio.com/pat.
    - **path** (`str`)
        The URL part to call.
    - **data** (`dict`, optional)
        Dictionary that will be sent as JSON data.
    - **method** (`str`, optional)
        HTTP method to use for the request. Defaults to GET if data is None else POST.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `list` | `str`):
        - On success, the parsed JSON document from the Bexio API
        - On failure, an error message string.
    """
    if data is None:
        data = {}

    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_token}',
    }

    return url.fetch_json(
        f'{BEXIO_API_BASE_URL}{path}',
        data=data,
        header=headers,
        timeout=BEXIO_API_DEFAULT_API_CALL_TIMEOUT,
        encoding='serialized-json',
        method=method,
        response_on_error=True,
    )


def get_all(api_token, path, params=None):
    """
    A wrapper function around `call_api()` that handles the pagination of the Bexio API and
    returns all items.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **path** (`str`):
        See `call_api()`.
    - **params** (`dict` | optional):
        Additional URL parameters to be added to the request.

    ### Returns
    - **tuple**:
        See `call_api()`.
    """
    if params is None:
        params = {}

    offset = 0
    result = []
    # highest limit of all endpoints. let's use that, if the max is less that's fine as well
    max_limit = 2000
    while True:
        params['offset'] = offset
        params['limit'] = max_limit
        current_path = f'{path}?{urllib.parse.urlencode(params)}'

        success, current_result = call_api(api_token, current_path)
        if not success:
            return success, current_result
        result.extend(current_result)

        # we get an empty list if the offset is too high
        if len(current_result) == 0:
            break

        offset += len(current_result)

    return (True, result)


def fetch_accounts(api_token):
    """
    Fetches all accounts from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all accounts as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Accounts/operation/v2ListAccounts
    """
    return get_all(api_token, BEXIO_API_ACCOUNT_URL)


def fetch_bank_accounts(api_token):
    """
    Fetches all bank accounts from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all bank accounts as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to API doc: https://docs.bexio.com/#tag/Bank-Accounts/operation/ListBankAccounts
    """
    return get_all(api_token, BEXIO_API_BANK_ACCOUNT_URL)


def fetch_business_activities(api_token):
    """
    Fetches all business activities from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all business activities as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to API doc:
    https://docs.bexio.com/#tag/Business-Activities/operation/v2ListBusinessActivities
    """
    return get_all(api_token, BEXIO_API_BUSINESS_ACTIVITY_URL)


def fetch_contacts(api_token, archived=False):
    """
    Fetches all (optionally including archived) contacts from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.
    - **archived** (`bool`, optional):
        If `True`, also request archived contacts from the API. Defaults to `False`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all contacts as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Contacts/operation/v2ListContacts
    """
    return get_all(api_token, BEXIO_API_CONTACT_URL, {'show_archived': archived})


def create_contact(api_token, data=None):
    """
    Creates a contact using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **data** (`dict`, optional):
        Contact data to be created, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the created contact.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Contacts/operation/v2CreateContact
    """
    return call_api(api_token, BEXIO_API_CONTACT_URL, data)


def edit_contact(api_token, contact_id, data=None):
    """
    Edits a contact using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **contact_id** (`int`):
        ID of the contact to edit.
    - **data** (`dict`):
        Contact data to be edited, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the edited contact.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Contacts/operation/v2EditContact
    """
    return call_api(api_token, BEXIO_API_CONTACT_URL + '/' + str(contact_id), data)


def fetch_contact_groups(api_token):
    """
    Fetches all contact groups from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all contact groups as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Contact-Groups/operation/v2ListContactGroups
    """
    return get_all(api_token, BEXIO_API_CONTACT_GROUP_URL)


def fetch_contact_relations(api_token):
    """
    Fetches all contact relations from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all contact relations as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc:
    https://docs.bexio.com/#tag/Contact-Relations/operation/v2ListContactRelations
    """
    return get_all(api_token, BEXIO_API_CONTACT_RELATION_URL)


def create_contact_relation(api_token, data=None):
    """
    Creates a contact relation using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **data** (`dict`):
        Contact relation data to be created, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the created contact relation.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc:
    https://docs.bexio.com/#tag/Contact-Relations/operation/v2CreateContactRelation
    """
    return call_api(api_token, BEXIO_API_CONTACT_RELATION_URL, data)


def edit_contact_relation(api_token, contact_relation_id, data=None):
    """
    Edits a contact relation using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **contact_relation_id** (`int`):
        ID of the contact relation to edit.
    - **data** (`dict`):
        Contact relation data to be edited, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the edited contact relation.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc:
    https://docs.bexio.com/#tag/Contact-Relations/operation/v2EditContactRelation
    """
    return call_api(
        api_token,
        BEXIO_API_CONTACT_RELATION_URL + '/' + str(contact_relation_id),
        data,
    )


def delete_contact_relation(api_token, contact_relation_id):
    """
    Deletes a contact relation using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **contact_relation_id** (`int`):
        ID of the contact relation to delete.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the deletion status.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc:
    https://docs.bexio.com/#tag/Contact-Relations/operation/v2DeleteContactRelation
    """
    return call_api(
        api_token,
        BEXIO_API_CONTACT_RELATION_URL + '/' + str(contact_relation_id),
        method='DELETE',
    )


def fetch_contact_sectors(api_token):
    """
    Fetches all contact sectors (branches) from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all contact sectors (branches) as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc:
    https://docs.bexio.com/#tag/Contact-Sectors/operation/v2ListContactSectors
    """
    return get_all(api_token, BEXIO_API_CONTACT_SECTOR_URL)


def fetch_countries(api_token):
    """
    Fetches all countries from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all countries as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Countries/operation/v2ListCountries
    """
    return get_all(api_token, BEXIO_API_COUNTRY_URL)


def fetch_currencies(api_token):
    """
    Fetches all currencies from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all currencies as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Currencies/operation/ListCurrencies
    """
    return get_all(api_token, BEXIO_API_CURRENCY_URL)


def fetch_invoices(api_token):
    """
    Fetches all invoices from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all invoices as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Invoices/operation/v2ListInvoices
    """
    return get_all(api_token, BEXIO_API_INVOICE_URL)


def create_invoice(api_token, data=None):
    """
    Creates an invoice using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **data** (`dict`, optional):
        Invoice data to be created, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the created invoice.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Invoices/operation/v2CreateInvoice
    """
    return call_api(api_token, BEXIO_API_INVOICE_URL, data)


def edit_invoice(api_token, invoice_id, data=None):
    """
    Edits an invoice using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **invoice_id** (`int`):
        ID of the invoice to edit.
    - **data** (`dict`, optional):
        Invoice data to be edited, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the edited invoice.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Invoices/operation/v2EditInvoice
    """
    return call_api(api_token, BEXIO_API_INVOICE_URL + '/' + str(invoice_id), data)


def fetch_items(api_token):
    """
    Fetches all items from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all items as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Items/operation/v2ListItems
    """
    return get_all(api_token, BEXIO_API_ITEM_URL)


def create_item(api_token, data=None):
    """
    Creates an item using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **data** (`dict`, optional):
        Item data to be created, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the created item.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Items/operation/v2CreateItem
    """
    return call_api(api_token, BEXIO_API_ITEM_URL, data)


def edit_item(api_token, item_id, data=None):
    """
    Edits an item using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **item_id** (`int`):
        ID of the item to edit.
    - **data** (`dict`, optional):
        Item data to be edited, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the edited item.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Items/operation/v2EditItem
    """
    return call_api(api_token, BEXIO_API_ITEM_URL + '/' + str(item_id), data)


def fetch_languages(api_token):
    """
    Fetches all languages from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all languages as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Languages/operation/v2ListLanguages
    """
    return get_all(api_token, BEXIO_API_LANGUAGE_URL)


def fetch_payment_types(api_token):
    """
    Fetches all payment types from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all payment types as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Payment-Types/operation/v2ListPaymentTypes
    """
    return get_all(api_token, BEXIO_API_PAYMENT_TYPE_URL)


def fetch_project_statuses(api_token):
    """
    Fetches all project statuses from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all project statuses as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Projects/operation/v2ListProjectStatus
    """
    return get_all(api_token, BEXIO_API_PROJECT_STATUS_URL)


def fetch_project_types(api_token):
    """
    Fetches all project types from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all project types as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Projects/operation/v2ListProjectType
    """
    return get_all(api_token, BEXIO_API_PROJECT_TYPE_URL)


def fetch_projects(api_token):
    """
    Fetches all projects from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all projects as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Projects/operation/v2ListProjects
    """
    return get_all(api_token, BEXIO_API_PROJECT_URL)


def create_project(api_token, data=None):
    """
    Creates a project using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **data** (`dict`, optional):
        Project data to be created, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the created project.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Projects/operation/v2CreateProject
    """
    return call_api(api_token, BEXIO_API_PROJECT_URL, data)


def edit_project(api_token, project_id, data=None):
    """
    Edits a project using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **project_id** (`int`):
        ID of the project to edit.
    - **data** (`dict`, optional):
        Project data to be edited, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the edited project.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Projects/operation/v2EditProject
    """
    return call_api(api_token, BEXIO_API_PROJECT_URL + '/' + str(project_id), data)


def fetch_salutations(api_token):
    """
    Fetches all salutations from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all salutations as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Salutations/operation/v2ListSalutations
    """
    return get_all(api_token, BEXIO_API_SALUTATION_URL)


def fetch_stock_areas(api_token):
    """
    Fetches all stock areas from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all stock areas as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Stock-Areas/operation/v2ListStockAreas
    """
    return get_all(api_token, BEXIO_API_STOCK_AREA_URL)


def fetch_stock_locations(api_token):
    """
    Fetches all stock locations from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all stock locations as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc:
    https://docs.bexio.com/#tag/Stock-locations/operation/v2ListStockLocations
    """
    return get_all(api_token, BEXIO_API_STOCK_LOCATION_URL)


def fetch_taxes(api_token):
    """
    Fetches all taxes from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all taxes as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Taxes/operation/ListTaxes
    """
    return get_all(api_token, BEXIO_API_TAX_URL)


def fetch_timesheets(api_token):
    """
    Fetches all timesheets from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all timesheets as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Timesheets/operation/v2ListTimesheets
    """
    return get_all(api_token, BEXIO_API_TIMESHEET_URL)


def create_timesheet(api_token, data=None):
    """
    Creates a timesheet using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **data** (`dict`, optional):
        Timesheet data to be created, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the created timesheet.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Timesheets/operation/v2CreateTimesheet
    """
    return call_api(api_token, BEXIO_API_TIMESHEET_URL, data)


def edit_timesheet(api_token, timesheet_id, data=None):
    """
    Edits a timesheet using the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `call_api()`.
    - **timesheet_id** (`int`):
        ID of the timesheet to edit.
    - **data** (`dict`, optional):
        Project data to be edited, as per the Bexio API documentation.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`dict` | `str`):
        - On success, a dictionary of the edited timesheet.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Timesheets/operation/v2EditTimesheet
    """
    return call_api(api_token, BEXIO_API_TIMESHEET_URL + '/' + str(timesheet_id), data)


def fetch_timesheet_statuses(api_token):
    """
    Fetches all timesheet statuses from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all timesheet statuses as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Timesheets/operation/v2ListTimesheets
    """
    return get_all(api_token, BEXIO_API_TIMESHEET_STATUS_URL)


def fetch_titles(api_token):
    """
    Fetches all titles from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all titles as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Titles/operation/v2ListTitles
    """
    return get_all(api_token, BEXIO_API_TITLE_URL)


def fetch_units(api_token):
    """
    Fetches all units from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all units as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/Units/operation/v2ListUnits
    """
    return get_all(api_token, BEXIO_API_UNIT_URL)


def fetch_users(api_token):
    """
    Fetches all users from the Bexio API.

    ### Parameters
    - **api_token** (`str`):
        See `get_all()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): `True` if the request was successful, `False` otherwise.
      - **result** (`list` | `str`):
        - On success, a list of all users as dictionaries.
        - On failure, an error message string.

    ### Notes
    - Refer to the API doc: https://docs.bexio.com/#tag/User-Management/operation/v3ListUsers
    """
    return get_all(api_token, BEXIO_API_USER_URL)
