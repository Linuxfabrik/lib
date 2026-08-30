#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Provides very common every-day functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026083001'

import math
import numbers
import operator
import os
import re
import sys
from traceback import format_exc

from . import human, txt
from .globals import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN

# A `<` that opens what a web interface would read as an HTML tag. This mirrors the
# expression Icinga Web uses to decide whether a plugin output is HTML or plain text
# (`Icingadb\Util\PluginOutput`, and the same one in the classic monitoring module).
# Only such a `<` is escaped, so comparisons and shell snippets survive verbatim while
# the output still cannot be mistaken for markup. See `oao()`.
TAG_START = re.compile(r'<(?=\w+(?:\s\w+=[^>]*)?>)')

WINDOWS = os.name == 'nt'
LINUX = sys.platform.startswith('linux')
# True on any 64-bit Python (x86_64, aarch64, ppc64*, s390x, riscv64, ...).
IS_64BIT = sys.maxsize > 2**32

_OPS = {
    'ge': operator.ge,
    'gt': operator.gt,
    'le': operator.le,
    'lt': operator.lt,
    'eq': operator.eq,
    'ne': operator.ne,
}

_STATE_NAMES = {
    STATE_OK: '[OK]',
    STATE_WARN: '[WARNING]',
    STATE_CRIT: '[CRITICAL]',
    STATE_UNKNOWN: '[UNKNOWN]',
}


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
    - This function is intended to be used **only** inside the `main()` function of the
      calling script, not inside library functions.
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
    # getting something like `(False, 'Error message')`; hide passwords in error message
    print(txt.sanitize_sensitive_data(result[1]))
    sys.exit(state)


def cu(msg=None, traceback=True):
    """
    See you (cu)

    Print an optional error message and stack trace, then exit with STATE_UNKNOWN.

    This function prints an optional sanitized message, attaches a stack trace if an error occurred,
    and exits the script with `STATE_UNKNOWN`. It ensures output is safe for display in web GUIs
    by replacing `<` and `>` characters.

    ### Parameters
    - **msg** (`str`, optional): An optional message to print before exiting.
      If provided, it will be stripped, sanitized, and printed.
    - **traceback** (`bool`, optional):
      Whether to attach the stack trace of the exception being handled. Defaults to
      `True`. Pass `False` where the exception is the expected answer rather than a
      defect: a socket that is not there because the service is not installed, a
      command that is absent on this platform. The admin gets the sentence that says
      so, and no Python stack trace for a situation nobody needs to debug.

    ### Returns
    - **None**: This function does not return; it always exits the script with `STATE_UNKNOWN`.

    ### Notes
    - If a traceback exists, it is included for debugging, with `<` and `>` replaced by `'`.
    - Sensitive information in the message is automatically redacted before printing.
    - If no traceback is present, only the optional message (if any) is printed.

    ### Example
    >>> cu('Unable to connect to server')

    >>> cu()

    >>> cu('strongSwan is not running here.', traceback=False)
    """
    has_traceback = traceback and sys.exc_info()[0] is not None
    tb = format_exc() if has_traceback else None

    if msg is not None:
        # Normalize line endings to LF (see oao); error output may also carry
        # CRLF, for example when a Windows command prints its error to stdout.
        msg = msg.replace('\r\n', '\n').replace('\r', '\n')
        msg = (
            txt.sanitize_sensitive_data(msg).strip().replace('<', "'").replace('>', "'")
        )
        print(msg, end='')
        print(
            ' (Traceback for debugging purposes attached)\n' if has_traceback else '\n'
        )

    if has_traceback:
        print(tb.replace('<', "'").replace('>', "'"))

    sys.exit(STATE_UNKNOWN)


