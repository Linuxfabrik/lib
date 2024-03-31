#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Extends argparse by new input argument data types on demand.
"""

import re  # pylint: disable=C0413


__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2024033101'


def csv(arg):
    """Returns a list from a `csv` input argument.
    """
    return [x.strip() for x in arg.split(',')]


def float_or_none(arg):
    """Returns None or float from a `float_or_none` input argument.
    """
    if arg is None or str(arg).lower() == 'none':
        return None
    return float(arg)


def help(param):
    """Return global valid help text for a parameter.
    """
    h = {
        '--match':
            'Uses Python regular expressions without any external flags like `re.IGNORECASE`. '
            'The regular expression is applied to each line of the output. '
            'Examples: '
            '`(?i)example` to match the word "example" in a case-insensitive manner. '
            '`^(?!.*example).*$` to match any string except "example" (negative lookahead). '
            '`(?: ... )*` is a non-capturing group that matches any sequence of characters  '
            'that satisfy the condition inside it, zero or more times. ',
        }
    return h[param]
    try:
        return h[param]
    except KeyError:
        return ''


def int_or_none(arg):
    """Returns None or int from a `int_or_none` input argument.
    """
    if arg is None or str(arg).lower() == 'none':
        return None
    return int(arg)


def number_unit_method(arg, unit='%', method='USED'):
    """Expects '<number>[unit][method]. Useful for threshold arguments.
    Number is an integer or float.
    Unit is one of `%%|K|M|G|T|P`.
      If "unit" is omitted, `%` is assumed.
      `K` means `kibibyte` etc.
    Method is one of `USED|FREE`.
      If "method" is ommitted, `USED` is assumed.
    Examples: '
    * `95`: returns (95, '%', 'USED')
    * `9.5M`: returns (9.5, 'M', 'USED')
    * `95%USED`: returns (95, '%', 'USED')
    * `5FREE`: : returns (5, '%', 'FREE')
    * `5%FREE`: : returns (5, '%', 'FREE')
    * `9.5GFREE`: returns (9.5, 'G', 'FREE')
    * `1400GUSED`: returns (1400, 'G', 'USED')
    """
    # use named groups in regex
    regex = re.compile(
        r'(?P<number>\d*\.?\d*)(?P<unit>%|K|M|G|T|P)?(?P<method>USED|FREE)?',
        re.IGNORECASE,
    )
    match = re.search(regex, arg)
    if match and match.groupdict().get('number'):
        arg = match.groupdict().get('number').strip()
        if match and match.groupdict().get('unit'):
            unit = match.groupdict().get('unit').strip()
        if match and match.groupdict().get('method'):
            method = match.groupdict().get('method').strip()
    return arg, unit.upper(), method.upper()


def range_or_none(arg):
    """Returns None or range from a `range_or_none` input argument.
    """
    return str_or_none(arg)


def str_or_none(arg):
    """Returns None or str from a `str_or_none` input argument.
    """
    if arg is None or str(arg).lower() == 'none':
        return None
    return str(arg)

