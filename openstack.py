#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Authenticates against an OpenStack cloud and queries its REST APIs.

Credentials are read from an rc file (the one the Horizon dashboard hands out), exchanged for a
Keystone token, and the token is reused across runs so a short-lived consumer does not
authenticate on every single call.

Everything goes over the Identity v3 REST API, which every OpenStack release since Queens
speaks, so reaching a service needs no client library of that service.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082501'

import datetime
import hashlib
import json
import re

# The standard library one, for the monotonic clock a time budget has to be measured against.
import time

from . import cache, txt, url

# How long a token may be reused, in minutes. `connect()` never hands out one past its own
# expiry anyway, so this bounds the reuse of a long-lived token.
DEFAULT_CACHE_EXPIRE = 50

# The time budget of a whole run, in seconds. Deliberately below the ten seconds a monitoring
# server commonly allows a check, so a consumer can still report on its own.
DEFAULT_TIMEOUT = 8

# What every request to an OpenStack API sends and expects back.
HEADER = {'Accept': 'application/json', 'Content-Type': 'application/json'}

# The smallest timeout a request is still sent with, in seconds. Below that the answer would not
# arrive anyway, and the caller learns that the budget is spent instead of waiting for a timeout
# it cannot use.
MIN_REQUEST_TIMEOUT = 1

# Seconds of headroom subtracted from the expiry of a token before it is cached. Keeps a token
# that expires mid-run out of the cache.
TOKEN_EXPIRY_HEADROOM = 60


def _get_api_message(text):
    """Return the message an OpenStack API puts in the body of an error response.

    Every service wraps it in a name of its own (`error`, `forbidden`, `itemNotFound`,
    `NeutronError`), so the wrapper is not worth naming: what they have in common is a
    `message` one level down.

    Some of those messages carry markup and line breaks, which would break the layout of
    whatever the caller prints them in, so the message is flattened to a single line.
    """
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return ''
    if not isinstance(body, dict):
        return ''
    message = str(body.get('message', ''))
    for value in body.values():
        if isinstance(value, dict) and value.get('message'):
            message = str(value['message'])
            break
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', message)).strip()


def _get_domain(env, id_key, name_key):
    """Return how a domain is addressed, by id where the rc file gives one.

    Every deployment carries the default domain under the id `default`, which is what an rc
    file naming no domain at all means.
    """
    if env.get(id_key):
        return {'id': env[id_key]}
    if env.get(name_key):
        return {'name': env[name_key]}
    return {'id': 'default'}


def _get_auth_body(env):
    """Build the Identity v3 token request from the rc file variables.

    A user and a project are addressed either by id or by name, never by both: a name needs the
    domain it lives in, an id is unique on its own.
    """
    user = {'password': env.get('OS_PASSWORD', None)}
    if env.get('OS_USER_ID'):
        user['id'] = env['OS_USER_ID']
    else:
        user['domain'] = _get_domain(env, 'OS_USER_DOMAIN_ID', 'OS_USER_DOMAIN_NAME')
        user['name'] = env.get('OS_USERNAME', None)
    if env.get('OS_PROJECT_ID'):
        project = {'id': env['OS_PROJECT_ID']}
    else:
        project = {
            'domain': _get_domain(
                env, 'OS_PROJECT_DOMAIN_ID', 'OS_PROJECT_DOMAIN_NAME'
            ),
            'name': env.get('OS_PROJECT_NAME', None),
        }
    return {
        'auth': {
            'identity': {'methods': ['password'], 'password': {'user': user}},
            'scope': {'project': project},
        }
    }


def _get_auth_url(env):
    """Return the Identity endpoint, pointed at its version 3.

    An rc file names it with or without the version, and Identity v2 has been gone since
    Queens, so the version is nothing a consumer should have to think about.
    """
    auth_url = (env.get('OS_AUTH_URL') or '').rstrip('/')
    if auth_url.endswith('/v3'):
        return auth_url
    if auth_url.endswith(('/v2.0', '/v2')):
        return auth_url.rsplit('/', 1)[0] + '/v3'
    return auth_url + '/v3'


def _get_cache_key(env, name):
    """Return a cache key that is unique per cloud, project and user.

    Several consumers on the same host share one cache database, so the key has to tell their
    tokens apart. The password is not part of it.
    """
    identity = '|'.join(
        [
            env.get('OS_AUTH_URL', ''),
            env.get('OS_USERNAME', ''),
            env.get('OS_PROJECT_NAME', ''),
            env.get('OS_PROJECT_ID', ''),
            env.get('OS_REGION_NAME', ''),
        ]
    )
    digest = hashlib.sha256(txt.to_bytes(identity)).hexdigest()[:32]
    return f'{name}-{digest}'


