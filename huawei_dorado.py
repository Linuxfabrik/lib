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

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026080501'

import time as _time

from . import base, cache, time, url


def _as_code(value):
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
    >>> _as_code('27')
    27
    >>> _as_code(None) is None
    True
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_controller_model(cm):
    """
    Convert a Huawei controller model code into a human-readable description.

    This function translates numeric controller model codes from Huawei storage systems into
    descriptive text for better hardware identification.

    ### Parameters
    - **cm** (`int` or `str`):
      The controller model code to interpret. If a string is passed, it will be converted to integer.

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
    return mapping.get(_as_code(cm), 'Unknown')


def get_cp_type(cp):
    """
    Convert a consistency protection (CP) type code into a human-readable description.

    This function translates numeric CP type codes from Huawei storage systems into descriptive
    labels that indicate the type of quorum mechanism in use.

    ### Parameters
    - **cp** (`int` or `str`):
      The CP type code to interpret. If a string is passed, it will be converted to integer.

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
    return mapping.get(_as_code(cp), 'Unknown')


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
        - `DEVICE_ID` (`str`): Unique device identifier.
        - `USERNAME` (`str`): Login username.
        - `PASSWORD` (`str`): Login password.
        - `SCOPE` (`str`): Authentication scope.
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.
        - `CACHE_EXPIRE` (`int`): Cache expiration time in minutes.
    - **force_relogin** (`bool`, optional):
      If `True`, ignore any cached token and perform a fresh login, overwriting the cache.
      Used to recover from a cached session that the appliance no longer accepts (for example
      after a controller reboot, a manual session reset, or the server-side 20-minute timeout).

    ### Returns
    - **tuple** (`str`, `str`):
      - `ibase_token` (str): The API session token (iBaseToken).
      - `cookie` (str): The session cookie.

    ### Notes
    - Tokens are stored in cache keys:
      - `huawei-{DEVICE_ID}-ibasetoken`
      - `huawei-{DEVICE_ID}-cookie`
    - If login is required, the request is sent as serialized JSON with headers.
    - A rejected login aborts the caller (UNKNOWN) instead of returning an empty token.
      The appliance answers a wrong password, an expired password or a locked account with
      HTTP 200 and a non-zero `error.code`, so without this check the empty token would travel
      into the next request header and surface as an unrelated type error. Failing here also
      keeps a wrong password from being replayed, which would drive the account towards the
      appliance's lockout threshold.

    ### Example
    >>> ibasetoken, cookie = get_creds(args)
    """
    token_key = f'huawei-{args.DEVICE_ID}-ibasetoken'
    cookie_key = f'huawei-{args.DEVICE_ID}-cookie'

    if not force_relogin:
        ibasetoken = cache.get(token_key)
        cookie = cache.get(cookie_key)
        # Both are required to build the request header, and both are cached with the same
        # expiry. Reuse them only as a complete pair, so a half-populated cache re-logs in
        # instead of sending an unusable header.
        if ibasetoken and cookie:
            return ibasetoken, cookie

    uri = f'{args.URL}/deviceManager/rest/{args.DEVICE_ID}/sessions'
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

    response_json = result.get('response_json', {})
    ibasetoken = response_json.get('data', {}).get('iBaseToken')
    # lib.url lower-cases all response header names (RFC 9110, section 5.1).
    cookie = result.get('response_header', {}).get('set-cookie')

    if not ibasetoken or not cookie:
        error = response_json.get('error', {})
        reason = error.get('description') or 'no session token returned'
        code = error.get('code', 'n/a')
        base.cu(f'Login at {args.URL} failed: {reason} (code {code}).')

    expire = time.now() + args.CACHE_EXPIRE * 60
    cache.set(token_key, ibasetoken, expire)
    cache.set(cookie_key, cookie, expire)

    return ibasetoken, cookie


def get_data(endpoint, args, params=''):
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
      The API endpoint to call (relative path after the device ID).
    - **args** (object):
      An object containing:
        - `URL` (`str`): Base API URL.
        - `DEVICE_ID` (`str`): Device ID.
        - `INSECURE` (`bool`): Disable SSL verification.
        - `NO_PROXY` (`bool`): Ignore proxy settings.
        - `TIMEOUT` (`int`): Timeout for API requests.
    - **params** (`str`, optional):
      Additional URL parameters (starting with `?`, if any). Default is empty. The string is
      appended to the request URL verbatim, so the caller is responsible for percent-encoding
      it; never build it from data the appliance itself returned.

    ### Returns
    - **dict**:
      The parsed JSON response from the API, plus an extra `counter` key showing how many attempts
      were made.

    ### Notes
    - Makes at most three attempts, forcing a fresh login before the second one, and waits one
      second between attempts. The retry count is kept low on purpose so the total runtime stays
      within the monitoring server's check timeout.
    - The API reference documents no dedicated "session expired" status code, so a fresh login is
      triggered on any non-zero error rather than by matching a specific code.

    ### Example
    >>> get_data('disk/list', args)
    {
        'error': {'code': 0},
        'data': {...},
        'counter': 1
    }
    """
    uri = f'{args.URL}/deviceManager/rest/{args.DEVICE_ID}/{endpoint}{params}'

    max_attempts = 3
    counter = 0
    result = {}

    for attempt in range(1, max_attempts + 1):
        counter = attempt
        # On the second attempt, drop the cached session and log in again; a
        # rejected request is most likely an expired session that retrying
        # with the same token cannot fix. The third attempt then reuses that
        # fresh token to absorb a remaining transient error.
        ibasetoken, cookie = get_creds(args, force_relogin=attempt == 2)
        header = {
            'Content-Type': 'application/json',
            'iBaseToken': ibasetoken,
            'Cookie': cookie,
        }
        result = base.coe(
            url.fetch_json(
                uri,
                header=header,
                insecure=args.INSECURE,
                no_proxy=args.NO_PROXY,
                timeout=args.TIMEOUT,
            )
        )
        if result.get('error', {}).get('code') in (0, '0'):
            break
        if attempt < max_attempts:
            _time.sleep(1)

    result['counter'] = counter
    return result


