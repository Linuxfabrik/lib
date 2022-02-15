#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Provides very common every-day functions.

The functions "to_text()" and "to_bytes()" are copied from 
/usr/lib/python3.10/site-packages/ansible/module_utils/_text.py (BSD license).
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2022021501'

import codecs
try:
    codecs.lookup_error('surrogateescape')
    HAS_SURROGATEESCAPE = True
except LookupError:
    HAS_SURROGATEESCAPE = False
import collections
import datetime
import hashlib
import math
import numbers
import operator
import os
import re
import shlex
import subprocess
import sys
import time

from traceback import format_exc # pylint: disable=C0413

from .globals3 import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN


WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")

string_types = str
integer_types = int
class_types = type
text_type = str
binary_type = bytes
_COMPOSED_ERROR_HANDLERS = frozenset((None, 'surrogate_or_replace',
                                      'surrogate_or_strict',
                                      'surrogate_then_replace'))


def bits2human(n, format="%(value).1f%(symbol)s"):
    """Converts n bits to a human readable format.

    >>> bits2human(8191)
    '1023.9B'
    >>> bits2human(8192)
    '1.0KiB'
    """
    symbols = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    prefix = {}
    prefix['B'] = 8
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1024**(i + 1) * 8
    for symbol in reversed(symbols):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)


def bps2human(n, format="%(value).1f%(symbol)s"):
    """Converts n bits per scond to a human readable format.

    >>> bps2human(72000000)
    '72Mbps'
    """
    symbols = ('bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps', 'Pbps', 'Ebps', 'Zbps', 'Ybps')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1000**(i + 1)
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)


def bytes2human(n, format="%(value).1f%(symbol)s"):
    """Converts n bytes to a human readable format.

    >>> bytes2human(1023)
    '1023.0B'
    >>> bytes2human(1024)
    '1.0KiB'

    https://github.com/giampaolo/psutil/blob/master/psutil/_common.py
    """
    symbols = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        # Returns 1 with the bits shifted to the left by (i + 1)*10 places
        # (and new bits on the right-hand-side are zeros). This is the same
        # as multiplying x by 2**y.
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)