def _get_endpoints(catalog, service_types, interface, region_name):
    """Pick the URL of every requested service out of the service catalog.

    A service the catalog does not offer in this interface or region is left out, so the caller
    can say what it can and cannot report on.
    """
    endpoints = {}
    for entry in catalog or []:
        if entry.get('type') not in service_types:
            continue
        for endpoint in entry.get('endpoints') or []:
            if endpoint.get('interface') != interface:
                continue
            if region_name and endpoint.get('region') != region_name:
                continue
            if endpoint.get('url'):
                endpoints[entry['type']] = endpoint['url']
                break
    return endpoints


def _get_expiry(token):
    """Return when a token expires, as a UNIX timestamp, or 0 when it does not say.

    Identity answers in UTC, commonly with a fraction of a second and occasionally without.
    """
    for pattern in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            expiry = datetime.datetime.strptime(token.get('expires_at', ''), pattern)
        except (AttributeError, TypeError, ValueError):
            continue
        return int(expiry.replace(tzinfo=datetime.timezone.utc).timestamp())
    return 0


def _get_interface(env):
    """Return the catalog interface to look endpoints up in.

    An rc file names it as `public`, `internal` or `admin`, and older ones append `URL`.
    """
    interface = env.get('OS_INTERFACE') or env.get('OS_ENDPOINT_TYPE') or 'public'
    interface = interface.strip().lower().replace('url', '')
    if interface not in ('public', 'internal', 'admin'):
        interface = 'public'
    return interface


def _fetch(conn, target, data=None, header=None, method=None, retries=0):
    """Make one request against the cloud, spending what is left of the time budget.

    Returns (True, response, status) where the response is the extended answer of `url.fetch()`,
    or (False, errormessage, status). The status is the one the API answered with, and 0 where
    the request never got an answer.

    Nothing is parsed here: a HEAD carries its answer in the headers and has no body at all,
    so the JSON step belongs to the callers that expect one.
    """
    remaining = conn['deadline'] - time.monotonic()
    if remaining < MIN_REQUEST_TIMEOUT:
        return (False, 'the time budget of this run is spent', 0)
    success, result = url.fetch(
        target,
        cacert=conn['cacert'],
        data=data,
        encoding='serialized-json',
        extended=True,
        header=dict(conn['header'], **(header or {})),
        insecure=conn['insecure'],
        method=method,
        no_proxy=conn['no_proxy'],
        proxy=conn['proxy'],
        response_on_error=True,
        retries=retries,
        # Rounded up, so a fraction of a second is never handed on as a timeout of zero, which
        # an HTTP client reads as "no timeout at all".
        timeout=int(remaining) + 1,
    )
    if success:
        return (True, result, result['status_code'])
    if not isinstance(result, dict):
        # No answer at all: a name that does not resolve, a refused connection, a timeout.
        return (False, result, 0)
    status = result.get('status_code', 0)
    message = _get_api_message(result.get('response', ''))
    return (False, f'HTTP {status}{": " + message if message else ""}', status)


def _get_json(response):
    """Parse the body of a response as JSON.

    Returns (True, document) or (False, errormessage).
    """
    try:
        return (True, json.loads(response.get('response') or ''))
    except (AttributeError, TypeError, ValueError) as e:
        return (False, f'{e}')


def _authenticate(conn):
    """Exchange the credentials for a token, look up the endpoints and cache both.

    Returns (True, conn) with `token`, `project_id` and `endpoints` filled in, or
    (False, errormessage).
    """
    env = conn['env']
    conn['header'] = dict(HEADER)
    success, result, status = _fetch(
        conn,
        _get_auth_url(env) + '/auth/tokens',
        data=_get_auth_body(env),
    )
    if not success:
        if status in (400, 401, 403):
            # Identity answers 400 to a request that carries no password at all, which is the
            # same mistake from where the administrator stands.
            return (False, 'Failed to authenticate.')
        return (False, f'Cannot authenticate against the Identity API: {result}')

    # The token itself travels in a response header, not in the body.
    token_header = result['response_header'].get('x-subject-token')
    if not token_header:
        return (False, 'The Identity API answered without a token.')
    success, document = _get_json(result)
    if not success:
        return (
            False,
            f'The Identity API answered with something else than a token: {document}',
        )
    token = (document or {}).get('token') or {}

    conn['cached'] = False
    conn['endpoints'] = _get_endpoints(
        token.get('catalog'),
        conn['service_types'],
        _get_interface(env),
        env.get('OS_REGION_NAME') or None,
    )
    conn['header'] = dict(HEADER, **{'X-Auth-Token': token_header})
    conn['project_id'] = (token.get('project') or {}).get('id')
    conn['token'] = token_header

    expire = int(time.time()) + conn['cache_expire'] * 60
    expiry = _get_expiry(token)
    if expiry:
        # Never hand out a token past its own lifetime.
        expire = min(expire, expiry - TOKEN_EXPIRY_HEADROOM)
    if conn['cache_expire'] > 0 and expire > int(time.time()):
        cache.set(
            conn['cache_key'],
            json.dumps(
                {
                    'endpoints': conn['endpoints'],
                    'project_id': conn['project_id'],
                    'token': conn['token'],
                }
            ),
            expire=expire,
        )
    return (True, conn)


