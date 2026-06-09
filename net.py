#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst


"""Provides network related functions and variables."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026060901'

import ipaddress
import random
import re
import socket
import ssl

try:
    import psutil

    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False

from . import (
    txt,  # pylint: disable=C0413
    url,  # pylint: disable=C0413
)

# address family
AF_INET = socket.AF_INET  # 2
AF_INET6 = getattr(socket, 'AF_INET6', object())  # 10
AF_UNSPEC = socket.AF_UNSPEC  # any kind of connection
try:
    AF_UNIX = socket.AF_UNIX
except AttributeError:
    # If the AF_UNIX constant is not defined then this protocol is unsupported.
    AF_UNIX = None

FAMILIYSTR = {
    # as defined in Python's socketmodule.c
    0: 'unspec',
    1: 'unix',
    2: '4',  # inet
    3: 'ax25',
    4: 'ipx',
    5: 'appletalk',
    6: 'netrom',
    7: 'bridge',
    8: 'atmpvc',
    9: 'x25',
    10: '6',  # inet6
    11: 'rose',
    12: 'decnet',
    13: 'netbeui',
    14: 'security',
    15: 'key',
    16: 'route',
    17: 'packet',
    18: 'ash',
    19: 'econet',
    20: 'atmsvc',
    22: 'sna',
    23: 'irda',
    24: 'pppox',
    25: 'wanpipe',
    26: 'llc',
    30: 'tipc',
    31: 'bluetooth',
}

FQDN_REGEX = re.compile(
    r'^((?!-)[-A-Z\d]{1,63}(?<!-)\.)+(?!-)[-A-Z\d]{1,63}(?<!-)\.?$', re.IGNORECASE
)

# protocol type
PROTO_TCP = socket.IPPROTO_TCP  # 6
PROTO_UDP = socket.IPPROTO_UDP  # 17
PROTO_IP = socket.IPPROTO_IP  # 0

PROTO_MAP = {
    # address family, socket type: proto
    (AF_INET, socket.SOCK_STREAM): 'tcp',
    (AF_INET, socket.SOCK_DGRAM): 'udp',
    (AF_INET6, socket.SOCK_DGRAM): 'udp6',
    (AF_INET6, socket.SOCK_STREAM): 'tcp6',
}

PROTOSTR = {
    # as defined in Python's socketmodule.c
    0: 'ip',
    1: 'icmp',
    2: 'igmp',
    6: 'tcp',
    8: 'egp',
    12: 'pup',
    17: 'udp',
    22: 'idp',
    41: 'ipv6',
    43: 'routing',
    44: 'fragment',
    50: 'esp',
    51: 'ah',
    58: 'icmpv6',
    59: 'none',
    60: 'dstopts',
    103: 'pim',
    255: 'raw',
}

# socket type
SOCK_TCP = socket.SOCK_STREAM  # 1
SOCK_UDP = socket.SOCK_DGRAM  # 2
SOCK_RAW = socket.SOCK_RAW

SOCKETSTR = {
    # as defined in Python's socketmodule.c
    1: 'tcp',  # stream
    2: 'udp',  # dgram
    3: 'raw',
    4: 'rdm',
    5: 'seqpacket',
}


def _socket_fetch(
    open_socket_func,
    connect_args,
    payload=None,
    dialog=None,
    timeout=3,
    socket_name='socket',
):
    """
    Fetch data via an open socket connection.

    This internal helper function opens a socket using a provided callable and runs either a
    single send-receive roundtrip (banner mode) or a multi-step request-response conversation
    (dialog mode). It supports both TCP/IP and Unix domain sockets transparently.

    ### Parameters
    - **open_socket_func** (`callable`):
      A function that creates and returns a new socket object.
    - **connect_args** (`tuple` or `str`):
      Arguments passed to the socket's `connect()` method.
    - **payload** (`bytes`, optional):
      Banner mode only. A payload to send after connecting. If `None`, no payload is sent.
      Mutually exclusive with `dialog`.
    - **dialog** (`list` of `(bytes_or_None, str_or_None)` tuples, optional):
      Dialog mode. Each step is `(send, expect)`:
        * `send` (`bytes` or `None`): payload to write. `None` skips the send.
        * `expect` (`str` or `None`): regex matched against the cumulative recv buffer for the
          step. `None` records an empty response and continues to the next step.
      No half-close is performed, so the server can keep reading further sends. Mutually
      exclusive with `payload`.
    - **timeout** (`int`, optional):
      Socket timeout in seconds. Defaults to `3`.
    - **socket_name** (`str`, optional):
      A human-readable name used in error messages for context. Defaults to `"socket"`.

    ### Returns
    - **tuple** (`bool`, `str` or `list`):
      - Banner mode: `(True, response_str)` on success.
      - Dialog mode: `(True, [response_str, ...])` with one entry per step, in order.
      - `(False, error_message)` on failure.

    ### Notes
    - Timeout and socket errors are handled gracefully.
    - Responses are decoded into UTF-8 text with replacement for decode errors.
    - This is an internal function intended for use by `fetch()`, `fetch_socket()`, and similar
      functions.

    ### Example
    >>> success, response = _socket_fetch(
    ...     open_socket_func, connect_args, payload=b'ping'
    ... )
    """
    if payload is not None and dialog is not None:
        return False, f'{socket_name}: payload and dialog are mutually exclusive.'

    try:
        with open_socket_func() as s:
            s.settimeout(timeout)
            s.connect(connect_args)

            if dialog is not None:
                # Multi-step conversation: send + read-until-pattern per step. No half-close,
                # so subsequent sends still reach the server.
                results = []
                for send_bytes, expect in dialog:
                    if send_bytes is not None:
                        try:
                            s.sendall(send_bytes)
                        except Exception as e:
                            return (
                                False,
                                f'Could not send payload on {socket_name}: {e}',
                            )

                    if expect is None:
                        results.append('')
                        continue

                    pattern = re.compile(expect, re.MULTILINE)
                    buffer = ''
                    while True:
                        try:
                            chunk = s.recv(1024)
                        except socket.timeout:
                            return False, (
                                f'{socket_name} timed out waiting for pattern {expect!r}.'
                            )
                        except OSError as e:
                            return False, f'Cannot fetch data from {socket_name}: {e}'
                        if not chunk:
                            return False, (
                                f'{socket_name} closed before pattern {expect!r} matched.'
                            )
                        buffer += chunk.decode('utf-8', errors='replace')
                        if pattern.search(buffer):
                            results.append(buffer)
                            break

                return True, results

            if payload is not None:
                try:
                    s.sendall(payload)
                except Exception as e:
                    return False, f'Could not send payload on {socket_name}: {e}'

            try:
                s.shutdown(socket.SHUT_WR)
            except Exception:
                pass  # Not fatal

            fragments = []
            while True:
                try:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    fragments.append(chunk.decode('utf-8', errors='replace'))
                except socket.timeout:
                    return False, f'{socket_name} timed out.'
                except OSError as e:
                    return False, f'Cannot fetch data from {socket_name}: {e}'

            return True, ''.join(fragments)

    except Exception as e:
        return False, f'Error using {socket_name}: {e}'


def fetch(host, port, msg=None, dialog=None, timeout=3, ipv6=False, tls=False):
    """
    Fetch data via a TCP/IP socket connection.

    This function opens a socket connection to a given host and port and runs either a single
    send-receive roundtrip (banner mode, via `msg`) or a multi-step conversation (dialog mode,
    via `dialog`). Supports IPv4, IPv6, and TLS-wrapped sockets.

    ### Parameters
    - **host** (`str`):
      Target hostname or IP address.
    - **port** (`int`):
      Target TCP port number.
    - **msg** (`bytes`, optional):
      Banner mode. A message sent once after connecting. The function then half-closes the
      write side and reads until EOF. Mutually exclusive with `dialog`.
    - **dialog** (`list` of `(bytes_or_None, str_or_None)` tuples, optional):
      Dialog mode. A list of `(send, expect)` steps walked in order. `expect` is a regex
      matched against the per-step recv buffer; `None` skips reading. No half-close is
      performed, so multi-step protocols (SMTP, NUT, IMAP, POP3, FTP, ...) work. Mutually
      exclusive with `msg`. See `_socket_fetch` for details.
    - **timeout** (`int`, optional):
      Socket timeout in seconds. Defaults to `3`.
    - **ipv6** (`bool`, optional):
      Use an IPv6 connection instead of IPv4. Defaults to `False`.
    - **tls** (`bool`, optional):
      Wrap the socket in a TLS 1.2+ context with SNI. Defaults to `False`. The legacy
      `fetch_ssl()` helper is equivalent to `fetch(..., tls=True)` and remains available for
      backward compatibility.

    ### Returns
    - **tuple** (`bool`, `str` or `list`):
      - Banner mode: `(True, response_str)` on success.
      - Dialog mode: `(True, [response_str, ...])` with one entry per step.
      - `(False, error_message)` on failure.

    ### Notes
    - Timeout and socket errors are handled gracefully.
    - Responses are decoded into text.
    - IPv6 addresses are supported when `ipv6=True`.

    ### Example
    >>> success, response = fetch('example.com', 80)
    >>> ok, [hello, vars_block, _] = fetch(
    ...     '127.0.0.1',
    ...     3493,
    ...     dialog=[
    ...         (None, r'^OK\\b|^ERR\\b'),
    ...         (b'LIST VAR myups\\n', r'END LIST VAR myups'),
    ...         (b'LOGOUT\\n', r'OK Goodbye'),
    ...     ],
    ... )
    """

    def open_tcp_socket():
        family = AF_INET6 if ipv6 else AF_INET
        raw_sock = socket.socket(family, SOCK_TCP)
        if not tls:
            return raw_sock
        # PROTOCOL_TLS_CLIENT automatically disables SSLv2/3 and TLSv1.0/1.1 on recent
        # OpenSSL builds; minimum_version then enforces TLS 1.2+ across all builds.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context.wrap_socket(raw_sock, server_hostname=host)

    try:
        return _socket_fetch(
            open_tcp_socket,
            (host, int(port)),
            payload=msg,
            dialog=dialog,
            timeout=timeout,
            socket_name=f'TCP socket {host}:{port}',
        )

    except Exception as e:
        return False, f'Could not open TCP socket {host}:{port}: {e}'


def fetch_socket(sock_file, cmd=None, dialog=None, timeout=3):
    """
    Fetch data via a Unix domain socket connection.

    This function opens a connection to a Unix socket file and runs either a single
    send-receive roundtrip (`cmd`) or a multi-step conversation (`dialog`). It is similar to
    `fetch()` but operates over local filesystem sockets.

    ### Parameters
    - **sock_file** (`str`):
      Path to the Unix domain socket file.
    - **cmd** (`bytes`, optional):
      Banner mode. A command sent once after connecting. Mutually exclusive with `dialog`.
    - **dialog** (`list` of `(bytes_or_None, str_or_None)` tuples, optional):
      Dialog mode. See `fetch()` for the step format. Mutually exclusive with `cmd`.
    - **timeout** (`int`, optional):
      Socket timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `str` or `list`):
      - Banner mode: `(True, response_str)` on success.
      - Dialog mode: `(True, [response_str, ...])` with one entry per step.
      - `(False, error_message)` on failure.

    ### Notes
    - Timeout and socket errors are handled gracefully.
    - Responses are decoded into text.
    - Unix domain sockets must exist and have appropriate permissions.

    ### Example
    >>> success, response = fetch_socket('/var/run/haproxy.sock', b'show stat\\n')
    """

    def open_unix_socket():
        return socket.socket(socket.AF_UNIX, SOCK_TCP)

    try:
        return _socket_fetch(
            open_unix_socket,
            sock_file,
            payload=cmd,
            dialog=dialog,
            timeout=timeout,
            socket_name=f'Unix socket "{sock_file}"',
        )

    except FileNotFoundError:
        return False, f'Socket file "{sock_file}" not found.'
    except PermissionError:
        return False, f'Access to socket file "{sock_file}" denied.'
    except TimeoutError:
        return False, f'Connection to socket "{sock_file}" timed out.'
    except ConnectionError as err:
        return False, f'Error during socket connection to "{sock_file}": {err}'
    except Exception as e:
        return False, f'Could not open Unix socket "{sock_file}": {e}'


def fetch_ssl(host, port, msg=None, timeout=3):
    """
    Fetch data via an SSL/TLS encrypted TCP socket connection.

    .. deprecated:: 2026050901
        Use `fetch(host, port, msg=..., tls=True)` instead. `fetch()` covers banner mode,
        dialog mode, IPv4/IPv6 and TLS in a single entry point. `fetch_ssl()` might be removed
        in a future major release and is unmaintained.

    This function opens a secure SSL/TLS socket connection to a given host and port, optionally
    sends a message, and returns the received response. It uses the system's default trusted CA
    certificates.

    ### Parameters
    - **host** (`str`):
      Target hostname or IP address for the SSL connection.
    - **port** (`int`):
      Target TCP port number (usually 443 for HTTPS services).
    - **msg** (`bytes`, optional):
      A message to send after connecting. If `None`, no message is sent.
    - **timeout** (`int`, optional):
      Socket timeout in seconds. Defaults to `3`.

    ### Returns
    - **tuple** (`bool`, `str`):
      - `True`, followed by the received response text if successful.
      - `False`, followed by an error message if failed.

    ### Notes
    - Deprecated wrapper kept for backward compatibility. Prefer `fetch(..., tls=True)` in new
      code; both call paths share the same TLS context.
    - Timeout, SSL, and socket errors are handled gracefully.
    - Response is decoded into UTF-8 text.
    - SSL certificate validation is performed automatically based on the system's trusted CAs.
    - Uses `server_hostname` to support Server Name Indication (SNI).

    ### Example
    >>> success, response = fetch_ssl(
    ...     'example.com', 443, b'GET / HTTP/1.0\\r\\nHost: example.com\\r\\n\\r\\n'
    ... )
    """

    def open_ssl_socket():
        # PROTOCOL_TLS_CLIENT automatically disables SSLv2/3 and
        # TLSv1.0/1.1 on recent OpenSSL builds
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        # context.check_hostname = True
        # context.verify_mode = ssl.CERT_REQUIRED
        context.minimum_version = (
            ssl.TLSVersion.TLSv1_2
        )  # enforce at least TLS 1.2 just to be sure

        raw_sock = socket.socket(socket.AF_INET, SOCK_TCP)
        return context.wrap_socket(raw_sock, server_hostname=host)

    try:
        return _socket_fetch(
            open_ssl_socket, (host, int(port)), payload=msg, timeout=timeout
        )

    except Exception as e:
        return False, f'Could not open SSL socket: {e}'


def _default_route_ip(family=socket.AF_INET):
    """
    Return the local IP address the kernel would use for the default route, or `None`.

    Opens a connected UDP socket towards an off-link address and reads back the source address the
    routing table selects. UDP `connect` only sets the peer, so no packet is sent; this works on
    Linux, Windows and macOS without external tools or privileges, and offline as long as a default
    route exists.

    ### Parameters
    - **family** (`int`, optional): `socket.AF_INET` (default) or `socket.AF_INET6`.

    ### Returns
    - **str** or **None**: The selected source address, or `None` if no route is available.
    """
    probe = '192.0.2.1' if family == socket.AF_INET else '2001:db8::1'
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
    except OSError:
        return None
    try:
        sock.connect((probe, 9))
        return sock.getsockname()[0].split('%')[0]
    except OSError:
        return None
    finally:
        sock.close()


def _default_gateway():
    """
    Return the IPv4 default gateway address, or `None` if it cannot be determined.

    Reads the kernel routing table from `/proc/net/route` (Linux). On platforms without that file
    the gateway is not available through a dependency-free, cross-platform API, so `None` is
    returned rather than guessing.

    ### Returns
    - **str** or **None**: The default gateway IPv4 address, or `None`.
    """
    try:
        with open('/proc/net/route', encoding='ascii') as routes:
            for line in routes.read().splitlines()[1:]:
                fields = line.split()
                # Destination 00000000 marks the default route; flags must have RTF_GATEWAY (0x2).
                if (
                    len(fields) > 3
                    and fields[1] == '00000000'
                    and int(fields[3], 16) & 0x2
                ):
                    # The gateway is a little-endian hex IPv4 in column 2.
                    return socket.inet_ntoa(bytes.fromhex(fields[2])[::-1])
    except (OSError, ValueError):
        return None
    return None


def _iface_for_ip(ip):
    """
    Return `(interface_name, netmask)` for the interface carrying `ip`, or `(None, None)`.

    Matches the address against psutil's per-interface address list, so it is platform-independent.

    ### Parameters
    - **ip** (`str`): The IPv4 or IPv6 address to look up.

    ### Returns
    - **tuple** (`str` or `None`, `str` or `None`): The interface name and its netmask.
    """
    try:
        wanted = ipaddress.ip_address(ip)
    except ValueError:
        return (None, None)
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family not in (socket.AF_INET, socket.AF_INET6):
                continue
            try:
                if ipaddress.ip_address((addr.address or '').split('%')[0]) == wanted:
                    return (iface, addr.netmask)
            except ValueError:
                continue
    return (None, None)


def get_netinfo():
    """
    Retrieve local and public network information.

    This function retrieves the system's primary IP address, netmask, CIDR mask, default gateway,
    and public IP address. Addresses come from `psutil` (platform-independent); the default gateway
    is read from the Linux routing table and is `None` on other platforms.

    ### Parameters
    - None

    ### Returns
    - **dict**:
      A dictionary containing:
        - `address` (`str`): The local IP address.
        - `mask` (`str`): The subnet mask.
        - `mask_cidr` (`str`): The subnet mask as CIDR.
        - `gateway` (`str` or `None`): The default gateway address.
        - `public_address` (`str`): The public IP address.

    ### Notes
    - If fetching any required information fails, an empty list is returned.
    - Requires `psutil` and the `ip_to_cidr()` helper.
    - The `public_address` field is always `None`; callers that want the public
      IP must call `get_public_ip()` separately with a list of lookup services.

    ### Example
    >>> netinfo = get_netinfo()
    >>> print(netinfo['address'])
    '192.168.1.10'
    """
    if not HAVE_PSUTIL:
        return []

    address = _default_route_ip(socket.AF_INET)
    if not address:
        return []
    iface, netmask = _iface_for_ip(address)
    if not iface or not netmask:
        return []

    return {
        'address': address,
        'mask': netmask,
        'mask_cidr': ip_to_cidr(netmask),
        'gateway': _default_gateway(),
        'public_address': None,
    }


def get_public_ip(services, insecure=False, no_proxy=False, timeout=2):
    """
    Retrieve the public IP address from a list of online services.

    This function queries a list of external services (e.g., "what is my IP") to retrieve the public
    IP address of the system. The list is shuffled before being used, and the first service that
    returns a valid IP address is used.

    ### Parameters
    - **services** (`str`): Comma-separated URLs of services to query for the public IP.
    - **insecure** (`bool`, optional): Disable SSL verification. Defaults to `False`.
    - **no_proxy** (`bool`, optional): Ignore proxy settings. Defaults to `False`.
    - **timeout** (`int`, optional): Request timeout in seconds. Defaults to `2`.

    ### Returns
    - **tuple** (`bool`, `str` or `None`):
      - `True` and the IP address (`str`) if successful.
      - `False` and `None` if no IP could be retrieved.

    ### Example
    >>> get_public_ip(
    ...     'https://ipv4.icanhazip.com,https://ipecho.net/plain,https://ipinfo.io/ip'
    ... )
    (True, '1.2.3.4')
    """
    if not services:
        return False, None

    service_list = [s.strip() for s in services.split(',') if s.strip()]
    random.shuffle(service_list)

    for uri in service_list:
        success, result = url.fetch(
            uri,
            insecure=insecure,
            no_proxy=no_proxy,
            timeout=timeout,
        )
        if success and result:
            ip = result.strip()
            try:
                return True, txt.to_text(ip)
            except Exception:
                return True, ip

    return False, None


def cidr_to_hosts(cidr, max_hosts=65536):
    """
    Return the usable host IP addresses of a network in CIDR notation.

    Enumerates the usable host addresses of an IPv4 or IPv6 network given as a
    CIDR string (e.g. `10.1.1.0/24` or `2001:db8::/120`). The network and
    broadcast address are excluded. Host bits set in the input are tolerated
    (`strict=False`).

    ### Parameters
    - **cidr** (`str`): Network in CIDR notation, e.g. `10.1.1.0/24`.
    - **max_hosts** (`int`, optional): Refuse to enumerate networks with more
      addresses than this, which protects against accidentally expanding a large
      range such as an IPv6 `/64` (2^64 addresses). Set to `None` to disable the
      limit. Defaults to `65536` (an IPv4 `/16`).

    ### Returns
    - **tuple** (`bool`, `list` or `str`):
      - `True` and the list of host IP address strings (IPv4 or IPv6) on success.
      - `False` and an error message on failure.

    ### Example
    >>> cidr_to_hosts('10.1.1.0/30')
    (True, ['10.1.1.1', '10.1.1.2'])
    >>> cidr_to_hosts('2001:db8::/126')
    (True, ['2001:db8::1', '2001:db8::2', '2001:db8::3'])
    """
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as e:
        return (False, f'Invalid network "{cidr}": {e}')
    if max_hosts is not None and network.num_addresses > max_hosts:
        return (
            False,
            f'Network "{cidr}" is too large to enumerate '
            f'({network.num_addresses} addresses, limit {max_hosts}).',
        )
    return (True, [str(host) for host in network.hosts()])


def _ipv6_prefixlen(netmask):
    """
    Return the prefix length (as a string) for an IPv6 netmask reported by psutil.

    psutil reports the IPv6 netmask either as a full mask ("ffff:ffff:ffff:ffff::"), as a
    "mask/prefix" string, or as `None`. All three are normalised to a prefix length, defaulting to
    "128" (a single host) when it cannot be derived.

    ### Parameters
    - **netmask** (`str` or `None`): The IPv6 netmask as reported by psutil.

    ### Returns
    - **str**: The prefix length, e.g. "64".
    """
    if not netmask:
        return '128'
    if '/' in netmask:
        return netmask.split('/')[-1]
    try:
        return str(bin(int(ipaddress.IPv6Address(netmask))).count('1'))
    except ipaddress.AddressValueError:
        return '128'


def get_subnet_hosts(interface=None, max_hosts=65536):
    """
    Return the usable host IP addresses of an interface's subnet.

    Resolves the address and netmask of the given interface (or the default
    interface, the one carrying the default route, if none is given), derives the
    subnet and enumerates its usable host addresses (network and broadcast
    address excluded). IPv4 is preferred; if an interface has no IPv4 address its
    IPv6 subnet is used. Note that an IPv6 `/64` exceeds `max_hosts` and is
    therefore reported as too large rather than enumerated.

    ### Parameters
    - **interface** (`str`, optional): Network interface name (e.g. `eth0`). If
      `None`, the default interface is used.
    - **max_hosts** (`int`, optional): Passed through to `cidr_to_hosts()` to cap
      enumeration. Defaults to `65536`.

    ### Returns
    - **tuple** (`bool`, `list` or `str`):
      - `True` and the list of host IP address strings on success.
      - `False` and an error message on failure.

    ### Notes
    - Requires the `psutil` library.

    ### Example
    >>> get_subnet_hosts('eth0')
    (True, ['192.168.1.1', '192.168.1.2', ..., '192.168.1.254'])
    """
    if not HAVE_PSUTIL:
        return (False, 'Python module "psutil" is not installed.')

    if interface is None:
        netinfo = get_netinfo()
        if not netinfo or not netinfo.get('address'):
            return (False, 'Unable to determine the default interface subnet.')
        return cidr_to_hosts(
            f'{netinfo["address"]}/{netinfo["mask_cidr"]}', max_hosts=max_hosts
        )

    if_addrs = psutil.net_if_addrs()
    if interface not in if_addrs:
        return (False, f'No such interface "{interface}".')

    # IPv4 first, then IPv6. psutil may suffix the address with a "%scope" and reports the IPv6
    # netmask as a full mask ("ffff:ffff:ffff:ffff::") rather than a prefix length.
    for family in (socket.AF_INET, socket.AF_INET6):
        for addr in if_addrs[interface]:
            if addr.family != family:
                continue
            address = (addr.address or '').split('%')[0]
            netmask = addr.netmask or ''
            if not address:
                continue
            if family == socket.AF_INET:
                cidr = ip_to_cidr(netmask)
            else:
                cidr = _ipv6_prefixlen(netmask)
            return cidr_to_hosts(f'{address}/{cidr}', max_hosts=max_hosts)

    return (False, f'No IPv4 or IPv6 address found on interface "{interface}".')


def ip_to_cidr(ip):
    """
    Convert an IPv4 netmask to CIDR notation.

    This function converts a traditional IPv4 netmask (e.g., '255.255.255.0') into its CIDR
    equivalent (e.g., `24`).

    ### Parameters
    - **ip** (`str` or `None`):
      The IP address mask to convert. If `None`, returns `0`.

    ### Returns
    - **int**:
      The corresponding CIDR number (e.g., 24).

    ### Example
    >>> ip_to_cidr('255.255.255.0')
    24
    """
    if not ip:
        return 0
    try:
        return sum(bin(int(octet)).count('1') for octet in ip.split('.'))
    except (ValueError, AttributeError):
        return 0


def is_valid_hostname(hostname):
    """
    Validate a fully-qualified domain name (FQDN) according to RFC 1035 and RFC 3696.

    This function checks if the given hostname is valid, whether relative or absolute. A
    hostname ending with a dot is allowed (representing the null byte), but must be less than
    254 bytes total.

    ### Parameters
    - **hostname** (`str`):
      The hostname to validate.

    ### Returns
    - **bool**:
      `True` if the hostname is valid, `False` otherwise.

    ### Notes
    - Complies fully with RFC 1035 and the preferred form of RFC 3696 Section 2.
    - Absolute FQDNs (ending with a dot) must be ≤ 254 bytes.
    - Relative FQDNs must be < 253 bytes.

    ### References
    - https://tools.ietf.org/html/rfc3696#section-2
    - https://tools.ietf.org/html/rfc1035

    ### Example
    >>> is_valid_hostname('example.com')
    True
    """
    if not isinstance(hostname, str):
        return False

    normalized = hostname.rstrip('.')
    if len(normalized) > 253:
        return False

    return bool(FQDN_REGEX.fullmatch(hostname))


def is_valid_absolute_hostname(hostname):
    """
    Validate a fully-qualified domain name (FQDN) that does not end with a dot.

    This function checks if the hostname is a valid FQDN according to the RFC preferred-form
    and ensures it does not end with a dot (`.`).

    ### Parameters
    - **hostname** (`str`):
      The hostname to validate.

    ### Returns
    - **bool**:
      `True` if the hostname is a valid absolute FQDN (does not end with a dot), `False` otherwise.

    ### Notes
    - Based on RFC 1035 and RFC 3696 specifications.
    - Absolute FQDNs are typically used without appending search domains in DNS lookups.

    ### References
    - https://tools.ietf.org/html/rfc3696#section-2
    - https://tools.ietf.org/html/rfc1035

    ### Example
    >>> is_valid_absolute_hostname('example.com')
    True
    >>> is_valid_absolute_hostname('example.com.')
    False
    """
    if not isinstance(hostname, str):
        return False

    return not hostname.endswith('.') and is_valid_hostname(hostname)


def is_valid_relative_hostname(hostname):
    """
    Validate a relative fully-qualified domain name (FQDN) that ends with a dot.

    This function checks if the hostname is a valid FQDN in the preferred RFC form, and ensures
    it ends with a dot (`.`).

    ### Parameters
    - **hostname** (`str`):
      The hostname to validate.

    ### Returns
    - **bool**:
      `True` if the hostname is a valid relative FQDN (ends with a dot), `False` otherwise.

    ### Notes
    - Based on the preferred form from RFC 1035 and RFC 3696.
    - Relative FQDNs ending with a dot can cause DNS resolvers to append search domains.

    ### References
    - https://tools.ietf.org/html/rfc3696#section-2
    - https://tools.ietf.org/html/rfc1035

    ### Example
    >>> is_valid_relative_hostname('example.com.')
    True
    >>> is_valid_relative_hostname('example.com')
    False
    """
    if not isinstance(hostname, str):
        return False

    return hostname.endswith('.') and is_valid_hostname(hostname)


def netmask_to_cidr(ip):
    """
    Convert a netmask IP address to CIDR notation.

    This function converts a standard IPv4 netmask (e.g., `255.255.255.0`) into its
    equivalent CIDR prefix length (e.g., `24`).

    ### Parameters
    - **ip** (`str`):
      Netmask IP address in string format (e.g., '255.255.255.0').

    ### Returns
    - **int**:
      CIDR prefix length corresponding to the given netmask.
      Returns 0 if input is `None`.

    ### Notes
    - Based on Glances project logic.
    - Each octet is converted to binary and counted for the number of '1' bits.

    ### Example
    >>> netmask_to_cidr('255.255.255.0')
    24
    >>> netmask_to_cidr('255.255.0.0')
    16

    ### References
    - https://github.com/nicolargo/glances/issues/1417#issuecomment-469894399
    """
    if not ip:
        return 0
    try:
        return sum(bin(int(octet)).count('1') for octet in ip.split('.'))
    except (ValueError, AttributeError):
        return 0
