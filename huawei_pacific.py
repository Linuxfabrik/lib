#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""This library collects functions for Huawei OceanStor Pacific storage systems,
which are accessed through the /api/v2/ REST API (X-Auth-Token authentication,
string- and integer-valued status fields).
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026070301'

import time as _time

from . import base, cache, time, url


def get_alarm_severity(sev):
    """
    Convert a Huawei OceanStor Pacific alarm severity code into a human-readable description.

    ### Parameters
    - **sev** (`int` or `str`):
      The alarm severity code. If a string is passed, it is converted to an integer.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_alarm_severity(6)
    'Critical (6)'
    """
    sev = int(sev)
    mapping = {
        2: 'Information (2)',
        3: 'Warning (3)',
        5: 'Major (5)',
        6: 'Critical (6)',
    }
    return mapping.get(sev, 'Unknown')


def get_alarm_status(st):
    """
    Convert a Huawei OceanStor Pacific alarm status code into a human-readable description.

    ### Parameters
    - **st** (`int` or `str`):
      The alarm status code. If a string is passed, it is converted to an integer.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_alarm_status(1)
    'Unrecovered (1)'
    """
    st = int(st)
    mapping = {
        1: 'Unrecovered (1)',
        2: 'Cleared (2)',
        4: 'Recovered (4)',
    }
    return mapping.get(st, 'Unknown')


def get_creds(args, force_relogin=False):
    """
    Retrieve and cache a Huawei OceanStor Pacific session token.

    This function authenticates against the `/api/v2/aa/sessions` endpoint and returns the
    `X-Auth-Token` used for all subsequent requests. The token is cached and reused across runs to
    avoid repeated logins, which may be rate-limited for security reasons. The appliance is
    identified by its base URL, since the login is not scoped to a device ID.

    ### Parameters
    - **args** (object):
      An argument object containing:
        - `URL` (`str`): Base URL of the Pacific API (`https://<ip>:<port>`).
        - `USERNAME` (`str`): Login user name.
        - `PASSWORD` (`str`): Login password.
        - `SCOPE` (`str`): User type (`'0'` local user, `'1'` LDAP user).
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.
        - `CACHE_EXPIRE` (`int`): Cache expiration time in minutes.
    - **force_relogin** (`bool`, optional):
      If `True`, ignore any cached token and perform a fresh login, overwriting the cache.
      Used to recover from a cached session that the appliance no longer accepts (for example
      after a session reset or the server-side session timeout).

    ### Returns
    - **str**:
      The `x_auth_token` session token.

    ### Notes
    - The token is stored in the cache key `huaweipacific-{URL}-xauthtoken`.
    - The password is sent as plaintext over HTTPS (`isEncrypt` is `False`); the token is returned
      in the response body, not in a response header.

    ### Example
    >>> x_auth_token = get_creds(args)
    """
    token_key = f'huaweipacific-{args.URL}-xauthtoken'

    if not force_relogin:
        x_auth_token = cache.get(token_key)
        if x_auth_token:
            return x_auth_token

    uri = f'{args.URL}/api/v2/aa/sessions'
    header = {'Content-Type': 'application/json'}
    data = {
        'user_name': args.USERNAME,
        'password': args.PASSWORD,
        'isEncrypt': False,
        'scope': args.SCOPE,
    }
    result = base.coe(
        url.fetch_json(
            uri,
            data=data,
            encoding='serialized-json',
            header=header,
            insecure=args.INSECURE,
            no_proxy=args.NO_PROXY,
            timeout=args.TIMEOUT,
        )
    )

    x_auth_token = result.get('data', {}).get('x_auth_token')

    expire = time.now() + args.CACHE_EXPIRE * 60
    cache.set(token_key, x_auth_token, expire)

    return x_auth_token


