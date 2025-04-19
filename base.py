#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Provides very common every-day functions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025041902'

import collections
import numbers
import operator
import os
import sys

from traceback import format_exc

from .globals import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN
from . import txt


WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")
X86_64 = sys.maxsize > 2**32


def coe(result, state=STATE_UNKNOWN):
    """
    Continue or Exit (CoE)

    This function simplifies error handling for function calls that return a `(success, result)`
    tuple. If the operation fails, it sanitizes and prints the error message and exits with a given
    state. Otherwise, it returns the successful result and allows the script to continue.

    ### Parameters
    - **result** (`tuple`): A two-element tuple returned from a function.
      - `result[0]` (`bool`): Success indicator (`True` if successful, `False` otherwise).
      - `result[1]` (`any`): The actual result or an error message.
    - **state** (`int`, optional): Exit code to use if the function fails.
      Defaults to `STATE_UNKNOWN` (3).

    ### Returns
    - **any type**: The second element of the result tuple (`result[1]`) if successful.

    ### Notes
    - Sensitive information in error messages is automatically redacted before printing.
    - This function is intended to be used **only** inside the `main()` function of a plugin,
      not inside library functions.
    - If the function fails (`result[0]` is `False`), the script immediately exits after printing
      the sanitized message.

    ### Example
    Without `coe`:
    >>> success, html = lib.url.fetch(URL)
    >>> if not success:
    >>>     print(html)
    >>>     sys.exit(STATE_UNKNOWN)

    With `coe`:
    >>> html = lib.base.coe(lib.url.fetch(URL))
    """
    if result[0]:
        # success
        return result[1]
    # hide passwords
    result[1] = txt.sanitize_sensitive_data(result[1])
    print(result[1])
    sys.exit(state)


def cu(msg=None):
    """
    See you (cu)

    Print an optional error message and stack trace, then exit with STATE_UNKNOWN.

    This function prints an optional sanitized message, attaches a stack trace if an error occurred,
    and exits the script with `STATE_UNKNOWN`. It ensures output is safe for display in web GUIs
    by replacing `<` and `>` characters.

    ### Parameters
    - **msg** (`str`, optional): An optional message to print before exiting.
      If provided, it will be stripped, sanitized, and printed.

    ### Returns
    - **None**: This function does not return; it always exits the script with `STATE_UNKNOWN`.

    ### Notes
    - If a traceback exists, it is included for debugging, with `<` and `>` replaced by `'`.
    - Sensitive information in the message is automatically redacted before printing.
    - If no traceback is present, only the optional message (if any) is printed.

    ### Example
    >>> cu("Unable to connect to server")

    >>> cu()
    """
    tb = format_exc()
    has_traceback = tb and 'NoneType: None' not in tb

    if msg is not None:
        msg = txt.sanitize_sensitive_data(msg).strip()
        print(msg, end='')
        if has_traceback:
            print(' (Traceback for debugging purposes attached)\n')
        else:
            print()

    if has_traceback:
        safe_tb = tb.replace('<', "'").replace('>', "'")
        print(safe_tb)

    sys.exit(STATE_UNKNOWN)


def get_perfdata(label, value, uom=None, warn=None, crit=None, _min=None, _max=None):
    """
    Returns a Nagios performance data string in the format:  
    `'label'=value[UOM];[warn];[crit];[min];[max]`

    ### Parameters
    - **label** (`str`): The name of the performance data label.
    - **value** (`int` or `float`): The measured value.
    - **uom** (`str`, optional): The unit of measurement (e.g., 's', 'B', '%'). Defaults to None.
    - **warn** (`int` or `float`, optional): Warning threshold. Defaults to None.
    - **crit** (`int` or `float`, optional): Critical threshold. Defaults to None.
    - **_min** (`int` or `float`, optional): Minimum value. Defaults to None.
    - **_max** (`int` or `float`, optional): Maximum value. Defaults to None.

    ### Returns
    - **str**: A properly formatted Nagios performance data string.

    ### Example
    >>> get_perfdata('load1', 0.42, '', 1.0, 5.0, 0, 10)
    "'load1'=0.42;1.0;5.0;0;10 "
    """
    msg = "'{}'={}".format(label, value)
    if uom is not None:
        msg += uom
    msg += ';'
    if warn is not None:
        msg += str(warn)
    msg += ';'
    if crit is not None:
        msg += str(crit)
    msg += ';'
    if _min is not None:
        msg += str(_min)
    msg += ';'
    if _max is not None:
        msg += str(_max)
    msg += ' '
    return msg


