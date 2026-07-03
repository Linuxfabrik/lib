#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Huawei related functions that are
needed by Huawei check plugins.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026070301'

import time as _time

from . import base, cache, time, url


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
    'V6R1C00 2U2C mid-range PALM control board'

    >>> get_controller_model('4144')
    'V6R3C00 2U2C low-end NVMe control board'
    """
    cm = int(cm)

    mapping = {
        4127: 'V6R1C00 2U2C mid-range PALM control board',
        4128: 'V6R1C00 2U2C mid-range _SAS control board',
        4129: 'V6R1C00 2U2C SAS entry-level control board (Hi1620S)',
        4132: 'V6R1C00 4U4C high-end control board',
        4135: 'V6R1C00 2U2C mid-range control Board',
        4136: 'V6R1C00 2U2C mid-range SAS1711 control board',
        4137: 'V6R1C00 2U2C SAS 1711 entry-level control board (Hi1620S)',
        4140: 'V6R1C00 4U4C high-end 1711 control board',
        4141: 'V6R1C00 2U2C mid-range SAS 1711 control board (100GE extension board)',
        4142: 'V6R1C00 2U2C mid-range SAS control board (100GE extension board)',
        4144: 'V6R3C00 2U2C low-end NVMe control board',
    }
    return mapping.get(cm, 'Unknown')


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
    cp = int(cp)

    mapping = {
        1: 'Quorum Server',
        2: 'Quorum Disk',
        3: 'None',
    }
    return mapping.get(cp, 'Unknown')


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

    ### Example
    >>> ibasetoken, cookie = get_creds(args)
    """
    token_key = f'huawei-{args.DEVICE_ID}-ibasetoken'
    cookie_key = f'huawei-{args.DEVICE_ID}-cookie'

    if not force_relogin:
        ibasetoken = cache.get(token_key)
        cookie = cache.get(cookie_key)
        if ibasetoken:
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

    ibasetoken = result.get('response_json', {}).get('data', {}).get('iBaseToken')
    # lib.url lower-cases all response header names (RFC 9110, section 5.1).
    cookie = result.get('response_header', {}).get('set-cookie')

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
      Additional URL parameters (starting with `?`, if any). Default is empty.

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
        if result.get('error', {}).get('code') == 0:
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
    em = int(em)

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
    return mapping.get(em, 'Unknown')


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
    hs = int(hs)

    mapping = {
        1: 'Normal (1)',
        2: 'Faulty (2)',
        3: 'About to fail (3)',
        4: 'Partially damaged (4)',
        5: 'Degraded (5)',
        9: 'Inconsistent (9)',
        11: 'No Input (11)',
        12: 'Low Battery (12)',
        14: 'Invalid (14)',
        15: 'Write-protected (15)',
        17: 'Single link (17)',
        18: 'Offline (18)',
    }
    return mapping.get(hs, 'Unknown')


