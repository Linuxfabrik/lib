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

from globals import *

import datetime
import hashlib
import math
import shlex
import subprocess
import time


def bytes2human(n, format="%(value).1f%(symbol)s"):
    """Used by various scripts. See:
    https://github.com/giampaolo/psutil/blob/master/psutil/_common.py
    http://goo.gl/zeJZl

    >>> bytes2human(10000)
    '9.8K'
    >>> bytes2human(100001221)
    '95.4M'
    """
    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)


def coe(result, state=3):
    """Continue or Exit (CoE)
    """

    if (result[0]):
        # if return code of a more complex function's result is true (= no exception)
        # return its result set/data, and you can continue your code
        return result[1]
    else:
        # print the error message instead and exit with STATE_UNKOWN (3)
        print(result[1])
        exit(state)


def filter_mltext(input, ignore):
    filtered_input = ''
    for line in input.splitlines():
        if not any(i_line in line for i_line in ignore):
            filtered_input += line + '\n'

    return filtered_input


def get_perfdata(label, value, uom, warn, crit, mini, maxi):
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
    if mini is not None:
        msg += str(mini)
    msg += ';'
    if maxi is not None:
        msg += str(maxi)
    msg += '; '
    return msg


def get_state(value, warn, crit, operator='ge'):
    """Returns the STATE by comparing `value` to the given thresholds using
    a comparison `operator`.

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


def get_table(data,
                    keys,
                    header=None,
                    sort_by_key=None,
                    sort_order_reverse=False):
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

    Inspired by https://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/
    """

    from operator import itemgetter
    from collections import OrderedDict

    if not data:
        return ''

    # Sort the data if a sort key is specified (default sort order
    # is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=itemgetter(sort_by_key),
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

    column_widths = OrderedDict()
    for key in keys:
        column_widths[key] = max(len(str(column[key])) for column in data)

    table = ''
    for element in data:
        for key, width in column_widths.items():
            table += '{:<{}} '.format(element[key], width)
        table += '\n'

    return table


def get_worst(state1, state2):
    """Get the more worst of two states, in this particular order:
        # CRIT    (2)
        # WARN    (1)
        # UNKNOWN (3)
        # OK      (0)
    """
    if state1 == STATE_CRIT or state2 == STATE_CRIT:
        return STATE_CRIT
    if state1 == STATE_WARN or state2 == STATE_WARN:
        return STATE_WARN
    if state1 == STATE_UNKNOWN or state2 == STATE_UNKNOWN:
        return STATE_UNKNOWN
    return STATE_OK


def match(spec, value):
    """Decides if `value` is inside/outside the threshold spec.

    Parameters
    ----------
    spec : str
        Nagios range specification
    value : int
        Numeric value

    Returns
    -------
    bool
        `True` if `value` is inside the bounds for a non-inverted
        `spec`, or outside the bounds for an inverted `spec`. Otherwise `False`.

    Inspired by https://github.com/mpounsett/nagiosplugin/blob/master/nagiosplugin/range.py
    """

    if spec is None or spec.lower() == 'none':
        return True
    start, end, invert = parse(spec)
    if value < start:
        return False ^ invert
    if value > end:
        return False ^ invert
    return True ^ invert


def md5sum(string):
    return hashlib.md5(string).hexdigest()


def mltext2array(input, skip_header=False, sort_key=-1):
    from operator import itemgetter
    input = input.strip(' \t\n\r').split('\n')
    lines = []
    if skip_header:
        del input[0]
    for row in input:
        lines.append(row.split())
    if sort_key != -1:
        lines = sorted(lines, key=itemgetter(sort_key))        
    return lines


def now(as_datetime=False):
    if as_datetime:
        return datetime.datetime.now()
    else:
        return int(time.time())


def number2human(n):
    """
    >>> number2human(123456.8)
    '123K'
    >>> number2human(123456789.0)
    '123 Mill.'
    """
    millnames = ['', 'K', ' Mill.', ' Bill.', ' Trill.']
    n = float(n)
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
        exit(0)
    exit(state)


def parse(spec):
    """
    Inspired by https://github.com/mpounsett/nagiosplugin/blob/master/nagiosplugin/range.py
    """

    if spec is None or spec.lower() == 'none':
        return None
    if type(spec) is not str:
        spec = str(spec)
    invert = False
    if spec.startswith('@'):
        invert = True
        spec = spec[1:]
    if ':' in spec:
        try:
            start, end = spec.split(':')
        except:
            raise ValueError('not using range definition correctly')
    else:
        start, end = '', spec
    if start == '~':
        start = float('-inf')
    else:
        start = parse_atom(start, 0)
    end = parse_atom(end, float('inf'))
    if start > end:
        raise ValueError('start %s must not be greater than end %s' % (
                         start, end))
    return start, end, invert


def parse_atom(atom, default):
    if atom == '':
        return default
    if '.' in atom:
        return float(atom)
    return int(atom)


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

    From https://kite.com/python/docs/django.template.defaultfilters.pluralize
    """

    if ',' in suffix:
        singular, plural = suffix.split(',')
    else:
        singular, plural = '', suffix
    if int(value) == 1:
        return noun + singular
    else:
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
    else:
        return ' '.join(result)


def shell_exec(command, env=None, shell=False, stdin_input=False):
    # https://docs.python.org/2/library/subprocess.html
    # TODO - Warning: Using shell=True can be a security hazard.
    # TODO - Note: Do not use stdout=PIPE or stderr=PIPE with this function as that can deadlock based on the child process output volume. Use Popen with the communicate() method when you need pipes. 
    if shell:
        sp = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=True)
        stdout, stderr = sp.communicate()
        retc = sp.returncode
        return stdout, stderr, retc

    if stdin_input:
        sp = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=True)
        stdout, stderr = sp.communicate(input=stdin_input)
        retc = sp.returncode
        return stdout, stderr, retc

    command_list = command.split('|')

    p_last = None
    first = True
    for command in command_list:
        if first:
            first = False
            args = shlex.split(command.strip())
            p_last = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=False)
            continue

        args = shlex.split(command.strip())
        p_last = subprocess.Popen(args, stdin=p_last.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=False)

    stdout, stderr = p_last.communicate()
    retc = p_last.returncode
    return stdout, stderr, retc


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


def sort(array, reverse=True):
    """Sort of a simple 1-dimensional dictionary
    """

    if type(array) is dict:
        return sorted(array.items(), key=lambda x: x[1], reverse=reverse)


def state2string(state, return_ok=False):
    if state == STATE_CRIT:
        return 'CRIT'
    if state == STATE_WARN:
        return 'WARN'
    if state == STATE_OK:
        if return_ok:
            return 'OK'
        else:
            return ''
    if state == STATE_UNKNOWN:
        return 'UNKNOWN'

    return state


def time2iso(timestamp):
    timestamp = float(timestamp)
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def today():
    return datetime.datetime.today()


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