def get_state(value, warn, crit, _operator='ge'):
    """
    Returns the STATE by comparing `value` to the given thresholds using
    a comparison `_operator`. `warn` and `crit` thresholds may also be `None`.

    ### Parameters
    - **value** (`float`): Numeric value to evaluate.
    - **warn** (`float`): Numeric warning threshold.
    - **crit** (`float`): Numeric critical threshold.
    - **_operator** (`str`): Comparison operator to use:  
      - `eq`: equal to  
      - `ge`: greater or equal  
      - `gt`: greater than  
      - `le`: less or equal  
      - `lt`: less than  
      - `ne`: not equal to  
      - `range`: match Nagios range definition

    ### Returns
    - **int**: `STATE_OK`, `STATE_WARN`, or `STATE_CRIT`.

    ### Example
    >>> get_state(15, 10, 20, 'ge')
    1  # STATE_WARN

    >>> get_state(10, 10, 20, 'gt')
    0  # STATE_OK
    """
    # make sure to use float comparison
    value = float(value)
    if _operator == 'ge':
        if crit is not None:
            if value >= float(crit):
                return STATE_CRIT
        if warn is not None:
            if value >= float(warn):
                return STATE_WARN
        return STATE_OK

    if _operator == 'gt':
        if crit is not None:
            if value > float(crit):
                return STATE_CRIT
        if warn is not None:
            if value > float(warn):
                return STATE_WARN
        return STATE_OK

    if _operator == 'le':
        if crit is not None:
            if value <= float(crit):
                return STATE_CRIT
        if warn is not None:
            if value <= float(warn):
                return STATE_WARN
        return STATE_OK

    if _operator == 'lt':
        if crit is not None:
            if value < float(crit):
                return STATE_CRIT
        if warn is not None:
            if value < float(warn):
                return STATE_WARN
        return STATE_OK

    if _operator == 'eq':
        if crit is not None:
            if value == float(crit):
                return STATE_CRIT
        if warn is not None:
            if value == float(warn):
                return STATE_WARN
        return STATE_OK

    if _operator == 'ne':
        if crit is not None:
            if value != float(crit):
                return STATE_CRIT
        if warn is not None:
            if value != float(warn):
                return STATE_WARN
        return STATE_OK

    if _operator == 'range':
        if crit is not None:
            if not coe(match_range(value, crit)):
                return STATE_CRIT
        if warn is not None:
            if not coe(match_range(value, warn)):
                return STATE_WARN
        return STATE_OK

    return STATE_UNKNOWN


