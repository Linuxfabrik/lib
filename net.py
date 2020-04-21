#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020041901'

import re
import socket


# address family
AF_INET    = socket.AF_INET                             # 2
AF_INET6   = getattr(socket, 'AF_INET6', object())      # 10
AF_UNSPEC  = socket.AF_UNSPEC                           # any kind of connection
AF_UNIX    = socket.AF_UNIX

# socket type
SOCK_TCP   = socket.SOCK_STREAM                         # 1
SOCK_UDP   = socket.SOCK_DGRAM                          # 2
SOCK_RAW   = socket.SOCK_RAW

# protocol type
PROTO_TCP  = socket.IPPROTO_TCP                         # 6
PROTO_UDP  = socket.IPPROTO_UDP                         # 17
PROTO_IP   = socket.IPPROTO_IP                          # 0

proto_map = {
    # address family, socket type:        proto
    (AF_INET,  socket.SOCK_STREAM): 'tcp',
    (AF_INET6, socket.SOCK_STREAM): 'tcp6',
    (AF_INET,  socket.SOCK_DGRAM):  'udp',
    (AF_INET6, socket.SOCK_DGRAM):  'udp6',
}

familystr = {
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

protostr = {
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

socketstr = {
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