def coe(result, state=STATE_UNKNOWN):
    """Continue or Exit (CoE)

    This is useful if calling complex library functions in your checks
    `main()` function. Don't use this in functions.

    If a more complex library function, for example `lib.url3.fetch()` fails, it
    returns `(False, 'the reason why I failed')`, otherwise `(True,
    'this is my result'). This forces you to do some error handling.
    To keep things simple, use `result = lib.base3.coe(lib.url.fetch(...))`.
    If `fetch()` fails, your plugin will exit with STATE_UNKNOWN (default) and
    print the original error message. Otherwise your script just goes on.

    The use case in `main()` - without `coe`:

    >>> success, html = lib.url3.fetch(URL)
    >>> if not success:
    >>>     print(html)             # contains the error message here
    >>>>    exit(STATE_UNKNOWN)

    Or simply:

    >>> html = lib.base3.coe(lib.url.fetch(URL))

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


def cu():
    """See you (cu)

    Prints a Stacktrace (replacing "<" and ">" to be printable in Web-GUIs), and exits with
    STATE_UNKNOWN.
    """
    print(format_exc().replace("<", "'").replace(">", "'"))
    sys.exit(STATE_UNKNOWN)


def epoch2iso(timestamp):
    """Returns the ISO representaton of a UNIX timestamp (epoch).

    >>> epoch2iso(1620459129)
    '2021-05-08 09:32:09'
    """
    timestamp = float(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


def extract_str(s, from_txt, to_txt, include_fromto=False, be_tolerant=True):
    """Extracts text between `from_txt` to `to_txt`.
    If `include_fromto` is set to False (default), text is returned without both search terms,
    otherwise `from_txt` and `to_txt` are included.
    If `from_txt` is not found, always an empty string is returned.
    If `to_txt` is not found and `be_tolerant` is set to True (default), text is returned from
    `from_txt` til the end of input text. Otherwise an empty text is returned.

    >>> extract_text('abcde', 'x', 'y')
    ''
    >>> extract_text('abcde', 'b', 'x')
    'cde'
    >>> extract_text('abcde', 'b', 'x', include_fromto=True)
    'bcde'
    >>> extract_text('abcde', 'b', 'x', include_fromto=True, be_tolerant=False)
    ''
    >>> extract_text('abcde', 'b', 'd')
    'c'
    >>> extract_text('abcde', 'b', 'd', include_fromto=True)
    'bcd'
    """
    pos1 = s.find(from_txt)
    if pos1 == -1:
        # nothing found
        return ''
    pos2 = s.find(to_txt, pos1+len(from_txt))
    # to_txt not found:
    if pos2 == -1 and be_tolerant and not include_fromto:
        return s[pos1+len(from_txt):]
    if pos2 == -1 and be_tolerant and include_fromto:
        return s[pos1:]
    if pos2 == -1 and not be_tolerant:
        return ''
    # from_txt and to_txt found:
    if not include_fromto:
        return s[pos1+len(from_txt):pos2-len(to_txt)+ 1]
    return s[pos1:pos2+len(to_txt)]


def filter_mltext(input, ignore):
    filtered_input = ''
    for line in input.splitlines():
        if not any(i_line in line for i_line in ignore):
            filtered_input += line + '\n'

    return filtered_input


def filter_str(s, charclass='a-zA-Z0-9_'):
    """Stripping everything except alphanumeric chars and '_' from a string -
    chars that are allowed everywhere in variables, database table or index names, etc.

    >>> filter_str('user@example.ch')
    'userexamplech'
    """
    regex = '[^{}]'.format(charclass)
    return re.sub(regex, "", s)


def get_command_output(cmd, regex=None):
    """Runs a shell command and returns its output. Optionally, applies a regex and just
    returns the first matching group. If the command is not found, an empty string is returned.

    >>> get_command_output('nano --version')
    GNU nano, version 5.3
     (C) 1999-2011, 2013-2020 Free Software Foundation, Inc.
     (C) 2014-2020 the contributors to nano
     Compiled options: --enable-utf8
    >>> get_command_output('nano --version', regex=r'version (.*)\n')
    5.3
    """
    success, result = shell_exec(cmd)
    if not success:
        return ''
    stdout, stderr, retc = result
    if stdout == '' and stderr != '':
        # https://stackoverflow.com/questions/26028416/why-does-python-print-version-info-to-stderr
        # https://stackoverflow.com/questions/13483443/why-does-java-version-go-to-stderr]
        stdout = stderr
    stdout = stdout.strip()
    if regex:
        # extract something special from output
        try:
            stdout = re.search(regex, stdout)
            return stdout.group(1).strip()
        except:
            return ''
    else:
        return stdout.strip()


def get_owner(file):
    """Returns the user ID of the owner of a file (for example "0" for "root").
    Returns -1 on failure.
    """
    try:
        return os.stat(file).st_uid
    except:
        return -1


def get_perfdata(label, value, uom, warn, crit, min, max):
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
    if min is not None:
        msg += str(min)
    msg += ';'
    if max is not None:
        msg += str(max)
    msg += ' '
    return msg


def get_state(value, warn, crit, operator='ge'):
    """Returns the STATE by comparing `value` to the given thresholds using
    a comparison `operator`. `warn` and `crit` threshold may also be `None`.

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
    operator : string
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
    if operator == 'ge':
        if crit is not None:
            if value >= float(crit):
                return STATE_CRIT
        if warn is not None:
            if value >= float(warn):
                return STATE_WARN
        return STATE_OK

    if operator == 'gt':
        if crit is not None:
            if value > float(crit):
                return STATE_CRIT
        if warn is not None:
            if value > float(warn):
                return STATE_WARN
        return STATE_OK

    if operator == 'le':
        if crit is not None:
            if value <= float(crit):
                return STATE_CRIT
        if warn is not None:
            if value <= float(warn):
                return STATE_WARN
        return STATE_OK

    if operator == 'lt':
        if crit is not None:
            if value < float(crit):
                return STATE_CRIT
        if warn is not None:
            if value < float(warn):
                return STATE_WARN
        return STATE_OK

    if operator == 'eq':
        if crit is not None:
            if value == float(crit):
                return STATE_CRIT
        if warn is not None:
            if value == float(warn):
                return STATE_WARN
        return STATE_OK

    if operator == 'ne':
        if crit is not None:
            if value != float(crit):
                return STATE_CRIT
        if warn is not None:
            if value != float(warn):
                return STATE_WARN
        return STATE_OK

    if operator == 'range':
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
    if STATE_CRIT in [state1, state2]:
        return STATE_CRIT
    if STATE_WARN in [state1, state2]:
        return STATE_WARN
    if STATE_UNKNOWN in [state1, state2]:
        return STATE_UNKNOWN
    return STATE_OK