def get_enclosure_model(em):
    """
    Convert a Huawei enclosure model code into a human-readable description.

    This function translates numeric enclosure model codes from Huawei storage systems into
    descriptive text to simplify hardware identification.

    ### Parameters
    - **em** (`int` or `str`):
      The enclosure model code to interpret. If a string is passed, it will be converted to integer.

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
    }
    return mapping.get(_as_code(em), 'Unknown')


def get_health_status(hs):
    """
    Convert a Huawei health status code into a human-readable description.

    This function translates numeric health status codes returned by Huawei appliances into
    descriptive text, making it easier to interpret device health states.

    ### Parameters
    - **hs** (`int` or `str`):
      The health status code to interpret. If a string is passed, it will be converted to integer.

    ### Returns
    - **str**:
      A human-readable description of the health status, including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

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
        17: 'Single link (17)',
        18: 'Offline (18)',
    }
    return mapping.get(_as_code(hs), 'Unknown')


def get_host_access_state(has):
    """
    Convert a host access state code into a human-readable description.

    This function translates the numeric read/write setting a Huawei storage system reports for
    a secondary resource (`SECRESACCESS`) into a descriptive label.

    ### Parameters
    - **has** (`int` or `str`):
      The host access state code to interpret. If a string is passed, it will be converted to integer.

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
    return mapping.get(_as_code(has), 'Unknown')


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

    return models.get(_as_code(im), 'Unknown')


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

    return runmodes.get(_as_code(rm), 'Unknown')


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

    return led_status.get(_as_code(st), 'Unknown')


def get_logic_type(lt):
    """
    Convert a Huawei logic type code into a human-readable description.

    This function translates numeric logic type codes reported by Huawei storage appliances
    into descriptive text to identify enclosure and system types.

    ### Parameters
    - **lt** (`int` or `str`):
      The logic type code to interpret. If a string is passed, it will be converted to integer.

    ### Returns
    - **str**:
      A human-readable description of the logic type.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_logic_type(1)
    'Controller Enclosure'

    >>> get_logic_type('3')
    'Management Switch'
    """
    mapping = {
        0: 'Expansion Enclosure (Disk Enclosure)',
        1: 'Controller Enclosure',
        2: 'Data Switch',
        3: 'Management Switch',
        4: 'Management Server',
    }
    return mapping.get(_as_code(lt), 'Unknown')


def get_os(os):
    """
    Convert an operating system (OS) code into a human-readable description.

    This function translates numeric OS codes from Huawei storage systems into descriptive
    names for better interpretation of connected or managed hosts.

    ### Parameters
    - **os** (`int` or `str`):
      The OS code to interpret. If a string is passed, it will be converted to integer.

    ### Returns
    - **str**:
      A human-readable description of the operating system.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_os(7)
    'VMware ESX'

    >>> get_os('0')
    'Linux'
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
    }
    return mapping.get(_as_code(os), 'Unknown')


