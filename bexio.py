#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This module tries to make accessing the Bexio API easier.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2024060601'

from . import url

import urllib
import urllib.parse

# https://docs.bexio.com/
BEXIO_API_BASE_URL = 'https://api.bexio.com'
BEXIO_API_CONTACT_TYPE_COMPANY = 1
BEXIO_API_CONTACT_TYPE_PERSON = 2
BEXIO_API_ACCOUNT_URL = '/2.0/accounts'
BEXIO_API_BANK_ACCOUNT_URL = '/3.0/banking/accounts'
BEXIO_API_BUSINESS_ACTIVITY_URL = '/2.0/client_service'  # API endpoint still uses the old name in the URL
BEXIO_API_CONTACT_URL = '/2.0/contact'
BEXIO_API_CONTACT_GROUP_URL = '/2.0/contact_group'
BEXIO_API_CONTACT_RELATION_URL = '/2.0/contact_relation'
BEXIO_API_CONTACT_SECTOR_URL = '/2.0/contact_branch'  # API endpoint still uses the old name in the URL
BEXIO_API_COUNTRY_URL = '/2.0/country'
BEXIO_API_CURRENCY_URL = '/3.0/currencies'
BEXIO_API_INVOICE_URL = '/2.0/kb_invoice'
BEXIO_API_ITEM_URL = '/2.0/article'  # API endpoint uses different name in the URL
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


def call_api(api_token: str, path: str, data: dict | None = None, method: str | None = None) -> tuple[bool, list | str]:
    """Makes an HTTP GET or POST call against the Bexio API
    and returns the parsed JSON.

    Parameters
    ----------
    api_token : str
        Bexio API Token. Create at https://office.bexio.com/index.php/admin/apiTokens.
    path : str
        The URL part to call.
    data : dict
        Dictionary that will be sent as JSON data.
    method : str
        HTTP method to use for the request. Defaults to GET if data is None else POST.

    Returns
    -------
    tuple[bool, dict]
        A boolean indicating the success / failure of the function, and
        a dictionary containing the parsed JSON response from the Bexio API
        or the error message in case of a failure.
    """
    if data is None:
        data = {}

    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer {}'.format(api_token),
    }

    return url.fetch_json(
        '{}{}'.format(BEXIO_API_BASE_URL, path),
        data=data,
        header=headers,
        timeout=20,  # TODO: choose a sensible value. NOTE: test servers seem to be slower to respond than prod servers?
        encoding='serialized-json',
        method=method,
        response_on_error=True,
    )


def get_all(api_token: str, path: str, params: dict | None = None) -> tuple[bool, list | str]:
    """A wrapper function around api_call() that handles the
    pagination of the API and returns all items.

    Parameters
    ----------
    api_token : str
        see call_api()
    path : str
        see call_api()
    params : dict
        Will be passed as URL parameters.

    Returns
    -------
    tuple[bool, dict | str]
        see call_api()
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
        current_path = '{}?{}'.format(path, urllib.parse.urlencode(params))

        success, current_result = call_api(api_token, current_path)
        if not success:
            return success, current_result
        result.extend(current_result)

        # we get an empty list if the offset is too high
        if len(current_result) == 0:
            break

        offset += len(current_result)

    return (True, result)


def fetch_accounts(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all accounts
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all accounts indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_ACCOUNT_URL)


def fetch_bank_accounts(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all bank accounts
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all bank accounts indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_BANK_ACCOUNT_URL)


def fetch_business_activities(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all business activities
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all business activities indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_BUSINESS_ACTIVITY_URL)


def fetch_contacts(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all contacts
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all contacts indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_CONTACT_URL)


def create_contact(api_token: str, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to create a contact
    and returns the created contact as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the created contact
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_CONTACT_URL, data)


def edit_contact(api_token: str, contact_id: int, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to edit a contact
    and returns the edited contact as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    contact_id : int
        id of the contact to edit
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the edited contact
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_CONTACT_URL + '/' + str(contact_id), data)


def fetch_contact_groups(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all contact groups
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all contact groups indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_CONTACT_GROUP_URL)


def fetch_contact_relations(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all contact relations
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all contact relations indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_CONTACT_RELATION_URL)


def create_contact_relation(api_token: str, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to create a new contact relation
    and returns the created contact relation as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the created contact relation
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_CONTACT_RELATION_URL, data)


def edit_contact_relation(api_token: str, contact_relation_id: int, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to edit a contact relation
    and returns the edited contact relation as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    contact_relation_id : int
        id of the contact relation to edit
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the edited contact relation
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_CONTACT_RELATION_URL + '/' + str(contact_relation_id), data)


def delete_contact_relation(api_token: str, contact_relation_id: int) -> tuple[bool, list | str]:
    """Calls the Bexio API to delete a contact relation
    and returns the edited contact relation as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    contact_relation_id : int
        id of the contact relation to delete

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the deletion status
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_CONTACT_RELATION_URL + '/' + str(contact_relation_id), method='DELETE')