def get_perfdata(label, value, uom=None, warn=None, crit=None, _min=None, _max=None):
    """
    Returns a Nagios performance data string in the format:
    `'label'=value[UOM];[warn];[crit];[min];[max]`

    ### Parameters
    - **label** (`str`): The name of the performance data label.
    - **value** (`int` or `float`): The measured value. `None` means "nothing to report",
      and yields an empty string rather than a metric.
    - **uom** (`str`, optional): The unit of measurement (e.g., 's', 'B', '%'). Defaults to None.
    - **warn** (`int` or `float`, optional): Warning threshold. Defaults to None.
    - **crit** (`int` or `float`, optional): Critical threshold. Defaults to None.
    - **_min** (`int` or `float`, optional): Minimum value. Defaults to None.
    - **_max** (`int` or `float`, optional): Maximum value. Defaults to None.

    ### Returns
    - **str**: A properly formatted Nagios performance data string, or an empty string if
      there is no value to report.

    ### Notes
    - A `value` of `None` returns an empty string. A source that did not report the reading
      hands `None` through, and interpolating that would emit the literal `'label'=None`,
      which is not a number: consumers that parse the perfdata line drop the whole line over
      it, not just the one broken metric. Callers therefore no longer have to guard every
      single call.

    ### Example
    >>> get_perfdata('load1', 0.42, '', 1.0, 5.0, 0, 10)
    "'load1'=0.42;1.0;5.0;0;10 "

    >>> get_perfdata('load1', None)
    ''
    """
    if value is None:
        return ''

    label = str(label).replace("'", '').replace('=', '_')
    msg = f"'{label}'={value}{uom or ''};"
    msg += f'{warn};' if warn is not None else ';'
    msg += f'{crit};' if crit is not None else ';'
    msg += f'{_min};' if _min is not None else ';'
    msg += f'{_max}' if _max is not None else ''
    return msg.rstrip(';') + ' '


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
    - **int**: `STATE_OK`, `STATE_WARN`, or `STATE_CRIT`. `STATE_UNKNOWN` for a
      threshold that does not parse, an unknown `_operator`, or a `value` that is not
      a number.

    ### Example
    >>> get_state(15, 10, 20, 'ge')
    1  # STATE_WARN

    >>> get_state(10, 10, 20, 'gt')
    0  # STATE_OK
    """
    # A value that is not a number is the same kind of unusable input as a threshold
    # that does not parse, and is answered the same way instead of raising. Float
    # comparison throughout, so a bound and a value are rounded alike.
    value = _value2float(value)
    if value is None:
        return STATE_UNKNOWN

    if _operator == 'range':
        if crit is not None:
            success, result = match_range(value, crit)
            if not success:
                return STATE_UNKNOWN
            if not result:
                return STATE_CRIT
        if warn is not None:
            success, result = match_range(value, warn)
            if not success:
                return STATE_UNKNOWN
            if not result:
                return STATE_WARN
        return STATE_OK

    op = _OPS.get(_operator)
    if op is None:
        return STATE_UNKNOWN

    if crit is not None and op(value, float(crit)):
        return STATE_CRIT
    if warn is not None and op(value, float(warn)):
        return STATE_WARN
    return STATE_OK


def _is_empty_cell(value):
    """Whether a rendered cell carries no information: empty, or one of the hyphen
    placeholders consumers print for "this object has no such field". A value that only
    starts with a hyphen, `-1` for instance, is a value and is not matched.
    """
    return str(value).strip().strip('-') == ''


def _escape_tag_start(text):
    """Replace a `<` that a web interface would read as the start of an HTML tag by
    `&lt;`. See `TAG_START` for which `<` that is.

    Both `oao()` and `get_table()` apply this. A table has to do it before it measures
    its columns: the replacement is three characters longer than what it replaces, so a
    cell escaped afterwards pushes the delimiters of its row out of line, and a value
    such as `<unknown>` bends the whole table. Escaping the cell first also leaves
    nothing for `oao()` to escape a second time.
    """
    return TAG_START.sub('&lt;', text)


def get_table(
    data,
    cols,
    header=None,
    strip=True,
    sort_by_key=None,
    sort_order_reverse=False,
    missing=None,
    hide_empty=False,
    max_rows=None,
    max_rows_label='row',
    max_rows_suffix='s',
):
    """
    Format a list of dictionaries into a simple ASCII table.

    Uses pure ASCII delimiters (`!`, `+`, `-`) instead of Unicode box-drawing characters
    (like `│`, `┼`, `─`) to guarantee correct rendering on any platform, locale, terminal,
    and transport layer regardless of encoding.

    Each dictionary must contain the specified columns (`cols`), unless `missing` states
    what to print for the ones it does not. Optionally supports a custom header, sorting by
    a given key, and stripping whitespace from values.

    ### Parameters
    - **data** (`list`): List of dictionaries representing the table rows.
    - **cols** (`list`): List of keys to display as table columns.
    - **header** (`list`, optional): List of custom column headers. Defaults to None.
    - **strip** (`bool`, optional): Whether to strip whitespace from values. Defaults to True.
    - **sort_by_key** (`str`, optional): Column key to sort the table by. Defaults to None.
    - **sort_order_reverse** (`bool`, optional): Sort descending if True. Defaults to False.
    - **missing** (`str`, optional):
      What to print in a cell whose key the row does not have. Defaults to `None`, which
      reports the missing column instead of printing the table at all.
    - **hide_empty** (`bool`, optional):
      Leave out every column that no row filled in, that is one whose cells are all empty
      or all a hyphen placeholder. Defaults to False.
    - **max_rows** (`int`, optional):
      Render at most this many data rows and state below the table how many were left out.
      Defaults to `None`, which renders every row.
    - **max_rows_label** (`str`, optional):
      What the rows left out by `max_rows` are called in that sentence, in the singular.
      It is pluralized as needed. Defaults to `'row'`.
    - **max_rows_suffix** (`str`, optional):
      How `max_rows_label` forms its plural, passed to `txt.pluralize()`, so an irregular
      noun can be spelled out as `'entr'` plus `'y,ies'`. Defaults to `'s'`.

    ### Returns
    - **str**: A string containing the formatted table.

    ### Notes
    - Without `missing`, a column no row carries is treated as a mistake in the calling
      code and reported as `Unknown column "..."`, which is what a mistyped column name
      deserves. That is the default because most consumers build their rows themselves and
      a silently empty column would hide the typo.
    - A consumer whose rows come from somewhere else, such as an API that only sends the
      fields it has something to say about, passes `missing='--'` instead. One optional
      field a firmware leaves out then costs that one cell rather than the whole table.
    - `hide_empty` is for the consumer whose column set is fixed but whose rows are not:
      a consumer listing several kinds of object prints the columns that apply to none of the
      objects it actually found as a wall of hyphens, pushing the text that matters off to
      the right. It is off by default, because a column that is empty today and filled
      tomorrow would otherwise make the table change shape between runs.
    - When `hide_empty` would leave nothing at all, every column is kept. A table of
      headers says more than a blank line.
    - `max_rows` is for the consumer whose row count grows with the very situation the
      table reports, where the interesting case is also the longest one: a table per
      affected object turns into thousands of lines exactly when something went wrong,
      and whatever stores or forwards that text carries all of them. The cap keeps the
      output readable and says how much it left out, so the number is never silently
      lost. It shapes the text alone: the caller counts, aggregates and reports on the
      full `data` it passed in, which the truncated table says nothing about.
    - Rows are cut after sorting, so `max_rows` together with `sort_by_key` keeps the
      rows that sort first rather than an arbitrary selection.
    - A cell carrying a `<` that a web interface would read as the start of an HTML tag,
      `<unknown>` for example, is escaped here rather than in `oao()`, so the column
      widths are measured on the text that is actually printed and the table keeps its
      shape. See `TAG_START`.
    - Column widths come from the rows that are actually printed. A long value in a row
      that was cut does not widen the table it no longer appears in.

    ### Example
    >>> data = [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]
    >>> cols = ['name', 'age']
    >>> print(get_table(data, cols))
    name  ! age
    ------+----
    Alice ! 30
    Bob   ! 25

    >>> print(get_table([{'name': 'Alice'}], ['name', 'age'], missing='--'))
    Alice ! --

    >>> data = [{'name': 'Alice', 'age': '-'}, {'name': 'Bob', 'age': '-'}]
    >>> print(get_table(data, ['name', 'age'], header=['Name', 'Age'], hide_empty=True))
    Name
    -----
    Alice
    Bob

    >>> data = [{'n': 'a'}, {'n': 'b'}, {'n': 'c'}]
    >>> print(get_table(data, ['n'], max_rows=1, max_rows_label='finding'))
    a
    ... and 2 more findings.
    """
    if not data:
        return ''
    data = data.copy()  # data has been passed by-reference - kick the reference

    if sort_by_key:
        data = sorted(
            data, key=operator.itemgetter(sort_by_key), reverse=sort_order_reverse
        )

    # Cut before anything is measured, so the rows that are not printed neither widen a
    # column nor keep a column alive that `hide_empty` would otherwise drop.
    left_out = 0
    if max_rows is not None and len(data) > max_rows:
        left_out = len(data) - max_rows
        data = data[:max_rows]
    if not data:
        # `max_rows=0` asked for the count alone. A header above nothing would be a table
        # promising rows that follow.
        return (
            f'... and {left_out} more '
            f'{txt.pluralize(max_rows_label, left_out, max_rows_suffix)}.\n'
        )

    if hide_empty:
        # Judged on the rows only, before the header joins them: the header text would
        # otherwise fill every column and nothing would ever be dropped.
        kept = [
            index
            for index, col in enumerate(cols)
            if any(not _is_empty_cell(row.get(col, missing or '')) for row in data)
        ]
        if kept:
            if header:
                header = [header[index] for index in kept]
            cols = [cols[index] for index in kept]

    if header:
        data.insert(0, dict(zip(cols, header)))

    # Process values and calculate column widths in a single pass
    processed_rows = []
    column_widths = {}

    for row in data:
        processed_row = {}
        for col in cols:
            if col not in row:
                if missing is None:
                    return f'Unknown column "{col}"'
                value = _escape_tag_start(missing)
                processed_row[col] = value
                column_widths[col] = max(column_widths.get(col, 0), len(value))
                continue
            value = str(row[col])
            if strip:
                value = value.strip()
            value = _escape_tag_start(value)
            processed_row[col] = value
            column_widths[col] = max(column_widths.get(col, 0), len(value))
        processed_rows.append(processed_row)

    if header:
        divider = {col: '-' * width for col, width in column_widths.items()}
        processed_rows.insert(1, divider)

    # Generate output lines
    lines = []
    for idx, row in enumerate(processed_rows):
        parts = [f'{row[col]:<{column_widths[col]}}' for col in column_widths]
        lines.append(('-+-' if header and idx == 1 else ' ! ').join(parts))

    if left_out:
        lines.append(
            f'... and {left_out} more '
            f'{txt.pluralize(max_rows_label, left_out, max_rows_suffix)}.'
        )

    return '\n'.join(lines) + '\n'


def get_worst(*states):
    """
    Returns the worst state among any number of input states, using the
    following priority: STATE_OK < STATE_UNKNOWN < STATE_WARNING < STATE_CRITICAL.
    Any non-OK state is prioritized over STATE_OK.

    Note that numerically the priority order does not match their integer
    values. Calling with no arguments returns `STATE_OK`.

    ### Parameters
    - ***states** (`int`): One or more states to compare.

    ### Returns
    - **int**: The worse state according to the priority order.

    ### Example
    >>> get_worst(STATE_OK, STATE_WARNING)
    STATE_WARNING

    >>> get_worst(STATE_UNKNOWN, STATE_CRITICAL)
    STATE_CRITICAL

    >>> get_worst(STATE_OK, STATE_WARNING, STATE_CRITICAL)
    STATE_CRITICAL
    """
    states = [int(s) for s in states]
    if STATE_CRIT in states:
        return STATE_CRIT
    if STATE_WARN in states:
        return STATE_WARN
    if STATE_UNKNOWN in states:
        return STATE_UNKNOWN
    return STATE_OK


def guess_type(v, consumer='python'):
    """
    Guess the type of a value (None, int, float, or string) for different types of consumers
    (e.g., Python, SQLite).

    For Python, it returns the actual value converted to its type (`int`, `float`, or `str`).
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
    if v is None:
        return None if consumer == 'python' else 'text'

    try:
        result = int(v)
        return result if consumer == 'python' else 'integer'
    except (ValueError, TypeError):
        try:
            result = float(v)
            return result if consumer == 'python' else 'real'
        except (ValueError, TypeError):
            return str(v) if consumer == 'python' else 'text'


def is_empty_list(lst):
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
    return all(not s.strip() for s in lst)


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
    ...     {'name': 'Tom', 'age': 10},
    ...     {'name': 'Mark', 'age': 5},
    ...     {'name': 'Pam', 'age': 7},
    ...     {'name': 'Dick', 'age': 12},
    ... ]
    >>> lookup_lod(haystack, 'name', 'Pam')
    (2, {'name': 'Pam', 'age': 7})

    >>> lookup_lod(haystack, 'name', 'Pamela')
    (-1, None)
    """
    for idx, item in enumerate(haystack):
        if isinstance(item, dict) and key in item and item[key] == needle:
            return idx, item
    return -1, None


# One bound of a range: an optional sign, digits with an optional decimal point, an
# optional exponent, and an optional percent sign.
_RANGE_ATOM = re.compile(r'^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?%?$')


def _parse_range_atom(atom, default):
    """Turns one bound of a range into a float, or raises `ValueError` if it is not a
    number. An empty bound is the omitted one and yields `default`.

    A trailing `%` is dropped: a percentage sign in a threshold repeats the unit of the
    value and carries nothing the comparison needs, so `90%:` means what `90:` means.
    Verified against monitoring-plugins 2.4.x, whose `lib/tests/test_utils.c` asserts
    the same for `1:12%`.

    Every bound is a float, never an int, because the reference implementation holds the
    whole range in C doubles and the value is a float here too. A bound kept as an exact
    Python int is compared exactly against a value that has already been rounded to a
    float, so `12345678901234567890` reads as greater than the very value it was written
    for and the caller alerts on it. Both sides have to be rounded the same way, which is
    what `lib/tests/test_utils.c` asserts for that bound.

    Deliberately stricter than the reference implementation, which reads a bound with
    `strtod()`: that takes the longest numeric prefix and silently answers 0 for a bound
    with no numeric prefix at all, so `1,5` becomes the threshold 1 and `abc` becomes 0.
    Guessing a number out of a typo gives an admin a threshold that alerts forever without
    saying why, so anything outside this grammar is refused and reported instead. The
    same refusal covers what Python would read but the range syntax does not define:
    `1_000`, `inf`, `nan`, `0x10`.
    """
    atom = atom.strip()
    if not atom:
        return default
    if not _RANGE_ATOM.match(atom):
        raise ValueError(f'{atom!r} is not a number')
    return float(atom.rstrip('%'))


def _value2float(value):
    """Reads the value of a threshold comparison as a `float`, or answers `None` when it
    is not a number the comparison can use.

    A value that is not numeric used to raise out of `match_range()` and reached the
    admin as a stack trace, the way a mistyped range once did. `None` raised as well,
    one type later, when it was compared against a bound.

    NaN is refused too, and it is the reason this is a single reader rather than a
    `try` around every conversion: every comparison against NaN is False, so a NaN
    value passed both bound checks and was reported as inside the range. A value the
    check could not read at all came out as OK.

    A trailing `%` is dropped, so a value of `90%` is compared like `90`, the way
    `_parse_range_atom()` reads a bound of `90%`.
    """
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode('utf-8')
        except UnicodeDecodeError:
            return None
    if isinstance(value, str):
        value = value.replace('%', '').strip()
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def _parse_range(spec_):
    """
    Inspired by
    https://github.com/mpounsett/nagiosplugin/blob/master/nagiosplugin/range.py

    +--------+-------------------+-------------------+----------------+
    | -w, -c | OK if result is   | WARN/CRIT if      | returns        |
    +--------+-------------------+-------------------+----------------+
    | 10     | in (0..10)        | not in (0..10)    | (0, 10, False) |
    +--------+-------------------+-------------------+----------------+
    | -10:0  | in (-10..0)       | not in (-10..0)   | (-10, 0, False)|
    +--------+-------------------+-------------------+----------------+
    | 10:    | in (10..inf)      | not in (10..inf)  | (10, inf, F)   |
    +--------+-------------------+-------------------+----------------+
    | :      | in (0..inf)       | not in (0..inf)   | (0, inf, False)|
    +--------+-------------------+-------------------+----------------+
    | ~:10   | in (-inf..10)     | not in (-inf..10) | (-inf, 10, F)  |
    +--------+-------------------+-------------------+----------------+
    | 10:20  | in (10..20)       | not in (10..20)   | (10, 20, False)|
    +--------+-------------------+-------------------+----------------+
    | @10:20 | not in (10..20)   | in 10..20         | (10, 20, True) |
    +--------+-------------------+-------------------+----------------+
    | @~:20  | not in (-inf..20) | in (-inf..20)     | (-inf, 20, T)  |
    +--------+-------------------+-------------------+----------------+
    | @      | not in (0..inf)   | in (0..inf)       | (0, inf, True) |
    +--------+-------------------+-------------------+----------------+
    """
    if spec_ is None or str(spec_).lower() == 'none':
        return True, None

    if not isinstance(spec_, str):
        spec_ = str(spec_)

    invert = spec_.startswith('@')
    if invert:
        spec_ = spec_[1:]

    if ':' in spec_:
        try:
            start, end = spec_.split(':')
        except ValueError:
            return False, 'Not using range definition correctly'
    else:
        start, end = '', spec_

    try:
        start = float('-inf') if start.strip() == '~' else _parse_range_atom(start, 0)
        end = _parse_range_atom(end, float('inf'))
    except ValueError:
        # An unparseable bound is reported the way an unparseable range has always been
        # reported, as a message the caller turns into UNKNOWN. Letting the `ValueError`
        # escape instead hands the admin a Python traceback in place of the threshold
        # they mistyped.
        return False, 'Range format incorrect'

    if start > end:
        return (
            False,
            f'Start {start:g} must not be greater than end {end:g}',
        )
    return True, (start, end, invert)


def match_range(value, spec):
    """
    Decides if `value` is inside or outside the Nagios threshold
    specification.

    ### Parameters
    - **value** (`int` or `float` or `str`): The numeric value to check.
    - **spec** (`str`): The Nagios range specification string.

    ### Returns
    - **tuple** of (`bool`, `bool` or `str`):
      - On a `spec` that parses: (True, matched), where `matched` is True if `value` is
        inside the bounds for a non-inverted `spec`, or outside the bounds for an
        inverted one. Callers alert when `matched` is False.
      - On a `spec` that does not parse: (False, reason). Callers turn this into UNKNOWN.
      - On a `value` that is not a number: (False, reason), the same way.

    ### Notes
    - Both bounds are inclusive.
    - A trailing `%` on a bound is ignored, so `90:` and `90%:` mean the same.

    ### Example
    >>> match_range(15, '10')  # outside 0..10
    (True, False)

    >>> match_range(5, '10')  # inside 0..10
    (True, True)

    >>> match_range(15, '-10')
    (False, 'Start 0 must not be greater than end -10')

    >>> match_range(15, '1,5')
    (False, 'Range format incorrect')

    >>> match_range('11.abc', '10')
    (False, "'11.abc' is not a number")

    >>> match_range(15, '10:')  # inside 10..inf
    (True, True)

    >>> match_range(15, ':')  # inside 0..inf
    (True, True)

    >>> match_range(15, '~:10')  # outside -inf..10
    (True, False)

    >>> match_range(15, '10:20')  # inside 10..20
    (True, True)

    >>> match_range(15, '@10:20')  # inside 10..20, and the range is inverted
    (True, False)

    >>> match_range(15, '@~:20')  # inside -inf..20, and the range is inverted
    (True, False)

    >>> match_range(15, '@')  # inside 0..inf, and the range is inverted
    (True, False)
    """
    if isinstance(spec, str):
        spec = spec.lstrip('\\')

    if spec is None or str(spec).lower() == 'none':
        return True, True

    success, result = _parse_range(spec)
    if not success:
        return success, result

    start, end, invert = result

    numeric_value = _value2float(value)
    if numeric_value is None:
        return False, f'{value!r} is not a number'
    value = numeric_value

    if value < start or value > end:
        return True, bool(invert)
    return True, not invert


def oao(msg, state=STATE_OK, perfdata='', always_ok=False, no_perfdata=False):
    """
    Over and Out (OaO)

    Print a sanitized result message with optional performance data and exit the script.

    This function formats and prints the message, appends performance data if provided,
    sanitizes sensitive information, replaces reserved `|` characters, and exits with the
    specified state code. Optionally, it can always exit with `STATE_OK` regardless of the given
    state.

    ### Parameters
    - **msg** (`str`): The message to print. Will be stripped, sanitized, and processed.
    - **state** (`int`, optional): The exit code to use. Defaults to `STATE_OK`.
    - **perfdata** (`str`, optional): Performance data to append after a `|` separator.
      Defaults to an empty string (no performance data).
    - **always_ok** (`bool`, optional): If `True`, forces the exit code to `STATE_OK` regardless
      of the specified `state`. Defaults to `False`.
    - **no_perfdata** (`bool`, optional): If `True`, suppresses the performance data section
      entirely, printing only the message and preserving the exit code. Defaults to `False`.

    ### Returns
    - **None**: This function does not return; it terminates the script via `sys.exit()`.

    ### Notes
    - Any `|` characters inside the message are replaced with `!`, the character being
      reserved as the performance data separator of the Monitoring Plugins output format.
    - A `<` that would open an HTML tag is replaced by `&lt;`, so a web interface cannot
      mistake the output for markup. Everything else is left as it is: `<= 10`,
      `< 5.3.2` and `echo 1 > /proc/sys/...` reach the terminal exactly as written, and
      `&` and `>` are never touched. A web interface escapes those itself when it renders
      the output as plain text, which is the path this keeps the output on. Rendering it
      as HTML instead would drop the monospace formatting that tables depend on.
    - Sensitive information like passwords, tokens, and keys is automatically redacted.
    - `perfdata`, if provided, must follow the Monitoring Plugins specification for
      performance metrics.
    - `no_perfdata` only affects what is printed; the message and the exit code are unchanged, so
      alerting keeps working while trending data is dropped from the output.

    ### Example
    >>> oao('Service is healthy', STATE_OK, 'load=0.12;1.00;5.00', always_ok=False)
    Service is healthy|load=0.12;1.00;5.00
    (and exits with code 0)

    >>> oao('password=secret123 found!', STATE_CRITICAL)
    password=****** found!
    (and exits with code 2)

    """
    # Normalize line endings to LF. Output captured on Windows (or read from a
    # file or HTTP response) can carry CRLF or stray CR, which a web UI showing
    # the output with `white-space: pre-wrap` would render as an extra line break.
    msg = msg.replace('\r\n', '\n').replace('\r', '\n')
    msg = _escape_tag_start(txt.sanitize_sensitive_data(msg.strip())).replace('|', '!')
    if always_ok and msg:
        # Instead of splitlines(), we just split('\n', 1), so only first line is touched.
        parts = msg.split('\n', 1)
        parts[0] += ' (always ok)'
        msg = '\n'.join(parts)
    print(f'{msg}|{perfdata.strip()}' if perfdata and not no_perfdata else msg)
    sys.exit(STATE_OK if always_ok else state)


def _bound2txt(bound, fmt):
    """Formats one bound of a range for a human reader.

    Infinity keeps its name whatever `fmt` does with it, an integral bound loses the
    `.0` that every bound carries as a float, and a `fmt` that answers with nothing
    falls back to the plain number instead of dropping the bound out of the sentence.
    """
    if bound == float('inf'):
        return 'inf'
    if bound == float('-inf'):
        return '-inf'
    plain = str(int(bound)) if float(bound).is_integer() else str(bound)
    if fmt is None:
        return plain
    formatted = fmt(bound)
    return str(formatted) if formatted else plain


def range2txt(spec, value=None, value_name='value', fmt=None, view='alert'):
    """
    Puts a Nagios threshold range, and optionally the value compared against it, into
    the wording of THRESHOLDS.md, so a message can say what was compared instead of
    repeating the range syntax at the admin.

    What is described is the condition, not where the value lies: by default the
    `WARN/CRIT if` column of THRESHOLDS.md, so a consumer that alerts can name what it
    alerted on. `view='ok'` gives the `OK if result is` column instead.

    ### Parameters
    - **spec** (`str`): The Nagios range specification string, as `match_range()` takes
      it. Note the argument order: the range comes first here, the value is optional.
    - **value** (`int` or `float` or `str`, optional): The value that was compared.
      Without it, only the condition is returned.
    - **value_name** (`str`, optional): What to call the value in the text. Defaults to
      `value`.
    - **fmt** (`callable`, optional): Turns a number into its human-readable form, for
      example `human.seconds2human` or `human.bytes2human`. Without it, the numbers are
      printed as they are.
    - **view** (`str`, optional): `alert` for the condition that alerts, `ok` for the
      condition that does not. Defaults to `alert`.

    ### Returns
    - **tuple** of (`bool`, `str`):
      - On success: (True, text), where `text` is `not in (start..end)`, or
        `name=value not in (start..end)` when a `value` was given. Empty for a `spec`
        of `None`, which is a threshold that was never set.
      - On a `spec` that does not parse, a `value` that is not a number, or an unknown
        `view`: (False, reason). Callers turn this into UNKNOWN, the same way they do
        for `match_range()`.

    ### Notes
    - Both bounds are inclusive, and a trailing `%` on a bound or on the value is
      dropped, the way `match_range()` reads them.
    - The state marker is left to the caller, who can pick its wording with
      `state2str()`: `f'{text}{state2str(state, prefix=" ")}'`.
    - An inverted range alerts inside its bounds, so `10:20` and `@10:20` describe
      opposite conditions and never read alike.

    ### Example
    >>> range2txt('10')
    (True, 'not in (0..10)')

    >>> range2txt('10', view='ok')
    (True, 'in (0..10)')

    >>> range2txt('~:10')
    (True, 'not in (-inf..10)')

    >>> range2txt('10:20', value=15, value_name='age')
    (True, 'age=15 not in (10..20)')

    >>> range2txt('@10:20', value=15, value_name='age')
    (True, 'age=15 in (10..20)')

    >>> range2txt('172800', value=259200, value_name='age', fmt=human.seconds2human)
    (True, 'age=3D not in (0s..2D)')

    >>> range2txt('10:20', value='11.abc')
    (False, "'11.abc' is not a number")

    >>> range2txt('1,5')
    (False, 'Range format incorrect')

    >>> range2txt(None, value=11, value_name='age')
    (True, '')
    """
    if view not in ('alert', 'ok'):
        return False, f'Unknown view {view!r}'

    if spec is None or str(spec).lower() == 'none':
        return True, ''

    success, result = _parse_range(spec)
    if not success:
        return False, result

    start, end, invert = result
    rng = f'({_bound2txt(start, fmt)}..{_bound2txt(end, fmt)})'
    # THRESHOLDS.md tabulates both columns: a plain range alerts outside its bounds,
    # an inverted one inside them, and the OK column is the other one. Rendering the
    # condition rather than where the value happens to lie is what keeps `10:20` and
    # `@10:20` apart, which the bounds alone cannot do.
    alerts_inside = invert
    if view == 'alert':
        condition = 'in' if alerts_inside else 'not in'
    else:
        condition = 'not in' if alerts_inside else 'in'

    if value is None:
        return True, f'{condition} {rng}'

    numeric_value = _value2float(value)
    if numeric_value is None:
        return False, f'{value!r} is not a number'

    return True, f'{value_name}={_bound2txt(numeric_value, fmt)} {condition} {rng}'


# One duration token such as `3d`, `12h`, `2W` or `1M`. The unit letters are the ones
# `human.human2seconds()` knows; listing fewer here would let a valid duration fall
# through and be read as a threshold range instead, which is silently wrong rather
# than an error.
_DURATION_ATOM = re.compile(r'^\d+(\.\d+)?[YMWwDdhms]$')


def resolve_time_threshold(threshold, total_seconds):
    """
    Normalize a "time left" threshold into a Nagios range expressed in days.

    A consumer that alerts on how much of a lifetime is left - a certificate, a
    licence, a token, a support contract - wants to let the operator say that in
    whichever way suits the subject: an absolute number of days, a share of the total
    lifetime, or a duration. This turns all three into the one form `get_state()`
    understands, so the comparison and the performance data stay in days throughout.

    Accepted forms:

    - empty: no threshold, passes through as empty
    - `N%`: N percent of `total_seconds`, converted to days
    - a single duration token (`3d`, `12h`, `2W`, `1M`): that duration in days
    - anything else: already a Nagios range in days (`14:`, `@5:10`), passed through

    A percentage and a duration both become a `<n>:` range, which alerts when *fewer*
    than `n` days are left. That is the direction "time left" runs in, and it is why
    the two shorthands cannot express the other one; an operator who needs that writes
    the range out.

    ### Parameters
    - **threshold** (`str`): The threshold as the operator wrote it.
    - **total_seconds** (`float`): The whole lifetime the percentage form refers to.
      Only read for that form.

    ### Returns
    - **str**: A Nagios range in days, ready for `get_state(..., _operator='range')`.

    ### Notes
    - A percentage that does not parse as a number is passed through unchanged, so it
      reaches the range parser and is reported there rather than being read as zero.

    ### Example
    >>> resolve_time_threshold('14:', 7776000)
    '14:'

    >>> resolve_time_threshold('10%', 7776000)
    '9:'

    >>> resolve_time_threshold('12h', 7776000)
    '0.5:'
    """
    threshold = str(threshold).strip()
    if not threshold:
        return ''
    if threshold.endswith('%'):
        try:
            pct = float(threshold[:-1])
        except ValueError:
            return threshold
        # `:g` drops trailing zeros, so 25% of 60 days reads "15:", not "15.000000:"
        return f'{pct / 100.0 * total_seconds / 86400.0:g}:'
    if _DURATION_ATOM.match(threshold):
        return f'{human.human2seconds(threshold) / 86400.0:g}:'
    return threshold


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
    try:
        return float(value)
    except (ValueError, TypeError):
        try:
            return str(value)
        except (ValueError, TypeError):
            return value


def sort(array, reverse=True, sort_by_key=False):
    """
    Sort a dict, list, or tuple.

    - If dict: sorts by values (default) or keys (if sort_by_key=True).
    - If list or tuple: sorts the elements.
    - Other types: returned unchanged.

    When a dictionary is provided, this function returns a list of (key, value)
    tuples sorted based on the specified criteria:
      - If `sort_by_key` is False (default), the dictionary items are sorted by their values.
      - If `sort_by_key` is True, the items are sorted by their keys (compared case-insensitively).

    The sort order is descending by default (`reverse=True`).
    If the input is not a dictionary, the original input is returned unmodified.

    ### Parameters
    - **array** (`dict` or `any`): The dictionary to be sorted. If not a dictionary, the input is
      returned as is.
    - **reverse** (`bool`, optional): If True, sort in descending order; if False, ascending.
      Defaults to True.
    - **sort_by_key** (`bool`, optional): If True, sort by dictionary keys; if False, by values.
      Defaults to False.

    ### Returns
    - **list** or **any**: A list of sorted (key, value) tuples if a dictionary is provided,
      otherwise the original input.

    ### Example
    >>> sort({'a': 2, 'b': 1})
    [('a', 2), ('b', 1)]

    >>> sort({'a': 2, 'b': 1}, reverse=False)
    [('b', 1), ('a', 2)]

    >>> sort({'a': 2, 'B': 1}, sort_by_key=True)
    [('a', 2), ('B', 1)]
    """
    if isinstance(array, dict):
        keyfunc = (lambda x: str(x[0]).lower()) if sort_by_key else (lambda x: x[1])
        return sorted(array.items(), key=keyfunc, reverse=reverse)

    if isinstance(array, (list, tuple)):
        return sorted(array, reverse=reverse)

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
    text = _STATE_NAMES.get(state, str(state))

    if state == STATE_OK and empty_ok:
        return ''
    return f'{prefix}{text}{suffix}'


def str2bool(s):
    """
    Return True or False depending on the given string.

    ### Parameters
    - **s** (`str`): The input string to evaluate.

    ### Returns
    - **bool**: True if the string is not empty and not equal to "false" (case-insensitive),
      otherwise False.

    ### Example
    >>> str2bool('')
    False

    >>> str2bool('false')
    False

    >>> str2bool('FalSE')
    False

    >>> str2bool('true')
    True

    >>> str2bool('Linuxfabrik')
    True

    >>> str2bool('0')
    True

    >>> str2bool('1')
    True
    """
    return bool(s) and s.lower() != 'false'


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
    lookup = {
        'ok': STATE_OK,
        'warn': STATE_WARN,
        'crit': STATE_CRIT,
        'unkn': STATE_UNKNOWN,
    }
    return lookup.get(str(string).lower()[:4], STATE_UNKNOWN if ignore_error else None)


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
    return sum_lod([dict1, dict2])


def sum_lod(mylist):
    """
    Sum up a list of (simple 1-dimensional) dictionary items.

    Only numeric values are considered for summation; non-numeric values are ignored.

    ### Parameters
    - **mylist** (`list`): A list of dictionaries to sum.

    ### Returns
    - **dict**: A dictionary with summed numeric values by key.

    ### Example
    >>> sum_lod(
    ...     [
    ...         {'in': 100, 'out': 10},
    ...         {'in': 50, 'out': 20},
    ...         {'error': 5, 'uuid': '1234-xyz'},
    ...     ]
    ... )
    {'in': 150, 'out': 30, 'error': 5}
    """
    total = {}

    for d in mylist:
        for key, value in d.items():
            if is_numeric(value):
                total[key] = total.get(key, 0) + value

    return total


def verbose(enabled, msg):
    """
    Print a progress message, but only when verbose output is switched on.

    Long-running consumers (a scan over a subnet, an external tool that runs for
    minutes) otherwise give no sign of life while they work. Guarding every such message
    with an `if` at the call site is what this replaces, so the condition and the
    destination are decided in one place.

    Output goes to STDOUT, never to STDERR, because the monitoring protocol only
    captures STDOUT. The message therefore becomes part of the result and is meant
    for interactive debugging, not for a scheduled run.

    The message is redacted the same way `coe()`, `cu()` and `oao()` redact theirs.
    Progress messages routinely carry the command that was run or the error a helper
    returned, and either can contain a credential the caller never meant to print.

    ### Parameters
    - **enabled** (`bool`): Whether verbose output is switched on. Pass the value of the
      consumer's own verbose switch.
    - **msg** (`str`): The message to print.

    ### Returns
    - **None**

    ### Example
    >>> verbose(args.VERBOSE, f'Scanning {url}...')
    """
    if enabled:
        print(txt.sanitize_sensitive_data(msg))