def connect(
    env,
    service_types,
    timeout=DEFAULT_TIMEOUT,
    insecure=False,
    no_proxy=False,
    proxy=None,
    cache_expire=DEFAULT_CACHE_EXPIRE,
    cache_name='openstack',
    use_cache=True,
):
    """
    Authenticate against an OpenStack cloud and look up the endpoints of its services.

    A token from a previous run is reused where there is one, which saves the request a token
    costs on a busy Identity API.

    ### Parameters
    - **env** (`dict`): The variables of an OpenStack rc file, for example as returned by
      `disk.read_env()`. Read are `OS_AUTH_URL`, `OS_CACERT`, `OS_ENDPOINT_TYPE`,
      `OS_INTERFACE`, `OS_PASSWORD`, `OS_PROJECT_DOMAIN_ID`, `OS_PROJECT_DOMAIN_NAME`,
      `OS_PROJECT_ID`, `OS_PROJECT_NAME`, `OS_REGION_NAME`, `OS_USERNAME`,
      `OS_USER_DOMAIN_ID`, `OS_USER_DOMAIN_NAME` and `OS_USER_ID`.
    - **service_types** (`list` of `str`): The catalog service types to look up, for example
      `['compute', 'volumev3', 'network']`.
    - **timeout** (`int`, optional): Time budget for the whole run in seconds, not per request:
      every request is given what is left of it. Defaults to `8`.
    - **insecure** (`bool`, optional): Do not verify the TLS certificate at all, which also
      makes a CA bundle named in `OS_CACERT` moot. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Ignore the proxy the environment names.
      Defaults to `False`.
    - **proxy** (`str`, optional): The proxy to reach the cloud through. Defaults to `None`.
    - **cache_expire** (`int`, optional): How long the token may be reused, in minutes. `0`
      turns the cache off, so the run neither reads a token nor leaves one behind.
      Defaults to `50`.
    - **cache_name** (`str`, optional): Prefix of the cache key, so consumers do not read each
      other's tokens. Defaults to `'openstack'`.
    - **use_cache** (`bool`, optional): Reuse a cached token. Defaults to `True`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the connection succeeded, otherwise False.
        - tuple[1] (**dict or str**):
          - If successful, a connection dict to hand to `fetch_json()`. Of interest to a caller
            are `project_id` (the project the token is scoped to), which many an endpoint needs
            in its path, and `endpoints` (the URL per service type that was found).
          - If unsuccessful, an error message string.

    ### Notes
    - A service type the catalog does not offer is left out of `endpoints` instead of failing
      the connection, because a caller asking for several services usually has something to say
      about the ones that did answer.
    - A CA bundle named in `OS_CACERT` is verified against on top of the trust store of the
      host, so a cloud whose certificate a private CA signed needs no `insecure`. A bundle
      that cannot be read fails the connection instead of quietly verifying against the trust
      store alone.
    - The connection dict carries the credentials and the token, so do not print it.

    ### Example
    >>> env = base.coe(disk.read_env('/var/spool/icinga2/.openstack.cnf'))
    >>> conn = base.coe(openstack.connect(env, ['compute'], timeout=8))
    >>> servers = base.coe(openstack.fetch_json(conn, 'compute', '/servers/detail'))
    """
    conn = {
        # A cloud whose certificate a private CA signed, as `OS_CACERT` names it.
        'cacert': env.get('OS_CACERT') or None,
        'cache_expire': cache_expire,
        'cache_key': _get_cache_key(env, cache_name),
        'cached': False,
        'deadline': time.monotonic() + timeout,
        'endpoints': {},
        'env': env,
        'header': dict(HEADER),
        'insecure': insecure,
        'no_proxy': no_proxy,
        'project_id': None,
        'proxy': proxy,
        'service_types': list(service_types),
    }
    if use_cache and cache_expire > 0:
        cached = cache.get(conn['cache_key'], as_dict=False)
        if cached:
            try:
                data = json.loads(cached)
                endpoints = data['endpoints']
                # A cache entry that predates the current set of service types would send the
                # caller looking for an endpoint that is not in it.
                if all(item in endpoints for item in conn['service_types']):
                    conn['cached'] = True
                    conn['endpoints'] = endpoints
                    conn['header'] = dict(HEADER, **{'X-Auth-Token': data['token']})
                    conn['project_id'] = data['project_id']
                    conn['token'] = data['token']
                    return (True, conn)
            except (KeyError, TypeError, ValueError):
                # A cache entry that cannot be read is one that gets replaced.
                pass
    return _authenticate(conn)


def fetch(conn, service_type, path, header=None, method=None, retries=0):
    """
    Make a request against one of the connected services and return the whole answer.

    Use this where the answer of a service is in its headers rather than in its body, which is
    how an object store reports what a container holds, and where a HEAD is the request that
    carries it. `fetch_json()` is the one to use for a service that answers with a document.

    ### Parameters
    - **conn** (`dict`): A connection as returned by `connect()`.
    - **service_type** (`str`): The catalog service type to talk to, for example
      `'object-store'`. Has to be one of the service types the connection was opened for.
    - **path** (`str`): The path below the endpoint, starting with a slash, for example
      `'/my-container'`. Anything a value contributes to it has to be URL-encoded by the
      caller.
    - **header** (`dict`, optional): Request headers on top of the ones every request carries,
      for example `{'OpenStack-API-Version': 'compute 2.1'}` to pin the microversion of a
      service that offers several. Defaults to `None`.
    - **method** (`str`, optional): The HTTP method, for example `'HEAD'`. Defaults to `None`,
      which is a GET. Defaults to `None`.
    - **retries** (`int`, optional): How many extra attempts to make when the request fails.
      Defaults to `0`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the request succeeded, otherwise False.
        - tuple[1] (**dict or str**): The extended answer of `url.fetch()`, whose
          `response_header` holds the headers with their names in lower case, or an error
          message string.

    ### Notes
    - A cached token that the service rejects is replaced by a fresh one and the request is
      repeated once, so a token revoked between two runs costs one retry instead of an error.
    - The error message names the reason the service gave, and starts in lower case, so a
      caller can put it behind whatever it calls the service.

    ### Example
    >>> success, result = openstack.fetch(
    ...     conn, 'object-store', '/backups', method='HEAD'
    ... )
    >>> result['response_header']['x-container-bytes-used']
    '1568051495913'
    """
    for attempt in (1, 2):
        endpoint = conn['endpoints'].get(service_type)
        if not endpoint:
            return (False, f'the service catalog holds no "{service_type}" endpoint')
        success, result, status = _fetch(
            conn,
            endpoint.rstrip('/') + path,
            header=header,
            method=method,
            retries=retries,
        )
        if success:
            return (True, result)
        if status != 401 or attempt == 2 or not conn['cached']:
            return (False, result)
        # The token from the previous run was revoked or expired early.
        success, result = _authenticate(conn)
        if not success:
            return (False, result)
    return (False, 'Failed to authenticate.')


def fetch_json(conn, service_type, path, header=None, retries=0, extended=False):
    """
    Fetch a JSON document from one of the connected services.

    Everything `fetch()` does, plus the JSON step on the body it answers with.

    ### Parameters
    - **conn** (`dict`): A connection as returned by `connect()`.
    - **service_type** (`str`): The catalog service type to talk to, for example `'compute'`.
      Has to be one of the service types the connection was opened for.
    - **path** (`str`): The path below the endpoint, starting with a slash, for example
      `'/limits'`. Anything a value contributes to it has to be URL-encoded by the caller.
    - **header** (`dict`, optional): Request headers on top of the ones every request carries,
      for example `{'OpenStack-API-Version': 'compute 2.1'}` to pin the microversion of a
      service that offers several. Defaults to `None`.
    - **retries** (`int`, optional): How many extra attempts to make when the request fails.
      Defaults to `0`.
    - **extended** (`bool`, optional): Return the whole answer with the parsed document added
      under `response_json`, rather than the document alone. For a service that says part of
      what it has to say in its headers and the rest in its body, which an object store does
      when it lists an account. Defaults to `False`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the request succeeded, otherwise False.
        - tuple[1] (**dict or str**): The parsed document, the whole answer with
          `response_json` added when `extended` is set, or an error message string.

    ### Example
    >>> success, result = openstack.fetch_json(conn, 'compute', '/limits')
    """
    success, result = fetch(conn, service_type, path, header=header, retries=retries)
    if not success:
        return (False, result)
    success, document = _get_json(result)
    if not success:
        return (False, f'the answer is not JSON: {document}')
    if extended:
        result['response_json'] = document
        return (True, result)
    return (True, document)
