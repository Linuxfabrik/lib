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

Typical use case:
```python
    pressure = lib.base.coe(lib.psi.read('memory'))
    if pressure is None:
        print('Pressure stall information is switched off in this kernel.')
    else:
        print(pressure['full']['avg60'])
```
"""

import os

from . import disk

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082501'

# The kernel creates this directory only where pressure accounting is switched on, so
# its absence is the normal state of a kernel built with CONFIG_PSI_DEFAULT_DISABLED
# and booted without `psi=1`, which is what the whole Red Hat family ships.
PRESSURE_DIR = '/proc/pressure'

# The resources the kernel accounts for. `irq` exists only where the kernel was built
# with CONFIG_IRQ_TIME_ACCOUNTING, and it is the one resource that reports a `full`
# line without a `some` line.
RESOURCES = ('cpu', 'io', 'irq', 'memory')

# The keys a line carries. They are read by name and never by position: the number of
# keys has grown before, and a reader going by position publishes one value under the
# name of another as soon as it grows again.
_AVERAGE_KEYS = ('avg10', 'avg60', 'avg300')


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
      switches it on where the kernel supports it.
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
        return (False, content)
    pressure = {}
    for line in content.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        values = {}
        for field in fields[1:]:
            key, _, value = field.partition('=')
            if key in _AVERAGE_KEYS:
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
