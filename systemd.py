#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library tells why a systemd unit failed, and what it last wrote to the
journal.

The reason comes from the `Result`, `ExecMainCode` and `ExecMainStatus` properties
that `systemctl show` prints for every unit. Reading them needs no privileges. The log
lines come from the system journal, which only root, sudo or the `systemd-journal`
group may read; without that access, the functions return no lines instead of an
error, and `journalctl_command()` names the command that shows the log.

The base is the systemd of RHEL 8 (systemd 239, read in redhat-plumbers/systemd-rhel8,
branch rhel-8.10.0): every command, option and property used here exists there, and
nothing depends on a later version. Verified with units failing on an exit status, a
signal, a core dump, a timeout, a missing binary, a missing user, a failing
ExecStartPre= and a failing mount, on ubi8-init (systemd 239, Python 3.6), ubi9-init
(252), ubi10-init (257), Debian 13 (257) and Ubuntu 26.04 (259). All of them give the
same result.

Typical use case:

.. code-block:: python

    reasons = lib.systemd.get_failure_reasons(['httpd.service'])
    logs = lib.systemd.get_log_lines(['httpd.service'])
"""

import shlex
import signal
import time

from . import shell, txt

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026111101'

# The si_code of the main process in `ExecMainCode`, from the kernel's
# include/uapi/asm-generic/siginfo.h. 0 means the main process never ran, for example
# because an ExecStartPre= failed.
CLD_EXITED = 1
CLD_KILLED = 2
CLD_DUMPED = 3

# The exit statuses systemd sets itself when it cannot start a process, from
# src/basic/exit-status.h. RHEL 8 (systemd 239) has 200 to 242; 243 to 246 come from
# later versions (src/shared/exit-status.h in systemd 257) and are listed so that a
# newer host reads right. 223 and 234 are reserved and have no name. The LSB (1 to 7)
# and BSD (64 to 78) names that systemctl also prints are left out on purpose: a
# program chooses those statuses itself, mostly without following either convention,
# so `3/NOTIMPLEMENTED` would mislead.
EXIT_STATUSES = {
    200: 'CHDIR',
    201: 'NICE',
    202: 'FDS',
    203: 'EXEC',
    204: 'MEMORY',
    205: 'LIMITS',
    206: 'OOM_ADJUST',
    207: 'SIGNAL_MASK',
    208: 'STDIN',
    209: 'STDOUT',
    210: 'CHROOT',
    211: 'IOPRIO',
    212: 'TIMERSLACK',
    213: 'SECUREBITS',
    214: 'SETSCHEDULER',
    215: 'CPUAFFINITY',
    216: 'GROUP',
    217: 'USER',
    218: 'CAPABILITIES',
    219: 'CGROUP',
    220: 'SETSID',
    221: 'CONFIRM',
    222: 'STDERR',
    224: 'PAM',
    225: 'NETWORK',
    226: 'NAMESPACE',
    227: 'NO_NEW_PRIVILEGES',
    228: 'SECCOMP',
    229: 'SELINUX_CONTEXT',
    230: 'PERSONALITY',
    231: 'APPARMOR',
    232: 'ADDRESS_FAMILIES',
    233: 'RUNTIME_DIRECTORY',
    235: 'CHOWN',
    236: 'SMACK_PROCESS_LABEL',
    237: 'KEYRING',
    238: 'STATE_DIRECTORY',
    239: 'CACHE_DIRECTORY',
    240: 'LOGS_DIRECTORY',
    241: 'CONFIGURATION_DIRECTORY',
    242: 'NUMA_POLICY',
    243: 'CREDENTIALS',
    244: 'BPF',
    245: 'KSM',
    246: 'MEMORY_THP',
    255: 'EXCEPTION',
}

# How systemd's `Result` property reads, complete for every unit type
# (`*_result_table` in src/core/{automount,mount,path,scope,service,socket,swap,
# timer}.c). RHEL 8 (systemd 239) has all of them except `oom-kill` and `unmounted`,
# which come from later versions (read in systemd 257) and are listed so that a newer
# host reads right. `success` is left out, since a unit with that result has not
# failed for a reason of its own (a unit that is not found, for example). `exit-code`,
# `signal` and `core-dump` are refined with the exit status or the signal of the main
# process where systemd knows them.
RESULT_REASONS = {
    'core-dump': 'dumped core',
    'exec-condition': 'its ExecCondition= failed',
    'exit-code': 'exited with an error',
    'mount-start-limit-hit': 'its mount unit was started too often',
    'oom-kill': 'killed by the OOM killer',
    'protocol': 'did not follow the start-up protocol of its type',
    'resources': 'a system operation failed while starting or stopping it',
    'service-start-limit-hit': 'its service was started too often',
    'signal': 'killed by a signal',
    'start-limit-hit': 'started too often',
    'timeout': 'timed out',
    'trigger-limit-hit': 'triggered too often',
    'unit-start-limit-hit': 'the unit it triggers was started too often',
    'unmounted': 'its automount point was unmounted',
    'watchdog': 'missed its watchdog',
}

# The properties `failure_reason()` reads.
SHOW_PROPERTIES = 'Result,ExecMainCode,ExecMainStatus'


def _is_count(value):
    """Tell whether `value` is a whole number, and not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def _signal_name(number):
    """Return the name of signal `number` (`SIGKILL`), or `signal 9` if Python does
    not know it.
    """
    try:
        return signal.Signals(number).name
    except ValueError:
        return f'signal {number}'


