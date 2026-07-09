#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This module tries to make accessing the Icinga2 API easier."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026070901'

import base64
import html
import time
import urllib.parse
from string import Template

from . import txt, url

# Take care of Icinga and throttle the amount of requests, don't overload it
# with too fast subsequent api-calls.
DEFAULT_SLEEP = 1.0


def api_post(
    uri,
    username,
    password,
    data=None,
    method_override='',
    insecure=False,
    no_proxy=False,
    timeout=3,
):
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
        'Authorization': f'Basic {txt.to_text(base64.b64encode(txt.to_bytes(f"{username}:{password}")))}',
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


def build_icingaweb2_url(base_url, hostname, servicename=None):
    """
    Build an Icinga Web 2 detail URL for a host or a service.

    Composes the Icinga DB module's host or service detail URL from a base Icinga Web 2 URL and the
    object name(s). A service URL is built when `servicename` is a non-empty string, otherwise a
    host URL.

    The object names are treated as untrusted: they are URL-encoded (including `/`, `&`, `?`, `#`,
    quotes and spaces), so a name cannot inject extra query parameters or break out of the URL. The
    returned link is meant to be embedded verbatim in notifications (mail, chat), so the function
    also pins the scheme to `http`/`https` and never emits a `javascript:`, `data:` or `file:` URL
    from a malformed base URL.

    ### Parameters
    - **base_url** (`str`): Base Icinga Web 2 URL, e.g. `https://example.com/icingaweb2`.
    - **hostname** (`str`): Host object name.
    - **servicename** (`str`, optional): Service object name. When a non-empty string, a service
      detail URL is built; otherwise a host detail URL. Defaults to `None`.

    ### Returns
    - **str** or **None**: The composed URL, or `None` when `base_url`/`hostname` is missing, not a
      string, or when `base_url` does not use the `http`/`https` scheme.

    ### Notes
    - Callers that embed the URL in HTML must still HTML-escape it; encoding a URL is not the same
      as escaping it for an HTML attribute.

    ### Example
    >>> build_icingaweb2_url('https://example.com/icingaweb2', 'web01')
    'https://example.com/icingaweb2/icingadb/host?name=web01'
    >>> build_icingaweb2_url('https://example.com/icingaweb2', 'web01', 'http')
    'https://example.com/icingaweb2/icingadb/service?name=http&host.name=web01'
    """
    if not isinstance(base_url, str) or not isinstance(hostname, str):
        return None
    if not base_url or not hostname:
        return None
    if urllib.parse.urlsplit(base_url).scheme.lower() not in ('http', 'https'):
        return None
    if isinstance(servicename, str) and servicename:
        query = urllib.parse.urlencode(
            {'name': servicename, 'host.name': hostname},
            quote_via=urllib.parse.quote,
        )
        path = f'icingadb/service?{query}'
    else:
        query = urllib.parse.urlencode(
            {'name': hostname},
            quote_via=urllib.parse.quote,
        )
        path = f'icingadb/host?{query}'
    return urllib.parse.urljoin(f'{base_url}/', path)


