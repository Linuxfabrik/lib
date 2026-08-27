#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library reads the LVM configuration of a host through `lvs` and `vgs`, and
turns their report into the facts a consumer needs to judge it.

Both commands need root: `/run/lvm` and `/run/lock/lvm` are `0700 root`, and
`/dev/mapper/control` is `0600 root:root`, so an unprivileged `lvs` exits 5 on the
global lock and `dmsetup` cannot reach the driver at all. Membership of the `disk`
group does not change that. Measured on Rocky 10 (lvm2 2.03.28) and Debian 13
(lvm2 2.03.31).

Both commands are asked for their report as JSON, which keeps the numbers on stdout
and the warnings LVM writes to stderr out of the way. Each is a fixed argument list,
so a sudo rule can spell the command out instead of ending in a wildcard. Every field
they ask for, `--reportformat json` and `--nosuffix` among them, exists in lvm2 2.03.14
(the oldest still in service) and has not been renamed since.

The report is read one row per logical volume. A segment-level field such as
`segtype` would turn that into one row per *segment*, so a volume spanning two
physical volumes would be counted twice; `lv_layout` carries the same information
per volume and is used in its place.

`health()` puts a value of `lv_health_status` into words. That field is the whole
truth for a thin pool, a cache and a volume with a missing physical volume, and
covers none of what happens to a classic snapshot: a snapshot the kernel threw away
because its copy-on-write store ran full leaves `lv_health_status` empty and says so
through `lv_snapshot_invalid` alone.

`metadata_limit()` answers at which fill level LVM stops creating thin volumes in a
pool, which happens well before its metadata is full.