def guess_type(v, consumer='python'):
    """Guess the type of a value (None, int, float or string) for different types of consumers (Python, SQLite etc.).
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
    >>> value_type = lib.base3.guess_type(value)
    >>> if isinstance(value_type, int) or isinstance(value_type, float):
    >>>     ...
    """
    if consumer == 'python':
        if v is None:
            return None
        else:
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
        else:
            try:
                int(v)
                return 'integer'
            except ValueError:
                try:
                    float(v)
                    return 'real'
                except ValueError:
                    return 'text'


def human2bytes(string, binary=True):
    """Converts a string such as '3.072GiB' to 3298534883 bytes. If "binary" is set to True
    (default due to Microsoft), it will use powers of 1024, otherwise powers of 1000 (decimal).
    Returns 0 on failure.
    """
    try:
        string = string.lower()
        if 'kib' in string:
            return int(float(string.replace('kib', '').strip()) * 1024)
        if 'kb' in string:
            if binary:
                return int(float(string.replace('kb', '').strip()) * 1024)
            else:
                return int(float(string.replace('kb', '').strip()) * 1000)
        if 'mib' in string:
            return int(float(string.replace('mib', '').strip()) * 1024 * 1024)
        if 'mb' in string:
            if binary:
                return int(float(string.replace('mb', '').strip()) * 1024 * 1024)
            else:
                return int(float(string.replace('mb', '').strip()) * 1000 * 1000)
        if 'gib' in string:
            return int(float(string.replace('gib', '').strip()) * 1024 * 1024 * 1024)
        if 'gb' in string:
            if binary:
                return int(float(string.replace('gb', '').strip()) * 1024 * 1024 * 1024)
            else:
                return int(float(string.replace('gb', '').strip()) * 1000 * 1000 * 1000)
        if 'tib' in string:
            return int(float(string.replace('tib', '').strip()) * 1024 * 1024 * 1024 * 1024)
        if 'tb' in string:
            if binary:
                return int(float(string.replace('tb', '').strip()) * 1024 * 1024 * 1024 * 1024)
            else:
                return int(float(string.replace('tb', '').strip()) * 1000 * 1000 * 1000 * 1000)
        if 'pib' in string:
            return int(float(string.replace('pib', '').strip()) * 1024 * 1024 * 1024 * 1024 * 1024)
        if 'pb' in string:
            if binary:
                return int(float(string.replace('pb', '').strip()) * 1024 * 1024 * 1024 * 1024 * 1024)
            else:
                return int(float(string.replace('pb', '').strip()) * 1000 * 1000 * 1000 * 1000 * 1000)
        if 'b' in string:
            return int(float(string.replace('b', '').strip()))
        return 0
    except:
        return 0


def is_empty_list(l):
    """Check if a list only contains either empty elements or whitespace
    """
    return all('' == s or s.isspace() for s in l)


def is_numeric(value):
    """Return True if value is really numeric (int, float, whatever).

    >>> is_numeric(+53.4)
    True
    >>> is_numeric('53.4')
    False
    """
    return isinstance(value, numbers.Number)


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
    if isinstance(value, str) or isinstance(value, bytes):
        value = float(value.replace('%', ''))
    if value < start:
        return (True, False ^ invert)
    if value > end:
        return (True, False ^ invert)
    return (True, True ^ invert)


def sha1sum(string):
    return hashlib.sha1(string.encode('utf-8')).hexdigest()


