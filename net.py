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
__version__ = '2023051201'

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

# socket type
SOCK_TCP = socket.SOCK_STREAM                        # 1
SOCK_UDP = socket.SOCK_DGRAM                         # 2
SOCK_RAW = socket.SOCK_RAW

# protocol type
PROTO_TCP = socket.IPPROTO_TCP                        # 6
PROTO_UDP = socket.IPPROTO_UDP                        # 17
PROTO_IP = socket.IPPROTO_IP                          # 0

PROTO_MAP = {
    # address family, socket type: proto
    (AF_INET, socket.SOCK_STREAM): 'tcp',
    (AF_INET, socket.SOCK_DGRAM):  'udp',
    (AF_INET6, socket.SOCK_DGRAM):  'udp6',
    (AF_INET6, socket.SOCK_STREAM): 'tcp6',
}

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

SOCKETSTR = {
    # as defined in Python's socketmodule.c
    1: 'tcp',        # stream
    2: 'udp',        # dgram
    3: 'raw',
    4: 'rdm',
    5: 'seqpacket',
}

FQDN_REGEX = re.compile(
        r"^((?!-)[-A-Z\d]{1,63}(?<!-)\.)+(?!-)[-A-Z\d]{1,63}(?<!-)\.?$", re.IGNORECASE
)


def fetch(host, port, msg=None, timeout=3, ipv6=False):
    """Fetch data via a TCP/IP socket connection. You may optionally send a msg first.
    Supports both IPv4 and IPv6.
    Taken from https://docs.python.org/3/library/socket.html, enhanced.
    """
    try:
        if ipv6:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(int(timeout))
        s.connect((host, int(port)))
    except:
        return (False, 'Could not open socket.')

    if msg is not None:
        try:
            s.sendall(msg)
        except:
            return (False, 'Could not send payload "{}".'.format(msg))

    fragments = []
    while True:
        try:
            chunk = s.recv(1024)
            if not chunk:
                break
            fragments.append(txt.to_text(chunk))
        except socket.timeout as e:
            # non-blocking behavior via a time out with socket.settimeout(n)
            err = e.args[0]
            # this next if/else is a bit redundant, but illustrates how the
            # timeout exception is setup
            if err == 'timed out':
                return (False, 'Socket timed out.')
            return (False, 'Can\'t fetch data: {}'.format(e))
        except socket.error as e:
            # Something else happened, handle error, exit, etc.
            return (False, 'Can\'t fetch data: {}'.format(e))

    try:
        s.close()
    except:
        s = None

    return (True,  ''.join(fragments))


def get_netinfo():
    if HAVE_NETIFACES:
        # Update stats using the netifaces lib
        try:
            default_gw = netifaces.gateways()['default'][netifaces.AF_INET]
        except (KeyError, AttributeError):
            return []

        stats = {}
        try:
            stats['address'] = netifaces.ifaddresses(default_gw[1])[netifaces.AF_INET][0]['addr']
            stats['mask'] = netifaces.ifaddresses(default_gw[1])[netifaces.AF_INET][0]['netmask']
            stats['mask_cidr'] = ip_to_cidr(stats['mask'])
            stats['gateway'] = netifaces.gateways()['default'][netifaces.AF_INET][0]
        except (KeyError, AttributeError):
            return []

        stats['public_address'] = None
        try:
            stats['public_address'] = get_ip_public()
        except:
            return []
        return stats


def get_public_ip(services):
    """Retrieve the public IP address from a list of online services.
    The list of "what is my ip" services is shuffled before being used. The first service
    returning an IP "wins".

    >>> get_public_ip('https://ipv4.icanhazip.com,https://ipecho.net/plain,https://ipinfo.io/ip')
    1.2.3.4
    """
    if not services:
        return (False, None)

    services = services.split(',')
    random.shuffle(services)

    ip = None
    for uri in services:
        success, ip = url.fetch(uri.strip(), timeout=2)
        if success and ip:
            ip = ip.strip()
            try:
                return (True, txt.to_text(ip))
            except:
                return (True, ip)
    return (False, ip)


def is_valid_hostname(hostname):
    """True for a validated fully-qualified domain name (FQDN), in full
    compliance with RFC 1035, and the "preferred form" specified in RFC
    3686 s. 2, whether relative or absolute.

    If and only if the FQDN ends with a dot (in place of the RFC1035
    trailing null byte), it may have a total length of 254 bytes, still it
    must be less than 253 bytes.

    https://tools.ietf.org/html/rfc3696#section-2
    https://tools.ietf.org/html/rfc1035

    from https://github.com/ypcrts/fqdn/blob/develop/fqdn
    """

    length = len(hostname)
    if hostname.endswith("."):
        length -= 1
    if length > 253:
        return False
    return bool(FQDN_REGEX.match(hostname))


def is_valid_relative_hostname(hostname):
    """True for a fully-qualified domain name (FQDN) that is RFC
    preferred-form compliant and ends with a `.`.
    With relative FQDNS in DNS lookups, the current hosts domain name or
    search domains may be appended.

    from https://github.com/ypcrts/fqdn/blob/develop/fqdn
    """

    return hostname.endswith(".") and is_valid_hostname(hostname)


def is_valid_absolute_hostname(hostname):
    """True for a validated fully-qualified domain name that compiles with the
    RFC preferred-form and does not end with a `.`.

    from https://github.com/ypcrts/fqdn/blob/develop/fqdn
    """

    return not hostname.endswith(".") and is_valid_hostname(hostname)


def netmask_to_cidr(ip):
    """Convert IP address to CIDR.

    >>> netmask_to_cdir('255.255.255.0')
    24
    """
    # Thanks to @Atticfire
    # See https://github.com/nicolargo/glances/issues/1417#issuecomment-469894399
    if ip is None:
        return 0
    return sum(bin(int(x)).count('1') for x in ip.split('.'))
