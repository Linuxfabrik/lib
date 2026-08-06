#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""This library collects functions for Huawei OceanStor Pacific storage systems,
which are accessed through their REST API (X-Auth-Token authentication, string-
and integer-valued status fields). Most of it lives below /api/v2/, an older
generation of endpoints below /dsware/service/ and /dfv/service/.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026080605'

import json
from time import sleep as _sleep

from . import base, cache, time, url
from .globals import STATE_CRIT, STATE_OK, STATE_WARN

# Own cache file, following `lib.redfish`. The shared default file is written by every
# plugin on the host, and `lib.cache` sweeps expired rows on the read path, so a session
# token that is read on every single check would sit in the middle of that lock traffic.
CACHE_FILENAME = 'linuxfabrik-monitoring-plugins-huawei-pacific.db'


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

    ### Notes
    - Scoped to the `/api/v2/` alarm and event endpoints. The older
      `/dsware/service/${version}/alarm/list` endpoint numbers its `ialarmLevel` field the
      other way round (`1` critical, `2` major, `3` minor, `4` warning, `5` other), where this
      mapping would render a critical alarm as `'Unknown'` and a major one as
      `'Information (2)'`.

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

    ### Notes
    - Scoped to the field named `alarmStatus`. The `status` field of `fms/alarms` shares the
      codes `1` and `2` but words them as uncleared and cleared, and never reports `4`.
    - Code `-1` is not in the enumeration table of the field. It is carried here because the
      response examples of `fms/events` and of the historical alarms and events endpoint show
      it in both REST Interface References: a plain event has nothing to recover from, so it
      reports no recovery state. Without the entry every row of an event listing would render
      as `'Unknown'`.

    ### Example
    >>> get_alarm_status(1)
    'Unrecovered (1)'
    """
    mapping = {
        -1: 'Not applicable (-1)',
        1: 'Unrecovered (1)',
        2: 'Cleared (2)',
        4: 'Recovered (4)',
    }
    return mapping.get(_as_code(st), 'Unknown')


def get_all_data(
    endpoint,
    args,
    page_size=100,
    max_pages=100,
    range_style='offset',
    **kwargs,
):
    """
    Fetch every object of a list endpoint, one page at a time.

    A list endpoint returns one page per request and expects the caller to page through the
    rest. Without paging an appliance simply stops being reported past the first page, which
    reads as a smaller but healthy inventory: exactly the failure a check must not have.

    ### Parameters
    - **endpoint** (`str`):
      The endpoint after the base path, optionally with a query string of its own (for
      example `common/alarms?filter=alarmStatus::1`). The `range` parameter is appended to
      it, so the caller must not supply one.
    - **args** (object):
      The same object `get_data()` reads.
    - **page_size** (`int`, optional):
      Objects to request per page.
    - **max_pages** (`int`, optional):
      Hard stop on the number of requests. It bounds the runtime of a check against an
      appliance with far more objects than anyone expected, and it keeps a firmware that
      ignores `range` from looping forever.
    - **range_style** (`str`, optional):
      Which of the API's two incompatible range syntaxes the endpoint speaks. `'offset'`
      sends `range={"offset":0,"limit":100}` and is the general form; `'bracket'` sends
      `range=[0-100]`, which is what the alarm and event endpoints expect. Neither is
      accepted by the other kind of endpoint, and the response does not say which one an
      endpoint wanted, so the caller states it from that endpoint's own description.
    - **kwargs**:
      Passed through to `get_data()`, for the endpoints that need a body, a forced method or
      an older base path.

    ### Returns
    - **tuple** (`dict`, `bool`):
      The envelope of the last request with its `data` replaced by every object collected,
      and a flag that is `True` when `max_pages` cut the walk short. On a failed request the
      envelope is handed back unchanged with the flag `False`, so the caller reports the
      appliance's own error text the same way it would after a single `get_data()`.

    ### Notes
    - A page shorter than `page_size` ends the walk. A page of exactly `page_size` objects is
      always followed by another request, which costs one empty request when the object count
      is an exact multiple of the page size.
    - The truncation flag is returned rather than turned into an abort here. Whether an
      incomplete inventory is worth an UNKNOWN or just a note in the output depends on the
      check, and this function has no way to tell.

    ### Example
    >>> result, truncated = get_all_data(
    ...     'common/alarms?filter=alarmStatus::1', args, range_style='bracket'
    ... )
    >>> len(result['data'])
    317
    """
    separator = '&' if '?' in endpoint else '?'
    collected = []
    result = {}
    truncated = False

    for page in range(max_pages):
        start = page * page_size
        if range_style == 'bracket':
            page_range = f'range=[{start}-{start + page_size}]'
        else:
            page_range = f'range={{"offset":{start},"limit":{page_size}}}'
        result = get_data(f'{endpoint}{separator}{page_range}', args, **kwargs)
        if get_result_code(result) not in (0, '0'):
            # Hand the failed envelope back whole. Reporting the objects collected so far
            # would present a partial inventory as a complete one.
            return result, False

        data = result.get('data') or []
        if not isinstance(data, list):
            # A single object rather than a list means this endpoint does not page at all.
            return result, False

        collected += data
        if len(data) < page_size:
            break
    else:
        truncated = True

    result['data'] = collected
    return result, truncated


def _from_string_code(value, mapping):
    """
    Look a string-keyed appliance code up, handing an undocumented one back unchanged.

    Used by the helpers whose codes are strings rather than numbers. A numeric code that is
    not in the vendor's table carries no information and renders as `'Unknown'`, but a string
    code is already readable, and the vendor's tables are demonstrably incomplete. Keeping it
    means a consumer still shows something an engineer can open a support case with.

    ### Parameters
    - **value** (`str`): The raw field value taken from the API response.
    - **mapping** (`dict`): Upper-case code to description.

    ### Returns
    - **str**:
      `'<description> (<code>)'` for a known code, the normalised code itself for an unknown
      one, and `'Unknown'` for a missing or empty value.
    """
    if value is None:
        return 'Unknown'
    code = str(value).strip().upper()
    if not code:
        return 'Unknown'
    if code not in mapping:
        return code
    return f'{mapping[code]} ({code})'


def get_base_board(bb):
    """
    Convert a Huawei OceanStor Pacific base board code into a human-readable description.

    The base board code names the product line a node's hardware belongs to, which the node's
    own `model` field does not always spell out.

    ### Parameters
    - **bb** (`str`):
      The base board code.
      A missing or empty value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      An unrecognised code is returned unchanged.

    ### Example
    >>> get_base_board('STL6SPCM')
    'Pacific (STL6SPCM)'
    """
    return _from_string_code(
        bb,
        {
            'STL6SPCM': 'Pacific',
            'STL6SPCN': 'Atlantic',
            'STL6SPCP': 'Arctic',
        },
    )


def get_component_status_state(st):
    """
    Convert a chassis component status into the state a check reports for it.

    The `hwm/fan` and `hwm/power` endpoints report a component's condition as a lower-case
    string rather than a numeric code.

    ### Parameters
    - **st** (`str`):
      The `status` field of a fan or power supply.

    ### Returns
    - **int**:
      `STATE_OK` for `'normal'`, `STATE_CRIT` for `'fault'`, `STATE_WARN` for anything else,
      including a value the vendor's table does not list and a missing one.

    ### Notes
    - The comparison is case-insensitive and ignores surrounding whitespace, so a firmware that
      capitalises the value differently does not silently turn a healthy component into a
      warning.
    - A value that is neither of the two documented ones warns rather than passing as OK. The
      vendor's tables for these endpoints are demonstrably incomplete, and a component this
      check cannot place is worth looking at.

    ### Example
    >>> get_component_status_state('normal') == STATE_OK
    True

    >>> get_component_status_state('fault') == STATE_CRIT
    True
    """
    if st is None:
        return STATE_WARN
    code = str(st).strip().lower()
    if code == 'normal':
        return STATE_OK
    if code == 'fault':
        return STATE_CRIT
    return STATE_WARN


# Password states that make a login pointless to continue from. Only an expired password
# qualifies: the account is out of its validity period, so the session it hands out cannot
# be relied on for anything.
#
# Kept deliberately narrow. Neither REST Interface Reference states which password states
# restrict a session, so every entry here is an assumption about the appliance rather than
# a documented rule. States 4 (initial password) and 6 (must be changed at the next login)
# used to abort as well, which took every check on a freshly deployed appliance to UNKNOWN
# before anyone had logged in to set a password. They now run: if the appliance really does
# refuse their requests, `get_data()` reports its error text, which names the cause better
# than a guess made here.
_UNUSABLE_PASSWORD_STATES = frozenset({3})


def _logout(args, x_auth_token):
    """
    End a session on the appliance, ignoring whatever comes back.

    Called on a session nothing will read back: the one a forced re-login replaces in
    `get_creds()`, and every session at all in `get_data()` when caching is switched off.
    Without it such a session stays open until the appliance's own timeout expires it, which
    is configurable between 30 and 100 minutes. A check that keeps failing would leave orphans
    behind run after run, so the count of open sessions grows for as long as the fault lasts.

    ### Parameters
    - **args** (object): An object containing `URL`, `INSECURE`, `NO_PROXY` and `TIMEOUT`.
    - **x_auth_token** (`str`): The session token to end.

    ### Returns
    - **None**

    ### Notes
    - Every outcome is discarded, errors included. This is housekeeping on the way to a fresh
      login, and the session most likely to be logged out here is one the appliance has
      already dropped, which is exactly the case that answers with an error. Letting that
      abort the re-login would break the recovery path this call is part of. `url.fetch()`
      reports failures through its return value rather than by raising, so no exception can
      escape either.
    - `is_timeout` is left off the request. It only tells the appliance why the session ended,
      and this is a deliberate logout, not one triggered by a timeout.
    """
    url.fetch(
        f'{args.URL}/api/v2/aa/sessions',
        # No `Content-Type`: this is a bare verb with no body, and announcing a JSON one
        # that is not there is what `get_data()` avoids for the same reason.
        header={'X-Auth-Token': x_auth_token},
        insecure=args.INSECURE,
        method='DELETE',
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )


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
    - The token is stored in the cache key `huaweipacific-{URL}-{USERNAME}-xauthtoken`, in the
      module's own cache file. The user name is part of the key because a session carries that
      user's role: without it a check running as a different account would silently reuse the
      first account's session and query the appliance with the wrong privileges.
    - A `CACHE_EXPIRE` of `0` turns caching off, rather than writing an entry that expires a
      moment later. Every call then logs in, which is what an operator asks for by setting it.
    - The password is sent as plaintext over HTTPS (`isEncrypt` is `False`); the token is returned
      in the response body, not in a response header.
    - A rejected login aborts the caller (UNKNOWN) instead of returning an empty token.
      The appliance answers a wrong password, an expired password or a locked account with
      HTTP 200 and a non-zero `result.code`, so without this check the empty token would travel
      into the next request header and surface as an unrelated type error. Failing here also
      keeps a wrong password from being replayed, which would drive the account towards the
      appliance's lockout threshold.
    - An accepted login whose `password_status` marks the password as expired aborts the
      caller: the account is past its validity period, so nothing useful follows. Which
      password states actually restrict a session is not documented, so no other state is
      treated as fatal; see `_UNUSABLE_PASSWORD_STATES`.
    - The login response also carries an `x_csrf_token`, which is not sent. The mandatory
      request-header table lists `X-Auth-Token` alone, and every `/api/v2/` example in the
      vendor's documentation authenticates with that header only. The prose does mention the
      CSRF token, but without saying which endpoints require it, so a firmware that starts
      demanding it would have to pick the token up from the login response here.
    - No logout is sent at the end of a run. Because the token is cached and reused across
      runs, that would force a login on every single run and multiply the login rate the
      appliance sees. The session that `force_relogin` replaces is a different matter and is
      handed back through `_logout()`, so it does not stay open until its own timeout
      expires it.

    ### Example
    >>> x_auth_token = get_creds(args)
    """
    token_key = f'huaweipacific-{args.URL}-{args.USERNAME}-xauthtoken'
    caching = args.CACHE_EXPIRE > 0

    if caching:
        x_auth_token = cache.get(token_key, filename=CACHE_FILENAME)
        if x_auth_token and not force_relogin:
            return x_auth_token
        if x_auth_token:
            # About to replace this session, so hand it back to the appliance instead of
            # leaving it open until its timeout expires.
            _logout(args, x_auth_token)

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

    if not isinstance(result, dict):
        base.cu(
            f'Login at {args.URL} returned {type(result).__name__} instead of the documented '
            'response object.'
        )

    session_data = result.get('data') or {}
    x_auth_token = (
        session_data.get('x_auth_token') if isinstance(session_data, dict) else None
    )

    if not x_auth_token:
        res = result.get('result') or {}
        reason = res.get('description') or 'no session token returned'
        code = res.get('code', 'n/a')
        base.cu(f'Login at {args.URL} failed: {reason} (code {code}).')

    password_status = _as_code(session_data.get('password_status'))
    if password_status in _UNUSABLE_PASSWORD_STATES:
        base.cu(
            f'Login at {args.URL} succeeded, but the account is unusable: '
            f'{get_password_status(password_status)}.'
        )

    if caching:
        expire = time.now() + args.CACHE_EXPIRE * 60
        cache.set(token_key, x_auth_token, expire, filename=CACHE_FILENAME)

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