def mltext2array(input, skip_header=False, sort_key=-1):
    input = input.strip(' \t\n\r').split('\n')
    lines = []
    if skip_header:
        del input[0]
    for row in input:
        lines.append(row.split())
    if sort_key != -1:
        lines = sorted(lines, key=operator.itemgetter(sort_key))
    return lines


def now(as_type=''):
    """Returns the current date and time as UNIX time in seconds (default), or
    as a datetime object.

    lib.base3.now()
    >>> 1586422786

    lib.base3.now(as_type='epoch')
    >>> 1586422786

    lib.base3.now(as_type='datetime')
    >>> datetime.datetime(2020, 4, 9, 11, 1, 41, 228752)

    lib.base3.now(as_type='iso')
    >>> '2020-04-09 11:31:24'
    """
    if as_type == 'datetime':
        return datetime.datetime.now()
    if as_type == 'iso':
        return time.strftime("%Y-%m-%d %H:%M:%S")
    return int(time.time())


def number2human(n):
    """
    >>> number2human(123456.8)
    '123K'
    >>> number2human(123456789.0)
    '123M'
    >>> number2human(9223372036854775808)
    '9.2E'
    """
    # according to the SI Symbols at
    # https://en.wikipedia.org/w/index.php?title=Names_of_large_numbers&section=5#Extensions_of_the_standard_dictionary_numbers
    millnames = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
    try:
        n = float(n)
    except:
        return n
    millidx = max(0, min(len(millnames) - 1,
                         int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))
    return '{:.1f}{}'.format(n / 10**(3 * millidx), millnames[millidx])


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
        sys.exit(0)
    sys.exit(state)


def pluralize(noun, value, suffix='s'):
    """Returns a plural suffix if the value is not 1. By default, 's' is used as
    the suffix.

    >>> pluralize('vote', 0)
    'votes'
    >>> pluralize('vote', 1)
    'vote'
    >>> pluralize('vote', 2)
    'votes'

    If an argument is provided, that string is used instead:

    >>> pluralize('class', 0, 'es')
    'classes'
    >>> pluralize('class', 1, 'es')
    'class'
    >>> pluralize('class', 2, 'es')
    'classes'

    If the provided argument contains a comma, the text before the comma is used
    for the singular case and the text after the comma is used for the plural
    case:

    >>> pluralize('cand', 0, 'y,ies)
    'candies'
    >>> pluralize('cand', 1, 'y,ies)
    'candy'
    >>> pluralize('cand', 2, 'y,ies)
    'candies'

    >>> pluralize('', 1, 'is,are')
    'is'
    >>> pluralize('', 2, 'is,are')
    'are'

    From https://kite.com/python/docs/django.template.defaultfilters.pluralize
    """
    if ',' in suffix:
        singular, plural = suffix.split(',')
    else:
        singular, plural = '', suffix
    if int(value) == 1:
        return noun + singular
    return noun + plural


def seconds2human(seconds, keep_short=True, full_name=False):
    """Returns a human readable time range string for a number of seconds.

    >>> lib.base3.seconds2human(0.125)
    '0.12s'
    >>> lib.base3.seconds2human(1)
    '1s'
    >>> lib.base3.seconds2human(59)
    '59s'
    >>> lib.base3.seconds2human(60)
    '1m'
    >>> lib.base3.seconds2human(61)
    '1m 1s'
    >>> lib.base3.seconds2human(1387775)
    '2W 2D'
    >>> lib.base3.seconds2human('1387775')
    '2W 2D'
    >>> lib.base3.seconds2human('1387775', full_name=True)
    '2weeks 2days'
    >>> lib.base3.seconds2human(1387775, keep_short=False, full_name=True)
    '2weeks 2days 1hour 29minutes 35seconds'
    """
    seconds = float(seconds)
    if seconds < 1:
        return '{:.2f}s'.format(seconds)

    if full_name:
        intervals = (
            ('years', 60*60*24*365),
            ('months', 60*60*24*30),
            ('weeks', 60*60*24*7),
            ('days', 60*60*24),
            ('hours', 60*60),
            ('minutes', 60),
            ('seconds', 1),
        )
    else:
        intervals = (
            ('Y', 60*60*24*365),
            ('M', 60*60*24*30),
            ('W', 60*60*24*7),
            ('D', 60*60*24),
            ('h', 60*60),
            ('m', 60),
            ('s', 1),
        )

    result = []
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if full_name and value == 1:
                name = name.rstrip('s') # "days" becomes "day"
            result.append('{:.0f}{}'.format(value, name))

    if len(result) > 2 and keep_short:
        return ' '.join(result[:2])
    return ' '.join(result)


