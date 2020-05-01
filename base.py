#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Provides very common every-day functions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020050101'

import collections
import datetime
import hashlib
import math
import numbers
import operator
import shlex
import subprocess
import sys
import time

from globals import STATE_OK, STATE_UNKNOWN, STATE_WARN, STATE_CRIT


def bits2human(n, format="%(value).1f%(symbol)s"):
    """Converts n bits to a human readable format.

    >>> bits2human(10000)
    '10K'
    >>> bits2human(100001221)
    '100.0M'
    """

    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
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

    >>> bytes2human(10000)
    '9.8K'
    >>> bytes2human(100001221)
    '95.4M'

    https://github.com/giampaolo/psutil/blob/master/psutil/_common.py
    """

    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
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


def coe(result, state=3):
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


def epoch2iso(timestamp):
    """Returns the ISO representaton of a UNIX timestamp (epoch).
    """

    timestamp = float(timestamp)
    return datetime.datetime.fromepoch(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def filter_mltext(input, ignore):
    filtered_input = ''
    for line in input.splitlines():
        if not any(i_line in line for i_line in ignore):
            filtered_input += line + '\n'

    return filtered_input


def get_perfdata(label, value, uom, warn, crit, min, max):
    """Returns 'label'=value[UOM];[warn];[crit];[min];[max]
    """

    msg = label + '=' + str(value)
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
    msg += '; '
    return msg


def get_state(value, warn, crit, operator='ge'):
    """Returns the STATE by comparing `value` to the given thresholds using
    a comparison `operator`. `warn` and `crit` threshold may also be `None`.

    >>> base.get_state(15, 10, 20, 'ge')
    1 (STATE_WARN)
    >>> base.get_state(10, 10, 20, 'gt')
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
        `ge` = greater or equal
        `gt` = greater than
        `le` = less or equal
        `lt` = less than
        `eq` = equal to
        `ne` = not equal to

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
    return STATE_UNKNOWN


def get_table(data, keys, header=None, sort_by_key=None, sort_order_reverse=False):
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        keys - List of keys in the dictionary. (Type: List)

    Optional Parameters:
        header - The table header. (Type: List)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: bool)

    Inspired by
    https://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/
    """

    if not data:
        return ''

    # Sort the data if a sort key is specified (default sort order
    # is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=operator.itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, add header to data
    if header:
        # Get the length of each header and create a divider based
        # on that length
        header_divider = []
        for name in header:
            header_divider.append('-' * len(name))

        # Create a list of dictionary from the keys and the header and
        # insert it at the beginning of the list. Do the same for the
        # divider and insert below the header.
        header_divider = dict(zip(keys, header_divider))
        data.insert(0, header_divider)
        header = dict(zip(keys, header))
        data.insert(0, header)

    column_widths = collections.OrderedDict()
    for key in keys:
        column_widths[key] = max(len(str(column[key])) for column in data)

    table = ''
    for element in data:
        for key, width in column_widths.items():
            table += '{:<{}} '.format(element[key], width)
        table += '\n'

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
        """

        def parse_atom(atom, default):
            if atom == '':
                return default
            if '.' in atom:
                return float(atom)
            return int(atom)


        if spec is None or spec.lower() == 'none':
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


    if spec is None or spec.lower() == 'none':
        return (True, True)
    success, result = parse_range(spec)
    if not success:
        return (success, result)
    start, end, invert = result
    if isinstance(value, str) or isinstance(value, unicode):
        value = float(value.replace('%', ''))
    if value < start:
        return (True, False ^ invert)
    if value > end:
        return (True, False ^ invert)
    return (True, True ^ invert)


