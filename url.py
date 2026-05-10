#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Get for example HTML or JSON from an URL."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026051002'

import base64
import json
import re
import ssl
import urllib.parse

# httpx is imported lazily inside fetch() so unrelated plugins that pull `lib.url` only
# transitively (e.g. via `lib.net`) keep working on hosts where httpx is not installed yet
try:
    import httpx
except ImportError:
    httpx = None

from . import txt


# stdlib ssl version names; '1.0' first because it is the most permissive minimum
_TLS_VERSIONS = {
    '1.0': ssl.TLSVersion.TLSv1,
    '1.1': ssl.TLSVersion.TLSv1_1,
    '1.2': ssl.TLSVersion.TLSv1_2,
    '1.3': ssl.TLSVersion.TLSv1_3,
}


def _redact_url(url):
    """Strip `token=...` and `password=...` query parameters before logging."""
    return re.sub(r'(token|password)=([^&]+)', r'\1=********', url)


def _build_ssl_context(insecure, tls_min, tls_max):
    """Build an SSL context with optional version pinning and ALPN advertised.

    ALPN ('h2', 'http/1.1') is advertised regardless of the requested HTTP version so the
    negotiated protocol can be inspected via `extended=True` for compliance plugins.
    """
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    if tls_min is not None:
        if tls_min not in _TLS_VERSIONS:
            raise ValueError(
                f'Invalid tls_min "{tls_min}"; expected one of '
                f'{sorted(_TLS_VERSIONS)}'
            )
        ctx.minimum_version = _TLS_VERSIONS[tls_min]
    if tls_max is not None:
        if tls_max not in _TLS_VERSIONS:
            raise ValueError(
                f'Invalid tls_max "{tls_max}"; expected one of '
                f'{sorted(_TLS_VERSIONS)}'
            )
        ctx.maximum_version = _TLS_VERSIONS[tls_max]
    ctx.set_alpn_protocols(['h2', 'http/1.1'])
    return ctx


def _capture_tls_info(response):
    """Extract TLS metadata from a streaming httpx response. Returns a 3-tuple
    `(tls_version, alpn, peer_cert_der)`. All entries are `None` over plain HTTP, when the
    network stream has already been released, or when httpx does not expose the SSL object
    (for example when a multiplexed HTTP/2 stream reuses an earlier connection).
    """
    stream = response.extensions.get('network_stream')
    if stream is None:
        return None, None, None
    ssl_obj = stream.get_extra_info('ssl_object')
    if ssl_obj is None:
        return None, None, None
    try:
        # getpeercert takes its `binary_form` argument positionally in some httpx/httpcore
        # configurations the SSL object hands us the C-level _sslobj, which rejects keyword
        # arguments
        return (
            ssl_obj.version(),
            ssl_obj.selected_alpn_protocol(),
            ssl_obj.getpeercert(True) or None,
        )
    except (AttributeError, TypeError, ValueError):
        return None, None, None


def fetch(
    url,
    insecure=False,
    no_proxy=False,
    timeout=8,
    header=None,
    data=None,
    encoding='urlencode',
    digest_auth_user=None,
    digest_auth_password=None,
    extended=False,
    to_text=True,
    http_version='1.1',
    tls_min=None,
    tls_max=None,
):
    """
    Fetch any URL with optional POST, basic/digest authentication and SSL/TLS handling.

    The HTTP engine is `httpx`. Sync only. HTTP/1.0 and HTTP/1.1 share the same h11 transport
    and are reported as `HTTP/1.1` by the server; pin TLS versions via `tls_min` / `tls_max`
    if you need wire-level control.

    HTTP/3 is accepted as a parameter value (`http_version='3'`) but not yet implemented and
    returns a clean error.

    Flowchart:

        Start
         |
         |--> Encode body (urlencode | serialized-json)
         |
         |--> Set headers (user first, then forced Connection: close + User-Agent)
         |
         |--> Build SSL context (insecure?, tls_min, tls_max, ALPN)
         |
         |--> Build httpx.Client (auth, http1/http2, proxy, timeout)
         |
         |--> client.stream(method, url, ...)
         |    |--> Capture TLS metadata from network stream
         |    |--> raise_for_status() on 4xx/5xx
         |    |--> Read body
         |
         |--> Decode body via response charset (default UTF-8)
         |
         |--> Return (True, body)            if extended is False
         |    Return (True, extended_dict)   if extended is True
        End

    ### Parameters
    - **url** (`str`):
        The URL to fetch.
    - **insecure** (`bool`, optional):
        If True, disables SSL certificate validation. Defaults to False.
    - **no_proxy** (`bool`, optional):
        If True, disables environment-based proxy detection (`HTTP_PROXY`, `HTTPS_PROXY`,
        `NO_PROXY`). Defaults to False.
    - **timeout** (`int`, optional):
        Timeout in seconds for the request, applied to all phases (connect, read, write,
        pool). Defaults to 8 seconds.
    - **header** (`dict`, optional):
        Headers to include in the request. Note: `Connection: close` and the
        `User-Agent: Linuxfabrik Monitoring Plugins` header are always set after the user's
        headers and override any user-supplied value of the same name.
    - **data** (`dict`, optional):
        Data to send in the request body. Truthy data triggers a POST.
    - **encoding** (`str`, optional):
        The encoding type for the request body. Defaults to `'urlencode'`. Also supports
        `'serialized-json'`.
    - **digest_auth_user** (`str`, optional):
        The username for HTTP Digest Authentication. Composes correctly with `insecure`.
    - **digest_auth_password** (`str`, optional):
        The password for HTTP Digest Authentication.
    - **extended** (`bool`, optional):
        If True, returns a dict with response body, status code, response headers, plus
        connection telemetry (`timings`, `tls_version`, `alpn`, `peer_cert_der`).
    - **to_text** (`bool`, optional):
        If True (default), converts the response body to text via the response charset.
    - **http_version** (`str`, optional):
        One of `'1.0'`, `'1.1'`, `'2'`, `'3'`. `'1.0'` is served by the same h11 transport
        as `'1.1'`. `'3'` is reserved and returns an error until QUIC support lands. Default
        `'1.1'`.
    - **tls_min** (`str`, optional):
        Minimum TLS version, one of `'1.0'`, `'1.1'`, `'1.2'`, `'1.3'`. Default uses the
        system default (typically TLS 1.2 on modern OpenSSL).
    - **tls_max** (`str`, optional):
        Maximum TLS version, same accepted values as `tls_min`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the request was successful, False otherwise.
      - **result** (`str` | `bytes` | `dict`):
        - On success, the response body (text or bytes depending on `to_text`).
        - On success with `extended=True`, a dict with keys:
            - `response`: response body
            - `status_code`: int
            - `response_header`: dict of response headers
            - `timings`: dict with at least `total` (seconds, float)
            - `tls_version`: str like `'TLSv1.3'` or None over plain HTTP
            - `alpn`: str like `'h2'` or `'http/1.1'` or None
            - `peer_cert_der`: DER-encoded server certificate as bytes, or None
        - On failure, an error message string.

    ### Example
    >>> result = fetch(
    ...     'https://api.example.com',
    ...     timeout=10,
    ...     header={'Authorization': 'Bearer token'},
    ... )

    >>> result = fetch('https://api.example.com', data={'key': 'value'}, extended=True)

    >>> # TLS-pinned compliance check, capture peer cert DER
    >>> ok, info = fetch(
    ...     'https://api.example.com',
    ...     tls_min='1.2', tls_max='1.3',
    ...     http_version='2',
    ...     extended=True,
    ... )
    """
    if header is None:
        header = {}
    if data is None:
        data = {}

    if httpx is None:
        return False, (
            'Python module "httpx" is not installed. '
            'Install it with `pip install \'httpx[http2]\'` or '
            '`dnf install python3-httpx python3-h2`.'
        )

    if http_version == '3':
        return False, f'HTTP/3 not implemented yet, while fetching {_redact_url(url)}'
    if http_version not in ('1.0', '1.1', '2'):
        return False, (
            f'Unsupported http_version "{http_version}"; expected one of '
            f'"1.0", "1.1", "2", "3"'
        )

    url_safe = _redact_url(url)

    if data:
        try:
            if encoding == 'urlencode':
                body = urllib.parse.urlencode(data)
            elif encoding == 'serialized-json':
                body = json.dumps(data)
            else:
                return False, f'Unknown encoding "{encoding}"'
            body = txt.to_bytes(body)
        except TypeError as e:
            return False, f'Type error "{e}", data="{data}"'
    else:
        body = None

    headers = dict(header)
    # urllib's AbstractHTTPHandler auto-sets application/x-www-form-urlencoded for any POST
    # body when the caller did not. Replicate that so consumers that relied on the implicit
    # behaviour (e.g. lib.icinga sending JSON without an explicit Content-Type) keep working.
    if body is not None and not any(k.lower() == 'content-type' for k in headers):
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    headers['Connection'] = 'close'
    headers['User-Agent'] = 'Linuxfabrik Monitoring Plugins'

    try:
        ctx = _build_ssl_context(insecure, tls_min, tls_max)
    except ValueError as e:
        return False, str(e)

    auth = None
    if digest_auth_user and digest_auth_password:
        auth = httpx.DigestAuth(digest_auth_user, digest_auth_password)

    try:
        client = httpx.Client(
            verify=ctx,
            http1=http_version in ('1.0', '1.1'),
            http2=http_version == '2',
            timeout=timeout,
            trust_env=not no_proxy,
            auth=auth,
            follow_redirects=True,
        )
    except Exception as e:
        return False, f'{e} while fetching {url_safe}'

    method = 'POST' if body else 'GET'
    tls_version = None
    alpn = None
    peer_cert_der = None
    body_bytes = b''
    status_code = None
    response_headers = {}
    elapsed_seconds = 0.0
    response_charset = None

    try:
        with client:
            with client.stream(method, url, headers=headers, content=body) as response:
                tls_version, alpn, peer_cert_der = _capture_tls_info(response)
                response.raise_for_status()
                body_bytes = response.read()
                status_code = response.status_code
                response_headers = dict(response.headers)
                elapsed_seconds = response.elapsed.total_seconds()
                response_charset = response.charset_encoding
    except httpx.HTTPStatusError as e:
        return False, (
            f'HTTP error "{e.response.status_code} {e.response.reason_phrase}"'
            f' while fetching {url_safe}'
        )
    except httpx.HTTPError as e:
        return False, f'URL error "{e}" for {url_safe}'
    except TypeError as e:
        return False, f'Type error "{e}", data="{data}"'
    except Exception as e:
        return False, f'{e} while fetching {url_safe}'

    try:
        charset = response_charset or 'UTF-8'
        body_decoded = body_bytes.decode(charset) if to_text else body_bytes

        if not extended:
            return True, body_decoded

        return True, {
            'response': body_decoded,
            'status_code': status_code,
            'response_header': response_headers,
            'timings': {'total': elapsed_seconds},
            'tls_version': tls_version,
            'alpn': alpn,
            'peer_cert_der': peer_cert_der,
        }
    except Exception as e:
        return False, f'{e} while fetching {url}'


def fetch_json(
    url,
    insecure=False,
    no_proxy=False,
    timeout=8,
    header=None,
    data=None,
    encoding='urlencode',
    digest_auth_user=None,
    digest_auth_password=None,
    extended=False,
    http_version='1.1',
    tls_min=None,
    tls_max=None,
):
    """
    Fetch JSON from a URL with optional POST, authentication and SSL/TLS handling.

    Thin wrapper around `fetch()` that decodes the response body as JSON. All `fetch()`
    parameters are forwarded; the only added behaviour is the JSON decode step.

    ### Parameters
    See `fetch()` for the shared parameters. `to_text` is forced to True because the JSON
    decoder needs a string.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the JSON was successfully fetched and parsed, False
        otherwise.
      - **result** (`dict` | `list` | `str`):
        - On success without `extended`: the parsed JSON document.
        - On success with `extended=True`: the same dict as `fetch()` plus a `response_json`
          key holding the parsed JSON document.
        - On failure: an error message string.

    ### Example
    >>> fetch_json('https://192.0.2.74/api/v2/?resource=cpu')
    (True, {'cpu': {'usage': '45%', 'temperature': '50C'}})
    """
    success, jsonst = fetch(
        url,
        data=data,
        digest_auth_password=digest_auth_password,
        digest_auth_user=digest_auth_user,
        encoding=encoding,
        extended=extended,
        header=header,
        http_version=http_version,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        tls_max=tls_max,
        tls_min=tls_min,
    )
    if not success:
        return False, jsonst

    try:
        if extended:
            jsonst['response_json'] = json.loads(jsonst['response'])
            return True, jsonst
        return True, json.loads(jsonst)
    except Exception as e:
        return False, f'{e}. No JSON object could be decoded.'


def get_latest_version_from_github(user, repo, key='tag_name'):
    """
    Get the newest release tag from a GitHub repository.

    This function fetches the latest release information from the GitHub API and retrieves
    the release tag.

    ### Parameters
    - **user** (`str`): The GitHub username or organization name.
    - **repo** (`str`): The GitHub repository name.
    - **key** (`str`, optional): The key to retrieve from the JSON response (default is
        `'tag_name'`).

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the latest version was successfully fetched, False
        otherwise.
      - **result** (`str` | `bool`):
        - The value of the specified key (e.g., the latest release tag) if successful.
        - `False` if no result was found or the GitHub API did not return any data.

    ### Example
    >>> get_latest_version_from_github('Linuxfabrik', 'monitoring-plugins')
    (True, 'v1.2.3')
    """
    url = f'https://api.github.com/repos/{user}/{repo}/releases/latest'
    success, result = fetch_json(url)

    if not success:
        return success, result
    if not isinstance(result, dict) or not result:
        return True, False

    return True, result.get(key, False)


def split_basic_auth(url):
    """Extract userinfo from `url` and return a `(url, headers)` tuple.

    The returned URL has any `user[:password]@` prefix stripped from
    its netloc so the credentials never reach the request line or
    any proxy log. If userinfo is present, `headers` contains the
    matching `Authorization: Basic ...` entry; otherwise it is an
    empty dict.

    Pass the returned `url` and `headers` to `lib.url.fetch()` /
    `lib.url.fetch_json()` so plugins can accept HTTP basic auth via
    the URL (e.g. `https://user:secret@host/path`) instead of
    exposing separate `--username` / `--password` arguments.

    >>> split_basic_auth('https://example.com/path')
    ('https://example.com/path', {})
    >>> u, h = split_basic_auth('https://alice:secret@example.com/path')
    >>> u
    'https://example.com/path'
    >>> h
    {'Authorization': 'Basic YWxpY2U6c2VjcmV0'}
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.username:
        return url, {}

    user = urllib.parse.unquote(parsed.username)
    password = urllib.parse.unquote(parsed.password or '')
    token = txt.to_text(base64.b64encode(txt.to_bytes(f'{user}:{password}')))

    netloc = parsed.hostname or ''
    if parsed.port is not None:
        netloc = f'{netloc}:{parsed.port}'
    stripped = urllib.parse.urlunparse(parsed._replace(netloc=netloc))

    return stripped, {'Authorization': f'Basic {token}'}


def strip_tags(html):
    """
    Strips all HTML tags from a given string.

    This function removes any HTML tags from the input string, leaving only the raw text
    content.

    ### Parameters
    - **html** (`str`): The string containing HTML tags to be stripped.

    ### Returns
    - **str**: The input string with all HTML tags removed.

    ### Example
    >>> strip_tags('<div>Hello, <b>world</b>!</div>')
    'Hello, world!'
    """
    return re.sub(r'<[^<]+?>', '', html or '')
