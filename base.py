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
__version__ = '2023071202'

import collections
import numbers
import operator
import os
import sys

from traceback import format_exc

from .globals import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN


WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")
X86_64 = sys.maxsize > 2**32


def coe(result, state=STATE_UNKNOWN):
    """Continue or Exit (CoE)

    This is useful if calling complex library functions in your checks
    `main()` function. Don't use this in functions.

    If a more complex library function, for example `lib.url.fetch()` fails, it
    returns `(False, 'the reason why I failed')`, otherwise `(True,
    'this is my result'). This forces you to do some error handling.
    To keep things simple, use `result = lib.base.coe(lib.url.fetch(...))`.
    If `fetch()` fails, your plugin will exit with STATE_UNKNOWN (default) and
    print the original error message. Otherwise your script just goes on.

    The use case in `main()` - without `coe`:

    >>> success, html = lib.url.fetch(URL)
    >>> if not success:
    >>>     print(html)             # contains the error message here
    >>>>    exit(STATE_UNKNOWN)

    Or simply:

    >>> html = lib.base.coe(lib.url.fetch(URL))

    Parameters
    ----------
    result : tuple
        The result from a function call.
        result[0] = expects the function return code (True on success)
        result[1] = expects the function result (could be of any type)
    state : int
        If result[0] is False, exit with this state.
        Default: 3 (which is STATE_UNKNOWN)

    Returns
    -------
    any type
        The result of the inner function call (result[1]).
    """
    if result[0]:
        # success
        return result[1]
    print(result[1])
    sys.exit(state)


def cu(msg=None):
    """See you (cu)

    Prints an optional message and a Stacktrace (replacing "<" and ">" to be printable in Web-GUIs),
    and always exits with STATE_UNKNOWN.
    Use this function to print error messages.
    """
    tb = format_exc()
    if 'NoneType: None' not in tb:
        # got a stacktrace
        tb = tb.replace("<", "'").replace(">", "'")
        if msg is not None:
            print(msg.strip() + '\n')
        print(tb)
    else:
        if msg is not None:
            print(msg.strip())
    sys.exit(STATE_UNKNOWN)


def get_perfdata(label, value, uom=None, warn=None, crit=None, _min=None, _max=None):
    """Returns 'label'=value[UOM];[warn];[crit];[min];[max]
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
    """Returns the STATE by comparing `value` to the given thresholds using
    a comparison `_operator`. `warn` and `crit` threshold may also be `None`.

    >>> get_state(15, 10, 20, 'ge')
    1 (STATE_WARN)
    >>> get_state(10, 10, 20, 'gt')
    0 (STATE_OK)

    Parameters
    ----------
    value : float
        Numeric value
    warn : float
        Numeric warning threshold
    crit : float
        Numeric critical threshold
    _operator : string
        `eq` = equal to
        `ge` = greater or equal
        `gt` = greater than
        `le` = less or equal
        `lt` = less than
        `ne` = not equal to
        `range` = match range

    Returns
    -------
    int
        `STATE_OK`, `STATE_WARN` or `STATE_CRIT`
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
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        cols - List of cols in the dictionary. (Type: List)

    Optional Parameters:
        header - The table header. (Type: List)
        strip - Strip/Trim values or not. (Type: Boolean)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: bool)

    Inspired by
    https://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/
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
            except:
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
    """Compares state1 to state2 and returns result based on the following
    STATE_OK < STATE_UNKNOWN < STATE_WARNING < STATE_CRITICAL
    It will prioritize any non-OK state.

    Note that numerically the above does not hold.
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
    """Guess the type of a value (None, int, float or string) for different types of consumers
    (Python, SQLite etc.).
    For Python, use isinstance() to check for example if a number is an integer.

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
    >>>
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
    """Check if a list only contains either empty elements or whitespace
    """
    return all(s == '' or s.isspace() for s in l)


def is_numeric(value):
    """Return True if value is really numeric (int, float, whatever).

    >>> is_numeric(+53.4)
    True
    >>> is_numeric('53.4')
    False
    """
    return isinstance(value, numbers.Number)


def lookup_lod(dicts, key, needle, default=None):
    """Search in a list of dictionaries ("lod)" for a value in a given dict key.
    Return a default if not found.

    >>> dicts = [
    ...     { "name": "Tom", "age": 10 },
    ...     { "name": "Mark", "age": 5 },
    ...     { "name": "Pam", "age": 7 },
    ...     { "name": "Dick", "age": 12 }
    ... ]
    >>> lookup_lod(dicts, 'name', 'Pam')
    {'name': 'Pam', 'age': 7}
    >>> lookup_lod(dicts, 'name', 'Pamela')
    >>>
    """
    return next((item for item in dicts if item[key] == needle), None)


def match_range(value, spec):
    """Decides if `value` is inside/outside the threshold spec.

    Parameters
    ----------
    spec : str
        Nagios range specification
    value : int or float
        Numeric value

    Returns
    -------
    bool
        `True` if `value` is inside the bounds for a non-inverted
        `spec`, or outside the bounds for an inverted `spec`. Otherwise `False`.

    Inspired by https://github.com/mpounsett/nagiosplugin/blob/master/nagiosplugin/range.py
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
    """Over and Out (OaO)

    Print the stripped plugin message. If perfdata is given, attach it
    by `|` and print it stripped. Exit with `state`, or with STATE_OK (0) if
    `always_ok` is set to `True`.
    """
    if perfdata:
        print(msg.strip() + '|' + perfdata.strip())
    else:
        print(msg.strip())
    if always_ok:
        sys.exit(STATE_OK)
    sys.exit(state)


def smartcast(value):
    """Returns the value converted to float if possible, else string, else the
    uncasted value.
    """
    for test in [float, str]:
        try:
            return test(value)
        except ValueError:
            continue
            # No match
    return value


def sort(array, reverse=True, sort_by_key=False):
    """Sort a simple 1-dimensional dictionary
    """
    if isinstance(array, dict):
        if not sort_by_key:
            return sorted(array.items(), key=lambda x: x[1], reverse=reverse)
        return sorted(array.items(), key=lambda x: str(x[0]).lower(), reverse=reverse)
    return array


def state2str(state, empty_ok=True, prefix='', suffix=''):
    """Return the state's string representation.
    The square brackets around the state cause icingaweb2 to color the state.

    >> lib.base.state2str(2)
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


def str2state(string, ignore_error=True):
    """Return the numeric state based on a (case-insensitive) string.
    Matches up to the first four characters.

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
    """Sum up two dictionaries, maybe with different keys.

    >>> sum_dict({'in': 100, 'out': 10}, {'in': 50, 'error': 5, 'uuid': '1234-xyz'})
    {'in': 150, 'error': 5, 'out': 10}
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
    """Sum up a list of (simple 1-dimensional) dictionary items.

    sum_lod([{'in': 100, 'out': 10}, {'in': 50, 'out': 20}, {'error': 5, 'uuid': '1234-xyz'}])
    >>> {'in': 150, 'out': 30, 'error': 5}
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
