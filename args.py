#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""Extends argparse by new input argument data types on demand."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026041002'


HELP_TEXTS = {
    '--always-ok': 'Always returns OK.',
    '--count': (
        'Number of consecutive checks the threshold must be exceeded before alerting. '
        'Default: %(default)s'
    ),
    '--critical': (
        'CRIT threshold in percent. Supports Nagios ranges. Default: >= %(default)s'
    ),
    '--critical-count': (
        'CRIT threshold for the number of matching items. '
        'Supports Nagios ranges. '
        'Default: %(default)s'
    ),
    '--critical-seconds': (
        'CRIT threshold in seconds. Supports Nagios ranges. Default: %(default)s'
    ),
    '--hostname': 'Hostname or IP address. Default: %(default)s',
    '--ignore': (
        'Any item matching this string will be ignored. '
        'Case-sensitive. '
        'Can be specified multiple times.'
    ),
    '--ignore-pattern': (
        'Any item containing this pattern will be ignored. '
        'Can be specified multiple times. '
        'Example: `boot` matches both `/boot` and `/boot/efi`.'
    ),
    '--ignore-regex': (
        'Any item matching this Python regex will be ignored. '
        'Can be specified multiple times. '
        'Example: `(?i)linuxfabrik` for a case-insensitive match.'
    ),
    '--insecure': 'This option explicitly allows insecure SSL connections.',
    '--lengthy': 'Extended reporting.',
    '--match': (
        'Filter by this Python regular expression. '
        'Case-sensitive by default; use `(?i)` for case-insensitive matching. '
        'Can be specified multiple times. '
        'Examples: '
        '`(?i)example` to match "example" regardless of case. '
        '`^(?!.*example).*$` to match any string except "example" (negative lookahead). '
        'Default: %(default)s'
    ),
    '--no-proxy': 'Do not use a proxy.',
    '--password': 'Password.',
    '--port': 'Port number. Default: %(default)s',
    '--stratum': (
        'Warns if the determined stratum of the time server is greater than or equal '
        'to this value. '
        'Stratum 1 indicates a computer with a locally attached reference clock. '
        'A computer that is synchronised to a stratum 1 computer is at stratum 2. '
        'A computer that is synchronised to a stratum 2 computer is at stratum 3, '
        'and so on. '
        'Default: %(default)s'
    ),
    '--test': (
        'For unit tests. Needs "path-to-stdout-file,path-to-stderr-file,expected-retc".'
    ),
    '--timeout': 'Network timeout in seconds. Default: %(default)s (seconds)',
    '--url': 'URL to the endpoint. Default: %(default)s',
    '--username': 'Username. Default: %(default)s',
    '--verbose': (
        'Makes this plugin verbose during the operation. '
        'Useful for debugging and seeing what is going on under the hood.'
    ),
    '--warning': (
        'WARN threshold in percent. Supports Nagios ranges. Default: >= %(default)s'
    ),
    '--warning-count': (
        'WARN threshold for the number of matching items. '
        'Supports Nagios ranges. '
        'Default: %(default)s'
    ),
    '--warning-seconds': (
        'WARN threshold in seconds. Supports Nagios ranges. Default: %(default)s'
    ),
}


# Predefined sets for checking units and methods
_UNITS = {'%', 'K', 'M', 'G', 'T', 'P'}
_METHODS = {'USED', 'FREE'}


def csv(arg):
    """Converts a CSV string into a list of values.

    ### Parameters
    - **arg** (`str`): A string containing values separated by commas.

    ### Returns
    - **list**: A list of stripped strings.

    ### Example
    >>> csv('apple, orange, banana, grape')
    ['apple', 'orange', 'banana', 'grape']
    """
    return [x.strip() for x in arg.split(',')]


def float_or_none(arg):
    """Converts an input to a float, or returns None if the input is 'none' or None.

    ### Parameters
    - **arg** (`str`, `None`, or `float`): The input value.

    ### Returns
    - **float** or **None**

    ### Example
    >>> float_or_none('123.45')
    123.45

    >>> float_or_none('none')
    None
    """
    if arg is None:
        return None
    if isinstance(arg, str) and arg.strip().lower() == 'none':
        return None
    return float(arg)


def help(param):
    """Retrieves the global help text for a given parameter.

    ### Parameters
    - **param** (`str`): The parameter name (e.g. '--timeout').

    ### Returns
    - **str**: The help text, or an empty string if not found.

    ### Example
    >>> help('--timeout')
    'Network timeout in seconds. Default: %(default)s (seconds)'
    """
    return HELP_TEXTS.get(param, '')


def int_or_none(arg):
    """Converts a given argument to an integer or returns None.

    ### Parameters
    - **arg** (`str` or `None`): The input value.

    ### Returns
    - **int** or **None**

    ### Example
    >>> int_or_none('42')
    42

    >>> int_or_none('none')
    None
    """
    if arg is None:
        return None
    if isinstance(arg, str) and arg.strip().lower() == 'none':
        return None
    return int(arg)


def number_unit_method(arg, unit='%', method='USED'):
    """Parses a string in the format `<number>[unit][method]` for threshold arguments.

    ### Parameters
    - **arg** (`str`): The input string.
    - **unit** (`str`, optional): Default unit. Defaults to `%`.
    - **method** (`str`, optional): Default method. Defaults to `USED`.

    ### Returns
    - **tuple**: (number, unit, method)

    ### Example
    >>> number_unit_method('95')
    ('95.0', '%', 'USED')

    >>> number_unit_method('9.5GFREE')
    ('9.5', 'G', 'FREE')
    """
    arg = arg.strip()
    number_part = []
    unit_part = ''
    method_part = ''

    i = 0
    while i < len(arg) and (arg[i].isdigit() or arg[i] == '.'):
        number_part.append(arg[i])
        i += 1

    if i < len(arg) and arg[i].upper() in _UNITS:
        unit_part = arg[i]
        i += 1

    if i < len(arg):
        method_part = arg[i:].upper()

    number = ''.join(number_part)
    if not number:
        return '0.0', unit.upper(), method.upper()

    if unit_part:
        unit = unit_part

    if method_part in _METHODS:
        method = method_part

    return number, unit.upper(), method.upper()


def range_or_none(arg):
    """See str_or_none()."""
    return str_or_none(arg)


def str_or_none(arg):
    """Converts an input argument into a string or returns None.

    ### Parameters
    - **arg** (`any`): The input argument.

    ### Returns
    - **str** or **None**

    ### Example
    >>> str_or_none(123)
    '123'

    >>> str_or_none('none')
    None
    """
    if arg is None:
        return None
    if isinstance(arg, str):
        if arg.strip().lower() == 'none':
            return None
        return arg

    return str(arg)