def fetch_contact_sectors(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all contact sectors (branches)
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all contact sectors (branches) indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_CONTACT_SECTOR_URL)


def fetch_countries(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all countries
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all countries indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_COUNTRY_URL)


def fetch_currencies(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all currencies
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all currencies indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_CURRENCY_URL)


def fetch_invoices(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all invoices
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all invoices indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_INVOICE_URL)


def fetch_items(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all items
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all items indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_ITEM_URL)


def create_item(api_token: str, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to create an item
    and returns the created item as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the created item
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_ITEM_URL, data)


def edit_item(api_token: str, item_id: int, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to edit an item
    and returns the edited item as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    item_id : int
        id of the item to edit
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the edited item
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_ITEM_URL + '/' + str(item_id), data)


def fetch_languages(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all languages
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all languages indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_LANGUAGE_URL)


def fetch_payment_types(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all payment types
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all payment types indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_PAYMENT_TYPE_URL)


def fetch_project_statuses(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all project statuses
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all project statuses indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_PROJECT_STATUS_URL)


def fetch_project_types(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all project types
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all project types indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_PROJECT_TYPE_URL)


def fetch_projects(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all projects
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all projects indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_PROJECT_URL)


def create_project(api_token: str, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to create a project
    and returns the created project as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the created project
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_PROJECT_URL, data)


def edit_project(api_token: str, project_id: int, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to edit a project
    and returns the edited project as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    project_id : int
        id of the project to edit
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the edited project
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_PROJECT_URL + '/' + str(project_id), data)


def fetch_salutations(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all salutations
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all salutations indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_SALUTATION_URL)


def fetch_stock_areas(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all stock areas
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all stock areas indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_STOCK_AREA_URL)


def fetch_stock_locations(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all stock locations
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all stock locations indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_STOCK_LOCATION_URL)


def fetch_taxes(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all taxes
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all taxes indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_TAX_URL)


def fetch_timesheets(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all timesheets
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all timesheets indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_TIMESHEET_URL)


def create_timesheet(api_token: str, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to create a timesheet
    and returns the created timesheet as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the created timesheet
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_TIMESHEET_URL, data)


def edit_timesheet(api_token: str, timesheet_id: int, data: dict | None = None) -> tuple[bool, list | str]:
    """Calls the Bexio API to edit a timesheet
    and returns the edited timesheet as a dictionary.

    Parameters
    ----------
    api_token : str
        see call_api()
    timesheet_id : int
        id of the timesheet to edit
    data : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of the edited timesheet
        or the error message in case of a failure.
    """
    return call_api(api_token, BEXIO_API_TIMESHEET_URL + '/' + str(timesheet_id), data)


def fetch_timesheet_statuses(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all timesheet statuses
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all timesheet statuses indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_TIMESHEET_STATUS_URL)


def fetch_titles(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all titles
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all titles indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_TITLE_URL)


def fetch_units(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all units
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all taxes indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_UNIT_URL)


def fetch_users(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all users
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all users indexed by their IDs
        or the error message in case of a failure.
    """
    return get_all(api_token, BEXIO_API_USER_URL)