# Base64-encoded Icinga logo (PNG, 100x35 px).
_LOGO_PNG_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAAGQAAAAjCAQAAADItmcLAAAAAmJLR0QA/4ePzL8AAAAJcEhZcwAA
CxMAAAsTAQCanBgAAAAHdElNRQfhChAQLB+jeuiSAAAFCklEQVRYw9WYf0yVVRjHP5d7uYAo6JKf
Ggm4NtY0S1PyF6FLW239wRICLfmnQEv+snJmtbExwVzRD2eWs5xDpQbD5la2tlolRKHJQmqZrulF
B1oKBMiFe5/+uIeX9733fbkX18a95/3jfc/zPOc553vOeX69MHGzU0MPLrYT4W0Xop5NkQ3krAak
IbwXGhWE/4/JV0S2fG4jCH3khPdCbUElDjKTTg7xV2SfSBYNREfCQn02kk4dW035m6hnJHL2/UsE
YV0AfS5NxEYGBN+J9ABeHjQ5jwZum47L5DFmhJ+xR1POJZ7gGjW4iWMj84nnHAUUMmAyqoB6HHSx
lKvheDpOdnKAzXRpQbCXFaaSrYq/I3yv2mt4NBiCMOwHZTrL2cIVxS0L3zhykSw/SjMrgAQWsohF
pNNBOwPsYT4nKLawoCkHspB2E5lqUkimg3bO8QceRY1hOJyuksPQW2AqM0oNF/D6UYdNPKAd8ARI
ms16D9Pp4obl9kZhwxuCJou2zmAfY89aE8lCPiDbsAVNuJX8D6zRcZbxIXm6fgy7+VtJ/sTKAM2z
qeWG4p+l2AJoFXUkWgNJZSgARj8xAXJJjCLUa/1nGDaM8fKqxvsT4ZLWu48Og6SHaoPmB3Q+0/cc
87s1ACUIwpGJzmRvAJAaE6l7EYQ21VvNCILgpplmBtS4ZxX3FoKowBvL74p7mZ81yS2a3hSuKlon
LfSq79qA+X9UHjXVGkiCSlfGnlPYgwJpVxdqrroajQhCt1q8Hohvm1zkAxDHOwjCv5qn3I8gXCEX
gHjF95BpmH2ptro3JjqT9bTRgeDlIictClw9kFS17ESdKXciCNP8gDjpQ/CySqfpMwShSjkLH/8h
Hb8BQXjSMPsRDcg168w8mSaygVk4gFROkBQEyP0IwnsG/jJ+4ZBy7eNAFqhLE+hevlK3QX/OY2lr
M98YzDqFYYQRLiAIJVZAanna0C81PT49kFwE4WXLEx4H8ohJ7T9Pp+kuBKExiGd9HUE4TimC0GJe
sxdh0/kigKPkU2tqJ8YmIQdfj4Hm1XFsIWiKphyAtznGdSCXJeMBcQbrmcdNfqOE5/0Uuckmj4N0
TEGwXsIGHMAA++hWtKdIA1poBQ6wC6jw+UcHGZxW/sZDpTZgvG0jh/NTkjx9wWz1PYtt2mp8BuDz
ca8QTRHb6YEo3lIwwM6LJr+Hmtgd0sX5v5vofkAlq/diHlbnUkcdb9IHOH05uMNQ4CaRwK2wyQNX
s5Y57NFRKtR7g0GunGpGovyMb/J7P6LqFH2L5QVDvhVa8/hp6uYopwAYUttcZDounQJw0ESpRrpM
/6Sn912Axw1uej+leIifZKI/iGBjOYn0arRHAXABUEYM8DXvGqK8z+DrIYlftcJ2ZYhT6uOIXeWq
42niRgRhFKdfHMlHED41aMpAEM6o3ncqRkRr9dFNBGEN4MCFIIZMGpx0I4jvx4mdLBaTQ1zIe2fM
tSrURnzLVspoxIsgfBQQEIMDyVNjz/MSm9nHIILQig0oRBCTwq8SQfjkzswwE0H4XnOUxwNy5jMk
KO51hCFswCoE4bBBU5pKOMfajgBNLjIAOIwgPGdiIW7EskQL6uNP4tblOVHspF9XjXysM9lKPOwF
YBptDAY4gUZGdFYKxVoqLwifk6ZlZW5Om/4urMLD+7Y7do52P38Xw93MxE4/LvosJf1HmdHszCEJ
BwO4DMHAidvyR5b7P+7cOe8ELUP1AAAAAElFTkSuQmCC"""


def get_logo():
    """
    Return the Icinga logo as PNG image bytes.

    Provides the bundled Icinga logo as a 100x35 px PNG.

    ### Returns
    - **bytes**: The decoded PNG image data.

    ### Example
    >>> get_logo()[:8]
    b'\\x89PNG\\r\\n\\x1a\\n'
    """
    return base64.b64decode(_LOGO_PNG_BASE64)


def get_service(
    uri,
    username,
    password,
    servicename,
    attrs='state',
    insecure=False,
    no_proxy=False,
    timeout=3,
):
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
    uri = f'{uri.rstrip("/")}/v1/objects/services'
    data = {
        'filter': f'match("{servicename}", service.__name)',
        'attrs': ['name', *attrs.split(',')],
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


def remove_ack(
    uri,
    username,
    password,
    objectname,
    _type='service',
    insecure=False,
    no_proxy=False,
    timeout=3,
):
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
    uri = f'{uri.rstrip("/")}/v1/actions/remove-acknowledgement'
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


def remove_downtime(
    uri, username, password, downtime, insecure=False, no_proxy=False, timeout=3
):
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


def render_notification_mail(rows, logo_cid, hostname):
    """
    Render the plain-text and HTML body of an Icinga notification mail.

    Turns a list of label/value rows into a two-column notification: a plain-text version and an
    HTML version whose header references the bundled logo by Content-ID. Cell values are treated as
    untrusted and HTML-escaped; a newline becomes `<br>` and a value that is a URL becomes a link.

    ### Parameters
    - **rows** (`list` of `dict`): One row per line. Each dict has:
      - `left_column` (`str`): The label.
      - `right_column` (`str` or falsy): The value. Escaped before it reaches the HTML.
      - `right_column_attributes` (`str`, optional): Extra attributes inserted verbatim into the
        value cell's `<td>` (e.g. a fixed `style="..."`). The caller must keep this trusted; it is
        not escaped.
    - **logo_cid** (`str`): Content-ID of the inline logo image as produced by
      `email.utils.make_msgid()` (with angle brackets); the brackets are stripped for the `cid:`
      reference.
    - **hostname** (`str`): Name of the host generating the notification, shown in the footer.

    ### Returns
    - **tuple** (`str`, `str`): `(plain_text, html)`.

    ### Notes
    - `right_column_attributes` is the only field inserted without escaping, so callers must build
      it from trusted data only (a state-keyed color lookup, not raw external input).
    """
    row_template = Template("""
                <tr>
                    <th width="180px" class="$row_class">$left_column</th><td class="$row_class" $right_column_attributes>$right_column</td>
                </tr>
