#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020040701'

import re

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