def shell_exec(cmd, env=None, shell=False, stdin=''):
    """Executes external command and returns the complete output as a
    string (stdout, stderr) and the program exit code (retc).

    Parameters
    ----------
    cmd : str
        Command to spawn the child process.
    env : None or dict
        Environment variables. Example: env={'PATH': '/usr/bin'}.
    shell : bool
        If True, the new process is called via what is set in the SHELL
        environment variable - means using shell=True invokes a program of the
        user's choice and is platform-dependent. It allows you to expand
        environment variables and file globs according to the shell's usual
        mechanism, which can be a security hazard. Generally speaking, avoid
        invocations via the shell. It is very seldom needed to set this
        to True.
    stdin : str
        If set, use this as input into `cmd`.

    Returns
    -------
    result : tuple
        result[0] = the functions return code (bool)
            False: result[1] contains the error message (str)
            True:  result[1] contains the result of the called `cmd`
                   as a tuple (stdout, stdin, retc)

    https://docs.python.org/2/library/subprocess.html
    """
    if not env:
        env = os.environ.copy()
    # set cmd output to English, no matter what the user has choosen
    env['LC_ALL'] = 'C'

    # subprocess.PIPE: Special value that can be used as the stdin,
    # stdout or stderr argument to Popen and indicates that a pipe to
    # the standard stream should be opened.
    if shell or stdin:
        # New console wanted, or we have some input for our cmd - then we
        # need a new console, too.
        # Pipes '|' are handled by the shell itself.
        try:
            sp = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, shell=True)
        except OSError as e:
            return (False, 'OS Error "{} {}" calling command "{}"'.format(e.errno, e.strerror, cmd))
        except ValueError as e:
            return (False, 'Value Error "{}" calling command "{}"'.format(e, cmd))
        except e:
            return (False, 'Unknown error "{}" while calling command "{}"'.format(e, cmd))

        if stdin:
            # provide stdin as input for the cmd
            stdout, stderr = sp.communicate(input=stdin)
        else:
            stdout, stderr = sp.communicate()
        retc = sp.returncode
        return (True, (stdout.decode(), stderr.decode(), retc))

    # No new console wanted, but then we have to do pipe handling on our own.
    # Example: `cat /var/log/messages | grep DENY | grep Rule` - we manage the art of piping here
    cmd_list = cmd.split('|')
    sp = None
    for cmd in cmd_list:
        args = shlex.split(cmd.strip())
        # use the previous output from last cmd call as input for next cmd in pipe chain,
        # if there is any
        stdin = sp.stdout if sp else subprocess.PIPE
        try:
            sp = subprocess.Popen(args, stdin=stdin, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, shell=False)
        except OSError as e:
            return (False, 'OS Error "{} {}" calling command "{}"'.format(e.errno, e.strerror, cmd))
        except ValueError as e:
            return (False, 'Value Error "{}" calling command "{}"'.format(e, cmd))
        except e:
            return (False, 'Unknown error "{}" while calling command "{}"'.format(e, cmd))

    stdout, stderr = sp.communicate()
    retc = sp.returncode
    return (True, (stdout.decode(), stderr.decode(), retc))


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


def str2state(string):
    """Return the state based on a string.

    >> lib.base.str2state('ok')
    0
    >>> lib.base.str2state('warn')
    1
    >>> lib.base.str2state('warning')
    1
    """
    string = str(string).lower()
    if string == 'ok':
        return STATE_OK
    if string.startswith('warn'):
        return STATE_WARN
    if string.startswith('crit'):
        return STATE_CRIT
    if string.startswith('unk'):
        return STATE_UNKNOWN