""")

    html_template = Template("""
<html><head><style type="text/css">
body {text-align: center; font-family: Verdana, sans-serif; font-size: 10pt;}
img.logo {float: left; margin: 10px 10px 10px; vertical-align: middle}
img.link {float: right;  margin: 0px 1px; vertical-align: middle}
span {font-family: Verdana, sans-serif; font-size: 12pt;}
table {text-align:center; margin-left: auto; margin-right: auto; border: 1px solid black;}
th {white-space: nowrap;}
th.even {background-color: #D9D9D9;}
td.even {background-color: #F2F2F2;}
th.odd {background-color: #F2F2F2;}
td.odd {background-color: #FFFFFF;}
th,td {font-family: Verdana, sans-serif; font-size: 10pt; text-align:left;}
th.customer {width: 600px; background-color: #004488; color: #ffffff;}
p.foot {width: 1002px; background-color: #004488; color: #ffffff; margin-left: auto; margin-right: auto;};
    </style></head>
        <body>
            <table width="1000px">
                <tr>
                    <td><img class="logo" src="cid:$logo_cid"></td><td><span>Icinga Monitoring System Notification</span></td>
                </tr>
                $table
            </table>

            <p class="foot">Generated by Icinga2 on $icinga_host, the OpenSource monitoring solution.</p>
        </body>
</html>
""")

    table = ''
    plain = ''
    for index, row in enumerate(rows):
        value = row.get('right_column')
        plain += f'{row["left_column"]} {value if value else ""}\n'

        if value:
            if value.startswith('http'):
                safe = html.escape(value, quote=True)
                cell = f'<a href="{safe}">{safe}</a>'
            else:
                cell = html.escape(value).replace('\n', '<br>')
        else:
            cell = ''

        table += row_template.substitute(
            row_class='even' if index % 2 == 0 else 'odd',
            left_column=html.escape(row['left_column']),
            right_column_attributes=row.get('right_column_attributes', ''),
            right_column=cell,
        )

    # the logo_cid arrives wrapped in <> from make_msgid(); the HTML cid: needs it without
    html_body = html_template.substitute(
        table=table,
        icinga_host=html.escape(hostname),
        logo_cid=logo_cid[1:-1],
    )
    return plain, html_body


def set_ack(
    uri,
    username,
    password,
    objectname,
    _type='service',
    author='Linuxfabrik lib.icinga',
    insecure=False,
    no_proxy=False,
    timeout=3,
):
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
    uri = f'{uri.rstrip("/")}/v1/actions/acknowledge-problem'
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


def set_downtime(
    uri,
    username,
    password,
    objectname,
    _type='service',
    starttime=None,
    endtime=None,
    author='Linuxfabrik lib.icinga',
    insecure=False,
    no_proxy=False,
    timeout=3,
):
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

    uri = f'{uri.rstrip("/")}/v1/actions/schedule-downtime'
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
