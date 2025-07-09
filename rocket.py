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
__version__ = '2025070901'

from . import url


def _flatten_params(params):
    """
    Recursively flatten a dictionary of parameters into a URL-style query string.

    This helper function takes a dictionary where values may be primitives (e.g., strings, numbers)
    or nested dictionaries, and converts it into a single query string. Nested dictionaries are
    rendered inside braces `{}` with their own `key=value` pairs joined by `&`.

    ### Parameters
    - **params** (`dict`): Mapping of parameter names to values. Values can be:
      - Primitive types (`str`, `int`, etc.), rendered as `key=value`.
      - Nested `dict`, rendered as `key={inner_key1=inner_val1&inner_key2=inner_val2}`.

    ### Returns
    - **str**: A query string with `&`-separated `key=value` pairs. Nested dicts are enclosed in
      `{}`.

    ### Example
    >>> params = {
    ...     'key1': 'value1',
    ...     'key2': 'value2',
    ...     'key3': {
    ...         'subkey1': 'subvalue1',
    ...         'subkey2': 'subvalue2',
    ...     }
    ... }
    >>> _flatten_params(params)
    'key1=value1&key2=value2&key3={subkey1=subvalue1&subkey2=subvalue2}'
    """
    parts = []
    for key, val in params.items():
        if isinstance(val, dict):
            inner = _flatten_params(val)
            parts.append(f"{key}={{{inner}}}")
        else:
            parts.append(f"{key}={val}")
    return '&'.join(parts)


def get_groups_history(
    rc_url, auth_token, user_id,
    room_id=None, params={},
    insecure=False, no_proxy=False, timeout=3
):
    """
    Retrieve message history for a private group via Rocket.Chat's `groups.history` API.

    This function constructs the correct endpoint URL for `groups.history`, injects the required
    `roomId` into the query parameters along with any additional options, attaches the
    authentication headers (`X-Auth-Token` and `X-User-Id`), and performs a GET request to fetch
    the message history.

    Equivalent to:

    ```bash
    curl -H "X-Auth-Token: <auth_token>" \
         -H "X-User-Id: <user_id>" \
         "https://chat.example.com/api/v1/groups.history?roomId=<roomId>&count=20&offset=0"
    ```

    ### Parameters
    - **rc_url** (`str`): Rocket.Chat base URL or full endpoint URL. If it does not already end with
      `/groups.history`, any trailing slashes will be stripped and `/groups.history` appended.
    - **auth_token** (`str`): Authentication token from login (for the `X-Auth-Token` header).
    - **user_id** (`str`): User ID from login (for the `X-User-Id` header).
    - **room_id** (`str`): ID of the private group whose history you want to fetch. Required.
    - **params** (`dict`, optional): Additional query parameters for pagination and date filtering,
      such as:
      - `count` (`int`): Number of messages to return.
      - `offset` (`int`): Number of messages to skip.
      - `oldest` (`str`): ISO8601 timestamp for the earliest message.
      - `latest` (`str`): ISO8601 timestamp for the latest message.
      Defaults to `{}`.
    - **insecure** (`bool`, optional): Allow insecure SSL connections. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Bypass proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional): Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - On success: `(True, response_json)` where `response_json` contains the history payload.
      - On failure: `(False, 'Error getting groups.history: <error message>')`.

    ### Example
    >>> success, history = get_groups_history(
    ...     'https://chat.example.com', 
    ...     'authTokenHere', 
    ...     'userIdHere',
    ...     room_id='ABC123',
    ...     params={'count': 50, 'offset': 0}
    ... )
    >>> if success:
    ...     for msg in history.get('messages', []):
    ...         print(msg['u']['username'], msg['msg'])
    """
    if not rc_url.endswith('/groups.history'):
        rc_url = rc_url.rstrip('/') + '/groups.history'

    params.update({'roomId': room_id})  # add the required room_id to the parameter list
    query = _flatten_params(params)
    rc_url = rc_url + f'{"?" + query if query else ""}'

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
        return False, f'Error getting groups.history: {result}'

    return True, result