def _unit_names(units):
    """Return the non-empty strings of the list `units`, or an empty list if `units`
    is not a list. A single string is refused, since iterating over it would yield
    one unit per character.
    """
    if not isinstance(units, (list, tuple)):
        return []
    return [unit for unit in units if isinstance(unit, str) and unit]


def failure_reason(props):
    """
    Tell in a few words why a unit failed.

    Parameters
    ----------
    props : dict
        The `Result`, `ExecMainCode` and `ExecMainStatus` properties of the unit, as
        `parse_show()` returns them. A unit that is not a service has no ExecMain
        properties.

    Returns
    -------
    str
        For example `exited with status 203/EXEC`, `killed by SIGKILL` or `timed out`.
        A result that this module does not know reads `failed with result '...'`.
        Empty if the unit has not failed, which includes a unit that is not found.
        systemd keeps the result of a failed run until the unit is started again,
        also while it waits in `auto-restart` (`service_start()` in
        src/core/service.c resets it, the same in systemd 239 and 257).

    Examples
    --------
    >>> failure_reason(
    ...     {'Result': 'exit-code', 'ExecMainCode': '1', 'ExecMainStatus': '217'}
    ... )
    'exited with status 217/USER'
    """
    if not isinstance(props, dict):
        return ''
    result = props.get('Result', '')
    if not isinstance(result, str) or not result or result == 'success':
        return ''
    try:
        code = int(props.get('ExecMainCode', 0))
        status = int(props.get('ExecMainStatus', 0))
    except (TypeError, ValueError):
        code, status = 0, 0
    if result == 'exit-code' and code == CLD_EXITED and status:
        name = EXIT_STATUSES.get(status)
        return f'exited with status {status}' + (f'/{name}' if name else '')
    if result == 'signal' and code == CLD_KILLED and status:
        return f'killed by {_signal_name(status)}'
    if result == 'core-dump' and code == CLD_DUMPED and status:
        return f'dumped core on {_signal_name(status)}'
    # a result that a later systemd adds still says something
    return RESULT_REASONS.get(result, f"failed with result '{result}'")


def failure_reasons(units, stdout):
    """
    Tell why each unit failed, from the output of one `systemctl show` call.

    Parameters
    ----------
    units : list
        The unit names, in the order they were passed to `systemctl show`.
    stdout : str
        The output of `systemctl show --property=Result,ExecMainCode,ExecMainStatus
        -- <units>`.

    Returns
    -------
    dict
        Unit name to `failure_reason()`. Empty if the output does not have one block
        per unit, since the blocks carry no unit name and could not be matched, and
        if `units` is not a list.

    Examples
    --------
    >>> failure_reasons(
    ...     ['a.service'], 'Result=timeout\\nExecMainCode=0\\nExecMainStatus=0\\n'
    ... )
    {'a.service': 'timed out'}
    """
    if not isinstance(units, (list, tuple)):
        return {}
    blocks = parse_show(stdout)
    if len(blocks) != len(units):
        return {}
    return {unit: failure_reason(props) for unit, props in zip(units, blocks)}


def get_failure_reasons(units, timeout=None):
    """
    Ask systemd why each unit failed, with one `systemctl show` call for all units.

    Reading the properties needs no privileges.

    Parameters
    ----------
    units : list
        The unit names. They are passed after `--`, so a name cannot be read as an
        option.
    timeout : int, optional
        Seconds the command is given. Defaults to `shell_exec()`'s default.

    Returns
    -------
    dict
        Unit name to `failure_reason()`. Empty on any error or on arguments of the
        wrong type, so a caller can go on without the reasons.

    Examples
    --------
    >>> get_failure_reasons(['httpd.service'])
    {'httpd.service': 'exited with status 1'}
    """
    units = _unit_names(units)
    if not units or not (timeout is None or _is_count(timeout)):
        return {}
    cmd = [
        'systemctl',
        'show',
        f'--property={SHOW_PROPERTIES}',
        '--',
        *units,
    ]
    kwargs = {} if timeout is None else {'timeout': timeout}
    success, result = shell.shell_exec(cmd, **kwargs)
    if not success:
        return {}
    stdout, _stderr, retc = result
    if retc != 0:
        return {}
    return failure_reasons(units, stdout)


