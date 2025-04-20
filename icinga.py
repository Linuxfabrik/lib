#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This module tries to make accessing the Icinga2 API easier.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042002'

import base64
import time

from . import txt
from . import url

# Take care of Icinga and throttle the amount of requests, don't overload it
# with too fast subsequent api-calls.
DEFAULT_SLEEP = 1.0


def api_post(uri, username, password, data=None, method_override='',
             insecure=False, no_proxy=False, timeout=3):
    """
    Send a low-level POST request to the Icinga API.

    This function manually crafts a POST request to the Icinga REST API, adding basic authentication
    headers and optionally overriding the HTTP method via `X-HTTP-Method-Override`.

    ### Parameters
    - **uri** (`str`):
      Full API endpoint URL (e.g., `https://icinga-server:5665/v1/objects/services`).
    - **username** (`str`):
      API username.
    - **password** (`str`):
      API password.
    - **data** (`dict`, optional):
      Payload to send with the request. Defaults to `{}`.
    - **method_override** (`str`, optional):
      If set, override HTTP method (e.g., `'GET'`). Defaults to `''`.
    - **insecure** (`bool`, optional):
      Disable SSL certificate verification. Defaults to `False`.
    - **no_proxy** (`bool`, optional):
      Bypass proxy. Defaults to `False`.
    - **timeout** (`int`, optional):
      Timeout for the request in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `object`):
      The result from the `url.fetch_json` call.

    ### Notes
    - Replaces double slashes `//v1` or `//v2` in the URI to ensure correct URL formatting.
    - Pauses execution for a short duration after sending the request (`DEFAULT_SLEEP`).

    ### Example
    >>> uri = 'https://icinga-server:5665/v1/objects/services'
    >>> data = {
    >>>     'filter': 'match("special-service", service.name)',
    >>>     'attrs': ['name', 'state', 'acknowledgement'],
    >>> }
    >>> result = lib.base.coe(
    >>>     lib.icinga.api_post(
    >>>         uri, args.USERNAME, args.PASSWORD, data=data,
    >>>         method_override='GET', timeout=3
    >>>     )
    >>> )
    """
    uri = uri.replace('//v1', '/v1').replace('//v2', '/v2')
    headers = {
        'Accept': 'application/json',
        'Authorization': f"Basic {txt.to_text(base64.b64encode(txt.to_bytes(f'{username}:{password}')))}"
    }
    if method_override:
        headers['X-HTTP-Method-Override'] = method_override

    result = url.fetch_json(
        uri,
        data=data or {},
        encoding='serialized-json',
        header=headers,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )
    time.sleep(DEFAULT_SLEEP)
    return result


def get_service(uri, username, password, servicename, attrs='state',
                insecure=False, no_proxy=False, timeout=3):
    """
    Query a service object from the Icinga API.

    This function sends a high-level request to the Icinga `/v1/objects/services` endpoint
    to retrieve attributes for a specific service, identified by its `__name`.

    ### Parameters
    - **uri** (`str`):
      Base API URL (e.g., `https://icinga-server:5665`).
    - **username** (`str`):
      API username.
    - **password** (`str`):
      API password.
    - **servicename** (`str`):
      Unique service name, typically in the format `hostname!service`.
    - **attrs** (`str`, optional):
      Comma-separated list of attributes to retrieve. Defaults to `'state'`.
    - **insecure** (`bool`, optional):
      Disable SSL certificate verification. Defaults to `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional):
      Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `object`):
      The result from the Icinga API request.

    ### Notes
    - The `servicename` must match the `__name` attribute exactly.
    - Uses a `GET` override on a `POST` request (`X-HTTP-Method-Override` header).

    ### Example
    >>> uri = 'https://icinga-server:5665'
    >>> result = lib.base.coe(
    >>>     lib.icinga.get_service(
    >>>         uri,
    >>>         args.USERNAME,
    >>>         args.PASSWORD,
    >>>         servicename='hostname!special-service',
    >>>         attrs='state,acknowledgement',
    >>>     )
    >>> )
    >>> print(result['result'][0]['attrs'])
    """
    uri = f"{uri.rstrip('/')}/v1/objects/services"
    data = {
        'filter': f'match("{servicename}", service.__name)',
        'attrs': ['name'] + attrs.split(','),
    }
    return api_post(
        uri=uri,
        username=username,
        password=password,
        data=data,
        method_override='GET',
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )


def remove_ack(uri, username, password, objectname, _type='service',
               insecure=False, no_proxy=False, timeout=3):
    """
    Remove an acknowledgement for a host or service in Icinga.

    This function posts a request to the Icinga API to remove an active acknowledgement. Once the
    acknowledgement is removed, notifications will be triggered again on state changes.

    ### Parameters
    - **uri** (`str`):
      Base API URL (e.g., `https://icinga-server:5665`).
    - **username** (`str`):
      API username.
    - **password** (`str`):
      API password.
    - **objectname** (`str`):
      Host or service name (must match the `__name` attribute).
    - **_type** (`str`, optional):
      Object type: `host` or `service`. Defaults to `'service'`.
    - **insecure** (`bool`, optional):
      Disable SSL certificate verification. Defaults to `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional):
      Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `dict`):
      API call result as a tuple (success flag, response body).

    ### Notes
    - Even if the host or service was not acknowledged, calling this is safe and returns success.

    ### Example
    >>> uri = 'https://icinga-server:5665'
    >>> icinga.remove_ack(
    >>>     uri, username, password, objectname='hostname!special-service'
    >>> )
    """
    uri = f"{uri.rstrip('/')}/v1/actions/remove-acknowledgement"
    data = {
        'type': _type.capitalize(),
        'filter': f'match("{objectname}", {_type.lower()}.__name)',
    }
    return api_post(
        uri=uri,
        username=username,
        password=password,
        data=data,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )


def remove_downtime(uri, username, password, downtime,
                    insecure=False, no_proxy=False, timeout=3):
    """
    Remove a downtime in Icinga by its name.

    This function posts a request to the Icinga API to remove a scheduled downtime. The downtime
    must be identified by the unique name returned earlier by `set_downtime()`.

    ### Parameters
    - **uri** (`str`):
      Base API URL (e.g., `https://icinga-server:5665`).
    - **username** (`str`):
      API username.
    - **password** (`str`):
      API password.
    - **downtime** (`str`):
      Downtime identifier (name).
    - **insecure** (`bool`, optional):
      Disable SSL certificate verification. Defaults to `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional):
      Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `dict`):
      API call result as a tuple (success flag, response body).

    ### Notes
    - Safe to call even if the downtime is already expired or invalid.

    ### Example
    >>> uri = 'https://icinga-server:5665'
    >>> icinga.remove_downtime(
    >>>     uri, args.ICINGA_USERNAME, args.ICINGA_PASSWORD,
    >>>     downtime='hostname!service!uuid'
    >>> )
    """
    uri = uri + '/v1/actions/remove-downtime'
    data = {
        'downtime': downtime,
    }
    return api_post(
        uri=uri,
        username=username,
        password=password,
        data=data,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )


def set_ack(uri, username, password, objectname, _type='service', author='Linuxfabrik lib.icinga',
            insecure=False, no_proxy=False, timeout=3):
    """
    Acknowledge a problem for a host or service in Icinga.

    This function allows you to acknowledge the current problem on a host or service via the
    Icinga API. Acknowledged problems disable future notifications for the same state (if sticky
    is false).

    ### Parameters
    - **uri** (`str`):
      Base API URL (e.g., `https://icinga-server:5665`).
    - **username** (`str`):
      API username.
    - **password** (`str`):
      API password.
    - **objectname** (`str`):
      Host or service name (must match the `__name` attribute).
    - **_type** (`str`, optional):
      Type of object to acknowledge (`host` or `service`). Defaults to `'service'`.
    - **author** (`str`, optional):
      Author of the acknowledgement. Defaults to `'Linuxfabrik lib.icinga'`.
    - **insecure** (`bool`, optional):
      Disable SSL certificate verification. Defaults to `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional):
      Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `object`):
      The result from the Icinga API request.

    ### Notes
    - Acknowledging a host/service that is already acknowledged is allowed until Icinga 2.11.
    - Acknowledging a host/service in OK state leads to a *500 Internal Server Error*.

    ### Example
    >>> uri = 'https://icinga-server:5665'
    >>> result = lib.icinga.set_ack(
    >>>     uri, username, password, 'hostname!special-service', _type='service'
    >>> )
    """
    uri = f"{uri.rstrip('/')}/v1/actions/acknowledge-problem"
    data = {
        'type': _type.capitalize(),
        'filter': f'match("{objectname}", {_type.lower()}.__name)',
        'author': author,
        'comment': 'automatically acknowledged',
        'notify': False,
    }
    return api_post(
        uri=uri,
        username=username,
        password=password,
        data=data,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )


def set_downtime(uri, username, password, objectname, _type='service',
                 starttime=None, endtime=None, author='Linuxfabrik lib.icinga',
                 insecure=False, no_proxy=False, timeout=3):
    """
    Schedule a downtime for a host or service in Icinga.

    This function posts a request to the Icinga API to schedule a downtime for a given host or
    service. The object must match the `__name` attribute in Icinga.

    ### Parameters
    - **uri** (`str`):
      Base API URL (e.g., `https://icinga-server:5665`).
    - **username** (`str`):
      API username.
    - **password** (`str`):
      API password.
    - **objectname** (`str`):
      Host or service name (must match the `__name` attribute).
    - **_type** (`str`, optional):
      Object type: `host` or `service`. Defaults to `'service'`.
    - **starttime** (`int`, optional):
      Unix timestamp when the downtime starts. Defaults to now.
    - **endtime** (`int`, optional):
      Unix timestamp when the downtime ends. Defaults to now + 1 hour.
    - **author** (`str`, optional):
      Author of the downtime entry. Defaults to `'Linuxfabrik lib.icinga'`.
    - **insecure** (`bool`, optional):
      Disable SSL certificate verification. Defaults to `False`.
    - **no_proxy** (`bool`, optional):
      Ignore proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional):
      Request timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `str` or `dict`):
      If successful, returns the downtime name.
      If failed, returns the original API result.

    ### Notes
    - The returned downtime name is needed if you want to remove the downtime later.

    ### Example
    >>> uri = 'https://icinga-server:5665'
    >>> result = lib.icinga.set_downtime(
    >>>     uri, username, password, objectname='hostname!special-service'
    >>> )
    'hostname!special-service!3ad20784-52f9-4acc-b2df-90788667d587'
    """
    now = int(time.time())
    starttime = starttime if starttime is not None else now
    endtime = endtime if endtime is not None else now + 3600

    uri = f"{uri.rstrip('/')}/v1/actions/schedule-downtime"
    data = {
        'type': _type.capitalize(),
        'filter': f'match("{objectname}", {_type.lower()}.__name)',
        'author': author,
        'comment': 'automatic downtime',
        'start_time': starttime,
        'end_time': endtime,
    }
    success, result = api_post(
        uri=uri,
        username=username,
        password=password,
        data=data,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )

    if success and result['results'][0].get('code') == 200:
        return True, result['results'][0]['name']
    return False, result