def get_rooms_get(rc_url, auth_token, user_id, insecure=False, no_proxy=False, timeout=3):
    """
    Retrieve the list of chat rooms accessible to the authenticated user via Rocket.Chat's
    `rooms.get` API.

    This function constructs the correct endpoint URL for `rooms.get`, attaches the required
    authentication headers (`X-Auth-Token` and `X-User-Id`), and performs a GET request to fetch
    metadata about all chat rooms that the user can access.

    Equivalent to:

    ```bash
    curl -H "X-Auth-Token: <auth_token>" \
         -H "X-User-Id: <user_id>" \
         https://chat.example.com/api/v1/rooms.get
    ```

    ### Parameters
    - **rc_url** (`str`): Rocket.Chat base URL or full endpoint URL. If it does not already end with
      `/rooms.get`, any trailing slashes will be stripped and `/rooms.get` appended.
    - **auth_token** (`str`): Authentication token obtained from `login` (for the `X-Auth-Token`
      header).
    - **user_id** (`str`): User ID obtained from `login` (for the `X-User-Id` header).
    - **insecure** (`bool`, optional): Allow insecure SSL connections. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Bypass proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional): Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - On success: `(True, response_json)` where `response_json` is the parsed JSON result from
        the API.
      - On failure: `(False, 'Error getting rooms.get: <error message>')`.

    ### Example
    >>> success, rooms = get_rooms_get(
    ...     'https://chat.example.com', 
    ...     'authTokenHere', 
    ...     'userIdHere'
    ... )
    >>> if success:
    ...     print(rooms)
    """
    if not rc_url.endswith('/rooms.get'):
        rc_url = rc_url.rstrip('/') + '/rooms.get'

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
        return False, f'Error getting rooms.get: {result}'

    return True, result


def get_rooms_info(
    rc_url, auth_token, user_id,
    room_id=None, room_name=None,
    insecure=False, no_proxy=False, timeout=3
):
    """
    Retrieve detailed information about a specific Rocket.Chat room via the `rooms.info` API.

    This function constructs the correct endpoint URL for `rooms.info`, optionally appending
    a `roomId` or `roomName` query parameter, attaches the required authentication headers
    (`X-Auth-Token` and `X-User-Id`), and performs a GET request to fetch metadata for the
    specified room.

    Equivalent to:

    ```bash
    curl -H "X-Auth-Token: <auth_token>" \
         -H "X-User-Id: <user_id>" \
         "https://chat.example.com/api/v1/rooms.info?roomId=<roomId>&roomName=<roomName>"
    ```

    ### Parameters
    - **rc_url** (`str`): Rocket.Chat base URL or full endpoint URL. If it does not already end with
      `/rooms.info`, any trailing slashes will be stripped and `/rooms.info` appended.
    - **auth_token** (`str`): Authentication token obtained from login (for the `X-Auth-Token`
      header).
    - **user_id** (`str`): User ID obtained from login (for the `X-User-Id` header).
    - **room_id** (`str`, optional): ID of the room to fetch info for. Defaults to `None`.
    - **room_name** (`str`, optional): Name (alias) of the room to fetch info for. Defaults to
      `None`.
      At least one of `room_id` or `room_name` should be provided.
    - **insecure** (`bool`, optional): Allow insecure SSL connections. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Bypass proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional): Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - On success: `(True, response_json)` where `response_json` is the parsed JSON result from
        the API.
      - On failure: `(False, 'Error getting rooms.info: <error message>')`.

    ### Example
    >>> success, info = get_rooms_info(
    ...     'https://chat.example.com', 
    ...     'authTokenHere', 
    ...     'userIdHere',
    ...     room_id='GENERAL'
    ... )
    >>> if success:
    ...     print(info)
    """
    if not rc_url.endswith('/rooms.info'):
        rc_url = rc_url.rstrip('/') + '/rooms.info'

    params = {
        'roomId': room_id,
        'roomName': room_name,
    }
    query = _flatten_params(params)
    rc_url = rc_url + f'{"?" + query if query else ""}'

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
        return False, f'Error getting rooms.info: {result}'

    return True, result


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


def send2webhook(rc_url, webhook, data, insecure=False, no_proxy=False, timeout=3):
    """
    Send a JSON payload to a Rocket.Chat incoming webhook.

    This function posts `data` to a Rocket.Chat incoming webhook endpoint, constructing the full URL
    from the provided `rc_url` and `webhook` ID or token.

    Equivalent to:

    ```bash
    curl -X POST \
         -H 'Content-type: application/json' \
         -d '{"text":"Hello"}' \
         https://chat.example.com/hooks/<webhook>
    ```

    ### Parameters
    - **rc_url** (`str`): Rocket.Chat base URL. May include `/api/v1`; if so, it will be stripped.
    - **webhook** (`str`): Incoming webhook identifier or token (e.g. `CWaA.../Zbpj...`).
    - **data** (`dict`): JSON-serializable payload to send (e.g., `{'text': 'message'}`).
    - **insecure** (`bool`, optional): Allow insecure SSL connections. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Bypass any proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional): Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `bool` or `str`):
      - On success: `(True, True)`.
      - On failure: `(False, 'Error: <error message>')`.

    ### Example
    >>> data = { 'text': '\\n'.join(['bitte beantworten:'] + output) }
    >>> send2webhook('https://chat.example.com/api/v1', 'CWaA.../Zbpj...', data)
    (True, True)
    """
    rc_url = rc_url.replace('/api/v1', '').rstrip('/') + '/hooks/' + webhook
    success, result = url.fetch_json(
        rc_url,
        data=data,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if not success or not result:
        return False, f'Error: {result}'

    return True, True
