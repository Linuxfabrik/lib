#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Extends argparse by new input argument data types on demand."""

import argparse
import os
import re
import textwrap

from . import base, disk

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082501'

# Base URL of the rendered online documentation.
DOCS_BASE_URL = 'https://linuxfabrik.github.io/monitoring-plugins'

# How an include filter and an exclude filter combine, for the consumers that offer both.
# Kept out of the two help texts themselves and appended by the consumer, because the
# purpose sentence in front of it names whatever the consumer filters - items, mount
# points, disks, findings - while this sentence is the same everywhere. It belongs on the
# include filter alone: it describes the pair, and saying it twice only makes both entries
# longer.
MATCH_IGNORE_PRECEDENCE = (
    'If both `--match` and `--ignore` are given, an item must match `--match` AND not '
    'match `--ignore` to be reported (include first, exclude second).'
)


# Help text descriptions only - no "Default:" here.
# A consumer appends its own default info, e.g.:
#   help=lib.args.help('--timeout') + ' Default: %(default)s (seconds)',
# Switches (store_true/store_false) don't need a default.
HELP_TEXTS = {
    '--always-ok': 'Always returns OK.',
    '--brief': (
        'Hide the rows that are within the thresholds and show only those in a WARN or '
        'CRIT state. '
        'Perfdata and alerting are unaffected: every item still emits performance data '
        'and still drives the overall check state, so this is safe to leave on.'
    ),
    '--cache-expire': (
        'The amount of time after which the credential/data cache expires, in minutes.'
    ),
    '--check-major': (
        'Alert when a new major release is available, even if the current version is '
        'not yet EOL. '
        'Example: running v26 (not yet EOL) and v27 is available.'
    ),
    '--check-minor': (
        'Alert when a new major.minor release is available, even if the current version '
        'is not yet EOL. '
        'Example: running v26.2 (not yet EOL) and v26.3 is available.'
    ),
    '--check-patch': (
        'Alert when a new major.minor.patch release is available, even if the current '
        'version is not yet EOL. '
        'Example: running v26.2.7 (not yet EOL) and v26.2.8 is available.'
    ),
    '--check-security': (
        'Alert when the vendor version-check service reports a security-relevant update '
        'for the currently installed version (security severity, critical vulnerability '
        'or similar). '
        'Requires online access to the vendor service. '
        'Has no effect on plugins that do not implement an upstream security check.'
    ),
    '--count': (
        'Number of consecutive checks the threshold must be exceeded before alerting.'
    ),
    '--critical': 'CRIT threshold in percent.',
    '--critical-count': 'CRIT threshold for the number of matching items.',
    '--critical-seconds': 'CRIT threshold in seconds.',
    '--critical-temperature': 'CRIT threshold in degrees Celsius.',
    '--critical-voltage': 'CRIT threshold in volts.',
    '--defaults-file': (
        'Specifies a cnf file to read parameters like user, host and password from '
        '(for MySQL/MariaDB cnf-style files).'
    ),
    '--defaults-group': 'Group/section to read from in the cnf file.',
    '--fail-severity': (
        'State to report for an item the monitored system itself marks as failed. '
        'A failed item means the installation is broken in a way that stops it from '
        'working correctly, which is worth acting on but rarely worth waking somebody '
        'up for.'
    ),
    '--hostname': 'Hostname or IP address.',
    '--ipv6': 'Use IPv6.',
    '--ignore': (
        'Any item matching this string will be ignored. '
        'Case-sensitive. '
        'Can be specified multiple times.'
    ),
    '--ignore-pattern': (
        'Any item containing this pattern will be ignored. '
        'Case-insensitive. '
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
    '--link-down-severity': (
        'State to report for a port whose link is down. '
        'A port that is simply not cabled reports the same thing, which is why this '
        'defaults to not alerting.'
    ),
    '--match': (
        'Filter by this Python regular expression. '
        'Case-sensitive by default; use `(?i)` for case-insensitive matching. '
        'Can be specified multiple times. '
        f'{MATCH_IGNORE_PRECEDENCE} '
        'Examples: '
        '`(?i)example` to match "example" regardless of case. '
        '`^(?!.*example).*$` to match any string except "example" (negative lookahead).'
    ),
    '--no-checksum-data-severity': (
        'State to report when no published checksums are available for a component and it '
        'could not be verified. '
        'The check still verifies everything it has checksums for, but a clean result then '
        'only covers those components, not the ones it had to skip.'
    ),
    '--no-insecure': (
        'Verify the TLS certificate against the system trust store, overriding the '
        'insecure default of this check. '
        'Use it once the endpoint presents a publicly trusted certificate, or once its '
        'CA has been added to the system trust store.'
    ),
    '--no-match-severity': (
        'State to report when no item matches the filters and nothing is checked.'
    ),
    '--no-perfdata': (
        'Suppress the performance data section from the output. '
        'The status message and the exit code are unaffected, so alerting keeps working '
        'while trending data is dropped.'
    ),
    '--no-proxy': 'Do not use a proxy.',
    '--no-vuln-data-severity': (
        'State to report when the vulnerability database could not be queried and no '
        'vulnerability data is available. '
        'The check still reports everything it can determine without that data, but a '
        'clean result then only means nothing else was found, not that the target is '
        'free of known vulnerabilities.'
    ),
    '--offset-eol': (
        'Alert n days before ("-30") or after an EOL date ("30" or "+30").'
    ),
    '--password': 'Password.',
    '--password-file': (
        'Path to a file holding the password, read from its first line. '
        'Keeps the password out of the process list, where a command-line argument is '
        'visible to every user on the host. '
        'Takes precedence over `--password`. '
        'Keep the file readable only by the monitoring user. '
        'Example: `--password-file=/etc/icinga2/secrets/storage`.'
    ),
    '--path': 'Local path to the installation.',
    '--port': 'Port number.',
    '--severity': 'Severity for alerting.',
    '--stratum': (
        'Warns if the determined stratum of the time server is greater than or equal '
        'to this value. '
        'Stratum 1 indicates a computer with a locally attached reference clock. '
        'A computer that is synchronised to a stratum 1 computer is at stratum 2. '
        'A computer that is synchronised to a stratum 2 computer is at stratum 3, '
        'and so on.'
    ),
    # Developer-only switch for the unit-test harness. Mapped to argparse.SUPPRESS
    # so it stays accepted on the command line but is hidden from --help (and
    # therefore from the generated READMEs and Director baskets), like the
    # deprecated parameters. Consumers keep declaring it via help('--test').
    '--test': argparse.SUPPRESS,
    '--timeout': 'Network timeout in seconds.',
    '--unreachable-severity': (
        'State to report when the online source is unreachable. '
        'What is used instead - bundled offline data, a cached copy, or nothing at all - '
        'is named in the output, and a clean result then only covers what that fallback '
        'could confirm.'
    ),
    '--unscored-severity': (
        'State to report for a finding that carries no severity score of its own. '
        'A source that scores its findings rarely scores all of them, and the unrated '
        'ones need a state of their own rather than the one a score would have earned '
        'them.'
    ),
    '--url': 'URL to the endpoint.',
    '--username': 'Username.',
    '--verbose': (
        'Makes this plugin verbose during the operation. '
        'Useful for debugging and seeing what is going on under the hood.'
    ),
    '--warning': 'WARN threshold in percent.',
    '--warning-count': 'WARN threshold for the number of matching items.',
    '--warning-seconds': 'WARN threshold in seconds.',
    '--warning-temperature': 'WARN threshold in degrees Celsius.',
    '--warning-voltage': 'WARN threshold in volts.',
}


# Predefined sets for checking units and methods
_UNITS = {'%', 'K', 'M', 'G', 'T', 'P'}
_METHODS = {'USED', 'FREE'}


class HelpFormatter(argparse.HelpFormatter):
    """Formats the help output like argparse does, but never splits long words.

    argparse's default formatter breaks words at hyphens to fit the terminal width,
    which turns a URL like `https://example.com/a-b/c/` into two unusable fragments.
    Here, a word that does not fit is kept intact and overflows instead.
    """

    def _fill_text(self, text, width, indent):
        return textwrap.fill(
            re.sub(r'\s+', ' ', text).strip(),
            width,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )


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


def epilog(path, section='check-plugins'):
    """Builds a pointer to the online documentation, to be used as an argparse epilog.

    The document name is derived from the file name of the calling script, so pass
    `__file__`. A trailing `.exe` or `.py` extension is stripped.

    Use together with `HelpFormatter`, otherwise argparse breaks the URL at its hyphens.

    ### Parameters
    - **path** (`str`): Path of the calling script, normally `__file__`.
    - **section** (`str`, optional): Section the document lives in.
      Defaults to `check-plugins`.

    ### Returns
    - **str**: A single line pointing to the documentation URL.

    ### Example
    >>> epilog('/usr/lib64/nagios/plugins/example')
    'Documentation: https://linuxfabrik.github.io/monitoring-plugins/check-plugins/example/'
    """
    name = os.path.basename(path)
    for suffix in ('.exe', '.py'):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return f'Documentation: {DOCS_BASE_URL}/{section}/{name}/'


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

    Returns only the description, without "Default:" suffix.
    The caller appends the default info as needed, e.g.:
        help=lib.args.help('--timeout') + ' Default: %(default)s (seconds)',

    ### Parameters
    - **param** (`str`): The parameter name (e.g. '--timeout').

    ### Returns
    - **str**: The help text, or an empty string if not found.

    ### Example
    >>> help('--timeout')
    'Network timeout in seconds.'
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


def load_secret(path, param='--password-file'):
    """
    Read a secret out of a file, so it does not have to be passed on the command line.

    A command-line argument is visible to every user on the host for as long as the
    process runs, and a scheduled process runs again and again. Reading the secret from
    a file that only its own user can read keeps it out of the process list.

    ### Parameters
    - **path** (`str`): The file to read.
    - **param** (`str`, optional): The parameter name to use in an error message.

    ### Returns
    - **str**: The secret, without the trailing newline a text editor appends.

    ### Notes
    - Aborts the calling process (UNKNOWN) when the file cannot be read or holds nothing.
      A secret that silently comes out empty would be sent to the remote end as an empty
      password, which drives the account towards its lockout threshold.
    - Only the first line is used, and only its trailing newline is stripped. Leading and
      trailing spaces are part of a password, and stripping them would make a valid
      password fail with no way to tell why.
    - The file permissions are deliberately not enforced here. Which user a consumer runs as
      differs per deployment, and refusing to start over a permission bit would take a
      working check down; keeping the file readable only by the monitoring user is the
      documented operator's job.

    ### Example
    >>> load_secret('/etc/icinga2/secrets/storage')
    'linuxfabrik'
    """
    success, content = disk.read_file(path)
    if not success:
        base.cu(f'Cannot read the file given in {param}: {content}')

    secret = content.split('\n', 1)[0].rstrip('\r')
    if not secret:
        base.cu(f'The file given in {param} is empty.')
    return secret


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