def md5sum(string):
    return hashlib.md5(string).hexdigest()


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

    base.now()
    >>> 1586422786

    base.now(as_type='epoch')
    >>> 1586422786

    base.now(as_type='datetime')
    >>> datetime.datetime(2020, 4, 9, 11, 1, 41, 228752)

    base.now(as_type='iso')
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
    '123 Mill.'
    """
    millnames = ['', 'K', ' Mill.', ' Bill.', ' Trill.']
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

    >>> lib.base.seconds2human(1387775)
    '2w 2d'
    >>> lib.base.seconds2human('1387775')
    '2w 2d'
    >>> lib.base.seconds2human('1387775', full_name=True)
    '2weeks 2days'
    >>> lib.base.seconds2human(1387775, keep_short=False)
    '2weeks 2days 1hour 29minutes 35seconds'
    """

    seconds = int(seconds)
    if full_name:
        intervals = (
            ('weeks', 604800),  # 60 * 60 * 24 * 7
            ('days', 86400),    # 60 * 60 * 24
            ('hours', 3600),    # 60 * 60
            ('minutes', 60),
            ('seconds', 1),
        )
    else:
        intervals = (
            ('w', 604800),      # 60 * 60 * 24 * 7
            ('d', 86400),       # 60 * 60 * 24
            ('h', 3600),        # 60 * 60
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
        If True, the new process has a new console, instead of
        inheriting its parent’s console (the default). It is very seldom
        needed to set this to True. Warning: Using shell=True can be a
        security hazard.
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

    # subprocess.PIPE: Special value that can be used as the stdin,
    # stdout or stderr argument to Popen and indicates that a pipe to
    # the standard stream should be opened.
    if shell:
        # Pipes '|' are handled by Shell directly
        try:
            sp = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, shell=True)
        except OSError as e:
            return (False, 'OS Error "{} {}" calling command "{}"'.format(e.errno, e.strerror, cmd))
        except ValueError as e:
            return (False, 'Value Error "{}" calling command "{}"'.format(e, cmd))
        except e:
            return (False, 'Unknown error "{}" while calling command "{}"'.format(e, cmd))
        stdout, stderr = sp.communicate()
        retc = sp.returncode
        return (True, (stdout, stderr, retc))

    if stdin:
        # We have some input for our cmd.
        # Pipes '|' are handled by Shell directly.
        try:
            sp = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, shell=True)
        except OSError as e:
            return (False, 'OS Error "{} {}" calling command "{}"'.format(e.errno, e.strerror, cmd))
        except ValueError as e:
            return (False, 'Value Error "{}" calling command "{}"'.format(e, cmd))
        except e:
            return (False, 'Unknown error "{}" while calling command "{}"'.format(e, cmd))
        # provide text as input for ...
        stdout, stderr = sp.communicate(input=stdin)
        retc = sp.returncode
        return (True, (stdout, stderr, retc))

    # Example: `cat /var/log/messages | grep DENY | grep Rule` - we manage the art of piping here
    cmd_list = cmd.split('|')
    sp = None
    for cmd in cmd_list:
        args = shlex.split(cmd.strip())
        # is set, use output from last cmd call as input for second cmd in pipe chain
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
    return (True, (stdout, stderr, retc))


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
        return sorted(array.items(), key=lambda x: x[0].lower(), reverse=reverse)
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


def state2str(state, empty_ok=True, prefix='', suffix=''):
    """Return the state's string representation.

    >> lib.base.state2str(2)
    'CRIT'
    >>> lib.base.state2str(0)
    ''
    >>> lib.base.state2str(0, empty_ok=False)
    'OK'
    >>> lib.base.state2str(0, empty_ok=False, suffix=' ')
    'OK '
    >>> lib.base.state2str(0, empty_ok=False, prefix=' (', suffix=')')
    ' (OK)'
    """

    state = int(state)
    if state == STATE_OK and empty_ok:
        return ''
    if state == STATE_OK and not empty_ok:
        return '{}OK{}'.format(prefix, suffix)
    if state == STATE_WARN:
        return '{}WARN{}'.format(prefix, suffix)
    if state == STATE_CRIT:
        return '{}CRIT{}'.format(prefix, suffix)
    if state == STATE_UNKNOWN:
        return '{}UNKNOWN{}'.format(prefix, suffix)

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


def version(v):
    """Use this function to compare numerical but string-based version numbers.

    >>> base.version('3.0.7') < base.version('3.0.11')
    True
    >>> '3.0.7' < '3.0.11'
    False
    >>> lib.base.version(psutil.__version__) >= lib.base.version('5.3.0')
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

    return tuple(map(int, (v.split("."))))
