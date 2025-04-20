#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst


"""Provides network related functions and variables.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

import random
import re
import socket
try:
    import netifaces
    HAVE_NETIFACES = True
except ImportError:
    HAVE_NETIFACES = False

from . import txt # pylint: disable=C0413
from . import url # pylint: disable=C0413


# address family
AF_INET = socket.AF_INET                             # 2
AF_INET6 = getattr(socket, 'AF_INET6', object())     # 10
AF_UNSPEC = socket.AF_UNSPEC                         # any kind of connection
try:
    AF_UNIX = socket.AF_UNIX
except AttributeError:
    # If the AF_UNIX constant is not defined then this protocol is unsupported.
    AF_UNIX = None

FAMILIYSTR = {
    # as defined in Python's socketmodule.c
    0: 'unspec',
    1: 'unix',
    2: '4',              # inet
    3: 'ax25',
    4: 'ipx',
    5: 'appletalk',
    6: 'netrom',
    7: 'bridge',
    8: 'atmpvc',
    9: 'x25',
    10: '6',             # inet6
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
        r"^((?!-)[-A-Z\d]{1,63}(?<!-)\.)+(?!-)[-A-Z\d]{1,63}(?<!-)\.?$", re.IGNORECASE
)

# protocol type
PROTO_TCP = socket.IPPROTO_TCP                       # 6
PROTO_UDP = socket.IPPROTO_UDP                       # 17
PROTO_IP = socket.IPPROTO_IP                         # 0

PROTO_MAP = {
    # address family, socket type: proto
    (AF_INET, socket.SOCK_STREAM): 'tcp',
    (AF_INET, socket.SOCK_DGRAM):  'udp',
    (AF_INET6, socket.SOCK_DGRAM):  'udp6',
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
SOCK_TCP = socket.SOCK_STREAM                        # 1
SOCK_UDP = socket.SOCK_DGRAM                         # 2
SOCK_RAW = socket.SOCK_RAW

SOCKETSTR = {
    # as defined in Python's socketmodule.c
    1: 'tcp',        # stream
    2: 'udp',        # dgram
    3: 'raw',
    4: 'rdm',
    5: 'seqpacket',
}


def fetch(host, port, msg=None, timeout=3, ipv6=False):
    """
    Fetch data via a TCP/IP socket connection.

    This function opens a socket connection to a given host and port, optionally sends a message,
    and returns the received response. Supports both IPv4 and IPv6 connections.

    ### Parameters
    - **host** (`str`):
      Target hostname or IP address.
    - **port** (`int`):
      Target TCP port number.
    - **msg** (`bytes`, optional):
      A message to send after connecting. If None, no message is sent.
    - **timeout** (`int`, optional):
      Socket timeout in seconds. Defaults to `3`.
    - **ipv6** (`bool`, optional):
      Whether to use an IPv6 connection instead of IPv4. Defaults to `False`.

    ### Returns
    - **tuple** (`bool`, `str`):
      - `True`, followed by the received response text if successful.
      - `False`, followed by an error message if failed.

    ### Notes
    - Timeout and socket errors are handled gracefully.
    - Response is decoded into text.

    ### Example
    >>> success, response = fetch('example.com', 80)
    """
    try:
        family = socket.AF_INET6 if ipv6 else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, int(port)))

            if msg is not None:
                try:
                    s.sendall(msg)
                except Exception as e:
                    return False, f'Could not send payload "{msg}": {e}'

            fragments = []
            while True:
                try:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    fragments.append(txt.to_text(chunk))
                except socket.timeout:
                    return False, 'Socket timed out.'
                except socket.error as e:
                    return False, f'Cannot fetch data: {e}'

            return True, ''.join(fragments)

    except Exception as e:
        return False, f'Could not open socket: {e}'


def get_netinfo():
    """
    Retrieve local and public network information.

    This function retrieves the system's primary IP address, netmask, CIDR mask, default gateway,
    and public IP address. Uses the `netifaces` library if available.

    ### Parameters
    - None

    ### Returns
    - **dict**:
      A dictionary containing:
        - `address` (`str`): The local IP address.
        - `mask` (`str`): The subnet mask.
        - `mask_cidr` (`str`): The subnet mask as CIDR.
        - `gateway` (`str`): The default gateway address.
        - `public_address` (`str`): The public IP address.

    ### Notes
    - If fetching any required information fails, an empty list is returned.
    - Requires `netifaces` and `ip_to_cidr()` helper.
    - Public IP is fetched via `get_ip_public()`.

    ### Example
    >>> netinfo = get_netinfo()
    >>> print(netinfo['address'])
    '192.168.1.10'
    """
    if not HAVE_NETIFACES:
        return []

    try:
        default_gateway = netifaces.gateways()['default'][netifaces.AF_INET]
        iface = default_gateway[1]
        iface_addrs = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]

        stats = {
            'address': iface_addrs.get('addr'),
            'mask': iface_addrs.get('netmask'),
            'mask_cidr': ip_to_cidr(iface_addrs.get('netmask')),
            'gateway': default_gateway[0],
            'public_address': None,
        }

        try:
            stats['public_address'] = get_ip_public()
        except Exception:
            return []

        return stats

    except (KeyError, AttributeError, IndexError):
        return []


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
    >>> get_public_ip('https://ipv4.icanhazip.com,https://ipecho.net/plain,https://ipinfo.io/ip')
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

    normalized = hostname.rstrip(".")
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