def get_table(data, cols, header=None, strip=True, sort_by_key=None, sort_order_reverse=False):
    """
    Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Inspired by:  
    https://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/

    ### Parameters
    - **data** (`list`): Data to process (list of dictionaries).
    - **cols** (`list`): List of keys/columns to include from the dictionaries.
    - **header** (`list`, optional): Custom table headers. Defaults to None.
    - **strip** (`bool`, optional): If True, strip/trim values. Defaults to True.
    - **sort_by_key** (`str`, optional): The key to sort the table by. Defaults to None.
    - **sort_order_reverse** (`bool`, optional): If True, sort descending. Defaults to False.

    ### Returns
    - **str**: A formatted text table as a single string.

    ### Example
    >>> data = [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]
    >>> cols = ['name', 'age']
    >>> print(get_table(data, cols))
    name  ! age
    ------+----
    Alice ! 30
    Bob   ! 25
    """
    if not data:
        return ''

    # Sort the data if a sort key is specified (default sort order is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=operator.itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, create a list of dictionary from the cols and the header and
    # insert it before first row of data
    if header:
        header = dict(zip(cols, header))
        data.insert(0, header)

    # prepare data: decode from (mostly) UTF-8 to Unicode, optionally strip values and get
    # the maximum length per column
    column_widths = collections.OrderedDict()
    for idx, row in enumerate(data):
        for col in cols:
            try:
                if strip:
                    data[idx][col] = str(row[col]).strip()
                else:
                    data[idx][col] = str(row[col])
            except KeyError as e:
                return 'Unknown column "{}"'.format(col)
            # get the maximum length
            try:
                column_widths[col] = max(column_widths[col], len(data[idx][col]))
            except:
                column_widths[col] = len(data[idx][col])

    if header:
        # Get the length of each column and create a '---' divider based on that length
        header_divider = []
        for col, width in column_widths.items():
            header_divider.append('-' * width)

        # Insert the header divider below the header row
        header_divider = dict(zip(cols, header_divider))
        data.insert(1, header_divider)

    # create the output
    table = ''
    cnt = 0
    for row in data:
        tmp = ''
        for col, width in column_widths.items():
            if cnt != 1:
                tmp += '{:<{}} ! '.format(row[col], width)
            else:
                # header row
                tmp += '{:<{}}-+-'.format(row[col], width)
        cnt += 1
        table += tmp[:-2] + '\n'

    return table


def get_worst(state1, state2):
    """
    Compares `state1` to `state2` and returns the worse state based on the following priority:  
    STATE_OK < STATE_UNKNOWN < STATE_WARNING < STATE_CRITICAL  
    It will prioritize any non-OK state.

    Note that numerically the priority order does not match their integer values.

    ### Parameters
    - **state1** (`int`): The first state to compare.
    - **state2** (`int`): The second state to compare.

    ### Returns
    - **int**: The worse state according to the priority order.

    ### Example
    >>> get_worst(STATE_OK, STATE_WARNING)
    STATE_WARNING

    >>> get_worst(STATE_UNKNOWN, STATE_CRITICAL)
    STATE_CRITICAL
    """
    state1 = int(state1)
    state2 = int(state2)
    if STATE_CRIT in [state1, state2]:
        return STATE_CRIT
    if STATE_WARN in [state1, state2]:
        return STATE_WARN
    if STATE_UNKNOWN in [state1, state2]:
        return STATE_UNKNOWN
    return STATE_OK


def guess_type(v, consumer='python'):
    """
    Guess the type of a value (None, int, float, or string) for different types of consumers
    (e.g., Python, SQLite).

    For Python, it returns the actual type (`int`, `float`, or `str`).
    For SQLite, it returns a string describing the type (`'integer'`, `'real'`, `'text'`).

    ### Parameters
    - **v** (`any`): The value to guess the type for.
    - **consumer** (`str`, optional): The consumer type ('python' or 'sqlite'). Defaults to
      'python'.

    ### Returns
    - **any**: 
      - If `consumer='python'`, returns `None`, `int`, `float`, or `str`.
      - If `consumer='sqlite'`, returns `'integer'`, `'real'`, or `'text'`.

    ### Example
    >>> guess_type('1')
    1

    >>> guess_type('1', 'sqlite')
    'integer'

    >>> guess_type('1.0')
    1.0

    >>> guess_type('1.0', 'sqlite')
    'real'

    >>> guess_type('abc')
    'abc'

    >>> guess_type('abc', 'sqlite')
    'text'

    >>> value_type = lib.base.guess_type(value)
    >>> if isinstance(value_type, int) or isinstance(value_type, float):
    >>>     ...
    """
    if consumer == 'python':
        if v is None:
            return None
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return str(v)

    if consumer == 'sqlite':
        if v is None:
            return 'string'
        try:
            int(v)
            return 'integer'
        except ValueError:
            try:
                float(v)
                return 'real'
            except ValueError:
                return 'text'