def get_log_lines(units, lines=3, line_length=200, timeout=5):
    """
    Read the last lines each unit's own processes wrote to the system journal in the
    current boot.

    The messages of systemd about the unit stay out, since `failure_reason()` already
    says what they say. One `journalctl` call is made per unit.

    Parameters
    ----------
    units : list
        The unit names. Each one is passed as the value of a `_SYSTEMD_UNIT=` match,
        so it cannot be read as an option.
    lines : int, optional
        Lines per unit. Defaults to 3.
    line_length : int, optional
        Maximum length of a line, since a program may write a whole document into
        one. Defaults to 200.
    timeout : int, optional
        Seconds all calls together are given. Units left when they are used up go
        without lines. Defaults to 5.

    Returns
    -------
    dict
        Unit name to its list of lines. A unit that wrote nothing is left out. Empty
        if the journal may not be read, which needs root, sudo or the
        `systemd-journal` group, and on arguments of the wrong type.

    Examples
    --------
    >>> get_log_lines(['t-exit.service'])
    {'t-exit.service': ['starting', 'Error: config file /etc/foo.conf not found']}
    """
    if not all(_is_count(value) for value in (lines, line_length, timeout)):
        return {}
    logs = {}
    deadline = time.monotonic() + timeout
    for unit in _unit_names(units):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        success, result = shell.shell_exec(
            [
                'journalctl',
                '--no-pager',
                '--boot=0',
                '--output=cat',
                f'--lines={lines}',
                f'_SYSTEMD_UNIT={unit}',
            ],
            timeout=remaining,
        )
        if not success:
            break
        stdout, _stderr, retc = result
        if retc != 0:
            # Without access, journalctl says "No journal files were opened due to
            # insufficient permissions" and exits 1; the next unit fares no better.
            # An account in neither group sees only its own journal, exits 0 and
            # finds no line of the unit.
            break
        found = log_lines(stdout, lines, line_length)
        if found:
            logs[unit] = found
    return logs


def journalctl_command(units):
    """
    Return the command that shows the journal of the units in the current boot,
    including the messages of systemd about them.

    Parameters
    ----------
    units : list
        The unit names.

    Returns
    -------
    str
        For example `journalctl --boot=0 --unit=httpd.service`. Every argument is
        quoted for a POSIX shell where needed, since an escaped unit name contains a
        backslash (`dev-disk-by\\x2duuid-...`).

    Examples
    --------
    >>> journalctl_command(['a.service', 'b.service'])
    'journalctl --boot=0 --unit=a.service --unit=b.service'
    """
    args = [shlex.quote(f'--unit={unit}') for unit in _unit_names(units)]
    return ' '.join(['journalctl', '--boot=0', *args])


def log_lines(stdout, lines=3, line_length=200):
    """
    Return the last non-empty lines of a `journalctl --output=cat` output.

    Parameters
    ----------
    stdout : str
        The output.
    lines : int, optional
        How many lines to return. Defaults to 3.
    line_length : int, optional
        Maximum length of a line. Longer lines are shortened in the middle. Defaults
        to 200.

    Returns
    -------
    list
        The lines, oldest first. Empty on arguments of the wrong type.

    Examples
    --------
    >>> log_lines('starting\\n\\nError: config file /etc/foo.conf not found\\n')
    ['starting', 'Error: config file /etc/foo.conf not found']
    """
    if not isinstance(stdout, str) or not _is_count(lines) or lines <= 0:
        return []
    if not _is_count(line_length):
        return []
    found = [
        txt.shorten(line.rstrip(), line_length)
        for line in stdout.splitlines()
        if line.strip()
    ]
    return found[-lines:]


def parse_show(stdout):
    """
    Split the output of `systemctl show <unit> <unit> ...` into one dict of
    properties per unit.

    systemctl prints one block per unit, in the order of the arguments, separated by
    an empty line, and leaves out the ExecMain properties for a unit that is not a
    service.

    Parameters
    ----------
    stdout : str
        The output.

    Returns
    -------
    list
        One dict per block, property name to value.

    Examples
    --------
    >>> parse_show('Result=success\\n\\nResult=timeout\\n')
    [{'Result': 'success'}, {'Result': 'timeout'}]
    """
    if not isinstance(stdout, str) or not stdout.strip():
        return []
    blocks = []
    for block in stdout.strip().split('\n\n'):
        props = {}
        for line in block.splitlines():
            key, sep, value = line.partition('=')
            if sep:
                props[key] = value
        blocks.append(props)
    return blocks