Typical use case:
```python
    volumes = lib.base.coe(lib.lvm.get_logical_volumes(timeout=8))
    for lv in volumes:
        if lib.lvm.is_thin_pool(lv):
            print(lv['lv_full_name'], lv['data_percent'], lv['metadata_percent'])
```
"""

import json

from . import shell, time
from .globals import STATE_UNKNOWN, STATE_WARN

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082701'

# The fields read per logical volume, sorted, and every one of them a volume-level
# field so the report stays at one row per volume.
LV_FIELDS = (
    'data_percent',
    'lv_active',
    'lv_attr',
    'lv_check_needed',
    'lv_full_name',
    'lv_health_status',
    'lv_layout',
    'lv_merge_failed',
    'lv_metadata_size',
    'lv_name',
    'lv_role',
    'lv_size',
    'lv_snapshot_invalid',
    'lv_time',
    'lv_when_full',
    'metadata_percent',
    'origin',
    'pool_lv',
    'vg_name',
)

# The fields read per volume group, sorted.
VG_FIELDS = (
    'lv_count',
    'pv_count',
    'snap_count',
    'vg_attr',
    'vg_extent_size',
    'vg_free',
    'vg_missing_pv_count',
    'vg_name',
    'vg_size',
)

# Sizes are asked for in bytes without a unit suffix, so they arrive as plain numbers
# rather than as `4.00g` in whatever unit LVM felt like using.
LVS_COMMAND = (
    'lvs',
    '--reportformat',
    'json',
    '--units',
    'b',
    '--nosuffix',
    '--options',
    ','.join(LV_FIELDS),
)

VGS_COMMAND = (
    'vgs',
    '--reportformat',
    'json',
    '--units',
    'b',
    '--nosuffix',
    '--options',
    ','.join(VG_FIELDS),
)

# Every value `lv_health_status` can take, from `_lvhealthstatus_disp()` in
# `lib/report/report.c`, put into the words somebody acting on it needs. `partial` is
# tested before every other case in LVM itself, so a RAID volume whose leg has gone
# missing reports `partial` and never `refresh needed`.
#
# `repair needed` and `refresh or repair needed` arrived in lvm2 2.03.39 (2026-03) and
# exist in no earlier release: up to and including 2.03.38, a RAID leg the kernel has
# marked dead is `refresh needed` whether its device is back or gone for good. Measured
# on 2.03.28, where `vgreduce --removemissing` leaves a virtual error segment behind and
# the volume still reports `refresh needed`. Both are carried here so a host on a newer
# LVM is not reported as being in a state this does not know.
HEALTH_LABELS = {
    'error': 'the writecache is erroring',
    'failed': 'the pool has failed and answers nothing',
    'metadata_read_only': (
        'the pool metadata is full, so the pool has gone read-only and every write to '
        'it fails'
    ),
    'mismatches exist': 'a scrub found blocks whose copies disagree',
    'out_of_data': (
        'the pool is out of data space, so every write to a volume in it is queued and '
        'then failed'
    ),
    'partial': 'one of the physical volumes it sits on is missing',
    'refresh needed': 'a device came back and the array has not been refreshed onto it',
    'refresh or repair needed': 'the array needs a refresh or a repair',
    'repair needed': 'the array needs a repair',
    'unknown': 'the state of the array could not be read',
    'writemostly': 'a leg is marked write-mostly and is read from only as a last resort',
}

# How much free metadata LVM insists on before it will create another thin volume or
# snapshot in a pool, from `thin_pool_metadata_min_threshold()` in
# `lib/metadata/thin_manip.c`: the smaller of 4 MiB and a quarter of the metadata
# volume. Measured on lvm2 2.03.28: at 75.10% of a 4 MiB metadata volume, `lvcreate`
# refuses with "free space in thin pool reached threshold" while the pool itself is
# still perfectly healthy.
METADATA_HEADROOM_BYTES = 4 * 1024**2
METADATA_HEADROOM_PERCENT = 25

# How LVM renders `lv_time`, from the default of `report/time_format` in
# `lib/config/defaults.h`. `%T` and the numeric offset are not locale-dependent, and
# the commands run under `LC_ALL=C` anyway, so this parses on any host that has not
# changed the setting.
TIME_FORMAT = '%Y-%m-%d %H:%M:%S %z'

# The three ways reading LVM fails, each opening the message it produces. What they
# say is about the host and not about the check, which is why `failure_state()` rates
# two of them as a problem to fix rather than as a check that could not run.
NO_ANSWER = 'LVM did not answer'
NOT_INSTALLED = 'The LVM tools are not installed on this host'
NO_PERMISSION = 'LVM refused to report as this user'

# What to tell somebody whose host has no LVM tools.
NOT_INSTALLED_HELP = (
    f'{NOT_INSTALLED}. Install them (`dnf install lvm2` on the Red Hat family, '
    '`apt install lvm2` on the Debian family), or stop reading LVM on this host.'
)

# What to tell somebody whose LVM did not answer. A command that reads LVM touches
# every physical volume on the host, and one that does not answer puts it into an
# uninterruptible sleep no signal ends. Naming a single volume group does not avoid
# it, because the volume group is found by scanning all of them.
NO_ANSWER_HELP = (
    'LVM reads every physical volume on this host, so one of them that has stopped '
    'answering blocks the whole command. `lsblk`, `dmesg` and the logs of the '
    'storage transport say which device it is; `pvs` will answer again once it is '
    'back or has been removed from the volume group with `vgreduce --removemissing`.'
)

# What to tell somebody who ran this without the rights it needs. LVM answers such a
# run with an empty report and the lock file it could not open, which is worth naming
# once here rather than quoting back on every run.
NO_PERMISSION_HELP = (
    f'{NO_PERMISSION}. Reading the volumes needs root, because `/run/lock/lvm` and '
    '`/dev/mapper/control` are readable by root alone and no supplementary group '
    'changes that. Run it through sudo, and deploy the sudoers rule that comes with '
    'the check.'
)


def created(lv):
    """
    Read when a volume was created, as a UNIX epoch timestamp.

    LVM renders `lv_time` with the pattern in `report/time_format`, whose default
    (`%Y-%m-%d %T %z`) carries no locale-dependent part. A host that has changed the
    setting, and a volume created before LVM started recording the time at all, yield
    None rather than a wrong number.

    ### Parameters
    - **lv** (`dict`): One row of `get_logical_volumes()`.

    ### Returns
    - **float** or **None**: The timestamp, or None where it could not be read.

    ### Example
    >>> created({'lv_time': '2026-08-27 11:19:13 +0200'})
    1787822353.0
    """
    value = (lv.get('lv_time') or '').strip()
    if not value:
        return None
    try:
        return time.timestr2epoch(value, pattern=TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def failure_state(message):
    """
    Rate a failure to read LVM.

    A host whose LVM has stopped answering, and one that carries no LVM tools although
    something is asking it about its volumes, both have a problem that belongs on the
    list of things to fix. Everything else - no rights, a report that will not parse -
    is the reading that is broken and says nothing about the host, which is what
    UNKNOWN is for.

    ### Parameters
    - **message** (`str`): The message one of the reading functions returned.

    ### Returns
    - **int**: `STATE_WARN` or `STATE_UNKNOWN`.

    ### Example
    >>> failure_state('LVM did not answer within 8s. ...') == STATE_WARN
    True
    """
    if (message or '').startswith((NO_ANSWER, NOT_INSTALLED)):
        return STATE_WARN
    return STATE_UNKNOWN


def get_logical_volumes(timeout=8):
    """
    Ask LVM for the logical volumes of this host.

    ### Parameters
    - **timeout** (`int`, optional): Seconds the command is given. Defaults to 8.

    ### Returns
    - **tuple**:
      - On success: `(True, list)` - one dict per logical volume, keyed by the field
        names in `LV_FIELDS`. An empty list means the host has no logical volume.
      - On failure: `(False, error_message)`.

    ### Example
    >>> get_logical_volumes()
    (True, [{'lv_full_name': 'vg0/root', 'lv_attr': '-wi-ao----', ...}])
    """
    return _run(LVS_COMMAND, 'lv', timeout)


def get_volume_groups(timeout=8):
    """
    Ask LVM for the volume groups of this host.

    ### Parameters
    - **timeout** (`int`, optional): Seconds the command is given. Defaults to 8.

    ### Returns
    - **tuple**:
      - On success: `(True, list)` - one dict per volume group, keyed by the field
        names in `VG_FIELDS`. An empty list means the host has no volume group.
      - On failure: `(False, error_message)`.

    ### Example
    >>> get_volume_groups()
    (True, [{'vg_name': 'vg0', 'vg_size': '107369988096', 'vg_free': '0', ...}])
    """
    return _run(VGS_COMMAND, 'vg', timeout)


def health(lv):
    """
    Say what is wrong with a volume, in one clause and without a subject.

    Covers `lv_health_status` and the two states LVM reports beside it: a classic
    snapshot the kernel threw away, and a snapshot whose merge back into its origin
    failed. Both leave `lv_health_status` empty.

    ### Parameters
    - **lv** (`dict`): One row of `get_logical_volumes()`.

    ### Returns
    - **str**: The clause, or an empty string when nothing is wrong.

    ### Example
    >>> health({'lv_health_status': 'out_of_data'})
    'the pool is out of data space, so every write to a volume in it is queued and then failed'
    """
    if is_snapshot_invalid(lv):
        return 'its copy-on-write store ran full and the kernel threw it away'
    if lv.get('lv_merge_failed') == 'merge failed':
        return 'merging it back into its origin failed'
    if lv.get('lv_check_needed') == 'check needed':
        return 'the pool is flagged as needing a check before it is used again'
    status = lv.get('lv_health_status') or ''
    if not status:
        return ''
    # An unknown value is reported rather than swallowed: LVM has added values to this
    # field before, and a check that only knows the ones it was written against would
    # report a volume in a state it does not recognise as healthy.
    return HEALTH_LABELS.get(status, f'LVM reports it as "{status}"')


def is_snapshot(lv):
    """
    Tell a snapshot, of either kind, from everything else.

    ### Parameters
    - **lv** (`dict`): One row of `get_logical_volumes()`.

    ### Returns
    - **bool**

    ### Example
    >>> is_snapshot({'lv_role': 'public,snapshot,thicksnapshot'})
    True
    """
    return 'snapshot' in _roles(lv)


def is_snapshot_invalid(lv):
    """
    Tell whether the kernel has thrown a classic snapshot away.

    This is the state a full copy-on-write store ends in. The origin keeps running,
    the snapshot answers every read with an I/O error, and `lv_health_status` says
    nothing about it.

    ### Parameters
    - **lv** (`dict`): One row of `get_logical_volumes()`.

    ### Returns
    - **bool**

    ### Example
    >>> is_snapshot_invalid({'lv_snapshot_invalid': 'snapshot invalid'})
    True
    """
    return lv.get('lv_snapshot_invalid') == 'snapshot invalid'


def is_thin(lv):
    """
    Tell a thin volume from a thick one. A thin pool is not a thin volume.

    ### Parameters
    - **lv** (`dict`): One row of `get_logical_volumes()`.

    ### Returns
    - **bool**

    ### Example
    >>> is_thin({'lv_layout': 'thin,sparse'})
    True
    """
    layout = _layout(lv)
    return 'thin' in layout and 'pool' not in layout


def is_thin_pool(lv):
    """
    Tell a thin pool from every other volume.

    ### Parameters
    - **lv** (`dict`): One row of `get_logical_volumes()`.

    ### Returns
    - **bool**

    ### Example
    >>> is_thin_pool({'lv_layout': 'thin,pool'})
    True
    """
    layout = _layout(lv)
    return 'thin' in layout and 'pool' in layout


def metadata_limit(metadata_size):
    """
    Answer at which metadata fill level LVM refuses to create another thin volume or
    snapshot in a pool.

    LVM keeps back the smaller of 4 MiB and a quarter of the metadata volume, so the
    limit is 75% for a metadata volume of 16 MiB or less and rises towards 100% for
    larger ones. A pool that has reached it is fully functional and still cannot take
    another snapshot, which is why it deserves an answer of its own rather than a flat
    percentage everywhere.

    ### Parameters
    - **metadata_size** (`int` or `str`): Size of the metadata volume in bytes, as
      `lv_metadata_size` reports it.

    ### Returns
    - **float** or **None**: The limit in percent, or None where the size is unknown.

    ### Example
    >>> metadata_limit(4 * 1024**2)
    75.0
    >>> metadata_limit(64 * 1024**2)
    93.75
    """
    size = to_number(metadata_size)
    if not size:
        return None
    headroom = min(
        METADATA_HEADROOM_PERCENT,
        METADATA_HEADROOM_BYTES / size * 100,
    )
    return 100 - headroom


def parse_report(stdout, section):
    """
    Read the rows out of an LVM JSON report.

    ### Parameters
    - **stdout** (`str`): What the command printed on stdout.
    - **section** (`str`): The report section to read, `lv` or `vg`.

    ### Returns
    - **tuple**:
      - On success: `(True, list)` - one dict per row.
      - On failure: `(False, error_message)`.

    ### Example
    >>> parse_report('{"report": [{"lv": [{"lv_name": "root"}]}]}', 'lv')
    (True, [{'lv_name': 'root'}])
    """
    try:
        data = json.loads(stdout)
    except (AttributeError, TypeError, ValueError):
        return (False, 'Unable to read the LVM report.')
    rows = []
    for report in data.get('report') or []:
        rows.extend(report.get(section) or [])
    return (True, rows)


def to_number(value):
    """
    Read one value of an LVM report as a number.

    LVM leaves a field that does not apply to a volume empty rather than reporting a
    zero, so an empty percentage means "not measured here" and never "nothing used".

    ### Parameters
    - **value** (`str`): The reported value.

    ### Returns
    - **float** or **None**: The number, or None where the field was empty or not a
      number.

    ### Example
    >>> to_number('74.34')
    74.34
    >>> to_number('') is None
    True
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _diagnosis(stdout, stderr):
    """
    Pick the lines worth quoting out of a run that failed.

    LVM puts its messages both on stderr and into the `log` array of the report, and
    the report itself is the last thing worth printing back at somebody. This takes
    the log messages where the report parses, falls back to stderr otherwise, and
    keeps the result to one line.
    """
    lines = []
    try:
        for entry in json.loads(stdout).get('log') or []:
            message = (entry.get('log_message') or '').strip()
            if message:
                lines.append(message)
    except (AttributeError, TypeError, ValueError):
        pass
    if not lines:
        lines = [line.strip() for line in (stderr or '').splitlines() if line.strip()]
    return ' '.join(' '.join(lines).split())[:300]