def is_empty_list(l):
    """
    Check if a list only contains either empty elements or whitespace.

    ### Parameters
    - **l** (`list`): The list to check.

    ### Returns
    - **bool**: True if all elements are empty strings or whitespace, otherwise False.

    ### Example
    >>> is_empty_list(['', '   ', ''])
    True

    >>> is_empty_list(['text', ''])
    False
    """
    return all(s == '' or s.isspace() for s in l)


def is_numeric(value):
    """
    Return True if the value is truly numeric (int, float, etc.).

    ### Parameters
    - **value** (`any`): The value to check.

    ### Returns
    - **bool**: True if the value is numeric, otherwise False.

    ### Example
    >>> is_numeric(+53.4)
    True

    >>> is_numeric('53.4')
    False
    """
    return isinstance(value, numbers.Number)


def lookup_lod(haystack, key, needle):
    """
    Search in a list of dictionaries ("lod") for a key containing a specific value
    and return the first dictionary item found.

    Returns `(index, item)` if the needle was found, otherwise `(-1, None)`.

    ### Parameters
    - **haystack** (`list`): A list of dictionaries to search through.
    - **key** (`str`): The key to look for in each dictionary.
    - **needle** (`any`): The value to match against the specified key.

    ### Returns
    - **tuple**: 
        - If found: (index, dictionary item).
        - If not found: (-1, None).

    ### Example
    >>> haystack = [
    ...     {"name": "Tom", "age": 10},
    ...     {"name": "Mark", "age": 5},
    ...     {"name": "Pam", "age": 7},
    ...     {"name": "Dick", "age": 12}
    ... ]
    >>> lookup_lod(haystack, 'name', 'Pam')
    (2, {'name': 'Pam', 'age': 7})

    >>> lookup_lod(haystack, 'name', 'Pamela')
    (-1, None)
    """
    try:
        for index, item in enumerate(haystack):
            if item[key] == needle:
                return index, item
    except:
        return -1, None
    return -1, None