def get_host_access_state(has):
    """
    Convert a host access state code into a human-readable description.

    This function translates numeric host access state codes from Huawei storage systems into
    descriptive labels indicating access permissions.

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
    'R/W'
    """
    has = int(has)

    mapping = {
        1: 'Forbidden',
        2: 'Read-only',
        3: 'R/W',
        5: 'Unknown',
    }
    return mapping.get(has, 'Unknown')


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
    im = int(im)

    models = {
        516: '4 ports FE 1 Gbit/s ETH I/O module',
        518: '4 ports BE 12 Gbit/s SAS I/O module',
        529: 'AI Accelerator Card',
        535: 'AI Accelerator Card',
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
        2323: '4 ports FE 10 Gbit/s ROCE I/O module',
        2324: '4 ports FE 25 Gbit/s ROCE I/O module',
        2325: '4 ports FE 10 Gbit/s ROCE I/O module',
        2326: '4 ports FE 25 Gbit/s ROCE I/O module',
        2327: '2 ports FE 40 Gbit/s ROCE I/O module',
        2328: '2 ports FE 100 Gbit/s ROCE I/O module',
        2329: '2 ports FE 40 Gbit/s ROCE I/O module',
        2330: '2 ports FE 10  Gbit/s ROCE I/O module',
        2331: '4 ports FE 10  Gbit/s ETH I/O module',
        2332: '4 ports FE 10 Gbit/s ETH I/O module',
        2333: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2334: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2335: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2336: '4 ports FE 10 Gbit/s ETH I/O module',
        2337: '4 ports FE 25 Gbit/s ETH I/O module',
        2338: '4 ports SO 25 Gbit/s RDMA I/O module',
        2339: '4 ports FE 10 Gbit/s ROCE I/O module',
        2340: '4 ports FE 25 Gbit/s ROCE I/O module',
        2341: '4 ports FE 8 Gbit/s Fibre Channel I/O module',
        2342: '4 ports FE 16 Gbit/s Fibre Channel I/O module',
        2343: '4 ports FE 32 Gbit/s Fibre Channel I/O module',
        2344: '4 ports FE 10 Gbit/s ETH I/O module',
        2345: '4 ports FE 25 Gbit/s ETH I/O module',
        2346: '4 ports FE 10 Gbit/s ROCE I/O module',
        2347: '4 ports FE 25 Gbit/s ROCE I/O module',
        2348: '2 ports FE 40 Gbit/s ETH I/O module',
        2349: '2 ports FE 100 Gbit/s ETH I/O module',
        2350: '2 ports BE 100 Gbit/s RDMA I/O module',
        2351: '2 ports SO 100 Gbit/s RDMA I/O module',
        2352: '2 ports FE 40 Gbit/s ROCE I/O module',
        2353: '2 ports FE 100 Gbit/s ROCE I/O module',
        2354: '2 ports FE 40 Gbit/s ETH I/O module',
        2355: '2 ports FE 100 Gbit/s ETH I/O module',
        2356: '2 ports BE 100 Gbit/s RDMA I/O module',
        2357: '2 ports SO 100 Gbit/s RDMA I/O module',
        2358: '2 ports FE 40 Gbit/s ROCE I/O module',
        2359: '2 ports FE 100 Gbit/s ROCE I/O module',
        2360: '4 ports FE 10 Gbit/s ETH I/O module',
        2361: '4 ports SO 25 Gbit/s RDMA I/O module',
        2362: '2 ports SO 100 Gbit/s RDMA I/O module',
        2363: '2 ports SO 100 Gbit/s RDMA I/O module',
        4133: 'System Management Module',
        4134: 'System Management Module',
    }

    return models.get(im, 'Unknown')


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

    ### Example
    >>> get_interface_runmode(1)
    'FC'
    """
    rm = int(rm)

    runmodes = {
        1: 'FC',
        2: 'FCoE/iSCSI',
        3: 'Cluster',
        4: 'Ethernet',
        5: 'RoCE',
    }

    return runmodes.get(rm, 'Unknown')


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
    st = int(st)

    led_status = {
        0: 'Off',
        1: 'On',
    }

    return led_status.get(st, 'Unknown')


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
    lt = int(lt)
    mapping = {
        0: 'Expansion Enclosure (Disk Enclosure)',
        1: 'Controller Enclosure',
        2: 'Data Switch',
        3: 'Management Switch',
        4: 'Management Server',
    }
    return mapping.get(lt, 'Unknown')


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
    os = int(os)

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
        9: 'Windows Server 2012',
        10: 'Oracle VM',
        11: 'OpenVMS',
        12: 'Oracle_VM_Server_for_x86',
        13: 'Oracle_VM_Server_for_SPARC',
    }
    return mapping.get(os, 'Unknown')


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
    pm = int(pm)

    mapping = {
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
        825: 'Dorado 3000 V6  (825)',
        826: 'Dorado 5000 V6 (826)',
        827: 'Dorado 6000 V6 (827)',
        828: 'Dorado 6000 V6 (828)',
        829: 'Dorado 8000 V6 (829)',
        830: 'Dorado 18000 V6 (830)',
        831: 'Dorado 18000 V6 (831)',
        832: 'Dorado 18000 V6 (832)',
    }
    return mapping.get(pm, 'Unknown')


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
    role = int(role)

    mapping = {
        0: 'Member',
        1: 'Primary',
        2: 'Secondary',
    }
    return mapping.get(role, 'Unknown')


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
    rl = int(rl)

    mapping = {
        0: 'low (0)',
        1: 'normal (1)',
        2: 'high (2)',
    }
    return mapping.get(rl, 'Unknown')


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
    rs = int(rs)
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
        93: 'Forcibly started (93)',
        94: 'Error (94)',
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
    }
    return mapping.get(rs, 'Unknown')


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
    st = int(st)
    mapping = {
        1: 'On',
        2: 'Off',
    }
    return mapping.get(st, 'Unknown')


def get_uuid(data):
    """
    Build the Universally Unique Identifier (UUID) for a managed object.

    This function creates a UUID by combining the object type and ID fields from
    a given dictionary. The UUID is typically used to query performance statistics
    or uniquely identify resources.

    ### Parameters
    - **data** (`dict`):
      A dictionary containing at least the keys `'TYPE'` and `'ID'`.

    ### Returns
    - **str**:
      The UUID in the format `'TYPE:ID'`, e.g., `'207:0A'`.

    ### Example
    >>> get_uuid({'TYPE': '207', 'ID': '0A'})
    '207:0A'
    """
    return '{}:{}'.format(data['TYPE'], data['ID'])
