#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""This library collects some Keycloak related functions that are
needed by more than one Keycloak plugin.

Typical use case:
```python
    # Discover the OIDC endpoints for the realm (no authentication needed),
    # obtain an admin access token and call the Admin REST API (fetch the realm's details).
    oidc_config = lib.base.coe(lib.keycloak.discover_oidc_endpoints(args))
    admin_token = lib.base.coe(lib.keycloak.obtain_admin_token(args, oidc_config))
    server_info = lib.base.coe(lib.keycloak.get_data(args, admin_token, '/admin/serverinfo'))
```
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082001'

from . import url


def discover_oidc_endpoints(args):
    """
    Discover the OIDC endpoints for the realm.

    This function fetches the OpenID Connect (OIDC) discovery document for a given Keycloak realm.
    Authentication is not required to perform the discovery. It retrieves endpoint information such
    as authorization, token, introspection, and user info endpoints.

    ### Parameters
    - **args** (object):
      An argument object containing:
        - `URL` (`str`): Base URL of the Keycloak server.
        - `REALM` (`str`): The Keycloak realm name.
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - `success` (`bool`): True if the fetch succeeded, False otherwise.
      - `result` (`dict` or `str`): Parsed JSON response or an error message.

    ### Notes
    - This uses the standard `.well-known/openid-configuration` path.
    - Automatically removes any trailing slash in the base URL.

    ### Example
    >>> success, endpoints = discover_oidc_endpoints(args)
    """
    url_base = args.URL.rstrip('/')
    uri = f'{url_base}/realms/{args.REALM}/.well-known/openid-configuration'
    return url.fetch_json(
        uri,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )


def get_data(args, token_data, uri):
    """
    Call the Keycloak REST API with a Bearer token.

    This function sends an authenticated request to the Keycloak REST API, using the provided
    access token obtained from a previous authentication step.

    ### Parameters
    - **args** (object):
      An argument object containing:
        - `URL` (`str`): Base URL of the Keycloak server.
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.
    - **token_data** (`dict`):
      A dictionary containing at least the `access_token`.
    - **uri** (`str`):
      Relative URI to be appended to the base URL (e.g., `/admin/realms/myrealm/users`).

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - `success` (`bool`): True if the request succeeded, False otherwise.
      - `result` (`dict` or `str`): Fetched data or error message.

    ### Notes
    - The Bearer token is passed in the `Authorization` header.

    ### Example
    >>> success, result = get_data(args, token_data, '/admin/realms/myrealm/users')
    """
    url_base = args.URL.rstrip('/')
    full_url = f'{url_base}{uri}'
    headers = {'Authorization': f'Bearer {token_data.get("access_token", "")}'}
    return url.fetch_json(
        full_url,
        header=headers,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )


def get_server_info_section(server_info, section):
    """
    Return one section of a Keycloak `/admin/serverinfo` document.

    Keycloak reports the `cpuInfo`, `memoryInfo` and `systemInfo` sections only to an
    account that is allowed to manage the realm it authenticates against, and reports
    them in full only in the administration realm (`master`). Every other account gets a
    document without those sections, so a consumer reading one of them ends up with
    nothing to evaluate and has to say why.

    ### Parameters
    - **server_info** (`dict`): The parsed `/admin/serverinfo` response.
    - **section** (`str`): Name of the section to return, for example `memoryInfo`.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - `success` (`bool`): True if the section holds data, False otherwise.
      - `result` (`dict` or `str`): The section or an error message naming the role that
        makes Keycloak report it.

    ### Notes
    - Verified against Keycloak 26.7.2. Up to 26.6 an account authenticating against the
      administration realm received these sections regardless of its roles; since 26.7.0
      the `manage-realm` role decides.

    ### Example
    >>> success, memory_info = get_server_info_section(server_info, 'memoryInfo')
    """
    data = server_info.get(section)
    if not data:
        return False, (
            f'Keycloak reports no "{section}" for this account.\n'
            f'Keycloak hands out that section only to an account holding the '
            f'"manage-realm" role in its administration realm ("master"). Grant that '
            f'role to the account used here, or use one that already has it.'
        )
    return True, data


def obtain_admin_token(args, oidc_config):
    """
    Obtain an admin access token from Keycloak.

    This function requests an access token using the Resource Owner Password Credentials Grant
    ("password grant"). It authenticates against the realm's token endpoint on the Keycloak
    server given as the base URL.

    ### Parameters
    - **args** (object):
      An argument object containing:
        - `URL` (`str`): Base URL of the Keycloak server.
        - `REALM` (`str`): The Keycloak realm name.
        - `CLIENT_ID` (`str`): Client ID registered in Keycloak.
        - `USERNAME` (`str`): Admin username.
        - `PASSWORD` (`str`): Admin password.
        - `INSECURE` (`bool`): Whether to disable SSL verification.
        - `NO_PROXY` (`bool`): Whether to ignore proxy settings.
        - `TIMEOUT` (`int`): Request timeout in seconds.
    - **oidc_config** (`dict`):
      OIDC discovery document containing endpoints (must have `token_endpoint`).

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - `success` (`bool`): True if authentication succeeded, False otherwise.
      - `result` (`dict` or `str`): Access token data or error message.

    ### Notes
    - Uses `grant_type=password`.
    - Make sure Resource Owner Password Credentials Grant is allowed in your realm settings.
    - The request URL is built from the base URL and the realm, exactly like the discovery
      request. The discovery document is served by the monitored host and therefore untrusted:
      taking its `token_endpoint` as the request URL would let a malicious or compromised host
      redirect this POST - which carries the cleartext admin credentials - to any host of its
      choosing (CWE-918/CWE-522). The document is only asked whether the realm announces a
      token endpoint at all.

    ### Example
    >>> success, token_data = obtain_admin_token(args, oidc_config)
    """
    if not oidc_config.get('token_endpoint'):
        return False, f'Realm "{args.REALM}" does not announce an OIDC token endpoint.'
    url_base = args.URL.rstrip('/')
    token_endpoint = f'{url_base}/realms/{args.REALM}/protocol/openid-connect/token'
    payload = {
        'grant_type': 'password',
        'client_id': args.CLIENT_ID,
        'username': args.USERNAME,
        'password': args.PASSWORD,
    }
    return url.fetch_json(
        token_endpoint,
        data=payload,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )
