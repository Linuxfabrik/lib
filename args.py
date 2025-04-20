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

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042002'


HELP_TEXTS = {
    '--match': (
        'Uses Python regular expressions without any external flags like `re.IGNORECASE`. '
        'The regular expression is applied to each line of the output. '
        'Examples: '
        '`(?i)example` to match the word "example" in a case-insensitive manner. '
        '`^(?!.*example).*$` to match any string except "example" (negative lookahead). '
        '`(?: ... )*` is a non-capturing group that matches any sequence of characters '
        'that satisfy the condition inside it, zero or more times.'
    ),
}

# Predefined sets for checking units and methods
_UNITS = {'%', 'K', 'M', 'G', 'T', 'P'}
_METHODS = {'USED', 'FREE'}


def csv(arg):
    """
    Converts a CSV string into a list of values.

    This function takes a comma-separated string (CSV format) and returns a list where each element
    corresponds to a value in the CSV string. Leading and trailing whitespace from each value is
    removed.

    ### Parameters
    - **arg** (`str`): A string containing values separated by commas (CSV format).

    ### Returns
    - **list**: A list of strings, each representing an element from the CSV input string.

    ### Example
    >>> csv("apple, orange, banana, grape")
    ['apple', 'orange', 'banana', 'grape']
    
    >>> csv(" one, two, three , four ")
    ['one', 'two', 'three', 'four']
    """
    return [x.strip() for x in arg.split(',')]


def float_or_none(arg):
    """
    Converts an input to a float, or returns None if the input is 'none' or None.

    This function attempts to convert the input argument into a float. If the input is `None` or
    the string 'none' (case insensitive), the function returns `None`. Otherwise, it returns the
    argument as a float.

    ### Parameters
    - **arg** (`str`, `None`, or `float`): The input value that will be converted to a float or
      returned as `None`.

    ### Returns
    - **float** or **None**: Returns the input as a float if it is convertible, or `None` if the
      input is 'none' or `None`.

    ### Example
    >>> float_or_none('123.45')
    123.45

    >>> float_or_none('none')
    None

    >>> float_or_none(None)
    None
    """
    if arg is None:
        return None
    if isinstance(arg, str) and arg.strip().lower() == 'none':
        return None
    return float(arg)


def help(param):
    """
    Retrieves the help text for a given parameter.

    This function returns the global help text associated with a specific parameter. It contains
    explanations for the valid options and usage of the parameter. If no help text is available
    for the parameter, it returns an empty string.

    ### Parameters
    - **param** (`str`): The parameter for which help text is to be retrieved.

    ### Returns
    - **str**: The help text for the given parameter, or an empty string if the parameter is not
      found.

    ### Example
    >>> help('--match')
    Lorem ipsum

    >>> help('--nonexistent')
    ''
    """
    return HELP_TEXTS.get(param, '')


def int_or_none(arg):
    """
    Converts a given argument to an integer or returns None.

    This function checks if the argument is `None` or the string `'none'`, in which case it returns
     `None`. Otherwise, it attempts to convert the argument to an integer and returns the result.

    ### Parameters
    - **arg** (`str` or `None`): The input value to be converted to an integer, or `None`.

    ### Returns
    - **int** or **None**: The integer value of the argument if it can be converted, or `None` if
      the argument is `None` or `'none'`.

    ### Example
    >>> int_or_none('42')
    42

    >>> int_or_none('none')
    None

    >>> int_or_none(None)
    None
    """
    if arg is None:
        return None
    if isinstance(arg, str) and arg.strip().lower() == 'none':
        return None
    return int(arg)


def number_unit_method(arg, unit='%', method='USED'):
    """
    Parses a string representing a number with an optional unit and method, and returns the
    corresponding components.

    This function expects an input string in the format `<number>[unit][method]`, typically
    used for threshold arguments. The function extracts and returns the numeric value, unit
    (defaults to `%`), and method (defaults to `USED`). The function supports various units
    such as `K`, `M`, `G`, `T`, `P`, and `%`, and methods like `USED` and `FREE`.

    ### Parameters
    - **arg** (`str`): The input string representing the number, unit, and method.
    - **unit** (`str`, optional): The unit of measurement, one of `%%|K|M|G|T|P`. Defaults to `%`.
    - **method** (`str`, optional): The method used, one of `USED|FREE`. Defaults to `USED`.

    ### Returns
    - **tuple**: A tuple containing:
      - **str**: The numeric value.
      - **str**: The unit (defaults to `%` if not specified).
      - **str**: The method (defaults to `USED` if not specified).

    ### Example
    >>> number_unit_method('95')
    ('95.0', '%', 'USED')

    >>> number_unit_method('9.5M')
    ('9.5', 'M', 'USED')

    >>> number_unit_method('95%USED')
    ('95.0', '%', 'USED')

    >>> number_unit_method('5FREE')
    ('5.0', '%', 'FREE')

    >>> number_unit_method('5%FREE')
    ('5.0', '%', 'FREE')

    >>> number_unit_method('9.5GFREE')
    ('9.5', 'G', 'FREE')

    >>> number_unit_method('1400GUSED')
    ('1400.0', 'G', 'USED')
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
    """
    See str_or_none()
    """
    return str_or_none(arg)


def str_or_none(arg):
    """
    Converts an input argument into a string or returns `None`.

    This function checks if the input is `None` or the string `"none"` (case-insensitive) and
    returns `None` in those cases. Otherwise, it returns the input as a string.

    ### Parameters
    - **arg** (`any`): The input argument that can be any type.

    ### Returns
    - **str** or **None**: If the input is not `None` or `"none"`, it returns the input as a
      string; otherwise, it returns `None`.

    ### Example
    >>> str_or_none(123)
    '123'

    >>> str_or_none('none')
    None

    >>> str_or_none(None)
    None
    """
    if arg is None:
        return None
    if isinstance(arg, str):
        if arg.strip().lower() == 'none':
            return None
        return arg

    return str(arg)