def match_range(value, spec):
    """
    Decides if `value` is inside or outside the Nagios threshold specification.

    ### Parameters
    - **value** (`int` or `float`): The numeric value to check.
    - **spec** (`str`): The Nagios range specification string.

    ### Returns
    - **bool**: 
      - True if `value` is inside the bounds for a non-inverted `spec`, or outside the bounds for an inverted `spec`.
      - Otherwise, False.

    ### Example
    >>> match_range(15, '10')
    0 10 False

    >>> match_range(15, '-10')
    (False, 'Start 0 must not be greater than end -10')

    >>> match_range(15, '10:')
    10 inf False

    >>> match_range(15, ':')
    0 inf False

    >>> match_range(15, '~:10')
    -inf 10 False

    >>> match_range(15, '10:20')
    10 20 False

    >>> match_range(15, '@10')
    0 10 True

    >>> match_range(15, '@~:20')
    -inf 20 True

    >>> match_range(15, '@')
    0 inf True
    """
    def parse_range(spec):
        """
        Inspired by https://github.com/mpounsett/nagiosplugin/blob/master/nagiosplugin/range.py

        +--------+-------------------+-------------------+--------------------------------+
        | -w, -c | OK if result is   | WARN/CRIT if      | lib.base.parse_range() returns |
        +--------+-------------------+-------------------+--------------------------------+
        | 10     | in (0..10)        | not in (0..10)    | (0, 10, False)                 |
        +--------+-------------------+-------------------+--------------------------------+
        | -10    | in (-10..0)       | not in (-10..0)   | (0, -10, False)                |
        +--------+-------------------+-------------------+--------------------------------+
        | 10:    | in (10..inf)      | not in (10..inf)  | (10, inf, False)               |
        +--------+-------------------+-------------------+--------------------------------+
        | :      | in (0..inf)       | not in (0..inf)   | (0, inf, False)                |
        +--------+-------------------+-------------------+--------------------------------+
        | ~:10   | in (-inf..10)     | not in (-inf..10) | (-inf, 10, False)              |
        +--------+-------------------+-------------------+--------------------------------+
        | 10:20  | in (10..20)       | not in (10..20)   | (10, 20, False)                |
        +--------+-------------------+-------------------+--------------------------------+
        | @10:20 | not in (10..20)   | in 10..20         | (10, 20, True)                 |
        +--------+-------------------+-------------------+--------------------------------+
        | @~:20  | not in (-inf..20) | in (-inf..20)     | (-inf, 20, True)               |
        +--------+-------------------+-------------------+--------------------------------+
        | @      | not in (0..inf)   | in (0..inf)       | (0, inf, True)                 |
        +--------+-------------------+-------------------+--------------------------------+
        """
        def parse_atom(atom, default):
            if atom == '':
                return default
            if '.' in atom:
                return float(atom)
            return int(atom)

        if spec is None or str(spec).lower() == 'none':
            return (True, None)
        if not isinstance(spec, str):
            spec = str(spec)
        invert = False
        if spec.startswith('@'):
            invert = True
            spec = spec[1:]
        if ':' in spec:
            try:
                start, end = spec.split(':')
            except:
                return (False, 'Not using range definition correctly')
        else:
            start, end = '', spec
        if start == '~':
            start = float('-inf')
        else:
            start = parse_atom(start, 0)
        end = parse_atom(end, float('inf'))
        if start > end:
            return (False, 'Start %s must not be greater than end %s' % (start, end))
        return (True, (start, end, invert))

    # workaround for https://github.com/Linuxfabrik/monitoring-plugins/issues/789
    if isinstance(spec, str):
        spec = spec.lstrip('\\')

    if spec is None or str(spec).lower() == 'none':
        return (True, True)
    success, result = parse_range(spec)
    if not success:
        return (success, result)
    start, end, invert = result
    if isinstance(value, (str, bytes)):
        value = float(value.replace('%', ''))
    if value < start:
        return (True, False ^ invert)
    if value > end:
        return (True, False ^ invert)
    return (True, True ^ invert)


def oao(msg, state=STATE_OK, perfdata='', always_ok=False):
    """
    Over and Out (OaO)

    Print a sanitized plugin message with optional performance data and exit the script.

    This function formats and prints a plugin message, appends performance data if provided,
    sanitizes sensitive information, replaces reserved `|` characters, and exits with the
    specified state code. Optionally, it can always exit with `STATE_OK` regardless of the given
    state.

    ### Parameters
    - **msg** (`str`): The plugin message to print. Will be stripped, sanitized, and processed.
    - **state** (`int`, optional): The exit code to use. Defaults to `STATE_OK`.
    - **perfdata** (`str`, optional): Performance data to append after a `|` separator.  
      Defaults to an empty string (no performance data).
    - **always_ok** (`bool`, optional): If `True`, forces the exit code to `STATE_OK` regardless
      of the specified `state`. Defaults to `False`.

    ### Returns
    - **None**: This function does not return; it terminates the script via `sys.exit()`.

    ### Notes
    - Any `|` characters inside the message are replaced with `!` to avoid breaking Nagios plugin
      output format.
    - Sensitive information like passwords, tokens, and keys is automatically redacted.
    - `perfdata`, if provided, must follow monitoring plugin standards for performance metrics.

    ### Example
    >>> oao("Service is healthy", STATE_OK, "load=0.12;1.00;5.00", always_ok=False)
    Service is healthy|load=0.12;1.00;5.00
    (and exits with code 0)

    >>> oao("password=secret123 found!", STATE_CRITICAL)
    password=****** found!
    (and exits with code 2)

    """
    msg = msg.strip()
    # The `|` character is a reserved one to seperate plugin output from performance data.
    # There is actually no way to escape it, so replace it.
    msg = msg.replace('|', '!')
    # hide passwords
    msg = txt.sanitize_sensitive_data(msg)
    if always_ok:
        msg += ' (always ok)'
    if perfdata:
        print(msg + '|' + perfdata.strip())
    else:
        print(msg)
    if always_ok:
        sys.exit(STATE_OK)
    sys.exit(state)


