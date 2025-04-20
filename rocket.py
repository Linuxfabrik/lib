#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Rocket.Chat related functions that are
needed by more than one Rocket.Chat plugin.

Typical use-case:

```python
credentials = lib.base.coe(lib.rocket.get_token(
    args.URL,
    args.USERNAME,
    args.PASSWORD,
    insecure=args.INSECURE,
    no_proxy=args.NO_PROXY,
    timeout=args.TIMEOUT,
))
auth_token, user_id = credentials.split(':')
result = lib.base.coe(lib.rocket.get_stats(
    args.URL,
    auth_token,
    user_id,
    insecure=args.INSECURE,
    no_proxy=args.NO_PROXY,
    timeout=args.TIMEOUT,
))
```
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

from . import url


def get_stats(rc_url, auth_token, user_id, insecure=False, no_proxy=False, timeout=3):
    """
    Retrieve Rocket.Chat statistics using an API token.

    This function calls the `api/v1/statistics` endpoint to retrieve server stats after
    authentication.

    Equivalent to:

    ```bash
    # https://rocket.chat/docs/developer-guides/rest-api/miscellaneous/statistics/
    curl -H "X-Auth-Token: 8h2mKAwxB3AQrFSjLVKMooJyjdCFaA7W45sWlHP8IzO"
         -H "X-User-Id: ew28DpvKw3R"
         http://localhost:3000/api/v1/statistics
    ```

    ### Parameters
    - **rc_url** (`str`): Rocket.Chat base URL.
    - **auth_token** (`str`): Authentication token.
    - **user_id** (`str`): User ID linked to the token.
    - **insecure** (`bool`, optional): Allow insecure SSL. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Ignore proxy. Defaults to `False`.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `dict`): Success flag and stats data or error message.

    ### Example
    >>> get_stats('https://chat.example.com', auth_token, user_id)
    (True, {...})
    """
    if not rc_url.endswith('/statistics'):
        rc_url = rc_url.rstrip('/') + '/statistics'

    headers = {
        'X-Auth-Token': auth_token,
        'X-User-Id': user_id,
    }

    success, result = url.fetch_json(
        rc_url,
        header=headers,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success or not result:
        return False, f'Error getting statistics: {result}'

    return True, result


def get_token(rc_url, user, password, insecure=False, no_proxy=False, timeout=3):
    """
    Retrieve an API token from Rocket.Chat using user credentials.

    This function authenticates against a Rocket.Chat instance and retrieves an `authToken` and 
    `userId` for future authenticated API calls.

    Equivalent to:

    ```bash
    curl -X "POST"
         -d "user=admin&password=mypassword"
         http://localhost:3000/api/v1/login
    ```

    ### Parameters
    - **rc_url** (`str`): Rocket.Chat base URL.
    - **user** (`str`): Username.
    - **password** (`str`): Password.
    - **insecure** (`bool`, optional): Allow insecure SSL. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Ignore proxy. Defaults to `False`.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `str`): Success flag and result string or error.

    ### Example
    >>> get_token('https://chat.example.com', 'admin', 'mypassword')
    (True, 'authToken:userId')
    """
    if not rc_url.endswith('/login'):
        rc_url = rc_url.rstrip('/') + '/login'

    data = {'user': user, 'password': password}

    success, result = url.fetch_json(
        rc_url,
        data=data,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success or not result:
        return False, f'Error getting token: {result}'

    data = result.get('data', {})
    auth_token = data.get('authToken')
    user_id = data.get('userId')

    if not auth_token or not user_id:
        return False, 'Authentication failed or user unauthorized.'

    return True, f'{auth_token}:{user_id}'
