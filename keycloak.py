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
__version__ = '2024123001'

from . import url


def discover_oidc_endpoints(args):
    """Discover the OIDC endpoints for the realm (no authentication needed).
    """
    return url.fetch_json(
        f'{args.URL}/realms/{args.REALM}/.well-known/openid-configuration',
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )


def obtain_admin_token(args, oidc_config):
    """Obtain an admin access token.
    """
    return url.fetch_json(
        oidc_config.get('token_endpoint', ''),
        data={
            'grant_type': 'password',
            'client_id': args.CLIENT_ID,
            'username': args.USERNAME,
            'password': args.PASSWORD,
        },
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )


def get_data(args, token_data, uri):
    """Call the REST API.
    """
    return url.fetch_json(
        f'{args.URL}{uri}',
        header={'Authorization': f'Bearer {token_data.get("access_token", "")}'},
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )
