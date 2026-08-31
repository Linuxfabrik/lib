#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Get for example HTML or JSON from an URL."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082505'

import base64
import json
import os
import re
import socket
import ssl
import time
import urllib.parse

# httpx is imported lazily inside fetch() so an unrelated consumer that pulls `lib.url` only
# transitively (e.g. via `lib.net`) keep working on hosts where httpx is not installed yet
try:
    import httpx
except ImportError:
    httpx = None
try:
    import httpcore
except ImportError:
    httpcore = None

from . import txt

# stdlib ssl version names; '1.0' first because it is the most permissive minimum.
# `ssl.TLSVersion` was added in Python 3.7. Build the dict only when available so
# `import lib.url` still works on older interpreters (e.g. RHEL 8's default `python3`
# = 3.6) - a consumer that doesn't actually use TLS version pinning then continues
# to work. Callers that pass `tls_min` / `tls_max` get a clearer RuntimeError in
# `_build_ssl_context()` instead of an AttributeError at import time.
_TLS_VERSIONS = {}
if hasattr(ssl, 'TLSVersion'):
    _TLS_VERSIONS = {
        '1.0': ssl.TLSVersion.TLSv1,
        '1.1': ssl.TLSVersion.TLSv1_1,
        '1.2': ssl.TLSVersion.TLSv1_2,
        '1.3': ssl.TLSVersion.TLSv1_3,
    }

# Transport headers that are safe to keep when a redirect crosses the origin.
# httpx only strips `Authorization` and `Cookie` on a cross-origin redirect, so
# any other credential header a caller set (an API session token such as
# Redfish's `X-Auth-Token`, an API key, ...) would still be sent to the new,
# possibly attacker-controlled host. Rather than enumerate every auth header a
# caller might use, keep only these benign transport headers on a cross-origin
# hop and drop everything else the caller supplied.
_REDIRECT_SAFE_HEADERS = frozenset(
    {
        'accept',
        'accept-encoding',
        'accept-language',
        'connection',
        'content-length',
        'content-type',
        'host',
        'transfer-encoding',
        'user-agent',
    }
)


# Certificate verification failures an operator runs into in practice, keyed by
# the OpenSSL X509_V_ERR_* code that `ssl.SSLCertVerificationError` reports in
# `verify_code`. The code is matched instead of the message text, which is not
# stable across OpenSSL releases. Codes measured against OpenSSL 3.5 with the
# badssl.com endpoints plus a real host serving an incomplete chain.
_TLS_CHAIN_HINT = (
    'The server sends no intermediate certificate to link its own certificate to '
    "a trusted root, or the issuing authority is not in this host's trust store. "
    'A browser papers over this by fetching the missing certificate itself, other '
    'clients do not. Compare with '
    '"openssl s_client -connect HOST:PORT -servername HOST": a chain listing only '
    'the server certificate has to be completed on the server, a private issuer '
    "has to be added to this host's trust store."
)
TLS_VERIFY_HINTS = {
    2: _TLS_CHAIN_HINT,  # unable to get issuer certificate
    9: (
        'The server certificate is not valid yet. Compare the clock on this host '
        'with the clock on the server.'
    ),
    10: 'The server certificate has expired and has to be renewed on the server.',
    18: (
        "The server presents a self-signed certificate. Add it to this host's "
        'trust store, or accept an unverified connection for this endpoint on '
        'purpose.'
    ),
    19: (
        'The chain ends in a certificate authority this host does not trust. Add '
        "that authority's certificate to this host's trust store."
    ),
    20: _TLS_CHAIN_HINT,  # unable to get local issuer certificate
    21: _TLS_CHAIN_HINT,  # unable to verify the first certificate
    62: (
        'The certificate was not issued for the name that was requested. Use a '
        'name the certificate covers, or have one issued for the name you check.'
    ),
}


def _tls_verify_error(exc):
    """Return the certificate verification error behind an exception, if any.

    Transport libraries wrap the original `ssl` exception, so the cause chain is
    walked rather than the outermost type inspected. Returns None when the
    failure was not a certificate verification failure.
    """
    import ssl

    seen = []
    while exc is not None and exc not in seen:
        if isinstance(exc, ssl.SSLCertVerificationError):
            return exc
        seen.append(exc)
        exc = exc.__cause__ or exc.__context__
    return None


def _tls_verify_message(exc, url_safe):
    """Return a full error message for a certificate that does not verify.

    Replaces the raw library wording, which names the failure twice and buries
    what an operator has to do about it. Returns None when the request failed
    for another reason.
    """
    verify_error = _tls_verify_error(exc)
    if verify_error is None:
        return None
    reason = (getattr(verify_error, 'verify_message', '') or '').strip().rstrip('.')
    hint = TLS_VERIFY_HINTS.get(verify_error.verify_code, '')
    message = f'TLS certificate verification failed for {url_safe}'
    if reason:
        message += f': {reason}'
    return message + '.' + (f' {hint}' if hint else '')


def _default_port(url):
    """Return the URL's port, filling in the scheme default when it is implicit."""
    if url.port is not None:
        return url.port
    return 443 if url.scheme == 'https' else 80


def _leaks_credentials_on_redirect(src, dst):
    """Return True if a redirect from `src` to `dst` crosses the origin in a way
    that must not carry credential headers. Mirrors httpx's own condition for
    stripping `Authorization`: a plain same-host HTTP-to-HTTPS upgrade is allowed,
    every other scheme/host/port change is treated as cross-origin."""
    same_origin = (
        src.scheme == dst.scheme
        and src.host == dst.host
        and _default_port(src) == _default_port(dst)
    )
    if same_origin:
        return False
    https_upgrade = (
        src.host == dst.host
        and src.scheme == 'http'
        and _default_port(src) == 80
        and dst.scheme == 'https'
        and _default_port(dst) == 443
    )
    return not https_upgrade


def _install_safe_redirect_stripping(client):
    """Wrap an httpx client's redirect-header logic so credential headers are
    dropped when a redirect crosses the origin. Patched on the instance (not via
    subclassing) so it also works when a caller has replaced `httpx.Client` with
    a test double, and so importing lib.url never touches `httpx` at module
    scope. httpx looks `_redirect_headers` up on the instance, so the wrapper
    shadows the original bound method."""
    original = getattr(client, '_redirect_headers', None)
    if original is None:
        # A test double or a future httpx without this internal: nothing to wrap.
        return client

    def _redirect_headers(request, url, method):
        headers = original(request, url, method)
        if _leaks_credentials_on_redirect(request.url, url):
            for name in list(headers.keys()):
                if name.lower() not in _REDIRECT_SAFE_HEADERS:
                    del headers[name]
        return headers

    client._redirect_headers = _redirect_headers
    return client


def _redact_url(url):
    """Strip `token=...` and `password=...` query parameters before logging."""
    return re.sub(r'(token|password)=([^&]+)', r'\1=********', url)


def _body_hint(data):
    """Describe a request body for an error message without disclosing its values.

    Request bodies routinely carry credentials (a login `password`, an API key, a bearer
    token). Rendering the body itself would put them into the caller's output, and
    `txt.sanitize_sensitive_data()` cannot be relied on to catch that: a Python mapping renders
    as `{'password': 'x'}`, which is neither the `password=x` nor the `"password": "x"` form its
    patterns match. Only the field names are reported, which is what identifies the offending
    field while the values stay out of the message.
    """
    if isinstance(data, dict):
        return (
            'body fields: ' + ', '.join(sorted(map(str, data)))
            if data
            else 'empty body'
        )
    return f'body of type {type(data).__name__}'


def _build_ssl_context(insecure, tls_min, tls_max, cacert=None):
    """Build an SSL context with optional version pinning and ALPN advertised.

    ALPN ('h2', 'http/1.1') is advertised regardless of the requested HTTP version so the
    negotiated protocol can be inspected via `extended=True` for a compliance check.

    `cacert` names a CA bundle to verify against, either a file or a directory of hashed
    certificates. It replaces the trust store of the host rather than adding to it, which is
    what `curl --cacert` and `REQUESTS_CA_BUNDLE` do as well: an endpoint whose certificate a
    private CA signed is then the only thing that verifies, and a certificate from a public CA
    no longer does. Handing the bundle to `create_default_context()` is what makes the
    difference; `load_verify_locations()` on a context that already holds the trust store
    would leave every public CA valid. Verified against Python 3.14 on Fedora 44.

    A bundle that cannot be read raises a ValueError rather than leaving the caller with a
    connection that verifies against something else than it asked for.
    """
    try:
        if not cacert:
            ctx = ssl.create_default_context()
        elif os.path.isdir(cacert):
            ctx = ssl.create_default_context(capath=cacert)
        else:
            ctx = ssl.create_default_context(cafile=cacert)
    except (OSError, ssl.SSLError) as e:
        raise ValueError(f'Cannot read the CA bundle "{cacert}": {e}') from e
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    if tls_min is not None or tls_max is not None:
        if not _TLS_VERSIONS:
            raise RuntimeError(
                'TLS version pinning (`tls_min` / `tls_max`) requires Python 3.7+ '
                '(`ssl.TLSVersion`); this interpreter is too old.'
            )
    if tls_min is not None:
        if tls_min not in _TLS_VERSIONS:
            raise ValueError(
                f'Invalid tls_min "{tls_min}"; expected one of {sorted(_TLS_VERSIONS)}'
            )
        ctx.minimum_version = _TLS_VERSIONS[tls_min]
    if tls_max is not None:
        if tls_max not in _TLS_VERSIONS:
            raise ValueError(
                f'Invalid tls_max "{tls_max}"; expected one of {sorted(_TLS_VERSIONS)}'
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


# Phase-by-phase timing instrumentation for `extended=True`. We swap httpcore's default
# network backend with a custom one that records the wall-clock time spent on DNS resolution,
# TCP connect, TLS handshake, TTFB (request-write to first response byte) and transfer
# (first response byte to last). The custom backend is opt-in: `fetch(extended=False)`
# takes the default fast path with zero instrumentation overhead.
def _build_timing_classes():
    """Build the timing-aware NetworkBackend / NetworkStream subclasses tied to the runtime
    httpcore module. Returns `(backend_cls, stream_cls)` or `(None, None)` when httpcore
    does not expose the public `NetworkBackend` / `NetworkStream` base classes (very old
    httpcore where the API was still private).
    """
    if httpcore is None or not hasattr(httpcore, 'NetworkBackend'):
        return None, None

    class _TimingNetworkStream(httpcore.NetworkStream):
        """Wraps an existing httpcore NetworkStream and times TLS handshake, TTFB and
        transfer. The underlying stream still does the I/O; we only record timestamps.
        """

        def __init__(self, inner, timings):
            self._inner = inner
            self._timings = timings
            self._request_sent_at = None
            self._first_byte_at = None

        def read(self, max_bytes, timeout=None):
            data = self._inner.read(max_bytes, timeout)
            now = time.monotonic()
            if data:
                if self._first_byte_at is None and self._request_sent_at is not None:
                    self._first_byte_at = now
                    self._timings['ttfb'] = now - self._request_sent_at
                if self._first_byte_at is not None:
                    self._timings['transfer'] = now - self._first_byte_at
            return data

        def write(self, buffer, timeout=None):
            self._inner.write(buffer, timeout)
            self._request_sent_at = time.monotonic()

        def close(self):
            return self._inner.close()

        def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            t = time.monotonic()
            wrapped = self._inner.start_tls(
                ssl_context,
                server_hostname=server_hostname,
                timeout=timeout,
            )
            self._timings['tls'] = time.monotonic() - t
            return _TimingNetworkStream(wrapped, self._timings)

        def get_extra_info(self, info):
            return self._inner.get_extra_info(info)

    class _TimingBackend(httpcore.NetworkBackend):
        """NetworkBackend that resolves DNS and opens the TCP socket itself so DNS and
        connect can be timed separately. Falls back to a plain httpcore default backend
        for unix sockets (not used by HTTP(S) checks).
        """

        def __init__(self):
            self.timings = {}
            # The default sync backend is used as a fallback for connect_unix_socket.
            # Importing it lazily so a missing private path doesn't crash the lib import.
            try:
                from httpcore._backends.sync import SyncBackend

                self._default = SyncBackend()
            except Exception:
                self._default = None

        def connect_tcp(
            self,
            host,
            port,
            timeout=None,
            local_address=None,
            socket_options=None,
        ):
            t = time.monotonic()
            try:
                addrs = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            except socket.gaierror as e:
                raise httpcore.ConnectError(str(e)) from e
            self.timings['dns'] = time.monotonic() - t

            # A name usually resolves to more than one address, and only one of
            # them may be listening. "localhost" on a dual-stacked host is the
            # everyday case: it yields ::1 before 127.0.0.1, while a service
            # bound to 0.0.0.0 answers on the second address only. Walk the
            # whole list the way socket.create_connection() does, so a refused
            # or unreachable first address does not end the attempt.
            sock = None
            last_error = None
            t = time.monotonic()
            for family, socktype, proto, _, sockaddr in addrs:
                try:
                    sock = socket.socket(family, socktype, proto)
                    if local_address is not None:
                        sock.bind((local_address, 0))
                    if socket_options is not None:
                        for opt in socket_options:
                            sock.setsockopt(*opt)
                    sock.settimeout(timeout)
                    sock.connect(sockaddr)
                except (OSError, socket.timeout) as e:
                    last_error = e
                    if sock is not None:
                        sock.close()
                        sock = None
                    continue
                break
            if sock is None:
                raise httpcore.ConnectError(str(last_error)) from last_error
            self.timings['connect'] = time.monotonic() - t

            # Wrap the raw socket in httpcore's standard sync stream so that read/write
            # semantics match httpcore's expectations, then wrap again in our timing
            # stream to capture TLS / TTFB / transfer.
            from httpcore._backends.sync import SyncStream

            inner = SyncStream(sock)
            return _TimingNetworkStream(inner, self.timings)

        def connect_unix_socket(self, path, timeout=None, socket_options=None):
            if self._default is None:
                raise httpcore.ConnectError('unix sockets unsupported in this backend')
            return self._default.connect_unix_socket(
                path,
                timeout=timeout,
                socket_options=socket_options,
            )

        def sleep(self, seconds):
            time.sleep(seconds)

    return _TimingBackend, _TimingNetworkStream


def _build_timing_transport(ssl_context, http1, http2, proxy):
    """Construct an httpx.HTTPTransport whose underlying connection pool uses our timing
    backend. Returns (transport, backend) or (None, None) if the runtime httpcore API
    does not expose the hooks we need; the caller falls back to default httpx behaviour
    and reports only `total` in the timings dict.

    `proxy` is the proxy URL the request has to take, or None for a direct connection.
    It has to be handled here rather than by the client: httpx only consults the
    environment for proxies while it builds the transport itself
    (`allow_env_proxies = trust_env and transport is None`), and a proxy handed to the
    client would be served by a mount of its own, which would bypass this transport and
    with it the phase timings. So the pool itself has to speak to the proxy.
    """
    backend_cls, _ = _build_timing_classes()
    if backend_cls is None:
        return None, None
    backend = backend_cls()
    transport = httpx.HTTPTransport(
        verify=ssl_context,
        http1=http1,
        http2=http2,
        trust_env=False,
    )
    if proxy:
        transport._pool = httpcore.HTTPProxy(
            proxy_url=proxy,
            ssl_context=ssl_context,
            http1=http1,
            http2=http2,
            network_backend=backend,
        )
    else:
        transport._pool = httpcore.ConnectionPool(
            ssl_context=ssl_context,
            http1=http1,
            http2=http2,
            network_backend=backend,
        )
    return transport, backend


def _check_github_name(value, name):
    """Reject anything that is not a GitHub owner or repository name.

    Owner and repository names end up in the path of the API request. Upstream limits
    them to letters, digits and `.`, `_`, `-`, so anything else is either a typo or an
    attempt to reach a different endpoint through the path. `..` is refused separately
    because the regex alone would let it pass and it is exactly what a path traversal
    needs.

    Returns a `(success, result)` tuple suitable for `lib.base.coe()`.
    """
    if (
        not isinstance(value, str)
        or '..' in value
        or not re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$', value)
    ):
        return False, f'Refusing {name} that is not a GitHub name: {value}'
    return True, value


def _check_github_ref(value, name):
    """Reject anything that is not a usable git ref (branch or tag).

    Same reasoning as `_check_github_name()`, except that a ref legitimately carries
    slashes (`feature/some-branch`), so those stay allowed while `..`, query strings and
    everything else that would change the shape of the request do not.

    Returns a `(success, result)` tuple suitable for `lib.base.coe()`.
    """
    if (
        not isinstance(value, str)
        or '..' in value
        or not re.match(r'^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$', value)
    ):
        return False, f'Refusing {name} that is not a git ref: {value}'
    return True, value


def _fetch_github_json(url, insecure, no_proxy, proxy, timeout, header):
    """Fetch a GitHub API endpoint, telling "nothing there" apart from "could not ask".

    GitHub answers 404 both for a repository that does not exist and for one that has no
    release yet. A consumer cannot tell those apart and does not need to, because both
    mean there is nothing here to compare against, so that case comes back as `(True,
    None)`. A request that never got an answer comes back as `(False, errormessage)` and
    stays distinguishable. The two errors an administrator can act on get a message that
    names the remedy: 401 is a token GitHub does not accept, 403 and 429 are the
    exhausted rate limit.

    Returns a `(success, result)` tuple.
    """
    success, result = fetch_json(
        url,
        extended=True,
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        proxy=proxy,
        response_on_error=True,
        timeout=timeout,
    )
    status_code = result.get('status_code') if isinstance(result, dict) else None

    if status_code == 404:
        return True, None
    if status_code == 401:
        return False, (
            'GitHub rejected the API token. Check that it is still valid and has not'
            ' expired.'
        )
    if status_code in (403, 429):
        return False, (
            f'GitHub refused the request with HTTP {status_code}. Without a token'
            f' the API allows 60 requests per hour and IP address; supply one or'
            f' ask less often.'
        )
    if not success:
        if isinstance(result, str):
            return False, result
        return False, f'GitHub answered with HTTP {status_code}.'
    if not isinstance(result, dict):
        return False, 'GitHub answered with an unreadable response.'

    return True, result.get('response_json')


def compare_github_refs(
    user,
    repo,
    base,
    head,
    insecure=False,
    no_proxy=False,
    proxy=None,
    timeout=8,
    header=None,
):
    """
    Count how far a GitHub repository's `head` ref is ahead of its `base` ref.

    Answers "how many commits has this branch gained since the release I am running",
    which is what a consumer needs to say something concrete about an installation
    tracking a development branch instead of a release.

    Note that GitHub also reports a non-zero count when the two refs have diverged, so
    the number says how many commits are on `head` and not on `base` - not that `base`
    is simply an ancestor of `head`.

    ### Parameters
    - **user** (`str`): The GitHub username or organization name.
    - **repo** (`str`): The GitHub repository name.
    - **base** (`str`): The ref to compare from, typically the installed tag.
    - **head** (`str`): The ref to compare to, typically a branch such as `main`.
    - **insecure**, **no_proxy**, **timeout**, **header**: See
        `get_latest_version_from_github()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the comparison was successfully fetched, False
        otherwise.
      - **result** (`int` | `bool`):
        - The number of commits `head` carries that `base` does not.
        - `False` if GitHub did not answer with a comparison, for example because
          one of the two refs does not exist.

    ### Example
    >>> compare_github_refs('Linuxfabrik', 'monitoring-plugins', 'v1.2.3', 'main')
    (True, 38)
    """
    success, result = _check_github_name(user, 'GitHub user')
    if not success:
        return success, result
    success, result = _check_github_name(repo, 'GitHub repository')
    if not success:
        return success, result
    success, result = _check_github_ref(base, 'GitHub base ref')
    if not success:
        return success, result
    success, result = _check_github_ref(head, 'GitHub head ref')
    if not success:
        return success, result

    url = f'https://api.github.com/repos/{user}/{repo}/compare/{base}...{head}'
    success, result = _fetch_github_json(url, insecure, no_proxy, proxy, timeout, header)

    if not success:
        return success, result
    if not isinstance(result, dict) or 'ahead_by' not in result:
        return True, False

    try:
        return True, int(result['ahead_by'])
    except (TypeError, ValueError):
        return True, False


def _fetch_once(
    url,
    insecure=False,
    no_proxy=False,
    proxy=None,
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
    method=None,
    response_on_error=False,
    cacert=None,
):
    """Make one attempt of `fetch()`, which documents every parameter and wraps this
    in its retry loop.
    """
    if header is None:
        header = {}
    if data is None:
        data = {}

    if httpx is None:
        return False, (
            'Python module "httpx" is not installed. '
            "Install it with `pip install 'httpx[http2]'` or "
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
            return (
                False,
                f'Type error "{e}" while encoding the request body ({_body_hint(data)})',
            )
    else:
        body = None

    headers = dict(header)
    # Content-Length is transport framing owned by the HTTP engine, which derives it from the
    # actual body. A caller-supplied value can only disagree with that body; h11 then refuses to
    # serialize the request with "Too much data for declared Content-Length". Drop any incoming
    # Content-Length so the correct value is always computed from the body we send.
    headers = {k: v for k, v in headers.items() if k.lower() != 'content-length'}
    # urllib's AbstractHTTPHandler auto-sets application/x-www-form-urlencoded for any POST
    # body when the caller did not. Replicate that so consumers that relied on the implicit
    # behaviour (e.g. lib.icinga sending JSON without an explicit Content-Type) keep working.
    if body is not None and not any(k.lower() == 'content-type' for k in headers):
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    headers['Connection'] = 'close'
    headers['User-Agent'] = 'Linuxfabrik Monitoring Plugins'

    try:
        ctx = _build_ssl_context(insecure, tls_min, tls_max, cacert=cacert)
    except ValueError as e:
        return False, str(e)

    auth = None
    if digest_auth_user and digest_auth_password:
        auth = httpx.DigestAuth(digest_auth_user, digest_auth_password)

    # Which proxy the request takes. `no_proxy` wins over everything, an explicit `proxy`
    # wins over the environment including the exceptions it lists in `no_proxy`, and
    # without either the environment applies. The environment is resolved here rather than
    # left to httpx only because the extended path installs a transport of its own, and
    # httpx skips its environment handling as soon as a caller does that.
    effective_proxy = None
    if not no_proxy:
        if proxy:
            # a bare `proxy.example.com:3128` means a plain HTTP proxy
            effective_proxy = proxy if '://' in proxy else f'http://{proxy}'
        elif extended:
            # imported here and not at module scope: lib.net imports this module, so the
            # dependency only works in this direction at call time
            from . import net

            success, resolved = net.get_proxy(url)
            if success:
                effective_proxy = resolved

    # Phase-by-phase timings are only collected when the caller asks for the extended
    # response. The default fast path uses httpx's built-in transport with no
    # instrumentation overhead.
    timing_transport = None
    timing_backend = None
    if extended:
        timing_transport, timing_backend = _build_timing_transport(
            ctx,
            http_version in ('1.0', '1.1'),
            http_version == '2',
            effective_proxy,
        )

    try:
        client_kwargs = {
            'timeout': timeout,
            'trust_env': not no_proxy,
            'auth': auth,
            'follow_redirects': True,
        }
        if effective_proxy and timing_transport is None:
            # An explicit proxy is served by a mount of its own, which is what we want
            # here. With the timing transport it would bypass that transport, so there the
            # proxy sits in the transport's own pool instead.
            client_kwargs['proxy'] = effective_proxy
        if timing_transport is not None:
            client_kwargs['transport'] = timing_transport
        else:
            client_kwargs['verify'] = ctx
            client_kwargs['http1'] = http_version in ('1.0', '1.1')
            client_kwargs['http2'] = http_version == '2'
        client = _install_safe_redirect_stripping(httpx.Client(**client_kwargs))
    except Exception as e:
        return False, f'{e} while fetching {url_safe}'

    method = (method or ('POST' if body else 'GET')).upper()
    tls_version = None
    alpn = None
    peer_cert_der = None
    body_bytes = b''
    status_code = None
    response_headers = {}
    elapsed_seconds = 0.0
    response_charset = None

    success = True
    try:
        # No parenthesized context managers here: they are Python 3.10+ syntax and
        # break `import lib.url` on RHEL 8's default Python 3.6.
        # fmt: off
        with client, client.stream(method, url, headers=headers, content=body) as response:
            # fmt: on
            tls_version, alpn, peer_cert_der = _capture_tls_info(response)
            # Read body and capture metadata before raise_for_status() so the
            # response_on_error path can surface error bodies, status codes and
            # timings to the caller (when using response_on_error).
            body_bytes = response.read()
            status_code = response.status_code
            # HTTP header field names are case-insensitive (RFC 9110, section 5.1).
            # Canonicalize them to lower case so callers can look a header up
            # deterministically regardless of how the server cased it. httpx
            # already lower-cases, but keep it explicit and backend-independent.
            response_headers = {
                key.lower(): value for key, value in response.headers.items()
            }
            elapsed_seconds = response.elapsed.total_seconds()
            response_charset = response.charset_encoding
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        if not response_on_error:
            return False, (
                f'HTTP error "{e.response.status_code} {e.response.reason_phrase}"'
                f' while fetching {url_safe}'
            )
        else:
            success = False
    except httpx.HTTPError as e:
        verify_message = _tls_verify_message(e, url_safe)
        if verify_message:
            return False, verify_message
        message = f'URL error "{e}" for {url_safe}'
        # A port that speaks TLS answers a plaintext request with a TLS record or
        # closes the connection, which surfaces as a protocol error naming
        # neither TLS nor the scheme.
        if url.lower().startswith('http://') and isinstance(
            e, (httpx.RemoteProtocolError, httpx.ConnectError)
        ):
            message += (
                '. If this endpoint speaks TLS, request it with "https://" '
                'instead of "http://"'
            )
        return False, message
    except TypeError as e:
        return False, (
            f'Type error "{e}" while fetching {url_safe} ({_body_hint(data)})'
        )
    except Exception as e:
        return False, f'{e} while fetching {url_safe}'

    try:
        charset = response_charset or 'UTF-8'
        if to_text:
            try:
                body_decoded = body_bytes.decode(charset)
            except UnicodeDecodeError:
                if response_charset:
                    # The server explicitly declared this charset, so a mismatch
                    # is a genuine error and must surface to the caller.
                    raise
                # No charset header was sent and our UTF-8 assumption was wrong.
                # Latin-1 maps every byte 1:1 and never fails, preserving bytes
                # like 0xb0 (° in ISO-8859-1) emitted by sensor firmware that
                # serves non-UTF-8 content without a charset header.
                body_decoded = body_bytes.decode('latin-1')
        else:
            body_decoded = body_bytes

        if not extended:
            return success, body_decoded

        timings = {'total': elapsed_seconds}
        if timing_backend is not None:
            timings.update(timing_backend.timings)
        return success, {
            'response': body_decoded,
            'status_code': status_code,
            'response_header': response_headers,
            'timings': timings,
            'tls_version': tls_version,
            'alpn': alpn,
            'peer_cert_der': peer_cert_der,
        }
    except Exception as e:
        return False, f'{e} while fetching {url}'




def fetch(
    url,
    insecure=False,
    no_proxy=False,
    proxy=None,
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
    method=None,
    response_on_error=False,
    cacert=None,
    retries=0,
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
         |--> Retry loop (`retries`), around everything below
         |
         |--> Encode body (urlencode | serialized-json)
         |
         |--> Set headers (user first, then forced Connection: close + User-Agent)
         |
         |--> Build SSL context (insecure?, cacert, tls_min, tls_max, ALPN)
         |
         |--> Build httpx.Client (auth, http1/http2, proxy, timeout)
         |
         |--> client.stream(method, url, ...)
         |    |--> Capture TLS metadata from network stream
         |    |--> Read body
         |    |--> raise_for_status() on 4xx/5xx
         |
         |--> Decode body via response charset (default UTF-8)
         |
         |--> Return (True, body)            if extended is False
         |    Return (True, extended_dict)   if extended is True
        End

    ### Parameters
    - **url** (`str`):
        The URL to fetch.
    - **cacert** (`str`, optional):
        Path to a CA bundle to verify the certificate against, either a file of PEM
        certificates or a directory of hashed ones, which is what `OS_CACERT`,
        `REQUESTS_CA_BUNDLE` and `curl --cacert` name as well. It replaces the trust store of
        the host instead of adding to it, so an endpoint signed by a public CA no longer
        verifies once a private bundle is named. A bundle that cannot be read is an error
        rather than a silent fallback to the trust store. Ignored when `insecure` is set,
        because that switches verification off altogether.
    - **insecure** (`bool`, optional):
        If True, disables SSL certificate validation. Defaults to False.
    - **proxy** (`str`, optional):
        Proxy URL to reach the target through, for example
        `http://user:password@proxy.example.com:3128`. The scheme defaults to `http` when
        omitted. Overrides the proxy the environment names together with the exceptions it
        lists in `NO_PROXY`, and is itself overridden by `no_proxy`. Defaults to `None`,
        which leaves the choice to the environment.
    - **no_proxy** (`bool`, optional):
        If True, disables environment-based proxy detection (`HTTP_PROXY`, `HTTPS_PROXY`,
        `NO_PROXY`). Defaults to False.
    - **timeout** (`int`, optional):
        Timeout in seconds for the request, applied to all phases (connect, read, write,
        pool). Defaults to 8 seconds.
    - **header** (`dict`, optional):
        Headers to include in the request. Note: `Connection: close` and the
        `User-Agent: Linuxfabrik Monitoring Plugins` header are always set after the user's
        headers and override any user-supplied value of the same name. A `Content-Length`
        header is always dropped; the HTTP engine derives the correct value from the body.
    - **data** (`dict`, optional):
        Data to send in the request body. Truthy data triggers a POST.
    - **method** (`str`, optional):
        Force the HTTP method (e.g. `'POST'`) regardless of the body. When omitted, the
        method is inferred from `data`: POST if a truthy body is present, GET otherwise.
        Use this to issue a bodyless POST (some APIs require POST as a pure verb but reject
        a request body and the Content-Type that comes with it).
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
    - **response_on_error** (`bool`, optional):
        If true, return the response for error conditions (useful when the response body of
        an API contains error details)
    - **retries** (`int`, optional):
        How many extra attempts to make when the request fails. `0` (default) means a single
        attempt. Useful against a flaky endpoint (a BMC, a storage controller) that drops the
        odd request. There is no delay between the attempts, because a check has a limited
        runtime and a timeout has usually passed already.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the request was successful, False otherwise.
      - **result** (`str` | `bytes` | `dict`):
        - On success, the response body (text or bytes depending on `to_text`).
        - On success with `extended=True`, a dict with keys:
            - `response`: response body
            - `status_code`: int
            - `response_header`: dict of response headers, keys lower-cased
            - `timings`: dict with at least `total` (seconds, float)
            - `tls_version`: str like `'TLSv1.3'` or None over plain HTTP
            - `alpn`: str like `'h2'` or `'http/1.1'` or None
            - `peer_cert_der`: DER-encoded server certificate as bytes, or None
        - On failure, an error message string.
        - On failure with `response_on_error=True`, the response body.

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
    ...     tls_min='1.2',
    ...     tls_max='1.3',
    ...     http_version='2',
    ...     extended=True,
    ... )
    """
    attempt = 0
    while True:
        result = _fetch_once(
            url,
            cacert=cacert,
            data=data,
            digest_auth_password=digest_auth_password,
            digest_auth_user=digest_auth_user,
            encoding=encoding,
            extended=extended,
            header=header,
            http_version=http_version,
            insecure=insecure,
            method=method,
            no_proxy=no_proxy,
            proxy=proxy,
            response_on_error=response_on_error,
            timeout=timeout,
            tls_max=tls_max,
            tls_min=tls_min,
            to_text=to_text,
        )
        if result[0] or attempt >= retries:
            return result
        attempt += 1


def fetch_json(
    url,
    insecure=False,
    no_proxy=False,
    proxy=None,
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
    method=None,
    retries=0,
    response_on_error=False,
    cacert=None,
):
    """
    Fetch JSON from a URL with optional POST, authentication and SSL/TLS handling.

    Thin wrapper around `fetch()` that decodes the response body as JSON. All `fetch()`
    parameters are forwarded; the only added behaviour is the JSON decode step.

    ### Parameters
    See `fetch()` for the shared parameters. `to_text` is forced to True because the JSON
    decoder needs a string.
    - **retries** (`int`, optional): Handed to `fetch()`, which repeats a request that
      failed. A body that arrived intact but holds no JSON is not a failed request and is
      therefore reported rather than fetched again.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the JSON was successfully fetched and parsed, False
        otherwise.
      - **result** (`dict` | `list` | `str`):
        - On success without `extended`: the parsed JSON document.
        - On success with `extended=True`: the same dict as `fetch()` plus a `response_json`
          key holding the parsed JSON document.
        - On failure (after all retries): an error message string.

    ### Example
    >>> fetch_json('https://192.0.2.74/api/v2/?resource=cpu')
    (True, {'cpu': {'usage': '45%', 'temperature': '50C'}})
    """
    success, jsonst = fetch(
        url,
        cacert=cacert,
        data=data,
        digest_auth_password=digest_auth_password,
        digest_auth_user=digest_auth_user,
        encoding=encoding,
        extended=extended,
        header=header,
        http_version=http_version,
        insecure=insecure,
        method=method,
        no_proxy=no_proxy,
        proxy=proxy,
        response_on_error=response_on_error,
        retries=retries,
        timeout=timeout,
        tls_max=tls_max,
        tls_min=tls_min,
    )
    if not success:
        return (False, jsonst)
    try:
        if extended:
            jsonst['response_json'] = json.loads(jsonst['response'])
            return (True, jsonst)
        return (True, json.loads(jsonst))
    except Exception as e:
        return (False, f'{e}. No JSON object could be decoded.')


def get_latest_tag_from_github(
    user,
    repo,
    insecure=False,
    no_proxy=False,
    proxy=None,
    timeout=8,
    header=None,
):
    """
    Get the newest tag from a GitHub repository.

    The fallback for repositories that tag their versions but never publish a GitHub
    release, where `get_latest_version_from_github()` answers with HTTP 404. GitHub
    returns the tags newest first, so the first entry is the newest one.

    ### Parameters
    See `get_latest_version_from_github()`.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the tag list was successfully fetched,
        False otherwise.
      - **result** (`str` | `bool`):
        - The name of the newest tag if successful.
        - `False` if the repository has no tags at all.

    ### Example
    >>> get_latest_tag_from_github('Icinga', 'icingaweb2-theme-company')
    (True, 'v1.0.0')
    """
    success, result = _check_github_name(user, 'GitHub user')
    if not success:
        return success, result
    success, result = _check_github_name(repo, 'GitHub repository')
    if not success:
        return success, result

    url = f'https://api.github.com/repos/{user}/{repo}/tags'
    success, result = _fetch_github_json(url, insecure, no_proxy, proxy, timeout, header)

    if not success:
        return success, result
    if not isinstance(result, list) or not result:
        return True, False
    if not isinstance(result[0], dict):
        return True, False

    return True, result[0].get('name', False)


def get_latest_version_from_github(
    user,
    repo,
    key='tag_name',
    insecure=False,
    no_proxy=False,
    proxy=None,
    timeout=8,
    header=None,
):
    """
    Get the newest release tag from a GitHub repository.

    This function fetches the latest release information from the GitHub API and
    retrieves the release tag. A repository that publishes tags but no releases answers
    with HTTP 404 here; use `get_latest_tag_from_github()` as the fallback for those.

    ### Parameters
    - **user** (`str`): The GitHub username or organization name.
    - **repo** (`str`): The GitHub repository name.
    - **key** (`str`, optional): The key to retrieve from the JSON response (default is
        `'tag_name'`).
    - **insecure** (`bool`, optional): Allow an untrusted certificate. Defaults to
      False.
    - **no_proxy** (`bool`, optional): Ignore the environment's proxy settings.
      Defaults to False.
    - **timeout** (`int`, optional): Network timeout in seconds. Defaults to 8.
    - **header** (`dict`, optional): Additional request headers, for example the
      one built by `github_token_header()`.

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
    success, result = _check_github_name(user, 'GitHub user')
    if not success:
        return success, result
    success, result = _check_github_name(repo, 'GitHub repository')
    if not success:
        return success, result

    url = f'https://api.github.com/repos/{user}/{repo}/releases/latest'
    success, result = _fetch_github_json(url, insecure, no_proxy, proxy, timeout, header)

    if not success:
        return success, result
    if not isinstance(result, dict) or not result:
        return True, False

    return True, result.get(key, False)


def github_token_header(token):
    """
    Build the `Authorization` header for a GitHub API token.

    Anonymous GitHub API access is rate limited to 60 requests per hour and IP address;
    a token raises that to 5000. Pass the result as the `header` of the
    `*_from_github()` functions. Returns an empty dict for an empty or missing token, so
    a caller can hand its optional token straight through without a branch of its own.

    ### Parameters
    - **token** (`str` | `None`): The API token.

    ### Returns
    - **dict**: `{'Authorization': 'Bearer <token>'}`, or `{}` when there is no token.

    ### Example
    >>> github_token_header('linuxfabrik')
    {'Authorization': 'Bearer linuxfabrik'}
    """
    if not token:
        return {}
    return {'Authorization': f'Bearer {token}'}


def server_product(response_header):
    """Return the product token of a `Server` response header, lower-cased.

    A `Server` header is written as `product/version (comment)`, so the part in front of
    the first slash names the software and the rest describes the build. A consumer that
    wants to know *what* answered, rather than which version did, needs only that first
    part - to decide whether advice about a product applies at all, for instance, since
    naming a directive of software the host does not run is worse than saying nothing.

    ### Parameters
    - **response_header** (`dict`):
      The response headers as `fetch(extended=True)` returns them, with lower-cased field
      names.

    ### Returns
    - **str**: The product token in lower case, or None where the response carries no
      `Server` header or an empty one. None means the product is genuinely unknown, which
      is not the same as it being something else.

    ### Example
    >>> server_product({'server': 'Apache/2.4.62 (Rocky Linux)'})
    'apache'
    >>> server_product({'server': 'nginx'})
    'nginx'
    >>> server_product({})
    """
    banner = response_header.get('server', '')
    if not banner:
        return None
    return banner.partition('/')[0].strip().lower() or None


def split_basic_auth(url):
    """Extract userinfo from `url` and return a `(url, headers)` tuple.

    The returned URL has any `user[:password]@` prefix stripped from
    its netloc so the credentials never reach the request line or
    any proxy log. If userinfo is present, `headers` contains the
    matching `Authorization: Basic ...` entry; otherwise it is an
    empty dict.

    Pass the returned `url` and `headers` to `lib.url.fetch()` /
    `lib.url.fetch_json()` so a consumer can accept HTTP basic auth via
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