def smartcast(value):
    """
    Returns the value converted to `float` if possible, else to `str`, else returns
    the uncasted value.

    ### Parameters
    - **value** (`any`): The value to attempt to cast.

    ### Returns
    - **float**, **str**, or **any**: 
      - If convertible to `float`, returns a `float`.
      - If not, tries to convert to `str`.
      - If neither succeeds, returns the original value unchanged.

    ### Example
    >>> smartcast('3.14')
    3.14

    >>> smartcast(42)
    42.0

    >>> smartcast('hello')
    'hello'
    """
    for test in [float, str]:
        try:
            return test(value)
        except ValueError:
            continue
            # No match
    return value


def sort(array, reverse=True, sort_by_key=False):
    """
    Sort a 1-dimensional dictionary by its values or keys.

    When a dictionary is provided, this function returns a list of (key, value)
    tuples sorted based on the specified criteria:
      - If `sort_by_key` is False (default), the dictionary items are sorted by their values.
      - If `sort_by_key` is True, the items are sorted by their keys (compared case-insensitively).

    The sort order is descending by default (`reverse=True`).  
    If the input is not a dictionary, the original input is returned unmodified.

    ### Parameters
    - **array** (`dict` or `any`): The dictionary to be sorted. If not a dictionary, the input is returned as is.
    - **reverse** (`bool`, optional): If True, sort in descending order; if False, ascending. Defaults to True.
    - **sort_by_key** (`bool`, optional): If True, sort by dictionary keys; if False, by values. Defaults to False.

    ### Returns
    - **list** or **any**: A list of sorted (key, value) tuples if a dictionary is provided, otherwise the original input.

    ### Example
    >>> sort({'a': 2, 'b': 1})
    [('a', 2), ('b', 1)]

    >>> sort({'a': 2, 'b': 1}, reverse=False)
    [('b', 1), ('a', 2)]

    >>> sort({'a': 2, 'B': 1}, sort_by_key=True)
    [('a', 2), ('B', 1)]
    """
    if isinstance(array, dict):
        if not sort_by_key:
            return sorted(array.items(), key=lambda x: x[1], reverse=reverse)
        return sorted(array.items(), key=lambda x: str(x[0]).lower(), reverse=reverse)
    return array


def state2str(state, empty_ok=True, prefix='', suffix=''):
    """
    Return the state's string representation.

    The square brackets around the state cause Icinga Web 2 to color the state.

    ### Parameters
    - **state** (`int`): The state code (e.g., 0, 1, 2, 3).
    - **empty_ok** (`bool`, optional): If True and the state is OK (0), return an empty string.
      Defaults to True.
    - **prefix** (`str`, optional): A prefix string to prepend to the result. Defaults to ''.
    - **suffix** (`str`, optional): A suffix string to append to the result. Defaults to ''.

    ### Returns
    - **str**: A formatted string representation of the state.

    ### Example
    >>> lib.base.state2str(2)
    '[CRIT]'

    >>> state2str(0)
    ''

    >>> state2str(0, empty_ok=False)
    '[OK]'

    >>> state2str(0, empty_ok=False, suffix=' ')
    '[OK] '

    >>> state2str(0, empty_ok=False, prefix=' (', suffix=')')
    ' ([OK])'
    """
    state = int(state)
    if state == STATE_OK and empty_ok:
        return ''
    if state == STATE_OK and not empty_ok:
        return '{}[OK]{}'.format(prefix, suffix)
    if state == STATE_WARN:
        return '{}[WARNING]{}'.format(prefix, suffix)
    if state == STATE_CRIT:
        return '{}[CRITICAL]{}'.format(prefix, suffix)
    if state == STATE_UNKNOWN:
        return '{}[UNKNOWN]{}'.format(prefix, suffix)
    return state


def str2bool(s):
    """
    Return True or False depending on the given string.

    ### Parameters
    - **s** (`str`): The input string to evaluate.

    ### Returns
    - **bool**: True if the string is not empty and not equal to "false" (case-insensitive),
      otherwise False.

    ### Example
    >>> str2bool("")
    False

    >>> str2bool("false")
    False

    >>> str2bool("FalSE")
    False

    >>> str2bool("true")
    True

    >>> str2bool("Linuxfabrik")
    True

    >>> str2bool("0")
    True

    >>> str2bool("1")
    True
    """
    if not s:
        return False
    elif s.lower() == 'false':
        return False
    else:
        return True


def str2state(string, ignore_error=True):
    """
    Return the numeric state based on a (case-insensitive) string.

    Matches up to the first four characters of the input string.

    ### Parameters
    - **string** (`str`): The input string to match against known states.
    - **ignore_error** (`bool`, optional): If True, unrecognized strings return `STATE_UNKNOWN`.  
      If False, unrecognized strings return None. Defaults to True.

    ### Returns
    - **int** or **None**: 
      - The numeric state code (`STATE_OK`, `STATE_WARN`, `STATE_CRIT`, `STATE_UNKNOWN`) if
        recognized.
      - Otherwise, `STATE_UNKNOWN` or None, depending on `ignore_error`.

    ### Example
    >>> str2state('ok')
    0

    >>> str2state('okidoki')
    3

    >>> str2state('okidoki', ignore_error=False)
    None

    >>> str2state('war')
    3

    >>> str2state('warn')
    1

    >>> str2state('Warnung')
    1

    >>> str2state('CrITical')
    2

    >>> str2state('UNKNOWN')
    3

    >>> str2state('gobbledygook')
    3

    >>> str2state('gobbledygook', ignore_error=False)
    None
    """
    string = str(string).lower()[0:4]
    if string == 'ok':
        return STATE_OK
    if string == 'warn':
        return STATE_WARN
    if string == 'crit':
        return STATE_CRIT
    if string == 'unkn':
        return STATE_UNKNOWN
    if ignore_error:
        return STATE_UNKNOWN
    return None


def sum_dict(dict1, dict2):
    """
    Sum up two dictionaries, possibly with different keys.

    Only numeric values are considered for summation; non-numeric values are ignored.

    ### Parameters
    - **dict1** (`dict`): The first dictionary to sum.
    - **dict2** (`dict`): The second dictionary to sum.

    ### Returns
    - **dict**: A new dictionary with summed numeric values by key.

    ### Example
    >>> sum_dict({'in': 100, 'out': 10}, {'in': 50, 'error': 5, 'uuid': '1234-xyz'})
    {'in': 150, 'out': 10, 'error': 5}
    """
    total = {}
    for key, value in dict1.items():
        if not is_numeric(value):
            continue
        if key in total:
            total[key] += value
        else:
            total[key] = value
    for key, value in dict2.items():
        if not is_numeric(value):
            continue
        if key in total:
            total[key] += value
        else:
            total[key] = value
    return total


def sum_lod(mylist):
    """
    Sum up a list of (simple 1-dimensional) dictionary items.

    Only numeric values are considered for summation; non-numeric values are ignored.

    ### Parameters
    - **mylist** (`list`): A list of dictionaries to sum.

    ### Returns
    - **dict**: A dictionary with summed numeric values by key.

    ### Example
    >>> sum_lod([{'in': 100, 'out': 10}, {'in': 50, 'out': 20}, {'error': 5, 'uuid': '1234-xyz'}])
    {'in': 150, 'out': 30, 'error': 5}
    """
    total = {}
    for mydict in mylist:
        for key, value in mydict.items():
            if not is_numeric(value):
                continue
            if key in total:
                total[key] += value
            else:
                total[key] = value
    return total