def get_data(endpoint, args, payload=None, method=None, base_path='api/v2'):
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
      The API endpoint after `/api/v2/` (for example `hwm/fan`), including the query string if
      the endpoint takes one. The string is appended to the request URL verbatim, so the caller
      is responsible for percent-encoding it; never build it from data the appliance itself
      returned. Note that the API knows two incompatible query syntaxes: the general one is
      `?range={"offset":0,"limit":100}`, while a part of the endpoints expects
      `?range=[0-100]&filter=alarmStatus::1` instead. The alarm and event endpoints are the
      ones most likely to be queried that way, but the second syntax is not limited to them,
      so check the endpoint's own description rather than assuming the general form.
    - **args** (object):
      An object containing `URL`, `INSECURE`, `NO_PROXY` and `TIMEOUT` (plus the credentials read
      by `get_creds()`).
    - **payload** (`dict`, optional):
      Request body. A truthy body turns the request into a `POST`; otherwise it is a `GET`.
    - **method** (`str`, optional):
      Force the HTTP method regardless of the body, for endpoints that require a bodyless `POST`
      or a `GET` that carries one.
    - **base_path** (`str`, optional):
      The path between the base URL and the endpoint, without surrounding slashes. Defaults to
      the `api/v2` the current API is built on. The appliance also serves an older generation of
      endpoints below `dsware/service` and `dfv/service`, and some information is only available
      there; a caller reaching for one of those passes its base path here. This is a developer
      constant, not something to build from data the appliance or a user supplied.

    ### Returns
    - **dict**:
      The parsed JSON response from the API.

    ### Notes
    - Success is indicated by a status code of `0`. The `api/v2` endpoints report it as
      `result.code`, the older ones as a bare `result`; `get_result_code()` reads both.
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
    - A request without the `X-Auth-Token` header is documented to answer with code `-401`.
      Whether an appliance reports a session it no longer accepts the same way is not
      documented, so the fresh login is not tied to that code: it is triggered on any non-zero
      error, which covers however a given firmware chooses to report it.
    - With caching switched off (`CACHE_EXPIRE` of `0`) every attempt logs in again and the
      session it gets is good for that one request only. Each is logged out right after it,
      because nothing will ever read it back from the cache. In this mode a call can therefore
      reach three logins and three logouts, which is the price of asking for no caching.

    ### Example
    >>> get_data('hwm/fan', args, payload={'server_list': ['192.0.2.10']})
    {
        'data': [...],
        'result': {'code': 0}
    }
    """
    uri = f'{args.URL}/{base_path}/{endpoint}'

    max_attempts = 3
    result = {}

    for attempt in range(1, max_attempts + 1):
        # On the second attempt, drop the cached session and log in again; a
        # rejected request is most likely an expired session that retrying
        # with the same token cannot fix. The third attempt then reuses that
        # fresh token to absorb a remaining transient error.
        x_auth_token = get_creds(args, force_relogin=attempt == 2)
        header = {'X-Auth-Token': x_auth_token}
        if payload or not method:
            # Announce a JSON body when the request carries one, and on a request whose
            # method is left to `lib.url` - that is the plain GET, where the vendor's own
            # examples send the header too. A caller that forces the method without a body
            # wants a bare verb, so the header is left off there rather than announcing a
            # body that is not there.
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
        if args.CACHE_EXPIRE <= 0:
            # Caching is off, so this session was created for this one request and nothing
            # will ever reuse it. Hand it back instead of leaving it open until its own
            # timeout expires it.
            _logout(args, x_auth_token)
        if get_result_code(result) in (0, '0'):
            break
        if attempt < max_attempts:
            _sleep(1)

    return result


def get_disk_role(r):
    """
    Convert a Huawei OceanStor Pacific media role into a human-readable description.

    ### Parameters
    - **r** (`str`):
      The media role.
      A missing or empty value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      An unrecognised role is returned unchanged.

    ### Example
    >>> get_disk_role('main_storage')
    'main storage (MAIN_STORAGE)'
    """
    return _from_string_code(
        r,
        {
            'MAIN_STORAGE': 'main storage',
            'OSD_CACHE': 'cache',
        },
    )


def get_disk_status(st):
    """
    Convert a Huawei OceanStor Pacific disk status code into a human-readable description.

    ### Parameters
    - **st** (`int` or `str`):
      The disk status code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_disk_status(0)
    'healthy (0)'
    """
    mapping = {
        0: 'healthy (0)',
        1: 'faulty (1)',
        2: 'sub-healthy (2)',
        101: 'removed from the storage pool (101)',
    }
    return mapping.get(_as_code(st), 'Unknown')


def get_disk_status_state(st):
    """
    Convert a Huawei OceanStor Pacific disk status code into the state a check reports for it.

    ### Parameters
    - **st** (`int` or `str`):
      The disk status code.

    ### Returns
    - **int**:
      `STATE_OK` for a healthy disk, `STATE_CRIT` for a faulty one, `STATE_WARN` for every
      other code, including one the enumeration does not know and a missing value.

    ### Notes
    - A disk removed from the storage pool (`101`) warns rather than going critical. The pool
      has already rebuilt around it, so the redundancy loss is over; what is left is a slot an
      administrator has to attend to.

    ### Example
    >>> get_disk_status_state(0) == STATE_OK
    True

    >>> get_disk_status_state('1') == STATE_CRIT
    True
    """
    code = _as_code(st)
    if code == 0:
        return STATE_OK
    if code == 1:
        return STATE_CRIT
    return STATE_WARN


def get_disk_type(t):
    """
    Convert a Huawei OceanStor Pacific media type into a human-readable description.

    ### Parameters
    - **t** (`str`):
      The media type.
      A missing or empty value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      An unrecognised media type is returned unchanged.

    ### Example
    >>> get_disk_type('ssd_card')
    'SSD card or NVMe SSD (SSD_CARD)'
    """
    return _from_string_code(
        t,
        {
            'SAS_DISK': 'SAS disk',
            'SATA_DISK': 'SATA disk',
            # The vendor's table folds SSD cards and NVMe SSDs into one code.
            'SSD_CARD': 'SSD card or NVMe SSD',
            'SSD_DISK': 'SSD',
        },
    )


def _assert_all_nodes_listed(listed, args):
    """
    Abort unless `cluster/servers` listed every node the cluster says it has.

    Used by `get_management_ips()`. Split out to keep the node loop readable.

    ### Parameters
    - **listed** (`int`): Number of nodes `cluster/servers` returned.
    - **args** (object): The argument object read by `get_data()`.

    ### Notes
    - A failing count query is not fatal. It is a cross-check, not the data itself, and a
      firmware that does not offer the endpoint must not take the hardware check down with it.
    """
    result = get_data('cluster/servers/count', args)
    if result.get('result', {}).get('code') not in (0, '0'):
        return

    data = result.get('data')
    if not isinstance(data, dict):
        return

    total = _as_code(data.get('count'))
    if total is not None and total > listed:
        base.cu(
            f'The cluster reports {total} nodes, but only {listed} were listed. The hardware '
            'of the remaining ones cannot be queried, so the check would silently cover part '
            'of the cluster only.'
        )


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
    - `in_cluster` has three documented values, not two: `True` (added), `False` (not added)
      and `null` (about to be added). Only a node that reports `True` is queried. A node still
      being added holds no cluster hardware yet, and treating its missing management IP as a
      fault would take the whole check to UNKNOWN while the cluster is perfectly healthy.
      A node that does not report the field at all is kept, so a firmware that omits it does
      not narrow the result.
    - Aborts the plugin (UNKNOWN) if the node query fails, if a node that is in the cluster has
      no management IP address, or if no node has one at all. Returning the remaining addresses
      instead would let a hardware check cover part of the cluster and still report OK, which
      hides a failed component on the nodes that were dropped.
    - The node list is compared against `cluster/servers/count` for the same reason. The
      endpoint documents no paging parameters, but the API-wide default caps a list response
      at 100 entries, and the documentation does not say which endpoints that applies to. On a
      cluster above that size a silently truncated list would leave nodes unmonitored while
      the check still reports OK, so a mismatch aborts instead.

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

    nodes = result.get('data') or []
    _assert_all_nodes_listed(len(nodes), args)

    ips = []
    without_ip = []
    for node in nodes:
        # `cluster/servers` documents an array of node objects, but the sibling endpoint for
        # a single node answers with a bare object. A firmware that does the same here would
        # otherwise put the field lookups below on a string and end the check in a traceback
        # instead of an UNKNOWN.
        if not isinstance(node, dict):
            continue
        # Anything but True means the node is not (yet) part of the cluster. Absent means
        # a firmware that does not report the field, which must not narrow the result.
        if 'in_cluster' in node and node['in_cluster'] is not True:
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


def get_node_running_status_state(rs):
    """
    Convert a cluster node's running status into the state a check reports for it.

    The `cluster/servers` endpoint reports a node's condition as a lower-case string rather
    than a numeric code.

    ### Parameters
    - **rs** (`str`):
      The `running_status` field of a node.

    ### Returns
    - **int**:
      `STATE_OK` for `'online'`, `STATE_CRIT` for `'offline'`, `STATE_WARN` for anything else,
      including a value the vendor's table does not list and a missing one.

    ### Notes
    - A node that has left the cluster takes its share of the storage with it, so an offline
      node is a failure rather than a degradation.
    - The comparison is case-insensitive and ignores surrounding whitespace.

    ### Example
    >>> get_node_running_status_state('online') == STATE_OK
    True

    >>> get_node_running_status_state('offline') == STATE_CRIT
    True
    """
    if rs is None:
        return STATE_WARN
    code = str(rs).strip().lower()
    if code == 'online':
        return STATE_OK
    if code == 'offline':
        return STATE_CRIT
    return STATE_WARN


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
        # 8.2.0 prints this state as a bare '--'; V800R001C20 spells it out as
        # 'not monitored', which is the wording a plugin's output can be read from.
        -1: 'not monitored (-1)',
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


def get_pool_status(st):
    """
    Convert a Huawei OceanStor Pacific pool status code into a human-readable description.

    ### Parameters
    - **st** (`int` or `str`):
      The pool status code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Storage pools and disk pools share this enumeration; both REST Interface References
      list the same codes for their respective `poolStatus` field.
    - Code `6` is not in the vendor's table and is deliberately absent here.

    ### Example
    >>> get_pool_status(0)
    'normal (0)'
    """
    mapping = {
        0: 'normal (0)',
        1: 'faulty (1)',
        2: 'write-protected (2)',
        3: 'stopped (3)',
        4: 'faulty and write-protected (4)',
        5: 'migrating data (5)',
        7: 'degraded (7)',
        8: 'rebuilding data (8)',
    }
    return mapping.get(_as_code(st), 'Unknown')


def get_pool_status_state(st):
    """
    Convert a Huawei OceanStor Pacific pool status code into the state a check reports.

    ### Parameters
    - **st** (`int` or `str`):
      The pool status code.

    ### Returns
    - **int**:
      `STATE_OK` for a normal pool, `STATE_CRIT` for one that has failed or stopped serving,
      `STATE_WARN` for every other code, including one the enumeration does not know and a
      missing value.

    ### Notes
    - Faulty (`1`), stopped (`3`) and faulty and write-protected (`4`) are the codes that
      report a pool which is no longer doing its job.
    - Write-protected (`2`), migrating (`5`), degraded (`7`) and rebuilding (`8`) warn: the
      pool still serves reads, and the last three are states it works itself out of.

    ### Example
    >>> get_pool_status_state(0) == STATE_OK
    True

    >>> get_pool_status_state('1') == STATE_CRIT
    True
    """
    code = _as_code(st)
    if code == 0:
        return STATE_OK
    if code in (1, 3, 4):
        return STATE_CRIT
    return STATE_WARN


def get_result_code(result):
    """
    Read the status code out of a Huawei OceanStor Pacific response, whichever envelope it uses.

    The API answers in two shapes. The `/api/v2/` endpoints wrap the code in an object
    (`{'result': {'code': 0, 'description': ...}}`), while the older `/dsware/service/` and
    `/dfv/service/` endpoints report it as a bare integer (`{'result': 0, 'nodeInfo': [...]}`).
    A consumer that has to work with both should not have to know which one it is talking to.

    ### Parameters
    - **result** (`dict`): A response as returned by `get_data()`.

    ### Returns
    - **int**, **str** or **None**:
      The status code as the appliance reported it (`0` means success in both shapes), or
      `None` if the response carries no `result` at all.

    ### Example
    >>> get_result_code({'result': {'code': 0}, 'data': []})
    0
    >>> get_result_code({'result': 0, 'nodeInfo': []})
    0
    """
    res = result.get('result') if isinstance(result, dict) else None
    return res.get('code') if isinstance(res, dict) else res
