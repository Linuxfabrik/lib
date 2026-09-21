#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library collects some LibreNMS related functions that are
needed by more than one LibreNMS consumer."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026092101'

from . import (
    base,  # pylint: disable=C0413
    url,  # pylint: disable=C0413
)
from .globals import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN


def get_data(args, uri=''):
    """
    Fetch data from the LibreNMS API.

    This function builds the API URL using the base URL and endpoint URI. It authenticates using
    the provided token and fetches the data. If the API returns an error status, it exits or
    handles the error appropriately.

    Parameters
    ----------
    args : object
        An object containing:

          - `URL` (`str`): Base URL of the LibreNMS API.
          - `TOKEN` (`str`): API authentication token.
          - `INSECURE` (`bool`): Whether to disable SSL verification.
          - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
          - `PROXY` (`str`, optional): Proxy to reach the target through, overriding the
            proxy the environment names.
          - `TIMEOUT` (`int`): Request timeout in seconds.
          - `ALWAYS_OK` (`bool`): Whether to always exit cleanly even on errors.
    uri : str, optional
        Endpoint URI to append to the base URL. Defaults to `''`.

    Returns
    -------
    dict
        The fetched data as a parsed JSON dictionary.

    Notes
    -----
    - Automatically ensures correct URL formatting.
    - If the response status is not `ok`, the function exits or handles the error.

    Examples
    --------
    >>> result = get_data(args, uri='/api/v0/devices')
    """

    url_base = args.URL.rstrip('/')
    endpoint = f'/{uri.lstrip("/")}'
    full_url = f'{url_base}{endpoint}'
    headers = {'X-Auth-Token': args.TOKEN}

    result = base.coe(
        url.fetch_json(
            full_url,
            header=headers,
            insecure=args.INSECURE,
            no_proxy=args.NO_PROXY,
            proxy=getattr(args, 'PROXY', None),
            timeout=args.TIMEOUT,
        )
    )

    if result.get('status', '').lower() != 'ok':
        base.oao(
            f'Error fetching data: "{result}"',
            STATE_UNKNOWN,
            always_ok=args.ALWAYS_OK,
        )

    return result


def get_state(librestate, severity='crit'):
    """
    Translate LibreNMS service state to a Nagios-compatible state.

    LibreNMS encodes the alert lifecycle in `alerts.state` (see
    `LibreNMS/Enum/AlertState.php`):
      - 0 = CLEAR / RECOVERED
      - 1 = ACTIVE
      - 2 = ACKNOWLEDGED
      - 3 = WORSE
      - 4 = BETTER
      - 5 = CHANGED

    ACTIVE, WORSE, BETTER and CHANGED all represent an open, notifiable
    alert, so they map to WARN/CRIT. ACKNOWLEDGED and CLEAR map to OK.

    Parameters
    ----------
    librestate : int
        The LibreNMS state code to translate.
    severity : str, optional
        If `crit`, maps alert states to critical. Otherwise, maps to warning.

    Returns
    -------
    int
        Nagios-compatible state code:

          - 0 = OK
          - 1 = WARNING
          - 2 = CRITICAL

    Notes
    -----
    - Assumes STATE_OK, STATE_WARN, and STATE_CRIT constants are defined.

    Examples
    --------
    >>> get_state(0)
    0
    >>> get_state(1, severity='warn')
    1
    >>> get_state(1, severity='crit')
    2
    >>> get_state(3, severity='crit')
    2
    """

    if librestate not in (1, 3, 4, 5):
        return STATE_OK
    return STATE_CRIT if severity == 'crit' else STATE_WARN
