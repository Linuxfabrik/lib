#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""This library collects functions for Huawei OceanStor Dorado storage systems,
which are accessed through the DeviceManager REST API (numeric status codes,
iBaseToken authentication).

The code-to-text mappings are the union of the OceanStor Dorado 6.1.0 and
V700R001C10 REST Interface References. A single appliance only ever reports the
subset its own firmware knows, so the union lets every documented code render a
readable label instead of `'Unknown'`, regardless of which firmware answers.
"""

# The module is long because it transcribes the vendor's enumeration tables, not
# because of branching; splitting it would only scatter that data.
# pylint: disable=C0302

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026080703'

import json
from time import sleep as _sleep

from . import base, cache, time, url
from .globals import STATE_CRIT, STATE_OK, STATE_WARN

# Own cache file, following `lib.redfish`. The shared default file is written by every
# plugin on the host, and `lib.cache` sweeps expired rows on the read path, so a session
# token that is read on every single check would sit in the middle of that lock traffic.
CACHE_FILENAME = 'linuxfabrik-monitoring-plugins-huawei-dorado.db'

# Bytes per sector, for the capacities the API counts in sectors. The appliance reports its
# own value as `SECTORSIZE` in the `system/` response, and that is what a consumer should
# hand to `sectors2bytes()` where it has it. This default covers the consumers that do not
# query `system/` just to learn it, and it is what every documented response example shows.
# It is not the per-LUN `SECTORSIZE`, which is the block size a LUN exposes to the host and
# is a different number on the same appliance.
DEFAULT_SECTOR_SIZE = 512

# The device ID the vendor's own login example sends. The appliance accepts any string here
# and answers with the real one, so a consumer that does not know its appliance's ID logs in
# with this placeholder and reads `data.deviceid` out of the response.
DEVICE_ID_PLACEHOLDER = 'xxxxx'


def assert_ok(result, what):
    """
    Abort the calling process (UNKNOWN) unless the appliance reported success.

    Every consumer has to check the response envelope before it reads anything out of it,
    and the check is easy to get subtly wrong: the appliance reports success as the number
    `0` on some endpoints and as the string `'0'` on others, and a response that carries no
    `error` object at all turns a naive `result['error']['code']` into an `AttributeError`
    instead of a clean UNKNOWN.

    ### Parameters
    - **result** (`dict`): A response envelope as `get_data()` returns it.
    - **what** (`str`):
      What was being queried, as a noun phrase for the message ("the fans", "the storage
      pools"). It is the only part of the output that tells an operator which of a check's
      several requests failed.

    ### Returns
    - **None**: Returns on success, and does not return otherwise.

    ### Notes
    - An empty response is an error as well. `get_data()` always answers with an envelope,
      so nothing at all means the consumer never reached the appliance.
    - The appliance's own description and suggestion are printed where it sends them. They
      name the cause far better than anything a consumer could infer from the code.

    ### Example
    >>> assert_ok({'error': {'code': 0}, 'data': []}, 'the fans')
    """
    if not result:
        base.cu('Got no response from the appliance.')

    code = get_error_code(result)
    if code in (0, '0'):
        return

    error = result.get('error') if isinstance(result, dict) else None
    if not isinstance(error, dict):
        error = {}
    description = error.get('description') or 'no description'
    suggestion = error.get('suggestion') or ''
    base.cu(f'Failed to query {what} (code {code}): {description} {suggestion}'.strip())


def as_code(value):
    """
    Normalise an API status code into an `int`, or `None` if it is unusable.

    The appliance reports its codes as strings, and a field may be missing entirely, in which
    case the caller hands in `None` (`data.get('HEALTHSTATUS')`). A missing or malformed code
    has to render as `'Unknown'`; aborting the calling process with a `TypeError` or
    `ValueError` would turn a single unexpected field into a crashed check.

    ### Parameters
    - **value** (`any`): The raw field value taken from the API response.

    ### Returns
    - **int** or **None**: The code as an integer, or `None` if it cannot be converted.

    ### Example
    >>> as_code('27')
    27
    >>> as_code(None) is None
    True
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_temperature(value):
    """
    Normalise a reported temperature into an `int`, or `None` if it is not a reading.

    A component without a temperature sensor still reports the field. Which placeholder it
    uses depends on the object: a controller answers with `-1`, a power module and a disk
    with `0`, and a firmware may leave the field out altogether. None of the three is a
    measurement, and all three have to be kept out of the performance data and away from
    the thresholds.

    ### Parameters
    - **value** (`any`): The raw field value taken from the API response.

    ### Returns
    - **int** or **None**: The temperature in degrees Celsius, or `None` when the object
      reported no reading.

    ### Notes
    - The placeholders are what the vendor's own response examples show: the controller
      example of the V700R001C10 REST Interface Reference carries `"TEMPERATURE": "-1"`,
      the power module example `"TEMPERATURE": "0"`.
    - `-1` in particular must not reach a threshold. A Nagios range such as `55` means
      `0:55`, so a value below zero is outside it, and a controller with no sensor would
      report CRITICAL as soon as an operator sets a temperature threshold at all.
    - Zero is discarded rather than kept as a reading. An appliance sitting at or below
      0 °C is outside every documented operating range, so the value is a placeholder
      rather than a measurement worth graphing.

    ### Example
    >>> as_temperature('42')
    42

    >>> as_temperature('-1') is None
    True

    >>> as_temperature('0') is None
    True
    """
    code = as_code(value)
    if code is None or code <= 0:
        return None
    return code


def field(data, *names, default=None):
    """
    Read a field whose name the appliance spells differently depending on the firmware.

    Most objects report their fields in upper case (`HEALTHSTATUS`), a few in camelCase
    (`healthStatus`), and the `sfp` object is documented both ways on the same page of the
    REST Interface Reference: its parameter table lists `rxPowerReal` and `sfpModeType`
    while its response example shows `RXPOWER` and `SFPMODETYPE`. A consumer that picks one
    spelling reads an empty field on half the fleet.

    ### Parameters
    - **data** (`dict`): One object as the API returned it.
    - **names** (`str`): The field names to try, in order of preference.
    - **default** (any, optional): What to return when none of them is present.

    ### Returns
    - The first value found under any of `names`, matched case-insensitively, or `default`.

    ### Notes
    - The exact spellings are tried first and in the order given, so a firmware that reports
      two of the names (an old field and its replacement) still yields the preferred one.
      Only then does the case-insensitive pass run.
    - A key that is present but empty counts as found. The appliance uses `'--'` and `''`
      for "no value", and turning those into the default would hide the difference between
      a field a firmware does not have and one it has nothing to say about.

    ### Example
    >>> field({'RXPOWER': '[1234]'}, 'rxPowerReal', 'RXPOWER')
    '[1234]'

    >>> field({'healthStatus': '1'}, 'HEALTHSTATUS')
    '1'

    >>> field({}, 'MODEL', default='--')
    '--'
    """
    for name in names:
        if name in data:
            return data[name]

    lowered = {str(key).lower(): key for key in data}
    for name in names:
        key = lowered.get(str(name).lower())
        if key is not None:
            return data[key]

    return default


def get_account_state(st):
    """
    Convert a Huawei password status code into a human-readable description.

    The appliance reports this as `accountstate` in the login response. It describes the state
    of the login account's password, not the outcome of the login itself: a login can succeed
    while the account is still unusable for anything but changing the password.

    ### Parameters
    - **st** (`int` or `str`):
      The password status code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_account_state(3)
    'password expired (3)'
    """
    mapping = {
        1: 'normal (1)',
        3: 'password expired (3)',
        4: 'initial password, which must be reset (4)',
        5: 'password about to expire (5)',
        6: 'password must be changed upon the next login (6)',
        7: 'password never expires (7)',
        8: 'email one-time password authentication required (8)',
        9: 'first login, password must be initialized (9)',
        10: 'RADIUS one-time password authentication required (10)',
        11: 'RADIUS challenge response required (11)',
    }
    return mapping.get(as_code(st), 'Unknown')


def get_alarm_severity(sev):
    """
    Convert a Huawei alarm severity code into a human-readable description.

    ### Parameters
    - **sev** (`int` or `str`):
      The alarm severity code.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - `alarm/currentalarm` documents only warning, major and critical. Informational (`2`)
      comes from the alarm type table, where an appliance may define an alarm at that
      severity, so it is carried here: a listing that does contain one has to render it
      rather than fall through to `'Unknown'`.
    - Code `4` (minor) exists on other Huawei product lines and is deliberately absent,
      because neither Dorado REST Interface Reference lists it.

    ### Example
    >>> get_alarm_severity(6)
    'Critical (6)'
    """
    mapping = {
        2: 'Informational (2)',
        3: 'Warning (3)',
        5: 'Major (5)',
        6: 'Critical (6)',
    }
    return mapping.get(as_code(sev), 'Unknown')


def get_alarm_severity_state(sev):
    """
    Convert a Huawei alarm severity code into the state a check reports for it.

    ### Parameters
    - **sev** (`int` or `str`):
      The alarm severity code.

    ### Returns
    - **int**:
      `STATE_OK` for an informational alarm, `STATE_CRIT` for a critical one, `STATE_WARN`
      for warning, major, a code the enumeration does not know and a missing value.

    ### Notes
    - An informational alarm is a note, not a fault, so it does not alert. It still appears
      in the output, where it is what an operator reads after the fact.
    - Major sits at warning rather than at critical on purpose: it marks a fault that
      degrades the array without stopping it, and an array full of major alarms that all
      page someone at night is an array nobody watches any more.

    ### Example
    >>> get_alarm_severity_state(6) == STATE_CRIT
    True

    >>> get_alarm_severity_state('2') == STATE_OK
    True
    """
    code = as_code(sev)
    if code == 2:
        return STATE_OK
    if code == 6:
        return STATE_CRIT
    return STATE_WARN


def get_all_data(endpoint, args, page_size=100, max_pages=100):
    """
    Fetch every object of a list endpoint, one page at a time.

    Most list endpoints return at most 100 objects per request and expect the caller to page
    through the rest. Without paging an array simply stops being reported past the first page,
    which reads as a smaller but healthy inventory: exactly the failure a check must not have.

    ### Parameters
    - **endpoint** (`str`):
      The endpoint after the device ID, optionally with a query string of its own (for example
      `alarm/currentalarm?filter=level::6`). The `range` parameter is appended to it, so the
      caller must not supply one.
    - **args** (object):
      The same object `get_data()` reads.
    - **page_size** (`int`, optional):
      Objects to request per page. The documented ceiling differs per endpoint: 100 for most,
      250 for the alarm and event endpoints, 10000 for storage pools. Staying at or below the
      ceiling is the caller's job, because the appliance rejects a larger range rather than
      capping it.
    - **max_pages** (`int`, optional):
      Hard stop on the number of requests. It bounds the runtime of a check against an array
      with far more objects than anyone expected, and it keeps a firmware that ignores `range`
      from looping forever.

    ### Returns
    - **tuple** (`dict`, `bool`):
      The envelope of the last request with its `data` replaced by every object collected, and
      a flag that is `True` when `max_pages` cut the walk short. On a failed request the
      envelope is handed back unchanged with the flag `False`, so the caller reports the
      appliance's own error text the same way it would after a single `get_data()`.

    ### Notes
    - `range=[i-j]` is half-open: the appliance documents it as "objects subscripted in
      sequence from i to j-1". Consecutive pages therefore start where the previous one
      ended, and no object is read twice.
    - A page shorter than `page_size` ends the walk: the appliance has nothing left to hand
      out. A page of exactly `page_size` objects is always followed by another request, which
      costs one empty request when the object count is an exact multiple of the page size.
    - The port endpoints (`fc_port`, `eth_port`, `sas_port` and their relatives) do not
      implement `range`. Query those with `get_data()` instead; asking them for a range either
      errors out or silently returns the full list on every iteration.
    - The truncation flag is deliberately returned rather than turned into an abort here.
      Whether an incomplete inventory is worth an UNKNOWN or just a note in the output depends
      on the check, and this function has no way to tell.

    ### Example
    >>> result, truncated = get_all_data('lun', args)
    >>> len(result['data'])
    237
    """
    separator = '&' if '?' in endpoint else '?'
    collected = []
    result = {}
    truncated = False

    for page in range(max_pages):
        start = page * page_size
        result = get_data(
            f'{endpoint}{separator}range=[{start}-{start + page_size}]',
            args,
        )
        if get_error_code(result) not in (0, '0'):
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


def get_controller_model(cm):
    """
    Convert a Huawei controller model code into a human-readable description.

    This function translates numeric controller model codes from Huawei storage systems into
    descriptive text for better hardware identification.

    ### Parameters
    - **cm** (`int` or `str`):
      The controller model code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the controller model.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_controller_model(4127)
    '2U2C PALM control board'

    >>> get_controller_model('4144')
    '2U2C NVMe control board'
    """
    mapping = {
        4127: '2U2C PALM control board',
        4128: '2U2C SAS control board',
        4129: '2U2C SAS control board (Hi1620S)',
        4132: '4U4C control board',
        4135: '2U2C PALM 1711 control board',
        4136: '2U2C SAS 1711 control board',
        4137: '2U2C SAS 1711 control board (Hi1620S)',
        4140: '4U4C 1711 control board',
        4141: '2U2C SAS 1711 control board (100GE extension board)',
        4142: '2U2C SAS control board (100GE extension board)',
        4144: '2U2C NVMe control board',
        4149: '4U2C 1711 control board',
        4158: '8U2C control board',
        4161: '2U2C PALM control board',
        4162: '2U2C PALM control board',
        4165: '2U2C 2P control board (100G extension board)',
        4166: '2P1 2U2C PALM control board (100GE extension board)',
        4167: '2P1 2U2C SAS control board (100GE extension board)',
        4168: '2P1 2U2C SAS control board (SAS extension board)',
        4169: '1P2 2U2C SAS control board (100GE extension board)',
        4170: '1P2 2U2C PALM control board (100GE extension board)',
        4174: '4U4C4P control board',
    }
    return mapping.get(as_code(cm), 'Unknown')


def get_controller_role(role):
    """
    Convert a controller's `ROLE` code into a human-readable description.

    ### Parameters
    - **role** (`int` or `str`):
      The role code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the role.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Scoped to the controller object on purpose. `ROLE` is reused with entirely different
      meanings elsewhere: on a logical port `1` is a management port, on a HyperMetro domain
      `0` is the preferred site. Applied to those objects this mapping would print a
      confident but wrong label, which is why the function name names its object.

    ### Example
    >>> get_controller_role(1)
    'Primary'

    >>> get_controller_role('2')
    'Secondary'
    """
    mapping = {
        0: 'Member',
        1: 'Primary',
        2: 'Secondary',
    }
    return mapping.get(as_code(role), 'Unknown')


def get_cp_type(cp):
    """
    Convert a consistency protection (CP) type code into a human-readable description.

    This function translates numeric CP type codes from Huawei storage systems into descriptive
    labels that indicate the type of quorum mechanism in use.

    ### Parameters
    - **cp** (`int` or `str`):
      The CP type code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the consistency protection type.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_cp_type(1)
    'Quorum Server'

    >>> get_cp_type('2')
    'Quorum Disk'
    """
    mapping = {
        1: 'Quorum Server',
        2: 'Quorum Disk',
        3: 'None',
    }
    return mapping.get(as_code(cp), 'Unknown')


# Password states that make a login pointless to continue from. Two groups qualify: an
# expired password, where the account is out of its validity period, and a login that is
# not finished at all because the appliance still waits for a one-time password or a
# challenge response. In the second group no session exists yet to query anything with.
#
# Everything else is deliberately left out. Neither REST Interface Reference states which
# password states restrict a session, so every entry here is an assumption about the
# appliance rather than a documented rule. States 4 (initial password) and 6 (must be
# changed at the next login) used to abort as well, which took every check on a freshly
# deployed appliance to UNKNOWN before anyone had logged in to set a password. They now
# run: if the appliance really does refuse their requests, `get_data()` reports its error
# text, which names the cause better than a guess made here. This matches
# `lib.huawei_pacific`, whose `_UNUSABLE_PASSWORD_STATES` covers the same ground.
_UNUSABLE_ACCOUNT_STATES = frozenset({3, 8, 9, 10, 11})


def _cached_session(session_key):
    """
    Read a cached `(iBaseToken, Cookie, deviceId)` triple, or `None` if there is no usable one.

    Used by `get_creds()`.

    ### Parameters
    - **session_key** (`str`): The cache key the triple is stored under.

    ### Returns
    - **tuple** (`str`, `str`, `str`) or **None**: The triple, or `None` if the cache holds
      nothing, something an older version wrote, or a half-populated entry. All three cases
      have the same answer: log in again rather than build a request header out of it.

    ### Notes
    - An entry of any other length is discarded rather than padded. An older version stored
      the token pair alone, and a device ID guessed for such an entry would send every
      request of the run to the wrong path.
    """
    cached = cache.get(session_key, filename=CACHE_FILENAME)
    if not cached:
        return None

    try:
        session = json.loads(cached)
    except (TypeError, ValueError):
        return None

    if isinstance(session, list) and len(session) == 3 and all(session):
        return session[0], session[1], session[2]
    return None


def _logout(args, session):
    """
    End a session on the appliance, ignoring whatever comes back.

    Called on a session nothing will read back: the one a forced re-login replaces in
    `get_creds()`, and every session at all in `get_data()` when caching is switched off.
    Without it such a session stays open until the appliance's own timeout expires it, which
    is 20 minutes by default. The appliance caps the sessions it holds system-wide at 32 by
    default (256 is the only other value `CHANGE_USER_LOGIN_MAX_SESSIONS` accepts), so a
    check that keeps failing would leave orphans behind run after run and, at a one-minute
    interval, fill that pool from a single service. Once it is full every login is refused,
    including an operator's login to DeviceManager.

    ### Parameters
    - **args** (object): An object containing `URL`, `INSECURE`, `NO_PROXY` and `TIMEOUT`.
    - **session** (`tuple` (`str`, `str`, `str`)): The `(iBaseToken, Cookie, deviceId)`
      triple to end.

    ### Returns
    - **None**

    ### Notes
    - The device ID comes from the session being ended, not from `args`. A session opened
      without a caller-supplied device ID carries the one the appliance answered with, and
      that is the only path the logout is accepted on.
    - Every outcome is discarded, errors included. This is housekeeping on the way to a fresh
      login, and the session most likely to be logged out here is one the appliance has
      already dropped, which is exactly the case that answers with an error. Letting that
      abort the re-login would break the recovery path this call is part of. `url.fetch()`
      reports failures through its return value rather than by raising, so no exception can
      escape either.
    """
    ibasetoken, cookie, device_id = session
    url.fetch(
        f'{args.URL}/deviceManager/rest/{device_id}/sessions',
        # No `Content-Type`: this is a bare verb with no body, and announcing a JSON one
        # that is not there is what `get_data()` avoids for the same reason.
        header={
            'Cookie': cookie,
            'iBaseToken': ibasetoken,
        },
        insecure=args.INSECURE,
        method='DELETE',
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )


def get_creds(args, force_relogin=False):
    """
    Retrieve and cache Huawei appliance credentials.

    This function handles authentication against a Huawei device API. It reuses cached tokens
    (`iBaseToken` and `cookie`) if available to avoid repeated logins, which may be rate-limited for
    security reasons. If no cached credentials are found, it performs a login request and caches
    the new credentials for future reuse.

    ### Parameters
    - **args** (object):
      An argument object containing:
        - `URL` (`str`): Base URL of the Huawei API.
        - `DEVICE_ID` (`str`): Unique device identifier. May be left empty, in which case the
          login is sent to the placeholder path the vendor's own example uses and the
          appliance answers with its real device ID.
        - `USERNAME` (`str`): Login username.
        - `PASSWORD` (`str`): Login password.
        - `SCOPE` (`str`): User type (`'0'` local user, `'1'` LDAP user, `'8'` RADIUS user).
          `'8'` is only documented from V700R001C10 on. The value is passed through
          unvalidated, so a firmware that knows further types works without a code change.
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.
        - `CACHE_EXPIRE` (`int`): Cache expiration time in minutes.
    - **force_relogin** (`bool`, optional):
      If `True`, ignore any cached token and perform a fresh login, overwriting the cache.
      Used to recover from a cached session that the appliance no longer accepts (for example
      after a controller reboot, a manual session reset, or the server-side 20-minute timeout).

    ### Returns
    - **tuple** (`str`, `str`, `str`):
      - `ibase_token` (str): The API session token (iBaseToken).
      - `cookie` (str): The session cookie.
      - `device_id` (str): The device ID every further request is addressed to.

    ### Notes
    - Token, cookie and device ID are stored together, JSON-encoded, under the single cache
      key `huaweidorado-{URL}-{USERNAME}-session`, in the module's own cache file. One key
      rather than three because a request needs all of them: split over several keys, a write
      that only partly succeeds leaves a cache that can never be reused, and the resulting
      login on every single run is exactly what the caching is there to avoid.
      The user name is part of the key because a session carries that user's role: without it
      a check running as a different account would silently reuse the first account's session
      and query the appliance with the wrong privileges. The device ID is deliberately not
      part of it: it is optional, and the appliance accepts any string for it on the initial
      login, so it does not identify an appliance on its own. The URL does.
    - The device ID does not have to be supplied. The login is documented against the
      placeholder path `/deviceManager/rest/xxxxx/sessions`, and the response carries the
      appliance's own `deviceid`, which is what the rest of the run then uses. A caller that
      does supply one keeps it, so an appliance that answers with something unexpected can
      still be addressed explicitly.
    - A `CACHE_EXPIRE` of `0` turns caching off, rather than writing an entry that expires a
      moment later. Every call then logs in, which is what an operator asks for by setting it.
    - If login is required, the request is sent as serialized JSON with headers.
    - A rejected login aborts the caller (UNKNOWN) instead of returning an empty token.
      The appliance answers a wrong password, an expired password or a locked account with
      HTTP 200 and a non-zero `error.code`, so without this check the empty token would travel
      into the next request header and surface as an unrelated type error. Failing here also
      keeps a wrong password from being replayed, which would drive the account towards the
      appliance's lockout threshold.
    - An accepted login whose `accountstate` marks the password as expired aborts the caller,
      as does one that still waits for a one-time password or a challenge response: the
      account is past its validity period, or the login never finished. Which password states
      actually restrict a session is not documented, so no other state is treated as fatal;
      see `_UNUSABLE_ACCOUNT_STATES`.
    - No logout is sent at the end of a run. Because the token is cached and reused across
      runs, that would force a login on every single run and multiply the login rate the
      appliance sees. The session that `force_relogin` replaces is a different matter and is
      handed back through `_logout()`, so it does not sit in the appliance's session pool
      until its own timeout expires it.
    - The complete `Set-Cookie` field is sent back as the `Cookie` request header, attributes
      and all, because that is what the vendor's own example does. The limit of that approach
      is an appliance sending more than one `Set-Cookie` header: `lib.url` exposes the response
      headers as a flat mapping, in which repeated fields arrive comma-joined and can no longer
      be told apart. Should a firmware ever do that, `lib.url` has to expose the raw header list
      first.

    ### Example
    >>> ibasetoken, cookie, device_id = get_creds(args)
    """
    session_key = f'huaweidorado-{args.URL}-{args.USERNAME}-session'
    caching = args.CACHE_EXPIRE > 0

    if caching:
        cached = _cached_session(session_key)
        if cached and not force_relogin:
            return cached
        if cached:
            # About to replace this session, so hand it back to the appliance instead of
            # leaving it to occupy a slot in the session pool until its timeout expires.
            _logout(args, cached)

    login_device_id = getattr(args, 'DEVICE_ID', '') or DEVICE_ID_PLACEHOLDER
    uri = f'{args.URL}/deviceManager/rest/{login_device_id}/sessions'
    header = {'Content-Type': 'application/json'}
    data = {
        'username': args.USERNAME,
        'password': args.PASSWORD,
        'scope': args.SCOPE,
    }
    result = base.coe(
        url.fetch_json(
            uri,
            data=data,
            encoding='serialized-json',
            extended=True,
            header=header,
            insecure=args.INSECURE,
            no_proxy=args.NO_PROXY,
            timeout=args.TIMEOUT,
        )
    )

    response_json = result.get('response_json')
    if not isinstance(response_json, dict):
        base.cu(
            f'Login at {args.URL} returned {type(response_json).__name__} instead of the '
            'documented response object.'
        )

    session_data = response_json.get('data')
    if not isinstance(session_data, dict):
        session_data = {}
    ibasetoken = session_data.get('iBaseToken')
    # lib.url lower-cases all response header names (RFC 9110, section 5.1).
    cookie = result.get('response_header', {}).get('set-cookie')

    if not ibasetoken or not cookie:
        error = response_json.get('error') or {}
        # Both halves are required to build the request header, so a response carrying only
        # one of them is as unusable as one carrying neither. The fallback text has to cover
        # that case too, rather than naming the token alone.
        base.cu(
            f'Login at {args.URL} failed: '
            f'{error.get("description") or "incomplete session in the login response"} '
            f'(code {error.get("code", "n/a")}).'
        )

    accountstate = as_code(session_data.get('accountstate'))
    if accountstate in _UNUSABLE_ACCOUNT_STATES:
        base.cu(
            f'Login at {args.URL} succeeded, but the account cannot query anything: '
            f'{get_account_state(accountstate)}.'
        )

    # A caller-supplied device ID wins. It is the one an operator can look up in
    # DeviceManager, so an appliance whose answer does not match it is still addressable.
    device_id = getattr(args, 'DEVICE_ID', '') or session_data.get('deviceid')
    if not device_id:
        base.cu(
            f'Login at {args.URL} succeeded, but the response carries no device ID and none '
            'was supplied. Pass the appliance device ID explicitly.'
        )

    if caching:
        cache.set(
            session_key,
            json.dumps([ibasetoken, cookie, device_id]),
            time.now() + args.CACHE_EXPIRE * 60,
            filename=CACHE_FILENAME,
        )

    return ibasetoken, cookie, device_id


def _as_envelope(success, response):
    """
    Normalise whatever `url.fetch_json()` returned into the documented response envelope.

    `get_data()` promises its caller a `{'error': {'code': ...}, 'data': ...}` document. Three
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
    >>> _as_envelope(True, {'error': {'code': 0}, 'data': []})
    {'error': {'code': 0}, 'data': []}
    >>> _as_envelope(False, 'URL error "timed out"')['error']['code']
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
        if isinstance(parsed, dict) and isinstance(parsed.get('error'), dict):
            return parsed

    return {
        'error': {
            'code': 'n/a',
            # Bounded: the body of an error status can be a full HTML page, and this
            # ends up in the check's plugin output.
            'description': f'{response}'[:200],
        },
    }


def get_data(endpoint, args, max_attempts=3):
    """
    Fetch data from a Huawei appliance endpoint, re-authenticating on a stale session.

    This function performs an authenticated GET request to a Huawei device's REST API. The first
    attempt reuses the cached session token. If the appliance rejects the request, the most common
    cause is a session the appliance no longer accepts (controller reboot, manual session reset, or
    the server-side 20-minute timeout expiring before the local cache). Retrying with the same token
    can never recover from that, so the next attempt forces a fresh login and retries. Any remaining
    attempts cover short-lived transient errors.

    ### Parameters
    - **endpoint** (`str`):
      The API endpoint to call (relative path after the device ID), including the query string
      if the endpoint takes one. The string is appended to the request URL verbatim, so the
      caller is responsible for percent-encoding it; never build it from data the appliance
      itself returned.
    - **args** (object):
      An object containing:
        - `URL` (`str`): Base API URL.
        - `DEVICE_ID` (`str`): Device ID. Optional; see `get_creds()`.
        - `INSECURE` (`bool`): Disable SSL verification.
        - `NO_PROXY` (`bool`): Ignore proxy settings.
        - `TIMEOUT` (`int`): Timeout for API requests.
    - **max_attempts** (`int`, optional):
      How often to try before giving up. The default of `3` is what a check wants. Pass `1` to
      ask a question whose expected answer may well be an error, such as probing which of two
      endpoint spellings a firmware answers to: the retry loop would then spend two further
      requests and a forced re-login on establishing what the first answer already said, and
      the re-login would drop a perfectly good cached session along the way.

    ### Returns
    - **dict**:
      The parsed JSON response from the API.

    ### Notes
    - Makes at most three attempts, forcing a fresh login before the second one, and waits one
      second between attempts. The retry count is kept low on purpose, so one call stays within
      the monitoring server's check timeout: the worst case is three requests plus one login,
      plus two seconds of waiting. This budget is per call. A caller that chains several calls
      has to size its own timeout for the sum.
    - A rejected request is retried instead of aborting the caller: a transport failure, an HTTP
      error status and a response that is not the documented `{'error': {'code': ...}}` envelope
      all count as a failed attempt and are handed back in that envelope. The caller therefore
      always receives the documented return value and can report the appliance's own error text.
    - A request without the `Cookie` and `iBaseToken` headers is documented to answer with code
      `-401`. Whether an appliance reports a session it no longer accepts the same way is not
      documented, so the fresh login is not tied to that code: it is triggered on any non-zero
      error, which covers however a given firmware chooses to report it.
    - With caching switched off (`CACHE_EXPIRE` of `0`) every attempt logs in again and the
      session it gets is good for that one request only. Each is logged out right after it,
      because nothing will ever read it back from the cache and the appliance holds a limited
      number of sessions. In this mode a call can therefore reach three logins and three
      logouts, which is the price of asking for no caching.

    ### Example
    >>> get_data('disk/list', args)
    {
        'error': {'code': 0},
        'data': {...}
    }
    """
    result = {}

    for attempt in range(1, max_attempts + 1):
        # On the second attempt, drop the cached session and log in again; a
        # rejected request is most likely an expired session that retrying
        # with the same token cannot fix. The third attempt then reuses that
        # fresh token to absorb a remaining transient error.
        ibasetoken, cookie, device_id = get_creds(args, force_relogin=attempt == 2)
        # The device ID comes from the session, not from `args`: it may have been the
        # appliance's own answer rather than a caller-supplied value, and a re-login can
        # in principle hand back a different one.
        uri = f'{args.URL}/deviceManager/rest/{device_id}/{endpoint}'
        header = {
            'Content-Type': 'application/json',
            'iBaseToken': ibasetoken,
            'Cookie': cookie,
        }
        # `response_on_error` keeps the appliance's own error body readable when it
        # answers with a 4xx/5xx status. Without it the body is dropped in favour of
        # the status line, and the request would abort the check on the spot instead
        # of becoming a failed attempt the forced re-login can still recover from.
        result = _as_envelope(
            *url.fetch_json(
                uri,
                header=header,
                insecure=args.INSECURE,
                no_proxy=args.NO_PROXY,
                response_on_error=True,
                timeout=args.TIMEOUT,
            )
        )
        if args.CACHE_EXPIRE <= 0:
            # Caching is off, so this session was created for this one request and nothing
            # will ever reuse it. Hand it back instead of leaving it to occupy a slot in the
            # appliance's session pool until its own timeout expires it.
            _logout(args, (ibasetoken, cookie, device_id))
        if get_error_code(result) in (0, '0'):
            break
        if attempt < max_attempts:
            _sleep(1)

    return result


def get_dr_star_running_status(rs):
    """
    Convert a DR Star trio's `RUNNINGSTATUS` code into a human-readable description.

    ### Parameters
    - **rs** (`int` or `str`):
      The running status code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the running status, including the original code in
      brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Scoped to the `dr_star` object, which renumbers `RUNNINGSTATUS` rather than sharing the
      enumeration `get_running_status()` covers. Read through that function a disabled trio
      would come out as `'Running (2)'`, which reads like the opposite of what it is.
    - Both REST Interface References agree on these four values.

    ### Example
    >>> get_dr_star_running_status(2)
    'Disabled (2)'
    """
    mapping = {
        0: 'Unknown (0)',
        1: 'Enabled (1)',
        2: 'Disabled (2)',
        3: 'Invalid (3)',
    }
    return mapping.get(as_code(rs), 'Unknown')


def get_enclosure_logic_type(lt):
    """
    Convert an enclosure's `LOGICTYPE` code into a human-readable description.

    ### Parameters
    - **lt** (`int` or `str`):
      The logic type code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the logic type.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Scoped to the enclosure object on purpose. `LOGICTYPE` is reused with entirely
      different meanings elsewhere: on a port `2` is a management port, on a disk `2` is a
      member disk. Applied to those objects this mapping would print a confident but wrong
      label, which is why the function name names its object.

    ### Example
    >>> get_enclosure_logic_type(1)
    'Controller Enclosure'

    >>> get_enclosure_logic_type('3')
    'Management Switch'
    """
    mapping = {
        0: 'Expansion Enclosure (Disk Enclosure)',
        1: 'Controller Enclosure',
        2: 'Data Switch',
        3: 'Management Switch',
        4: 'Management Server',
    }
    return mapping.get(as_code(lt), 'Unknown')


def get_enclosure_model(em):
    """
    Convert a Huawei enclosure model code into a human-readable description.

    This function translates numeric enclosure model codes from Huawei storage systems into
    descriptive text to simplify hardware identification.

    ### Parameters
    - **em** (`int` or `str`):
      The enclosure model code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the enclosure model.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_enclosure_model(39)
    '4 U 75-slot 3.5-inch 12 Gbit/s SAS disk enclosure'

    >>> get_enclosure_model('122')
    '2 U 2-controller 25-slot 2.5-inch NVMe controller enclosure'
    """
    mapping = {
        39: '4 U 75-slot 3.5-inch 12 Gbit/s SAS disk enclosure',
        67: '2 U 25-slot 2.5-inch SAS disk enclosure',
        69: '4 U 24-slot 3.5-inch SAS disk enclosure',
        73: '4 U 12 Gbit/s 75-slot 3.5-inch SAS disk enclosure',
        112: '4 U 4-controller controller enclosure',
        113: '2 U 2-controller 25-slot 2.5-inch SAS controller enclosure',
        114: '2 U 2-controller 12-slot 3.5-inch SAS controller enclosure',
        115: '2 U 2-controller 36-slot NVMe controller enclosure',
        116: '2 U 2-controller 25-slot 2.5-inch SAS controller enclosure',
        117: '2 U 2-controller 12-slot 3.5-inch SAS controller enclosure',
        118: '2 U 25-slot 2.5-inch smart SAS disk enclosure',
        119: '2 U 12-slot 3.5-inch smart SAS disk enclosure',
        120: '2 U 36-slot smart NVMe disk enclosure',
        122: '2 U 2-controller 25-slot 2.5-inch NVMe controller enclosure',
        130: '2 U 2-controller 25-slot 2.5-inch SAS controller enclosure',
        131: '2 U 2-controller 12-slot 3.5-inch SAS controller enclosure',
        132: '4 U 2-controller 10-slot 3.5-inch controller enclosure',
    }
    return mapping.get(as_code(em), 'Unknown')


def get_error_code(result):
    """
    Read the status code out of a response envelope.

    ### Parameters
    - **result** (`dict`): A response envelope as `get_data()` returns it.

    ### Returns
    - **int**, **str** or **None**:
      The value of `error.code`, the bare `error` if the appliance answered with a scalar
      instead of the documented object, or `None` if the envelope carries neither.

    ### Notes
    - Success is code `0`. The appliance reports it as a number on some endpoints and as the
      string `'0'` on others, so compare against both rather than against one of them.

    ### Example
    >>> get_error_code({'error': {'code': 0}})
    0
    """
    error = result.get('error')
    if isinstance(error, dict):
        return error.get('code')
    return error


def get_health_status(hs):
    """
    Convert a Huawei health status code into a human-readable description.

    This function translates numeric health status codes returned by Huawei appliances into
    descriptive text, making it easier to interpret device health states.

    ### Parameters
    - **hs** (`int` or `str`):
      The health status code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the health status, including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - `HEALTHSTATUS` is a shared enumeration, and code `17` is the one value whose wording
      depends on the object it is read from: a disk reports it as `single link`, a host as
      `no redundant link`. The response carries no marker for which of the two applies, so
      the code renders as `'Single link / No redundant link'`, which holds for both, rather
      than picking one and being wrong on the other object type.
    - The table is the complete union of the codes both REST Interface References list. The
      appliance's SNMP MIB defines a larger enumeration, among it bad sectors found, busy
      and single link fault, and those codes look like an omission when the two interfaces
      are compared. They are not: the REST API never sends them, and carrying them here
      would document behaviour this module cannot produce.

    ### Example
    >>> get_health_status(1)
    'Normal (1)'

    >>> get_health_status('5')
    'Degraded (5)'
    """
    mapping = {
        0: 'Unknown (0)',
        1: 'Normal (1)',
        2: 'Faulty (2)',
        3: 'About to fail (3)',
        4: 'Partially damaged (4)',
        5: 'Degraded (5)',
        7: 'Bit errors found (7)',
        9: 'Inconsistent (9)',
        11: 'No Input (11)',
        12: 'Low Battery (12)',
        14: 'Invalid (14)',
        15: 'Write-protected (15)',
        17: 'Single link / No redundant link (17)',
        18: 'Offline (18)',
    }
    return mapping.get(as_code(hs), 'Unknown')


# `HEALTHSTATUS` codes that mean the object has failed outright, as opposed to still serving
# I/O in a reduced state. Everything else the enumeration knows describes a degradation, and
# everything it does not know is a code this firmware invented; both are worth a look but
# neither justifies waking someone, so they end up as a warning.
#
# `No Input (11)` is in this set because of where it is reported: it is what a power module
# answers when its feed is dead, which the vendor's own `power` response example shows next
# to an offline running status. A power supply without a feed is not degraded, it is gone,
# and a second one failing the same way takes the array with it.
_FAILED_HEALTH_STATES = frozenset({2, 11, 14, 18})


def get_health_status_state(hs):
    """
    Convert a Huawei health status code into the state a check reports for it.

    ### Parameters
    - **hs** (`int` or `str`):
      The health status code to interpret.

    ### Returns
    - **int**:
      `STATE_OK` for a normal object, `STATE_CRIT` for a failed one, `STATE_WARN` for every
      other code, including one the enumeration does not know and a missing value.

    ### Notes
    - Faulty (`2`), No Input (`11`), Invalid (`14`) and Offline (`18`) are the codes that
      report an object which has stopped doing its job, so they are the ones that reach
      `STATE_CRIT`.
    - An unrecognised code cannot be assumed to be harmless, so it warns rather than passing as
      OK. It renders as `'Unknown'` through `get_health_status()`, which tells the reader that
      the code, not the object, is what the check could not place.
    - `HEALTHSTATUS` is shared across object types, which is why this mapping needs no
      per-object parameter. `RUNNINGSTATUS` is not, hence the `ok_codes` argument on
      `get_running_status_state()`.

    ### Example
    >>> get_health_status_state(1) == STATE_OK
    True

    >>> get_health_status_state('2') == STATE_CRIT
    True

    >>> get_health_status_state(5) == STATE_WARN
    True
    """
    code = as_code(hs)
    if code == 1:
        return STATE_OK
    if code in _FAILED_HEALTH_STATES:
        return STATE_CRIT
    return STATE_WARN


def get_host_access_state(has):
    """
    Convert a host access state code into a human-readable description.

    This function translates the numeric read/write setting a Huawei storage system reports for
    a secondary resource (`SECRESACCESS`) into a descriptive label.

    ### Parameters
    - **has** (`int` or `str`):
      The host access state code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the host access state.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_host_access_state(2)
    'Read-only'

    >>> get_host_access_state('3')
    'Read/write'
    """
    mapping = {
        1: 'Access denied',
        2: 'Read-only',
        3: 'Read/write',
    }
    return mapping.get(as_code(has), 'Unknown')


def get_hypermetro_domain_running_status(rs):
    """
    Convert a HyperMetro domain's `RUNNINGSTATUS` code into a human-readable description.

    ### Parameters
    - **rs** (`int` or `str`):
      The running status code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the running status, including the original code in
      brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Scoped to the `HyperMetroDomain` object, which renumbers `RUNNINGSTATUS` from `0` up
      rather than sharing the enumeration `get_running_status()` covers. Every code below
      collides: read through that function a faulty domain would come out as `'Running (2)'`
      and an invalid one as `'Sleep in High Temperature (5)'`, so a broken HyperMetro pair
      would look healthy in a check's output.
    - Documented in the V700R001C10 REST Interface Reference. Code `4` exists nowhere else
      and is deliberately absent from `get_running_status()`.

    ### Example
    >>> get_hypermetro_domain_running_status(2)
    'Faulty (2)'
    """
    mapping = {
        0: 'Normal (0)',
        1: 'Recovering (1)',
        2: 'Faulty (2)',
        3: 'Split (3)',
        4: 'Force started (4)',
        5: 'Invalid (5)',
    }
    return mapping.get(as_code(rs), 'Unknown')


def get_hypermetro_domain_running_status_state(rs):
    """
    Convert a HyperMetro domain's `RUNNINGSTATUS` code into the state a check reports for it.

    ### Parameters
    - **rs** (`int` or `str`):
      The running status code to interpret.

    ### Returns
    - **int**:
      `STATE_OK` for a normal domain, `STATE_CRIT` for a faulty or invalid one, `STATE_WARN`
      for every other code, including one the enumeration does not know and a missing value.

    ### Notes
    - Scoped to the `HyperMetroDomain` object for the same reason as
      `get_hypermetro_domain_running_status()`: the codes are renumbered from `0` up and every
      one of them collides with the shared enumeration, so `get_running_status_state()` cannot
      be used here.
    - Split (`3`) warns rather than going critical. A split domain no longer mirrors, but each
      side still serves its own I/O, and an administrator splits a domain deliberately during
      maintenance.

    ### Example
    >>> get_hypermetro_domain_running_status_state(0) == STATE_OK
    True

    >>> get_hypermetro_domain_running_status_state('2') == STATE_CRIT
    True
    """
    code = as_code(rs)
    if code == 0:
        return STATE_OK
    if code in (2, 5):
        return STATE_CRIT
    return STATE_WARN


def get_interface_model(im):
    """
    Convert an interface module (I/O module) ID into a human-readable model description.

    This function translates numeric hardware IDs from Huawei hardware into a descriptive
    model name.

    ### Parameters
    - **im** (`int` or `str`):
      The numeric ID of the interface module.

    ### Returns
    - **str**:
      A human-readable description of the interface model.
      Returns `'Unknown'` if the ID is not recognized.

    ### Example
    >>> get_interface_model(2306)
    '4 ports FE 32 Gbit/s Fibre Channel I/O module'
    """
    models = {
        516: '4 ports FE 1 Gbit/s ETH I/O module',
        518: '4 ports BE 12 Gbit/s SAS I/O module',
        529: 'AI accelerator card',
        535: 'AI accelerator card',
        537: '4 ports FE 1 Gbit/s ETH I/O module',
        538: '4 ports BE 12 Gbit/s SAS I/O module',
        580: '4 ports FE 1 Gbit/s ETH I/O module',
        583: '4 ports BE 12 Gbit/s SAS V2 I/O module',
        601: '4 ports FE 1 Gbit/s ETH I/O module',
        2304: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2305: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2306: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2307: '4 ports FE 10 Gbit/s ETH I/O module',
        2308: '4 ports FE 25 Gbit/s ETH I/O module',
        2309: '4 ports SO 25 Gbit/s RDMA I/O module',
        2310: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2311: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2312: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2313: '4 ports FE 10 Gbit/s ETH I/O module',
        2314: '4 ports FE 25 Gbit/s ETH I/O module',
        2315: '2 ports FE 40 Gbit/s ETH I/O module',
        2316: '2 ports FE 100 Gbit/s ETH I/O module',
        2317: '2 ports BE 100 Gbit/s RDMA I/O module',
        2318: '2 ports SO 100 Gbit/s RDMA I/O module',
        2319: '2 ports FE 40 Gbit/s ETH I/O module',
        2320: '2 ports FE 100 Gbit/s ETH I/O module',
        2321: '2 ports BE 100 Gbit/s RDMA I/O module',
        2322: '2 ports SO 100 Gbit/s RDMA I/O module',
        2323: '4 ports FE 10 Gbit/s RoCE I/O module',
        2324: '4 ports FE 25 Gbit/s RoCE I/O module',
        2325: '4 ports FE 10 Gbit/s RoCE I/O module',
        2326: '4 ports FE 25 Gbit/s RoCE I/O module',
        2327: '2 ports FE 40 Gbit/s RoCE I/O module',
        2328: '2 ports FE 100 Gbit/s RoCE I/O module',
        2329: '2 ports FE 40 Gbit/s RoCE I/O module',
        2330: '2 ports FE 100 Gbit/s RoCE I/O module',
        2331: '4 ports FE 10 Gbit/s ETH I/O module',
        2332: '4 ports FE 10 Gbit/s ETH I/O module',
        2333: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2334: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2335: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2336: '4 ports FE 10 Gbit/s ETH I/O module',
        2337: '4 ports FE 25 Gbit/s ETH I/O module',
        2338: '4 ports SO 25 Gbit/s RDMA I/O module',
        2339: '4 ports FE 10 Gbit/s RoCE I/O module',
        2340: '4 ports FE 25 Gbit/s RoCE I/O module',
        2341: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2342: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2343: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2344: '4 ports FE 10 Gbit/s ETH I/O module',
        2345: '4 ports FE 25 Gbit/s ETH I/O module',
        2346: '4 ports FE 10 Gbit/s RoCE I/O module',
        2347: '4 ports FE 25 Gbit/s RoCE I/O module',
        2348: '2 ports FE 40 Gbit/s ETH I/O module',
        2349: '2 ports FE 100 Gbit/s ETH I/O module',
        2350: '2 ports BE 100 Gbit/s RDMA I/O module',
        2351: '2 ports SO 100 Gbit/s RDMA I/O module',
        2352: '2 ports FE 40 Gbit/s RoCE I/O module',
        2353: '2 ports FE 100 Gbit/s RoCE I/O module',
        2354: '2 ports FE 40 Gbit/s ETH I/O module',
        2355: '2 ports FE 100 Gbit/s ETH I/O module',
        2356: '2 ports BE 100 Gbit/s RDMA I/O module',
        2357: '2 ports SO 100 Gbit/s RDMA I/O module',
        2358: '2 ports FE 40 Gbit/s RoCE I/O module',
        2359: '2 ports FE 100 Gbit/s RoCE I/O module',
        2360: '4 ports FE 10 Gbit/s ETH I/O module',
        2361: '4 ports SO 25 Gbit/s RDMA I/O module',
        2362: '2 ports SO 100 Gbit/s RDMA I/O module',
        2363: '2 ports SO 100 Gbit/s RDMA I/O module',
        2364: '4 ports FE 10 Gbit/s ETH I/O module',
        2365: '4 ports FE 25 Gbit/s ETH I/O module',
        2366: '4 ports FE 10 Gbit/s ETH I/O module',
        2367: '4 ports FE 25 Gbit/s RoCE I/O module',
        2368: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2369: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2370: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2371: '4 ports FE 10 Gbit/s ETH I/O module',
        2372: '4 ports FE 25 Gbit/s ETH I/O module',
        2373: '4 ports FE 25 Gbit/s RoCE I/O module',
        2375: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2376: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2377: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2378: '4 ports FE 10 Gbit/s ETH I/O module',
        2379: '4 ports FE 25 Gbit/s ETH I/O module',
        2380: '4 ports FE 10 Gbit/s RoCE I/O module',
        2381: '4 ports FE 25 Gbit/s NoF I/O module',
        2382: '2 ports FE 40 Gbit/s ETH I/O module',
        2383: '2 ports FE 100 Gbit/s ETH I/O module',
        2384: '2 ports BE 100 Gbit/s RDMA I/O module',
        2385: '2 ports SO 100 Gbit/s RDMA I/O module',
        2386: '2 ports FE 40 Gbit/s RoCE I/O module',
        2387: '2 ports FE 100 Gbit/s RoCE I/O module',
        2388: '2 ports FE 100 Gbit/s NoF I/O module',
        2389: '4 ports BE 12 Gbit/s SAS I/O module',
        2390: '4 ports FE 1 Gbit/s ETH I/O module',
        2391: '2 ports FE 1 Gbit/s ETH I/O module',
        2393: '4 ports FE 25 Gbit/s RoCE I/O module',
        2394: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2395: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2396: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2397: '4 ports FE 10 Gbit/s ETH I/O module',
        2398: '4 ports FE 25 Gbit/s ETH I/O module',
        2399: '4 ports SO 25 Gbit/s RDMA I/O module',
        2400: '4 ports FE 10 Gbit/s RoCE I/O module',
        2401: '4 ports FE 25 Gbit/s RoCE I/O module',
        2402: '2 ports FE 40 Gbit/s ETH I/O module',
        2403: '2 ports FE 100 Gbit/s ETH I/O module',
        2404: '2 ports BE 100 Gbit/s RDMA I/O module',
        2405: '2 ports SO 100 Gbit/s RDMA I/O module',
        2406: '2 ports FE 40 Gbit/s RoCE I/O module',
        2407: '2 ports FE 100 Gbit/s RoCE I/O module',
        2408: '4 ports FE 10 Gbit/s ETH I/O module',
        2409: '4 ports FE 25 Gbit/s ETH I/O module',
        2410: '4 ports FE 25 Gbit/s RoCE I/O module',
        2411: '4 ports FE 10 Gbit/s ETH I/O module',
        2412: '4 ports FE 10 Gbit/s ETH I/O module',
        2413: '4 ports FE 25 Gbit/s ETH I/O module',
        2414: '4 ports FE 25 Gbit/s RoCE I/O module',
        2415: '4 ports FE 10 Gbit/s ETH I/O module',
        2416: '4 ports FE 10 Gbit/s ETH I/O module',
        2417: '4 ports FE 1 Gbit/s ETH I/O module',
        2419: '4 ports FE 10 Gbit/s ETH I/O module',
        2420: '4 ports FE 25 Gbit/s ETH I/O module',
        2421: '4 ports FE 10 Gbit/s ETH I/O module',
        2422: '4 ports FE 25 Gbit/s ETH I/O module',
        2423: 'OceanCyber 100 Data Security Card',
        2424: 'OceanCyber 100 Data Security Card',
        2425: 'HyperDetect ransomware detection module',
        2426: 'HyperDetect ransomware detection module',
        2427: '4 ports FE 10 Gbit/s ETH I/O module',
        2428: '4 ports FE 25 Gbit/s ETH I/O module',
        2429: '2 ports FE 40 Gbit/s ETH I/O module',
        2430: '2 ports FE 100 Gbit/s ETH I/O module',
        2431: '2 ports FE 200 Gbit/s ETH I/O module',
        2432: '4 ports FE 10 Gbit/s ETH I/O module',
        2433: '4 ports FE 25 Gbit/s ETH I/O module',
        2434: '2 ports FE 40 Gbit/s ETH I/O module',
        2435: '2 ports FE 100 Gbit/s ETH I/O module',
        2436: '2 ports FE 200 Gbit/s ETH I/O module',
        2437: '4 ports FE 64 Gbit/s Fibre Channel I/O module',
        2438: '4 ports FE 64 Gbit/s Fibre Channel I/O module',
        2439: '2 ports FE 200 Gbit/s ETH I/O module',
        2440: '2 ports FE 200 Gbit/s ETH I/O module',
        2441: '2 ports FE 200 Gbit/s RoCE I/O module',
        2442: '2 ports FE 200 Gbit/s RoCE I/O module',
        2443: '2 ports FE 200 Gbit/s NoF I/O module',
        2444: '2 ports SO 200 Gbit/s RDMA I/O module',
        2445: '2 ports SO 200 Gbit/s RDMA I/O module',
        2446: '2 ports FE 40 Gbit/s ETH I/O module',
        2447: '2 ports FE 40 Gbit/s ETH I/O module',
        2448: '2 ports FE 40 Gbit/s RoCE I/O module',
        2449: '2 ports FE 40 Gbit/s RoCE I/O module',
        2450: '2 ports FE 100 Gbit/s ETH I/O module',
        2451: '2 ports FE 100 Gbit/s ETH I/O module',
        2452: '2 ports FE 100 Gbit/s RoCE I/O module',
        2453: '2 ports FE 100 Gbit/s RoCE I/O module',
        2454: '2 ports FE 100 Gbit/s NoF I/O module',
        2455: '2 ports BE 100 Gbit/s RDMA I/O module',
        2456: '2 ports BE 100 Gbit/s RDMA I/O module',
        2457: '2 ports SO 100 Gbit/s RDMA I/O module',
        2458: '2 ports SO 100 Gbit/s RDMA I/O module',
        2464: 'SmartDedupe and SmartCompression acceleration module',
        4133: 'management module',
        4134: 'management module',
    }

    return models.get(as_code(im), 'Unknown')


def get_interface_runmode(rm):
    """
    Convert an interface runmode ID into a human-readable run mode description.

    This function translates numeric runmode IDs from Huawei hardware into a descriptive
    operational mode name (e.g., FC, Ethernet, Cluster).

    ### Parameters
    - **rm** (`int` or `str`):
      The numeric ID representing the interface run mode.

    ### Returns
    - **str**:
      A human-readable description of the interface run mode.
      Returns `'Unknown'` if the ID is not recognized.

    ### Notes
    - Code `5` is the one value whose meaning differs between the two documented firmware
      generations: 6.1.0 defines it as RoCE, V700R001C10 as RDMA (and moves RoCE to `10`). The
      response carries no firmware marker, and the appliance model does not imply the firmware,
      so the code cannot be disambiguated from a single interface module. It therefore renders
      as `'RDMA/RoCE'`, which holds under both revisions, rather than picking one and being
      wrong on the other half of the fleet.
    - Scoped to the interface module (`intf_module`). Controllers and expansion modules carry
      their own, much shorter `RUNMODE` with only `1` for Fibre Channel and `2` for Ethernet,
      where this mapping would render `2` as `'FCoE/iSCSI'`.

    ### Example
    >>> get_interface_runmode(1)
    'FC'
    """
    runmodes = {
        1: 'FC',
        2: 'FCoE/iSCSI',
        3: 'Cluster',
        4: 'Ethernet',
        5: 'RDMA/RoCE',
        6: 'NoF',
        9: 'NoF',
        10: 'RoCE',
    }

    return runmodes.get(as_code(rm), 'Unknown')


def get_led_status(st):
    """
    Convert an LED status ID into a human-readable LED state.

    This function translates numeric LED status codes into readable status descriptions
    (e.g., On, Off).

    ### Parameters
    - **st** (`int` or `str`):
      The numeric LED status ID.

    ### Returns
    - **str**:
      A human-readable LED status. Returns `'Unknown'` if the ID is not recognized.

    ### Example
    >>> get_led_status(1)
    'On'
    """
    led_status = {
        0: 'Off',
        1: 'On',
    }

    return led_status.get(as_code(st), 'Unknown')


def get_os(os):
    """
    Convert an operating system (OS) code into a human-readable description.

    This function translates numeric OS codes from Huawei storage systems into descriptive
    names for better interpretation of connected or managed hosts.

    ### Parameters
    - **os** (`int` or `str`):
      The OS code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the operating system.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Code `255` is not in the `OPERATIONSYSTEM` table of either REST Interface Reference. It
      is carried here because appliances report it for a host that never delivered an
      operating system, where rendering it as `'Unknown'` would read like a code the vendor
      forgot to document. Treat the wording as observed behaviour, not as a documented value.

    ### Example
    >>> get_os(7)
    'VMware ESX'

    >>> get_os('0')
    'Linux'

    >>> get_os(255)
    'not specified (255)'
    """
    mapping = {
        0: 'Linux',
        1: 'Windows',
        2: 'Solaris',
        3: 'HP-UX',
        4: 'AIX',
        5: 'XenServer',
        6: 'Mac OS',
        7: 'VMware ESX',
        8: 'LINUX_VIS',
        9: 'Windows Server 2012 (not recommended)',
        10: 'Oracle VM (not recommended)',
        11: 'OpenVMS',
        12: 'Oracle_VM_Server_for_x86',
        13: 'Oracle_VM_Server_for_SPARC',
        # Not a real operating system, and not in the vendor's table either: appliances
        # report 255 for a host that never delivered one. Kept because 'Unknown', which
        # is what an undocumented code means everywhere else in this module, would read
        # as a gap in this mapping rather than as the absence of an answer.
        255: 'not specified (255)',
    }
    return mapping.get(as_code(os), 'Unknown')


# The vendor misspelled the performance endpoint as `performace_statistic` and corrected it to
# `performance_statistic` in a later firmware generation. Both spellings are live in the field,
# and nothing in a response says which one an appliance answers to, so the working one is found
# by trying and then remembered for the rest of the run.
_PERFORMANCE_PATHS = (
    'performance_statistic/cur_statistic_data',
    'performace_statistic/cur_statistic_data',
)
_performance_path = None


def get_performance(uuid, data_ids, args):
    """
    Fetch the current performance counters of one managed object.

    ### Parameters
    - **uuid** (`str`):
      The object's UUID in the appliance's own `TYPE:ID` notation, as `get_uuid()` builds it.
      For example `'207:0A'` for a controller.
    - **data_ids** (iterable of `int`):
      The performance indicators to read. The vendor numbers them per indicator, not per
      object: `18` utilisation in percent, `19` queue length, `21` block bandwidth in MB/s,
      `22` IOPS, `23` and `26` read and write bandwidth, `25` and `28` read and write IOPS,
      `370` average I/O response time. Not every object supports every indicator.
    - **args** (object):
      The same object `get_data()` reads.

    ### Returns
    - **dict**:
      Indicator number to reported value, both as strings, in the order the appliance listed
      them. Empty if the request failed or the appliance returned no sample, which is the
      normal answer for an object whose counters are not being collected.

    ### Notes
    - The appliance answers with two parallel comma-separated lists, one of indicator numbers
      and one of values. They are zipped back together here so a caller reads a counter by its
      number instead of by its position.
    - Every value is a gauge (a rate, a percentage or a time), not a cumulative counter, so it
      can go into performance data as it is. See
      [#320](https://github.com/Linuxfabrik/monitoring-plugins/issues/320).
    - The first call of a run may cost two requests while the endpoint spelling is being
      determined; every later call in the same run goes straight to the one that answered.

    ### Example
    >>> get_performance('207:0A', (21, 22, 370), args)
    {'21': '132', '22': '4711', '370': '385'}
    """
    global _performance_path

    ids = ','.join(str(data_id) for data_id in data_ids)
    query = f'?CMO_STATISTIC_UUID={uuid}&CMO_STATISTIC_DATA_ID_LIST={ids}'
    paths = (_performance_path,) if _performance_path else _PERFORMANCE_PATHS
    # While probing, an error is an expected answer rather than a fault, so it is taken at
    # face value. Retrying would cost two more requests and a forced re-login per wrong
    # spelling, and the re-login would drop the cached session the rest of the check reuses.
    attempts = 1 if len(paths) > 1 else 3

    for path in paths:
        result = get_data(f'{path}{query}', args, max_attempts=attempts)
        if get_error_code(result) not in (0, '0'):
            continue
        _performance_path = path

        data = result.get('data') or []
        if isinstance(data, dict):
            data = [data]
        if not data:
            return {}

        sample = data[0]
        keys = str(sample.get('CMO_STATISTIC_DATA_ID_LIST', '')).split(',')
        values = str(sample.get('CMO_STATISTIC_DATA_LIST', '')).split(',')
        return {
            key: value for key, value in zip(keys, values) if key != '' and value != ''
        }

    return {}


# The performance indicators, keyed by the number the vendor gives them, as
# `(label, uom, factor)`. The label is the metric name a consumer emits, `uom` is the
# Nagios unit of measurement, and `factor` converts the vendor's unit into it.
#
# Two conversions are worth naming. The response times are documented in microseconds and
# go out in seconds, the unit Nagios knows. The bandwidths and I/O sizes are documented as
# MB/s and KB, and are read as binary multiples: every capacity this API reports is binary
# (sectors of 512 bytes), and so is what DeviceManager itself displays.
PERFORMANCE_INDICATORS = {
    18: ('usage_percent', '%', 1),
    19: ('queue_length', None, 1),
    21: ('block_bandwidth', 'B', 1024 * 1024),
    22: ('total_iops', None, 1),
    23: ('read_bandwidth', 'B', 1024 * 1024),
    24: ('avg_read_io_size', 'B', 1024),
    25: ('read_iops', None, 1),
    26: ('write_bandwidth', 'B', 1024 * 1024),
    27: ('avg_write_io_size', 'B', 1024),
    28: ('write_iops', None, 1),
    68: ('cpu_usage_percent', '%', 1),
    69: ('cache_usage_percent', '%', 1),
    93: ('read_cache_hit_ratio_percent', '%', 1),
    95: ('write_cache_hit_ratio_percent', '%', 1),
    110: ('read_cache_usage_percent', '%', 1),
    120: ('write_cache_usage_percent', '%', 1),
    303: ('avg_cache_hit_ratio_percent', '%', 1),
    370: ('avg_io_response_time', 's', 1 / 1_000_000),
    384: ('avg_read_io_response_time', 's', 1 / 1_000_000),
    385: ('avg_write_io_response_time', 's', 1 / 1_000_000),
}

# Object type numbers of the performance API, from the "Statistics Type" columns of the
# performance indicator tables. They are the `TYPE` an object reports, so a consumer
# normally builds its UUID with `get_uuid()` rather than naming the number here.
PERFORMANCE_TYPE_CONTROLLER = 207
PERFORMANCE_TYPE_ETH_PORT = 213
PERFORMANCE_TYPE_FC_PORT = 212
PERFORMANCE_TYPE_LUN = 11
PERFORMANCE_TYPE_STORAGE_POOL = 216


def get_performance_perfdata(prefix, samples, indicators=None):
    """
    Turn the samples `get_performance()` returned into performance data.

    ### Parameters
    - **prefix** (`str`):
      What every metric name starts with, normally the object's sanitised UUID.
    - **samples** (`dict`):
      Indicator number to value, as `get_performance()` returns it.
    - **indicators** (`dict`, optional):
      The descriptor table to read the label, unit and conversion factor from. Defaults
      to `PERFORMANCE_INDICATORS`.

    ### Returns
    - **str**: The performance data, ready to be appended to a consumer's own.

    ### Notes
    - An indicator the table does not describe is skipped rather than emitted under its
      bare number. A number is not a metric name a dashboard can be built on, and the
      appliance answers with indicators a consumer never asked for on some firmware.
    - A percentage carries `0` and `100` as its bounds; everything else only a lower bound
      of `0`. None of these counters can be negative.
    - A value that does not parse as a number is skipped for the same reason a missing one
      is: the appliance sends `'--'` for a counter it is not collecting.

    ### Example
    >>> get_performance_perfdata('207_0A', {'22': '4711', '370': '385'})
    "'207_0A_total_iops'=4711;;;0 '207_0A_avg_io_response_time'=0.000385s;;;0 "
    """
    if indicators is None:
        indicators = PERFORMANCE_INDICATORS

    perfdata = ''
    for data_id, raw in samples.items():
        descriptor = indicators.get(as_code(data_id))
        if descriptor is None:
            continue
        label, uom, factor = descriptor
        try:
            value = float(raw) * factor
        except (TypeError, ValueError):
            continue
        perfdata += base.get_perfdata(
            f'{prefix}_{label}',
            round(value, 6) if factor < 1 else round(value),
            uom=uom,
            _min=0,
            _max=100 if uom == '%' else None,
        )
    return perfdata


def get_product_mode(pm):
    """
    Convert a Huawei product mode code into a human-readable description.

    This function translates numeric product mode codes for Huawei Dorado storage systems
    into descriptive text, making it easier to identify hardware models.

    ### Parameters
    - **pm** (`int` or `str`):
      The product mode code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the product model, including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_product_mode(812)
    'Dorado 5000 V6 (NVMe) (812)'

    >>> get_product_mode('818')
    'Dorado 18000 V6 (NVMe) (818)'
    """
    mapping = {
        806: 'Dorado6000 V3 (806)',
        811: 'Dorado 5000 V6 (SAS) (811)',
        812: 'Dorado 5000 V6 (NVMe) (812)',
        813: 'Dorado 6000 V6 (SAS) (813)',
        814: 'Dorado 6000 V6 (NVMe) (814)',
        815: 'Dorado 8000 V6 (SAS) (815)',
        816: 'Dorado 8000 V6 (NVMe) (816)',
        817: 'Dorado 18000 V6 (SAS) (817)',
        818: 'Dorado 18000 V6 (NVMe) (818)',
        819: 'Dorado 3000 V6 (SAS) (819)',
        821: 'Dorado 5000 V6 (IP SAS) (821)',
        822: 'Dorado 6000 V6 (IP SAS) (822)',
        823: 'Dorado 8000 V6 (IP SAS) (823)',
        824: 'Dorado 18000 V6 (IP SAS) (824)',
        825: 'Dorado 3000 V6 (825)',
        826: 'Dorado 5000 V6 (826)',
        827: 'Dorado 6000 V6 (827)',
        828: 'Dorado 6000 V6 (828)',
        829: 'Dorado 8000 V6 (829)',
        830: 'Dorado 18000 V6 (830)',
        831: 'Dorado 18000 V6 (831)',
        832: 'Dorado 18000 V6 (832)',
        833: 'OceanStor 5310 (833)',
        834: 'OceanStor 5510 (834)',
        835: 'OceanStor 5610 (835)',
        836: 'OceanStor 6810 (836)',
        837: 'OceanStor 18510 (837)',
        838: 'OceanStor 18810 (838)',
        851: 'OceanStor Dorado 2000 (851)',
        852: 'OceanProtect X3000 (852)',
        853: 'OceanStor 2200 (853)',
        854: 'OceanStor 2220 (854)',
        855: 'OceanStor 2600 (855)',
        900: 'OceanStor Dorado 5000 (900)',
        901: 'OceanStor Dorado 5000 (901)',
        902: 'OceanStor Dorado 6000 (902)',
        903: 'OceanStor Dorado 6000 (903)',
        904: 'OceanStor Dorado 8000 (904)',
        905: 'OceanStor Dorado 8000 (905)',
        906: 'OceanStor Dorado 18000 (906)',
        907: 'OceanStor Dorado 18000 (907)',
        908: 'OceanStor Dorado 3000 (908)',
        909: 'OceanStor Dorado 5000 (909)',
        910: 'OceanStor Dorado 6000 (910)',
        911: 'OceanStor Dorado 8000 (911)',
        912: 'OceanStor Dorado 18000 (912)',
        913: 'OceanStor Dorado 3000 (913)',
        914: 'OceanStor Dorado 5000 (914)',
        915: 'OceanStor Dorado 6000 (915)',
        917: 'OceanStor Dorado 8000 (917)',
        918: 'OceanStor Dorado 18000 (918)',
        919: 'OceanStor Dorado 18000 (919)',
        922: 'OceanStor Dorado 2100 (922)',
        923: 'OceanStor 5310 Capacity Flash Storage (923)',
        924: 'OceanStor 5510 Capacity Flash Storage (924)',
    }
    return mapping.get(as_code(pm), 'Unknown')


def get_runlevel(rl):
    """
    Convert a Huawei device run level code into a human-readable description.

    This function translates numeric run level codes reported by Huawei appliances into readable
    text. It makes it easier to interpret device operation levels.

    ### Parameters
    - **rl** (`int` or `str`):
      The run level code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the run level, including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_runlevel(1)
    'normal (1)'

    >>> get_runlevel('2')
    'high (2)'
    """
    mapping = {
        0: 'low (0)',
        1: 'normal (1)',
        2: 'high (2)',
    }
    return mapping.get(as_code(rl), 'Unknown')


def get_running_status(rs):
    """
    Convert a Huawei device running status code into a human-readable description.

    This function translates numeric running status codes reported by Huawei appliances into
    descriptive text for easier interpretation of device operational states.

    ### Parameters
    - **rs** (`int` or `str`):
      The running status code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the running status, including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Not scoped to `HyperMetroDomain` and `dr_star`. Both renumber `RUNNINGSTATUS` instead
      of sharing this enumeration, and both collide on the low codes this function is most
      likely to be handed: `2` is faulty on a HyperMetro domain and disabled on a DR Star
      trio, not running. Read through this function either would look healthy, so they have
      their own mappings in `get_hypermetro_domain_running_status()` and
      `get_dr_star_running_status()`.
    - Code `94` is the one value whose meaning differs between the two documented firmware
      generations: 6.1.0 defines it as error, V700R001C10 as faulty. The response carries no
      firmware marker, so it renders as `'Error/Faulty'`, which holds under both revisions.
    - Codes `16` and `112` follow the V700R001C10 wording, which is the newer of the two
      references. 6.1.0 words `16` as `reconstruction`, and `112` alongside its own
      `faulty restoration`, which reads as "restoring after a fault" and therefore states
      the opposite of what the code means.

    ### Example
    >>> get_running_status(1)
    'Normal (1)'

    >>> get_running_status('47')
    'Powering off (47)'
    """
    # The table is the union of the codes both REST Interface References list. The
    # appliance's SNMP MIB defines about twice as many, which makes this look incomplete
    # when the two interfaces are compared. The REST API never sends the extra ones.
    # RUNNINGSTATUS is a shared enumeration across many object types, so a
    # single object only ever reports a subset of these codes. The union is
    # kept complete here so that every documented state renders a readable
    # label instead of 'Unknown'.
    mapping = {
        0: 'Unknown (0)',
        1: 'Normal (1)',
        2: 'Running (2)',
        3: 'Not running (3)',
        5: 'Sleep in High Temperature (5)',
        8: 'Spin down (8)',
        10: 'Link up (10)',
        11: 'Link down (11)',
        12: 'Powering on (12)',
        13: 'Powered off (13)',
        14: 'Pre-Copy (14)',
        16: 'Rebuilding (16)',
        23: 'Synchronizing (23)',
        25: 'Unsynchronized (25)',
        26: 'Split (26)',
        27: 'Online (27)',
        28: 'Offline (28)',
        30: 'Enabled (30)',
        31: 'Disabled (31)',
        32: 'Balancing (32)',
        33: 'To be recovered (33)',
        34: 'Interrupted (34)',
        35: 'Invalid (35)',
        37: 'Queuing (37)',
        41: 'Paused (41)',
        43: 'Activated (43)',
        44: 'Rolling back (44)',
        45: 'Inactive (45)',
        46: 'Idle (46)',
        47: 'Powering off (47)',
        48: 'Charging (48)',
        49: 'Charging completed (49)',
        50: 'Discharging (50)',
        51: 'Upgrading (51)',
        53: 'Initializing (53)',
        74: 'Migration fault (74)',
        75: 'Migrating (75)',
        76: 'Migration completed (76)',
        89: 'Overloaded (89)',
        93: 'Forcibly started (93)',
        94: 'Error/Faulty (94)',
        96: 'Partition migrating (96)',
        100: 'To be synchronized (100)',
        101: 'Connecting (101)',
        103: 'Power-on failed (103)',
        105: 'Abnormal (105)',
        106: 'Deleting (106)',
        107: 'Modifying (107)',
        110: 'Standby (110)',
        111: 'Stopping (111)',
        112: 'Rollback failure (112)',
        114: 'Erasing (114)',
        115: 'Verifying (115)',
        117: 'Removing (117)',
        118: 'Air Gap link down (118)',
        119: 'Creating (119)',
    }
    return mapping.get(as_code(rs), 'Unknown')


# `RUNNINGSTATUS` codes that report a failure whatever object they are read from. The rest of
# the enumeration is object-dependent - `Powered off (13)` is a fault on a controller and the
# resting state of a spare power module, `Charging (48)` is routine on a BBU and nonsense
# elsewhere - so a caller states its own healthy codes through `ok_codes` and everything left
# over warns.
#
# `ok_codes` is consulted before this set, so an object for which one of these codes really is
# healthy can still declare it as such.
#
# Three of them are less obvious than the rest. `Not running (3)` is the plain statement that
# the object is not doing its job. `Sleep in High Temperature (5)` is a disk the array parked
# because it got too hot, so it reports both a component out of service and a cooling problem
# behind it. `To be synchronized (100)` is a replication or HyperMetro relationship that is
# not mirroring, which means the second copy an operator relies on for a site failure does
# not exist right now.
_FAILED_RUNNING_STATES = frozenset({3, 5, 28, 35, 74, 94, 100, 103, 105, 112})


def get_running_status_state(rs, ok_codes):
    """
    Convert a Huawei running status code into the state a check reports for it.

    ### Parameters
    - **rs** (`int` or `str`):
      The running status code to interpret.
    - **ok_codes** (iterable of `int`):
      The codes that count as healthy for the object being checked. A disk passes `(1, 27)`,
      a controller `(1, 2, 27)`, a backup power module `(1, 2, 27, 48, 49)`.

    ### Returns
    - **int**:
      `STATE_OK` for a code the caller listed as healthy, `STATE_CRIT` for a code that reports
      a failure on any object, `STATE_WARN` for every other code, including one the enumeration
      does not know and a missing value.

    ### Notes
    - Unlike `HEALTHSTATUS`, this enumeration is not shared: the same code means different
      things on different objects, and there is no code that is healthy everywhere. That is why
      the healthy set is the caller's to state and cannot live in this function.
    - A code the enumeration does not know warns rather than passing as OK, for the same reason
      as in `get_health_status_state()`.

    ### Example
    >>> get_running_status_state(27, (1, 27)) == STATE_OK
    True

    >>> get_running_status_state('94', (1, 27)) == STATE_CRIT
    True

    >>> get_running_status_state(51, (1, 27)) == STATE_WARN
    True
    """
    code = as_code(rs)
    if code is not None and code in ok_codes:
        return STATE_OK
    if code in _FAILED_RUNNING_STATES:
        return STATE_CRIT
    return STATE_WARN


def get_switch_status(st):
    """
    Convert a `SWITCHSTATUS` code into a human-readable description.

    ### Parameters
    - **st** (`int` or `str`):
      The switch status code to interpret.
      A missing or malformed value renders as `'Unknown'`.

    ### Returns
    - **str**:
      A human-readable description of the switch status.
      Returns `'Unknown'` if the code is not recognized.

    ### Notes
    - Scoped to the field named `SWITCHSTATUS`, not to on/off fields in general. Other
      switch-like fields number their states differently and would be rendered wrongly:
      `QUOTASWITCHSTATUS`, for example, uses `0` for off, `1` for on and `2` for
      initializing, so `2` would come out as `'Off'` here.

    ### Example
    >>> get_switch_status(1)
    'On'

    >>> get_switch_status('2')
    'Off'
    """
    mapping = {
        1: 'On',
        2: 'Off',
    }
    return mapping.get(as_code(st), 'Unknown')


def get_uuid(data):
    """
    Build the Universally Unique Identifier (UUID) for a managed object.

    This function creates a UUID by combining the object type and ID fields from
    a given dictionary. The UUID is typically used to query performance statistics
    or uniquely identify resources.

    ### Parameters
    - **data** (`dict`):
      A dictionary containing the keys `'TYPE'` and `'ID'`.

    ### Returns
    - **str**:
      The UUID in the format `'TYPE:ID'`, e.g., `'207:0A'`. A field the appliance did not
      report is rendered as `'--'`, so an incomplete object still yields a printable
      identifier instead of aborting the caller with a `KeyError`.

    ### Example
    >>> get_uuid({'TYPE': '207', 'ID': '0A'})
    '207:0A'

    >>> get_uuid({'TYPE': '207'})
    '207:--'
    """
    return f'{data.get("TYPE", "--")}:{data.get("ID", "--")}'


def sectors2bytes(sectors, sector_size=DEFAULT_SECTOR_SIZE):
    """
    Convert a sector count reported by the appliance into bytes.

    Every capacity in the API is counted in sectors. A consumer that reports one has to
    convert it, so that a dashboard can label its axis without knowing the sector size.

    ### Parameters
    - **sectors** (`int`, `str` or `None`):
      The sector count as the API reported it.
    - **sector_size** (`int`, optional):
      Bytes per sector. `system/` reports the appliance's own value in its `SECTORSIZE`
      field; pass that where it is available and leave the default in place otherwise.

    ### Returns
    - **int** or **None**:
      The capacity in bytes, or `None` for a value that cannot be used.

    ### Notes
    - A negative sector count is `None` rather than a negative capacity. The appliance uses
      `-1` for a capacity it does not report, and `4294967295` and its 64-bit sibling for
      the same purpose on other fields; a consumer that graphs those gets a spike instead
      of a gap.
    - `None` is also what a missing field yields, which is what `lib.base.get_perfdata()`
      turns into no metric at all.

    ### Example
    >>> sectors2bytes('2048')
    1048576

    >>> sectors2bytes('2048', 4096)
    8388608

    >>> sectors2bytes('-1') is None
    True
    """
    value = as_code(sectors)
    if value is None or value < 0:
        return None
    return value * sector_size
