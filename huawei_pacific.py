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
__version__ = '2026080502'

import json
from time import sleep as _sleep

from . import base, cache, time, url


def _as_code(value):
    """
    Normalise an API status code into an `int`, or `None` if it is unusable.

    The appliance reports some of its codes as strings, and a field may be missing entirely, in
    which case the caller hands in `None` (`node.get('oam_agent_status')`). A missing or
    malformed code has to render as `'Unknown'`; aborting the calling process with a
    `TypeError` or `ValueError` would turn a single unexpected field into a crashed check.

    ### Parameters
    - **value** (`any`): The raw field value taken from the API response.

    ### Returns
    - **int** or **None**: The code as an integer, or `None` if it cannot be converted.

    ### Example
    >>> _as_code('6')
    6
    >>> _as_code(None) is None
    True
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_alarm_severity(sev):
    """
    Convert a Huawei OceanStor Pacific alarm severity code into a human-readable description.

    ### Parameters
    - **sev** (`int` or `str`):
      The alarm severity code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_alarm_severity(6)
    'Critical (6)'
    """
    mapping = {
        2: 'Information (2)',
        3: 'Warning (3)',
        4: 'Minor (4)',
        5: 'Major (5)',
        6: 'Critical (6)',
    }
    return mapping.get(_as_code(sev), 'Unknown')


def get_alarm_status(st):
    """
    Convert a Huawei OceanStor Pacific alarm status code into a human-readable description.

    ### Parameters
    - **st** (`int` or `str`):
      The alarm status code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_alarm_status(1)
    'Unrecovered (1)'
    """
    mapping = {
        1: 'Unrecovered (1)',
        2: 'Cleared (2)',
        4: 'Recovered (4)',
    }
    return mapping.get(_as_code(st), 'Unknown')


# Password states in which a login succeeds but the resulting session cannot query
# anything: the appliance then only accepts the password endpoints. The states left out
# are the ones a session survives: normal, and about to expire.
_UNUSABLE_PASSWORD_STATES = frozenset({3, 4, 6})


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
    - The token is stored in the cache key `huaweipacific-{URL}-{USERNAME}-xauthtoken`.
      The user name is part of the key because a session carries that user's role: without it
      a check running as a different account would silently reuse the first account's session
      and query the appliance with the wrong privileges.
    - The password is sent as plaintext over HTTPS (`isEncrypt` is `False`); the token is returned
      in the response body, not in a response header.
    - A rejected login aborts the caller (UNKNOWN) instead of returning an empty token.
      The appliance answers a wrong password, an expired password or a locked account with
      HTTP 200 and a non-zero `result.code`, so without this check the empty token would travel
      into the next request header and surface as an unrelated type error. Failing here also
      keeps a wrong password from being replayed, which would drive the account towards the
      appliance's lockout threshold.
    - An accepted login whose `password_status` marks the password as expired, initial or due
      for a change also aborts the caller. Such a session is only good for changing the
      password, so every later request would fail with an unrelated API error instead of naming
      the actual cause.
    - The login response also carries an `x_csrf_token`. The `/api/v2/` endpoints used here
      authenticate on `X-Auth-Token` alone, so it is not sent. Endpoints below the
      `/deviceManager/rest/{system_esn}/` prefix additionally require the CSRF token as a
      request header and would have to pick it up from the login response.
    - The session is deliberately never deleted. Because the token is cached and reused across
      runs, a logout at the end of a run would force a login on every single run and multiply
      the login rate the appliance sees. The one session that `force_relogin` replaces lingers
      until the appliance's own session timeout expires it.

    ### Example
    >>> x_auth_token = get_creds(args)
    """
    token_key = f'huaweipacific-{args.URL}-{args.USERNAME}-xauthtoken'

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

    session_data = result.get('data', {})
    x_auth_token = session_data.get('x_auth_token')

    if not x_auth_token:
        res = result.get('result', {})
        reason = res.get('description') or 'no session token returned'
        code = res.get('code', 'n/a')
        base.cu(f'Login at {args.URL} failed: {reason} (code {code}).')

    password_status = _as_code(session_data.get('password_status'))
    if password_status in _UNUSABLE_PASSWORD_STATES:
        base.cu(
            f'Login at {args.URL} succeeded, but the account cannot query anything: '
            f'{get_password_status(password_status)}.'
        )

    expire = time.now() + args.CACHE_EXPIRE * 60
    cache.set(token_key, x_auth_token, expire)

    return x_auth_token


def _as_envelope(success, response):
    """
    Normalise whatever `url.fetch_json()` returned into the documented response envelope.

    `get_data()` promises its caller a `{'result': {'code': ...}, 'data': ...}` document. Three
    things can arrive instead: a transport failure (the message string), an HTTP error status
    (the unparsed response body, because `url.fetch_json()` only decodes JSON on success), and
    an appliance answering with something other than a JSON object. Wrapping all of them in the
    envelope keeps a single bad response from turning into a type error inside the retry loop,
    and lets the caller print the appliance's own error text.

    ### Parameters
    - **success** (`bool`): The first element of the `url.fetch_json()` result tuple.
    - **response** (`any`): The second element of that tuple.

    ### Returns
    - **dict**: The response envelope, either as the appliance sent it or synthesised.

    ### Example
    >>> _as_envelope(True, {'result': {'code': 0}, 'data': []})
    {'result': {'code': 0}, 'data': []}
    >>> _as_envelope(False, 'URL error "timed out"')['result']['code']
    'n/a'
    """
    if success and isinstance(response, dict):
        return response

    # An HTTP error status still carries the appliance's own JSON body, which names the
    # actual cause (`-401` for a session it no longer accepts, for example). Only the
    # status made `url.fetch_json()` skip the decode, so decode it here.
    if not success and isinstance(response, str):
        try:
            parsed = json.loads(response)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get('result'), dict):
            return parsed

    return {
        'result': {
            'code': 'n/a',
            # Bounded: the body of an error status can be a full HTML page, and this
            # ends up in the check's plugin output.
            'description': f'{response}'[:200],
        },
    }