def state2str(state, empty_ok=True, prefix='', suffix=''):
    """Return the state's string representation.
    The square brackets around the state cause icingaweb2 to color the state.

    >> lib.base.state2str(2)
    '[CRIT]'
    >>> lib.base.state2str(0)
    ''
    >>> lib.base.state2str(0, empty_ok=False)
    '[OK]'
    >>> lib.base.state2str(0, empty_ok=False, suffix=' ')
    '[OK] '
    >>> lib.base.state2str(0, empty_ok=False, prefix=' (', suffix=')')
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


def timestr2datetime(timestr, pattern='%Y-%m-%d %H:%M:%S'):
    """Takes a string (default: ISO format) and returns a
    datetime object.
    """
    return datetime.datetime.strptime(timestr, pattern)


def timestrdiff(timestr1, timestr2, pattern1='%Y-%m-%d %H:%M:%S', pattern2='%Y-%m-%d %H:%M:%S'):
    """Returns the difference between two datetime strings in seconds. This
    function expects two ISO timestamps, by default each in ISO format.
    """
    timestr1 = timestr2datetime(timestr1, pattern1)
    timestr2 = timestr2datetime(timestr2, pattern2)
    timedelta = abs(timestr1 - timestr2)
    return timedelta.total_seconds()


# from /usr/lib/python3.10/site-packages/ansible/module_utils/_text.py
def to_bytes(obj, encoding='utf-8', errors=None, nonstring='simplerepr'):
    """Make sure that a string is a byte string

    :arg obj: An object to make sure is a byte string.  In most cases this
        will be either a text string or a byte string.  However, with
        ``nonstring='simplerepr'``, this can be used as a traceback-free
        version of ``str(obj)``.
    :kwarg encoding: The encoding to use to transform from a text string to
        a byte string.  Defaults to using 'utf-8'.
    :kwarg errors: The error handler to use if the text string is not
        encodable using the specified encoding.  Any valid `codecs error
        handler <https://docs.python.org/2/library/codecs.html#codec-base-classes>`_
        may be specified. There are three additional error strategies
        specifically aimed at helping people to port code.  The first two are:

            :surrogate_or_strict: Will use ``surrogateescape`` if it is a valid
                handler, otherwise it will use ``strict``
            :surrogate_or_replace: Will use ``surrogateescape`` if it is a valid
                handler, otherwise it will use ``replace``.

        Because ``surrogateescape`` was added in Python3 this usually means that
        Python3 will use ``surrogateescape`` and Python2 will use the fallback
        error handler. Note that the code checks for ``surrogateescape`` when the
        module is imported.  If you have a backport of ``surrogateescape`` for
        Python2, be sure to register the error handler prior to importing this
        module.

        The last error handler is:

            :surrogate_then_replace: Will use ``surrogateescape`` if it is a valid
                handler.  If encoding with ``surrogateescape`` would traceback,
                surrogates are first replaced with a replacement characters
                and then the string is encoded using ``replace`` (which replaces
                the rest of the nonencodable bytes).  If ``surrogateescape`` is
                not present it will simply use ``replace``.  (Added in Ansible 2.3)
                This strategy is designed to never traceback when it attempts
                to encode a string.

        The default until Ansible-2.2 was ``surrogate_or_replace``
        From Ansible-2.3 onwards, the default is ``surrogate_then_replace``.

    :kwarg nonstring: The strategy to use if a nonstring is specified in
        ``obj``.  Default is 'simplerepr'.  Valid values are:

        :simplerepr: The default.  This takes the ``str`` of the object and
            then returns the bytes version of that string.
        :empty: Return an empty byte string
        :passthru: Return the object passed in
        :strict: Raise a :exc:`TypeError`

    :returns: Typically this returns a byte string.  If a nonstring object is
        passed in this may be a different type depending on the strategy
        specified by nonstring.  This will never return a text string.

    .. note:: If passed a byte string, this function does not check that the
        string is valid in the specified encoding.  If it's important that the
        byte string is in the specified encoding do::

            encoded_string = to_bytes(to_text(input_string, 'latin-1'), 'utf-8')

    .. version_changed:: 2.3

        Added the ``surrogate_then_replace`` error handler and made it the default error handler.
    """
    if isinstance(obj, binary_type):
        return obj

    # We're given a text string
    # If it has surrogates, we know because it will decode
    original_errors = errors
    if errors in _COMPOSED_ERROR_HANDLERS:
        if HAS_SURROGATEESCAPE:
            errors = 'surrogateescape'
        elif errors == 'surrogate_or_strict':
            errors = 'strict'
        else:
            errors = 'replace'

    if isinstance(obj, text_type):
        try:
            # Try this first as it's the fastest
            return obj.encode(encoding, errors)
        except UnicodeEncodeError:
            if original_errors in (None, 'surrogate_then_replace'):
                # We should only reach this if encoding was non-utf8 original_errors was
                # surrogate_then_escape and errors was surrogateescape

                # Slow but works
                return_string = obj.encode('utf-8', 'surrogateescape')
                return_string = return_string.decode('utf-8', 'replace')
                return return_string.encode(encoding, 'replace')
            raise

    # Note: We do these last even though we have to call to_bytes again on the
    # value because we're optimizing the common case
    if nonstring == 'simplerepr':
        try:
            value = str(obj)
        except UnicodeError:
            try:
                value = repr(obj)
            except UnicodeError:
                # Giving up
                return to_bytes('')
    elif nonstring == 'passthru':
        return obj
    elif nonstring == 'empty':
        # python2.4 doesn't have b''
        return to_bytes('')
    elif nonstring == 'strict':
        raise TypeError('obj must be a string type')
    else:
        raise TypeError('Invalid value %s for to_bytes\' nonstring parameter' % nonstring)

    return to_bytes(value, encoding, errors)


# from /usr/lib/python3.10/site-packages/ansible/module_utils/_text.py
def to_text(obj, encoding='utf-8', errors=None, nonstring='simplerepr'):
    """Make sure that a string is a text string

    :arg obj: An object to make sure is a text string.  In most cases this
        will be either a text string or a byte string.  However, with
        ``nonstring='simplerepr'``, this can be used as a traceback-free
        version of ``str(obj)``.
    :kwarg encoding: The encoding to use to transform from a byte string to
        a text string.  Defaults to using 'utf-8'.
    :kwarg errors: The error handler to use if the byte string is not
        decodable using the specified encoding.  Any valid `codecs error
        handler <https://docs.python.org/2/library/codecs.html#codec-base-classes>`_
        may be specified.   We support three additional error strategies
        specifically aimed at helping people to port code:

            :surrogate_or_strict: Will use surrogateescape if it is a valid
                handler, otherwise it will use strict
            :surrogate_or_replace: Will use surrogateescape if it is a valid
                handler, otherwise it will use replace.
            :surrogate_then_replace: Does the same as surrogate_or_replace but
                `was added for symmetry with the error handlers in
                :func:`ansible.module_utils._text.to_bytes` (Added in Ansible 2.3)

        Because surrogateescape was added in Python3 this usually means that
        Python3 will use `surrogateescape` and Python2 will use the fallback
        error handler. Note that the code checks for surrogateescape when the
        module is imported.  If you have a backport of `surrogateescape` for
        python2, be sure to register the error handler prior to importing this
        module.

        The default until Ansible-2.2 was `surrogate_or_replace`
        In Ansible-2.3 this defaults to `surrogate_then_replace` for symmetry
        with :func:`ansible.module_utils._text.to_bytes` .
    :kwarg nonstring: The strategy to use if a nonstring is specified in
        ``obj``.  Default is 'simplerepr'.  Valid values are:

        :simplerepr: The default.  This takes the ``str`` of the object and
            then returns the text version of that string.
        :empty: Return an empty text string
        :passthru: Return the object passed in
        :strict: Raise a :exc:`TypeError`

    :returns: Typically this returns a text string.  If a nonstring object is
        passed in this may be a different type depending on the strategy
        specified by nonstring.  This will never return a byte string.
        From Ansible-2.3 onwards, the default is `surrogate_then_replace`.

    .. version_changed:: 2.3

        Added the surrogate_then_replace error handler and made it the default error handler.
    """
    if isinstance(obj, text_type):
        return obj

    if errors in _COMPOSED_ERROR_HANDLERS:
        if HAS_SURROGATEESCAPE:
            errors = 'surrogateescape'
        elif errors == 'surrogate_or_strict':
            errors = 'strict'
        else:
            errors = 'replace'

    if isinstance(obj, binary_type):
        # Note: We don't need special handling for surrogate_then_replace
        # because all bytes will either be made into surrogates or are valid
        # to decode.
        return obj.decode(encoding, errors)

    # Note: We do these last even though we have to call to_text again on the
    # value because we're optimizing the common case
    if nonstring == 'simplerepr':
        try:
            value = str(obj)
        except UnicodeError:
            try:
                value = repr(obj)
            except UnicodeError:
                # Giving up
                return u''
    elif nonstring == 'passthru':
        return obj
    elif nonstring == 'empty':
        return u''
    elif nonstring == 'strict':
        raise TypeError('obj must be a string type')
    else:
        raise TypeError('Invalid value %s for to_text\'s nonstring parameter' % nonstring)

    return to_text(value, encoding, errors)


def uniq(string):
    """Removes duplicate words from a string (only the second duplicates).
    The sequence of the words will not be changed.

    """
    words = string.split()
    return ' '.join(sorted(set(words), key=words.index))


def utc_offset():
    """Returns the current local UTC offset, for example '+0200'.

    utc_offset()
    >>> '+0200'
    """
    return time.strftime("%z")


def version(v):
    """Use this function to compare string-based version numbers.

    >>> '3.0.7' < '3.0.11'
    False
    >>> lib.base3.version('3.0.7') < lib.base3.version('3.0.11')
    True
    >>> lib.base3.version('v3.0.7-2') < lib.base3.version('3.0.11')
    True
    >>> lib.base3.version(psutil.__version__) >= lib.base3.version('5.3.0')
    True

    Parameters
    ----------
    v : str
        A version string.

    Returns
    -------
    tuple
        A tuple of version numbers.
    """
    # if we get something like "v0.10.7-2", remove everything except "." and "-",
    # and convert "-" to "."
    v = re.sub(r'[^0-9\.-]', '', v)
    v = v.replace('-', '.')
    return tuple(map(int, (v.split("."))))


def version2float(v):
    """Just get the version number as a float.

    >>> version2float('Version v17.3.2.0')
    17.320
    >>> version2float('21.60-53-93285')
    21.605393285
    """
    v = re.sub(r'[^0-9\.]', '', v)
    v = v.split('.')
    if len(v) > 1:
        return float('{}.{}'.format(v[0], ''.join(v[1:])))
    else:
        return float(''.join(v))


def yesterday(as_type='', tz_utc=False):
    """Returns yesterday's date and time as UNIX time in seconds (default), or
    as a datetime object.

    >>> lib.base3.yesterday()
    1626706723
    >>> lib.base3.yesterday(as_type='', tz_utc=False)
    1626706723
    >>> lib.base3.yesterday(as_type='', tz_utc=True)
    1626706723

    >>> lib.base3.yesterday(as_type='datetime', tz_utc=False)
    datetime.datetime(2021, 7, 19, 16, 58, 43, 11292)
    >>> lib.base3.yesterday(as_type='datetime', tz_utc=True)
    datetime.datetime(2021, 7, 19, 14, 58, 43, 11446, tzinfo=datetime.timezone.utc)

    >>> lib.base3.yesterday(as_type='iso', tz_utc=False)
    '2021-07-19 16:58:43'
    >>> lib.base3.yesterday(as_type='iso', tz_utc=True)
    '2021-07-19T14:58:43Z'
    """
    if tz_utc:
        if as_type == 'datetime':
            today = datetime.datetime.now(tz=datetime.timezone.utc)
            return today - datetime.timedelta(days=1)
        if as_type == 'iso':
            today = datetime.datetime.now(tz=datetime.timezone.utc)
            yesterday = today - datetime.timedelta(days=1)
            return yesterday.isoformat(timespec='seconds').replace('+00:00', 'Z')
    if as_type == 'datetime':
        today = datetime.datetime.now()
        return today - datetime.timedelta(days=1)
    if as_type == 'iso':
        today = datetime.datetime.now()
        yesterday = today - datetime.timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d %H:%M:%S")
    return int(time.time()-86400)
