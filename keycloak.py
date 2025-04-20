#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

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
__version__ = '2025042001'

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
    uri = f"{url_base}/realms/{args.REALM}/.well-known/openid-configuration"
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
    headers = {
        'Authorization': f'Bearer {token_data.get("access_token", "")}'
    }
    return url.fetch_json(
        full_url,
        header=headers,
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )


def obtain_admin_token(args, oidc_config):
    """
    Obtain an admin access token from Keycloak.

    This function requests an access token using the Resource Owner Password Credentials Grant
    ("password grant"). It authenticates against the `token_endpoint` discovered via OIDC.

    ### Parameters
    - **args** (object):
      An argument object containing:
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

    ### Example
    >>> success, token_data = obtain_admin_token(args, oidc_config)
    """
    token_endpoint = oidc_config.get('token_endpoint', '')
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
