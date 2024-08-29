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
BEXIO_API_CONTACT_URL = '/2.0/contact'
BEXIO_API_CONTACT_GROUP_URL = '/2.0/contact_group'
BEXIO_API_CONTACT_RELATION_URL = '/2.0/contact_relation'
BEXIO_API_CONTACT_SECTOR_URL = '/2.0/contact_branch'  # API endpoint still uses the old name in the URL
BEXIO_API_COUNTRY_URL = '/2.0/country'
BEXIO_API_LANGUAGE_URL = '/2.0/language'
BEXIO_API_SALUTATION_URL = '/2.0/salutation'
BEXIO_API_TITLE_URL = '/2.0/title'
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


def fetch_contacts(api_token: str) -> tuple[bool, list | str]:
    """Calls the Bexio API to get a list of all the contacts
    and returns them in a dictionary indexed by their IDs.

    Parameters
    ----------
    api_token : str
        see call_api()

    Returns
    -------
    tuple[bool, dict | str]
        A boolean indicating the success / failure of the function, and
        a dictionary of all monitors indexed by their IDs
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