def get_data(endpoint, args, payload=None, method=None):
    """
    Fetch data from a Huawei OceanStor Pacific endpoint, re-authenticating on a stale session.

    This function performs an authenticated request to a Pacific `/api/v2/` endpoint. The first
    attempt reuses the cached session token. If the appliance rejects the request, the most common
    cause is a session the appliance no longer accepts (session reset or server-side timeout
    expiring before the local cache). Retrying with the same token can never recover from that, so
    the next attempt forces a fresh login and retries. Any remaining attempts cover short-lived
    transient errors.

    Reads on this API are a mix of `GET` (no body) and `POST` (a body selecting the nodes to
    query), so both the request body and the HTTP method can be supplied by the caller.

    ### Parameters
    - **endpoint** (`str`):
      The API endpoint after `/api/v2/` (for example `hwm/fan`).
    - **args** (object):
      An object containing `URL`, `INSECURE`, `NO_PROXY` and `TIMEOUT` (plus the credentials read
      by `get_creds()`).
    - **payload** (`dict`, optional):
      Request body. A truthy body turns the request into a `POST`; otherwise it is a `GET`.
    - **method** (`str`, optional):
      Force the HTTP method regardless of the body, for endpoints that require a bodyless `POST`.

    ### Returns
    - **dict**:
      The parsed JSON response from the API, plus an extra `counter` key showing how many attempts
      were made.

    ### Notes
    - Success is indicated by `result.code == 0` in the response envelope.
    - Makes at most three attempts, forcing a fresh login before the second one, and waits one
      second between attempts, so the total runtime stays within the monitoring server's check
      timeout.

    ### Example
    >>> get_data('hwm/fan', args, payload={'server_list': ['192.0.2.10']}))
    {
        'data': [...],
        'result': {'code': 0},
        'counter': 1
    }
    """
    uri = f'{args.URL}/api/v2/{endpoint}'

    max_attempts = 3
    counter = 0
    result = {}

    for attempt in range(1, max_attempts + 1):
        counter = attempt
        # On the second attempt, drop the cached session and log in again; a
        # rejected request is most likely an expired session that retrying
        # with the same token cannot fix. The third attempt then reuses that
        # fresh token to absorb a remaining transient error.
        x_auth_token = get_creds(args, force_relogin=attempt == 2)
        header = {
            'Content-Type': 'application/json',
            'X-Auth-Token': x_auth_token,
        }
        result = base.coe(
            url.fetch_json(
                uri,
                data=payload,
                encoding='serialized-json',
                header=header,
                insecure=args.INSECURE,
                method=method,
                no_proxy=args.NO_PROXY,
                timeout=args.TIMEOUT,
            )
        )
        res = result.get('result', {})
        code = res.get('code') if isinstance(res, dict) else res
        if code in (0, '0'):
            break
        if attempt < max_attempts:
            _time.sleep(1)

    result['counter'] = counter
    return result


def get_management_ips(args):
    """
    Query the cluster nodes and return their internal management IP addresses.

    The hardware endpoints (for example `hwm/fan` and `hwm/power`) are node-scoped and require a
    `server_list` of node management IPs in the request body. This helper enumerates the cluster
    nodes through `cluster/servers` and collects that list, so a caller can query hardware across
    the whole cluster without hard-coding node addresses.

    ### Parameters
    - **args** (object):
      The argument object read by `get_data()` / `get_creds()`.

    ### Returns
    - **list** of `str`:
      The `management_ip` of every cluster node. Aborts the plugin (UNKNOWN) if the node query
      itself fails.

    ### Example
    >>> get_management_ips(args)
    ['192.0.2.11', '192.0.2.12']
    """
    result = get_data('cluster/servers', args)
    if result.get('result', {}).get('code') != 0:
        base.cu('Failed to query cluster nodes for their management IP addresses.')
    return [
        node['management_ip']
        for node in result.get('data', [])
        if node.get('management_ip')
    ]


def get_oam_agent_status(s):
    """
    Convert a Huawei OceanStor Pacific OAM agent status code into a human-readable description.

    ### Parameters
    - **s** (`int` or `str`):
      The OAM agent status code. If a string is passed, it is converted to an integer.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_oam_agent_status(0)
    'healthy (0)'
    """
    s = int(s)
    mapping = {
        -1: '-- (-1)',
        0: 'healthy (0)',
        1: 'faulty (1)',
    }
    return mapping.get(s, 'Unknown')