def _layout(lv):
    """Split `lv_layout` into its parts."""
    return (lv.get('lv_layout') or '').split(',')


def _roles(lv):
    """Split `lv_role` into its parts."""
    return (lv.get('lv_role') or '').split(',')


def _run(cmd, section, timeout):
    """Run one LVM reporting command and read its report."""
    success, result = shell.shell_exec(list(cmd), timeout=timeout)
    if not success:
        if 'Timeout after' in result:
            return (False, f'{NO_ANSWER} within {timeout}s. {NO_ANSWER_HELP}')
        if 'No such file or directory' in result:
            return (False, NOT_INSTALLED_HELP)
        return (False, result)
    stdout, stderr, retc = result
    if retc != 0:
        # LVM writes warnings to stderr even on a successful run, so its text is only
        # worth reporting where the command actually failed. What it failed at has to
        # be read from that text and never from the exit code: `ECMD_FAILED` in
        # `tools/errors.h` is 5 and covers every failure alike, so a volume group that
        # does not exist and a run without the rights both end in 5. Measured on
        # lvm2 2.03.28: `lvs no-such-vg`, `lvs -o no_such_field` and an unprivileged
        # `lvs` all exit 5.
        text = f'{stderr}{stdout}'
        if 'Permission denied' in text or 'Running as a non-root user' in text:
            return (False, NO_PERMISSION_HELP)
        return (False, f'LVM did not report: {_diagnosis(stdout, stderr)}')
    return parse_report(stdout, section)
