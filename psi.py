#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library reads the pressure stall information (PSI) that the Linux kernel
exports below `/proc/pressure`, one file per contended resource.

A pressure value is the share of wall clock time in which work could not proceed
because a resource was contended. The `some` line counts the time in which at
least one task was stalled, the `full` line the time in which every non-idle task
was stalled at once, which is the state where the machine spends its cycles
waiting rather than working. Each line carries three averages over the last 10,
60 and 300 seconds in percent, and the absolute stall time since boot in
microseconds. Verified against `kernel/sched/psi.c` and
`Documentation/accounting/psi.rst`, and measured on kernel 7.1 (Fedora 44).

`read()` returns the raw numbers. `get_states()`, `get_summary()`,
`get_perfdata()` and `get_table()` turn a reading into a report, so that every
consumer judges and prints the same numbers the same way.

Typical use case:
```python
    pressure = lib.base.coe(lib.psi.read('memory'))
    if pressure is None:
        print('Pressure stall information is switched off in this kernel.')
    else:
        thresholds = {'avg60': ('5', '10')}
        states = lib.psi.get_states(pressure, 'full', thresholds)
        print(lib.psi.get_summary(
            pressure, 'memory', 'memory', ('some', 'full'), 'full', states,
        ))
```
"""

import errno
import os

from . import base, disk
from .globals import STATE_OK

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082601'

# The kernel creates this directory only where pressure accounting is switched on, so
# its absence is the normal state of a kernel built with CONFIG_PSI_DEFAULT_DISABLED
# and booted without `psi=1`, which is what the whole Red Hat family ships.
PRESSURE_DIR = '/proc/pressure'

# The resources the kernel accounts for. `irq` exists only where the kernel was built
# with CONFIG_IRQ_TIME_ACCOUNTING, and it is the one resource that reports a `full`
# line without a `some` line.
RESOURCES = ('cpu', 'io', 'irq', 'memory')

# The averaging windows a line carries, oldest kernel first and in the order a report
# lists them. They are read by name and never by position: the number of keys has grown
# before, and a reader going by position publishes one value under the name of another
# as soon as it grows again.
AVERAGE_KEYS = ('avg10', 'avg60', 'avg300')

# What each line means, in the words somebody acting on the number needs. The subject
# of the sentence is completed by the caller with the resource that was waited for.
KIND_LABELS = {
    'full': 'every task with work to do waited',
    'some': 'at least one task waited',
}

# The averaging windows in plain words, so a report does not have to spell out what
# `avg10` covers.
WINDOW_LABELS = {
    'avg10': 'last ten seconds',
    'avg60': 'last minute',
    'avg300': 'last five minutes',
}


def get_perfdata(pressure, kinds, alert_kind, thresholds):
    """
    Build the performance data of a pressure report, one metric per line and
    averaging window.

    Only the values that are actually judged carry their thresholds, so a graph
    does not draw a warning line across the windows nobody alerts on.

    ### Parameters
    - **pressure** (`dict`): A reading as returned by `read()`.
    - **kinds** (`tuple`): The lines to report, in the order they are printed.
    - **alert_kind** (`str`): The line the thresholds belong to.
    - **thresholds** (`dict`): Maps an averaging window to a `(warn, crit)` tuple,
      as handed to `get_states()`.

    ### Returns
    - **str**: The performance data string.

    ### Example
    >>> get_perfdata(pressure, ('some', 'full'), 'full', {'avg60': ('40', '60')})
    "'some_avg10'=0.0%;;;0;100 ..."
    """
    perfdata = ''
    for kind in kinds:
        if kind not in pressure:
            continue
        for window in AVERAGE_KEYS:
            if window not in pressure[kind]:
                continue
            warn, crit = None, None
            if kind == alert_kind and window in thresholds:
                warn, crit = thresholds[window]
            perfdata += base.get_perfdata(
                f'{kind}_{window}',
                pressure[kind][window],
                uom='%',
                warn=warn,
                crit=crit,
                _min=0,
                _max=100,
            )
    return perfdata


def get_states(pressure, kind, thresholds):
    """
    Evaluate one line of a pressure reading against a threshold per averaging
    window.

    ### Parameters
    - **pressure** (`dict`): A reading as returned by `read()`.
    - **kind** (`str`): The line to judge, `full` or `some`.
    - **thresholds** (`dict`): Maps an averaging window to a `(warn, crit)` tuple
      of Nagios range expressions. A bound of `None` is not evaluated.

    ### Returns
    - **dict**: Maps every window that was judged to its state. A window the
      reading does not carry is left out rather than counted as zero.

    ### Example
    >>> get_states(pressure, 'full', {'avg60': ('40', '60')})
    {'avg60': 0}
    """
    states = {}
    for window in AVERAGE_KEYS:
        if window not in thresholds:
            continue
        value = pressure.get(kind, {}).get(window)
        if value is None:
            continue
        warn, crit = thresholds[window]
        states[window] = base.get_state(value, warn, crit, _operator='range')
    return states


def get_summary(
    pressure, resource, waiting_for, kinds, alert_kind, states, window='avg60'
):
    """
    Build the human-readable part of a pressure report: one headline over the
    averaging window that is being judged, plus a line spelling out what the
    kernel's `some` and `full` mean here.

    A window other than `window` shows up in the headline only while it is out of
    its range, so a burst that the longer average smooths away is named at the
    moment it matters and stays out of the way otherwise.

    ### Parameters
    - **pressure** (`dict`): A reading as returned by `read()`.
    - **resource** (`str`): The resource the reading belongs to, used as the
      subject of the headline.
    - **waiting_for** (`str`): What the tasks were waiting for, completing the
      sentences in `KIND_LABELS`, for example `a CPU` or `storage`.
    - **kinds** (`tuple`): The lines to report, in the order they are printed.
    - **alert_kind** (`str`): The line that carries the state markers.
    - **states** (`dict`): Maps an averaging window to its state, as returned by
      `get_states()`.
    - **window** (`str`, optional): The averaging window the headline reports.
      Defaults to `avg60`.

    ### Returns
    - **str**: The headline and the legend, separated by a newline.

    ### Example
    >>> get_summary(pressure, 'io', 'storage', ('some', 'full'), 'full', states)
    'io pressure, last minute: some 18.57%, full 9.76%\\nsome = ...'
    """
    reported = [kind for kind in kinds if kind in pressure]
    msg = f'{resource} pressure, {WINDOW_LABELS[window]}: '
    msg += ', '.join(f'{kind} {pressure[kind][window]}%' for kind in reported)
    if window in states:
        msg += base.state2str(states[window], prefix=' ')
    for other in AVERAGE_KEYS:
        if other == window or states.get(other, STATE_OK) == STATE_OK:
            continue
        msg += f'; {WINDOW_LABELS[other]}: {alert_kind} '
        msg += f'{pressure[alert_kind][other]}%'
        msg += base.state2str(states[other], prefix=' ')
    msg += '\n' + ', '.join(
        f'{kind} = {KIND_LABELS[kind]} for {waiting_for}' for kind in reported
    )
    return msg


def get_table(pressure, kinds, alert_kind, states):
    """
    Build the table of a pressure report: one row per averaging window, one
    column per reported line.

    Order `kinds` so that `alert_kind` comes last. The state marker sits at the
    end of its cell, and a marker that is not at the end of the row breaks the
    alignment of a monospace table wherever a web interface replaces it with an
    icon.

    ### Parameters
    - **pressure** (`dict`): A reading as returned by `read()`.
    - **kinds** (`tuple`): The lines to report, in the order they are printed.
    - **alert_kind** (`str`): The line that carries the state markers.
    - **states** (`dict`): Maps an averaging window to its state, as returned by
      `get_states()`.

    ### Returns
    - **str**: The rendered table.

    ### Example
    >>> print(get_table(pressure, ('some', 'full'), 'full', states))
    Window ! Some  ! Full
    ...
    """
    reported = [kind for kind in kinds if kind in pressure]
    data = []
    for window in AVERAGE_KEYS:
        row = {'window': window}
        for kind in reported:
            value = pressure[kind].get(window)
            if value is None:
                continue
            row[kind] = f'{value}%'
            if kind == alert_kind and window in states:
                row[kind] += base.state2str(states[window], prefix=' ')
        data.append(row)
    return base.get_table(
        data,
        ['window', *reported],
        header=['Window', *[kind.capitalize() for kind in reported]],
    )


def is_enabled(root='/'):
    """
    Whether the kernel keeps pressure statistics at all.

    Tells the two reasons `read()` answers `None` apart: the kernel accounts for
    nothing, or it accounts for other resources but not for the one that was asked
    for. The remedy differs, so a consumer that reports the state has to know which
    of the two it is looking at.

    ### Parameters
    - **root** (`str`, optional): Prefix for the path that is read, so a directory
      tree can stand in for the running system's `/proc`. Defaults to `/`.

    ### Returns
    - **bool**: True where the kernel publishes pressure statistics, which it does
      by creating the directory the per-resource files live in.

    ### Example
    >>> is_enabled()
    True
    """
    return disk.dir_exists(os.path.join(root, PRESSURE_DIR.lstrip('/')))


def _accounting_is_off(path):
    """
    Whether a pressure file exists but the kernel keeps no statistics behind it.

    The kernel creates `/proc/pressure/irq` whenever the accounting is compiled in,
    and then refuses the read with `EOPNOTSUPP` for as long as interrupt time
    accounting is switched off at runtime, which on x86 is what the `tsc=noirqtime`
    boot parameter does. Read against `psi_show()` in `kernel/sched/psi.c` of Linux
    7.1. That is the same "nothing is measured here" state as a file the kernel never
    created, and not a failure worth reporting as one.

    ### Parameters
    - **path** (`str`): The pressure file whose read failed.

    ### Returns
    - **bool**: True if the read failed because the kernel does not keep these
      statistics, False for every other reason.
    """
    try:
        with open(path) as f:
            f.read()
    except OSError as e:
        return e.errno in (errno.ENOTSUP, errno.EOPNOTSUPP)
    except Exception:
        return False
    return False


def read(resource, root='/'):
    """
    Read the pressure stall information of one resource.

    ### Parameters
    - **resource** (`str`): One of `cpu`, `io`, `irq` or `memory`.
    - **root** (`str`, optional): Prefix for the path that is read, so a directory
      tree can stand in for the running system's `/proc`. Defaults to `/`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the file was read or is absent, otherwise
          False.
        - tuple[1] (**dict | None | str**):
          - A mapping of `some` and `full` to their values, each a mapping of
            `avg10`, `avg60` and `avg300` (`float`, percent) and `total` (`int`,
            microseconds since boot). Only the lines the kernel actually prints are
            present.
          - `None` if pressure accounting is unavailable on this system.
          - An error message string if the file exists but could not be read or
            parsed.

    ### Notes
    - `None` is a state and not an error: the kernel exports nothing at all where
      pressure accounting is switched off, and an unprivileged caller cannot tell
      that apart from a kernel built without `CONFIG_PSI`. Booting with `psi=1`
      switches it on where the kernel supports it. A resource whose file exists but
      whose accounting is switched off at runtime reads as `None` as well, because
      it is the same state seen from userspace.
    - `irq` is the one resource that reports a `full` line without a `some` line, and
      the only one whose file the kernel may refuse to read. It needs
      `CONFIG_IRQ_TIME_ACCOUNTING` and a kernel that carries the accounting, which
      upstream has since 6.1.
    - The `full` line of the `cpu` resource is undefined at the system level. The
      kernel has been printing it as a hardcoded zero since v5.13 for backward
      compatibility and left it out before that, so a consumer must not read a
      meaning into it either way.
    - An unknown resource name is rejected rather than turned into a path, so a
      caller cannot reach outside `/proc/pressure`.

    ### Example
    >>> success, pressure = read('io')
    >>> pressure['full']['avg60']
    3.04
    """
    if resource not in RESOURCES:
        return (False, f'"{resource}" is not a resource the kernel accounts for.')
    path = os.path.join(root, PRESSURE_DIR.lstrip('/'), resource)
    # Files below /proc report a size of zero, so their presence has to be probed
    # allowing an empty file.
    if not disk.file_exists(path, allow_empty=True):
        return (True, None)
    success, content = disk.read_file(path)
    if not success:
        if _accounting_is_off(path):
            return (True, None)
        return (False, content)
    pressure = {}
    for line in content.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        values = {}
        for field in fields[1:]:
            key, _, value = field.partition('=')
            if key in AVERAGE_KEYS:
                try:
                    values[key] = float(value)
                except ValueError:
                    return (False, f'{path} reports "{field}", which is no average.')
            elif key == 'total':
                try:
                    values['total'] = int(value)
                except ValueError:
                    return (False, f'{path} reports "{field}", which is no duration.')
        pressure[fields[0]] = values
    if not pressure:
        return (False, f'{path} holds no pressure values.')
    return (True, pressure)