def get_data(endpoint, args, payload=None, method=None, params=''):
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
    - **params** (`str`, optional):
      Additional URL parameters (starting with `?`, if any). Default is empty. The string is
      appended to the request URL verbatim, so the caller is responsible for percent-encoding
      it; never build it from data the appliance itself returned. Appending the query string to
      `endpoint` instead has the same effect and the same caveat.

    ### Returns
    - **dict**:
      The parsed JSON response from the API, plus an extra `counter` key showing how many attempts
      were made.

    ### Notes
    - Success is indicated by `result.code == 0` in the response envelope.
    - Makes at most three attempts, forcing a fresh login before the second one, and waits one
      second between attempts. The retry count is kept low on purpose, so one call stays within
      the monitoring server's check timeout: the worst case is three requests plus one login,
      plus two seconds of waiting. This budget is per call. A caller that chains several calls,
      for example `get_management_ips()` followed by a hardware query, has to size its own
      timeout for the sum.
    - A rejected request is retried instead of aborting the caller: a transport failure, an HTTP
      error status and a response that is not the documented `{'result': {'code': ...}}` envelope
      all count as a failed attempt and are handed back in that envelope. The caller therefore
      always receives the documented return value and can report the appliance's own error text.
    - The appliance answers a missing or no longer accepted `X-Auth-Token` with code `-401`. The
      fresh login is not tied to that code: it is triggered on any non-zero error, so a firmware
      that reports an expired session differently still recovers.

    ### Example
    >>> get_data('hwm/fan', args, payload={'server_list': ['192.0.2.10']})
    {
        'data': [...],
        'result': {'code': 0},
        'counter': 1
    }
    """
    uri = f'{args.URL}/api/v2/{endpoint}{params}'

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
        header = {'X-Auth-Token': x_auth_token}
        if payload or not method:
            # Announce a JSON body only when the request can carry one. A caller that
            # forces the method without a body wants a bare verb, and the content type
            # would announce a body that is not there - which is the very case
            # `lib.url.fetch()` offers the forced method for. On a plain GET the header
            # is kept, because the vendor's own examples send it.
            header['Content-Type'] = 'application/json'
        # `response_on_error` keeps the appliance's own error body readable when it
        # answers with a 4xx/5xx status. Without it the body is dropped in favour of
        # the status line, and the request would abort the check on the spot instead
        # of becoming a failed attempt the forced re-login can still recover from.
        result = _as_envelope(
            *url.fetch_json(
                uri,
                data=payload,
                encoding='serialized-json',
                header=header,
                insecure=args.INSECURE,
                method=method,
                no_proxy=args.NO_PROXY,
                response_on_error=True,
                timeout=args.TIMEOUT,
            )
        )
        res = result.get('result')
        code = res.get('code') if isinstance(res, dict) else res
        if code in (0, '0'):
            break
        if attempt < max_attempts:
            _sleep(1)

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
      The `management_ip` of every cluster node.

    ### Notes
    - Nodes that report `in_cluster` as `False` are left out: they hold no cluster hardware to
      query. A node that does not report the field at all is kept, so a firmware that omits it
      does not narrow the result.
    - Aborts the plugin (UNKNOWN) if the node query fails, if a node that is in the cluster has
      no management IP address, or if no node has one at all. Returning the remaining addresses
      instead would let a hardware check cover part of the cluster and still report OK, which
      hides a failed component on the nodes that were dropped.

    ### Example
    >>> get_management_ips(args)
    ['192.0.2.11', '192.0.2.12']
    """
    result = get_data('cluster/servers', args)
    res = result.get('result', {})
    if res.get('code') not in (0, '0'):
        base.cu(
            'Failed to query cluster nodes for their management IP addresses: '
            f'{res.get("description") or "no description"} (code {res.get("code", "n/a")}).'
        )

    ips = []
    without_ip = []
    for node in result.get('data', []):
        if node.get('in_cluster') is False:
            continue
        if node.get('management_ip'):
            ips.append(node['management_ip'])
        else:
            without_ip.append(str(node.get('name') or node.get('id') or '?'))

    if without_ip:
        base.cu(
            'These cluster nodes report no management IP address, so their hardware cannot '
            f'be queried: {", ".join(without_ip)}.'
        )
    if not ips:
        base.cu('The cluster reported no node with a management IP address.')

    return ips


def get_oam_agent_status(s):
    """
    Convert a Huawei OceanStor Pacific OAM agent status code into a human-readable description.

    ### Parameters
    - **s** (`int` or `str`):
      The OAM agent status code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_oam_agent_status(0)
    'healthy (0)'
    """
    mapping = {
        -1: '-- (-1)',
        0: 'healthy (0)',
        1: 'faulty (1)',
    }
    return mapping.get(_as_code(s), 'Unknown')


def get_password_status(st):
    """
    Convert a Huawei OceanStor Pacific password status code into a human-readable description.

    The appliance reports this as `password_status` in the login response. It describes the
    state of the login account's password, not the outcome of the login itself: a login can
    succeed while the account is still unusable for anything but changing the password.

    ### Parameters
    - **st** (`int` or `str`):
      The password status code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_password_status(3)
    'password expired (3)'
    """
    mapping = {
        1: 'normal (1)',
        3: 'password expired (3)',
        4: 'initial password (4)',
        5: 'password about to expire (5)',
        6: 'password must be changed at the next login (6)',
    }
    return mapping.get(_as_code(st), 'Unknown')