def get_product_mode(pm):
    """
    Convert a Huawei product mode code into a human-readable description.

    This function translates numeric product mode codes for Huawei Dorado storage systems
    into descriptive text, making it easier to identify hardware models.

    ### Parameters
    - **pm** (`int` or `str`):
      The product mode code to interpret. If a string is passed, it will be converted to integer.

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
    return mapping.get(_as_code(pm), 'Unknown')


def get_role(role):
    """
    Convert a role code into a human-readable description.

    This function translates numeric role codes from Huawei storage systems into descriptive
    labels representing the role of a device or component.

    ### Parameters
    - **role** (`int` or `str`):
      The role code to interpret. If a string is passed, it will be converted to integer.

    ### Returns
    - **str**:
      A human-readable description of the role.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_role(1)
    'Primary'

    >>> get_role('2')
    'Secondary'
    """
    mapping = {
        0: 'Member',
        1: 'Primary',
        2: 'Secondary',
    }
    return mapping.get(_as_code(role), 'Unknown')


def get_runlevel(rl):
    """
    Convert a Huawei device run level code into a human-readable description.

    This function translates numeric run level codes reported by Huawei appliances into readable
    text. It makes it easier to interpret device operation levels.

    ### Parameters
    - **rl** (`int` or `str`):
      The run level code to interpret. If a string is passed, it will be converted to integer.

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
    return mapping.get(_as_code(rl), 'Unknown')


def get_running_status(rs):
    """
    Convert a Huawei device running status code into a human-readable description.

    This function translates numeric running status codes reported by Huawei appliances into
    descriptive text for easier interpretation of device operational states.

    ### Parameters
    - **rs** (`int` or `str`):
      The running status code to interpret. If a string is passed, it will be converted to integer.

    ### Returns
    - **str**:
      A human-readable description of the running status, including the original code in brackets.
      Returns `'Unknown'` if the code is not recognized.

    ### Example
    >>> get_running_status(1)
    'Normal (1)'

    >>> get_running_status('47')
    'Powering off (47)'
    """
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
        16: 'Reconstruction (16)',
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
        94: 'Error (94)',
        96: 'Partition migrating (96)',
        100: 'To be synchronized (100)',
        101: 'Connecting (101)',
        103: 'Power-on failed (103)',
        105: 'Abnormal (105)',
        106: 'Deleting (106)',
        107: 'Modifying (107)',
        110: 'Standby (110)',
        111: 'Stopping (111)',
        112: 'Faulty restoration (112)',
        114: 'Erasing (114)',
        115: 'Verifying (115)',
        117: 'Removing (117)',
        118: 'Air Gap link down (118)',
        119: 'Creating (119)',
    }
    return mapping.get(_as_code(rs), 'Unknown')


def get_switch_status(st):
    """
    Convert a switch status code into a human-readable description.

    This function translates numeric switch status codes from Huawei systems into descriptive
    text for easier interpretation.

    ### Parameters
    - **st** (`int` or `str`):
      The switch status code to interpret. If a string is passed, it will be converted to integer.

    ### Returns
    - **str**:
      A human-readable description of the switch status.
      Returns `'Unknown'` if the code is not recognized.

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
    return mapping.get(_as_code(st), 'Unknown')


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
