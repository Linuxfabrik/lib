#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library parses data returned from the Redfish API."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082502'

import atexit
import base64
import json
import os
import sys
import urllib.parse

from . import base, cache, db_sqlite, disk, human, time, txt, url
from .globals import STATE_CRIT, STATE_OK, STATE_WARN

# Shared cache database filename for the Redfish fetch layer. The fetch helpers below cache by URL,
# but only when a caller opts in by passing a non-zero `cache_expire`; with the default
# `cache_expire=0` they fetch straight through and touch no cache. Several consumers read the
# same data from one controller each cycle (its session token, its `$expand` support, the
# Systems or Managers collection and their members), so the first one to miss the cache fetches
# and fills it and every sibling reuses the entry instead of hitting the controller again.
# Kept out of the default cache database so those response bodies do not mingle with other cached
# data. Named here so every consumer and this library agree on the same file and can share
# entries.
CACHE_FILENAME = 'linuxfabrik-monitoring-plugins-redfish.db'

# Upper bound for the Redfish `$expand` `$levels` we ask for, even when a controller advertises a
# higher `MaxLevels`. A single deeply expanded document already inlines every member a caller reads;
# going deeper only inflates the response (and the controller's work) without a caller that needs
# it. Three levels reach the deepest tree we walk (Systems -> Storage -> Drives/Volumes).
MAX_EXPAND_LEVELS = 3

# `$expand` suffix used when the controller does not advertise its expand support (or the service
# root cannot be read): ask for one level of subordinate members. `fetch_collection()` falls back
# to a plain request if the controller rejects it, so this stays safe on controllers without
# `$expand`.
DEFAULT_EXPAND = '?$expand=.($levels=1)'

# File the diagnostic trace is written to, inside the same per-user directory as the cache
# database. The trace is a support aid: it records what this library asked the controller for,
# how long each request took and which path the authentication took, so a slow or flapping run
# can be diagnosed from one file instead of from a dozen hand-run curl commands. A consumer
# writes it only when its `--verbose` switch turned the trace on; otherwise the trace costs one
# `if` per request and nothing is opened. See `start_trace()` for why this goes to a file rather
# than to the caller's output.
# Upper bound for the extra attempts a login is given, however high a caller's own retry budget
# is. A login is not a read: a controller creates the session before it answers, so an attempt the
# client abandons on timeout still leaves a session behind on the controller (measured: three
# attempts against a controller answering slower than the timeout left three sessions). Retrying a
# login as often as a GET would therefore exhaust the controller's session pool, which is the very
# condition that makes logins fail. Two extra attempts cover a dropped request without turning a
# slow controller into a flooded one.
MAX_LOGIN_RETRIES = 2

TRACE_FILENAME = 'linuxfabrik-monitoring-plugins-redfish-trace.log'

# Sentence a consumer appends to its own `--verbose` help, so every Redfish consumer describes
# the trace in the same words and an admin is told where to look before it has run once. Kept
# free of a literal '%', which argparse would try to expand.
TRACE_HELP = (
    'For this check that also writes a trace of every Redfish request, with timings, to '
    + TRACE_FILENAME
    + " below the temporary directory. Unlike this check's output, the trace survives a check "
    'that the monitoring server terminates for exceeding its timeout, which is what makes it '
    'useful against a slow management controller.'
)

# Upper bound for the trace file, in bytes. A caller that runs every minute would otherwise fill
# the temporary directory while an admin leaves `--verbose` on over a weekend. Once the file has
# grown past this, `start_trace()` refuses instead of appending, so an admin is told to move the
# file away rather than losing the temporary directory to it.
TRACE_MAX_BYTES = 10 * 1024 * 1024

CHASSIS_FAN_KEYS = (
    'FanName',
    'HotPluggable',
    'LowerThresholdCritical',
    'LowerThresholdFatal',
    'LowerThresholdNonCritical',
    'Name',
    'PhysicalContext',
    'Reading',
    'ReadingUnits',
    'SensorNumber',
    'UpperThresholdCritical',
    'UpperThresholdFatal',
    'UpperThresholdNonCritical',
)

CHASSIS_FAN_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_KEYS = (
    'AssetTag',
    'ChassisType',
    'Id',
    'IndicatorLED',
    'Manufacturer',
    'Model',
    'PartNumber',
    'PowerState',
    'SerialNumber',
    'SKU',
)

CHASSIS_NESTED_KEYS = {
    'Sensors_@odata.id': ('Sensors', '@odata.id'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

CHASSIS_POWER_CONTROL_KEYS = (
    'MemberId',
    'Name',
    'PowerCapacityWatts',
    'PowerConsumedWatts',
)

CHASSIS_POWER_CONTROL_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_POWER_KEYS = (
    'FirmwareVersion',
    'LastPowerOutputWatts',
    'LineInputVoltage',
    'LineInputVoltageType',
    'Manufacturer',
    'Model',
    'PartNumber',
    'PowerCapacityWatts',
    'PowerSupplyType',
    'SerialNumber',
    'SparePartNumber',
)

CHASSIS_POWER_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_SENSOR_KEYS = (
    'Id',
    'Name',
    'PhysicalContext',
    'Reading',
    'ReadingRangeMax',
    'ReadingRangeMin',
    'ReadingUnits',
)

CHASSIS_SENSOR_NESTED_KEYS = {
    'Thresholds_LowerCaution': ('Thresholds', 'LowerCaution', 'Reading'),
    'Thresholds_LowerCautionUser': ('Thresholds', 'LowerCautionUser', 'Reading'),
    'Thresholds_LowerCritical': ('Thresholds', 'LowerCritical', 'Reading'),
    'Thresholds_LowerCriticalUser': ('Thresholds', 'LowerCriticalUser', 'Reading'),
    'Thresholds_UpperCaution': ('Thresholds', 'UpperCaution', 'Reading'),
    'Thresholds_UpperCautionUser': ('Thresholds', 'UpperCautionUser', 'Reading'),
    'Thresholds_UpperCritical': ('Thresholds', 'UpperCritical', 'Reading'),
    'Thresholds_UpperCriticalUser': ('Thresholds', 'UpperCriticalUser', 'Reading'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

CHASSIS_THERMAL_REDUNDANCY_KEYS = ('Mode', 'Name')

CHASSIS_THERMAL_REDUNDANCY_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_THERMAL_TEMP_KEYS = (
    'LowerThresholdCritical',
    'LowerThresholdFatal',
    'LowerThresholdNonCritical',
    'Name',
    'PhysicalContext',
    'ReadingCelsius',
    'UpperThresholdCritical',
    'UpperThresholdFatal',
    'UpperThresholdNonCritical',
)

CHASSIS_THERMAL_TEMP_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_VOLTAGE_KEYS = (
    'LowerThresholdCritical',
    'LowerThresholdFatal',
    'LowerThresholdNonCritical',
    'Name',
    'PhysicalContext',
    'ReadingVolts',
    'UpperThresholdCritical',
    'UpperThresholdFatal',
    'UpperThresholdNonCritical',
)

CHASSIS_VOLTAGE_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

ETHERNET_KEYS = (
    'Description',
    'FQDN',
    'FullDuplex',
    'HostName',
    'Id',
    'LinkStatus',
    'MACAddress',
    'Name',
    'PermanentMACAddress',
    'SpeedMbps',
)

ETHERNET_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

FIRMWARE_KEYS = (
    'Id',
    'Manufacturer',
    'Name',
    'ReleaseDate',
    'SoftwareId',
    'Updateable',
    'Version',
)

FIRMWARE_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

MANAGER_KEYS = (
    'FirmwareVersion',
    'Id',
    'ManagerType',
    'Model',
    'Name',
    'PowerState',
    'UUID',
)

MANAGER_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

MEMORY_KEYS = (
    'BaseModuleType',
    'CapacityMiB',
    'ErrorCorrection',
    'Id',
    'Manufacturer',
    'MemoryDeviceType',
    'MemoryType',
    'Name',
    'OperatingSpeedMhz',
    'PartNumber',
    'RankCount',
    'SerialNumber',
)

MEMORY_NESTED_KEYS = {
    'Location_ServiceLabel': ('Location', 'PartLocation', 'ServiceLabel'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

# Some controllers leave the standard Status.State/Health empty on memory
# modules and report the real condition only in an OEM-specific field. These
# tables fold those vendor operational values back onto the standard Redfish
# vocabulary so the generic get_state() can evaluate them. Modules in an absent
# state are skipped by the callers; healthy operational states map to "Enabled",
# everything else is surfaced as a problem.
MEMORY_OEM_ABSENT_STATES = ('Absent', 'EmptyOrNotInstalled', 'NotPresent')
MEMORY_OEM_HEALTHY_HEALTH = ('enabled', 'nominal', 'ok')
MEMORY_OEM_HEALTHY_STATES = ('Enabled', 'GoodInUse', 'Operable', 'Quiesced')

PROCESSOR_KEYS = (
    'Id',
    'InstructionSet',
    'Manufacturer',
    'MaxSpeedMHz',
    'Model',
    'Name',
    'ProcessorArchitecture',
    'ProcessorType',
    'Socket',
    'TotalCores',
    'TotalThreads',
)

PROCESSOR_NESTED_KEYS = {
    'Location_ServiceLabel': ('Location', 'PartLocation', 'ServiceLabel'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

SEVERITY_TO_STATE = {
    'critical': STATE_CRIT,
    'warning': STATE_WARN,
}

SYSTEMS_KEYS = (
    'BiosVersion',
    'HostName',
    'Id',
    'IndicatorLED',
    'Manufacturer',
    'Model',
    'PowerState',
    'SerialNumber',
    'SKU',
)

SYSTEMS_NESTED_KEYS = {
    'EthernetInterfaces_@odata.id': ('EthernetInterfaces', '@odata.id'),
    'Memory_@odata.id': ('Memory', '@odata.id'),
    'Processors_@odata.id': ('Processors', '@odata.id'),
    'ProcessorSummary_Count': ('ProcessorSummary', 'Count'),
    'ProcessorSummary_LogicalProcessorCount': (
        'ProcessorSummary',
        'LogicalProcessorCount',
    ),
    'ProcessorSummary_Model': ('ProcessorSummary', 'Model'),
    'Storage_@odata.id': ('Storage', '@odata.id'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

SYSTEMS_STORAGE_DRIVES_KEYS = (
    'BlockSizeBytes',
    'CapableSpeedGbs',
    'Description',
    'EncryptionAbility',
    'EncryptionStatus',
    'FailurePredicted',
    'HotspareType',
    'Id',
    'Manufacturer',
    'MediaType',
    'Model',
    'Name',
    'NegotiatedSpeedGbs',
    'PartNumber',
    'PowerOnHours',
    'PredictedMediaLifeLeftPercent',
    'Protocol',
    'Revision',
    'RotationSpeedRPM',
    'SerialNumber',
    'WriteCacheEnabled',
)

SYSTEMS_STORAGE_DRIVES_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

SYSTEMS_STORAGE_KEYS = ('Description', 'Drives@odata.count', 'Id', 'Name')

SYSTEMS_STORAGE_NESTED_KEYS = {
    'Volumes_@odata.id': ('Volumes', '@odata.id'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

VOLUME_KEYS = (
    'CapacityBytes',
    'Encrypted',
    'Id',
    'Name',
    'RAIDType',
    'VolumeType',
)

VOLUME_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}


# Diagnostic trace state. `_TRACE['fd']` is the open trace file descriptor and doubles as the
# on/off switch: everything below returns immediately while it is None, which is every run that
# did not call `start_trace()`.
_TRACE = {
    'fd': None,
    'path': '',
    'started': 0.0,
    'requests': 0,
    'seconds': 0.0,
    # per request kind: [count, seconds], so the summary can say where the time actually went
    'by_kind': {},
}


def _trace_timestamp():
    """Return the current local time as `YYYY-MM-DD HH:MM:SS.mmm`.

    Millisecond resolution, because the point of the trace is to tell a request that took 200 ms
    apart from one that took 8 s, and because the gap between two consecutive lines is what
    reveals time spent outside the requests.
    """
    return time.now(as_type='datetime').strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def _trace_pid():
    """Return the current process id, padded, for the trace's second column.

    A host's Redfish consumers are scheduled together and append to the same file, so their
    lines interleave. Without a process id on every line the file cannot be split back into the
    runs it came from, and a `+12.000s` from one run reads as if it belonged to another. With it,
    `grep` on one id yields one run.
    """
    return f'{os.getpid():>7}'


def _trace(event, detail):
    """Append one line to the trace file, if the trace is on.

    The line carries an absolute timestamp, the seconds elapsed since `start_trace()`, a
    fixed-width event name and a free-form detail, so an admin can both read it top to bottom and
    `grep`/`awk` it by column.

    Every line is passed through `txt.sanitize_sensitive_data()` before it is written. Callers
    are expected to keep credentials out of the detail in the first place (this module never
    passes a request header, a request body or a session token in here), but the trace is a file
    an admin mails to a bug tracker, so the redaction is applied unconditionally as a second
    line of defence.

    Failures are swallowed: a diagnostic aid must never turn a working check into an UNKNOWN
    because the temporary directory filled up mid-run.
    """
    if _TRACE['fd'] is None:
        return
    elapsed = time.now(as_type='float') - _TRACE['started']
    line = f'{_trace_timestamp()}  {_trace_pid()}  +{elapsed:7.3f}s  {event:<9}  {detail}\n'
    try:
        os.write(_TRACE['fd'], txt.sanitize_sensitive_data(line).encode('utf-8'))
    except OSError:
        pass


def _trace_summary():
    """Write the closing summary and close the trace file. Registered with `atexit`.

    Runs on a normal exit and on `sys.exit()`, but not when the process is killed by a signal,
    which is exactly the case this trace exists for. That is why every line above is written and
    flushed as it happens (unbuffered `os.write()`) instead of being collected and printed at the
    end: a run terminated from outside for exceeding a timeout still leaves a complete trace up
    to the moment it was killed, just without this summary. A trace whose last line is a request
    that never completed is the finding.
    """
    if _TRACE['fd'] is None:
        return
    wall = time.now(as_type='float') - _TRACE['started']
    other = wall - _TRACE['seconds']
    _trace(
        'summary',
        f'{_TRACE["requests"]} requests, {_TRACE["seconds"]:.3f}s waiting for the '
        f'controller, {other:.3f}s elsewhere, {wall:.3f}s total',
    )
    # Break the controller time down by what was being read. This is the line that names the
    # culprit: 60 member requests worth 55s say the collection was not inlined, while a single
    # login worth 55s says the controller is slow to authenticate.
    for kind, (count, seconds) in sorted(
        _TRACE['by_kind'].items(), key=lambda item: item[1][1], reverse=True
    ):
        share = 100 * seconds / wall if wall > 0 else 0
        _trace(
            'summary',
            f'  {seconds:8.3f}s ({share:4.1f}% of the run) in {count} {kind} '
            f'request(s), {seconds / count:.3f}s each on average',
        )
    try:
        os.close(_TRACE['fd'])
    except OSError:
        pass
    _TRACE['fd'] = None


def start_trace(path='', filename=TRACE_FILENAME):
    """
    Start writing a diagnostic trace of every Redfish request this run makes.

    Turn this on from a `--verbose` switch. It records, line by line and with millisecond
    timestamps, which URL was requested with which timeout and retry budget, how long the
    controller took to answer, whether an answer came from the shared cache, which `$expand`
    support the controller advertised, whether its members arrived inlined or had to be fetched
    one by one, and which of the three authentication paths (cached token, fresh session, Basic
    fallback) the run took. Between them, those lines answer why a run against a slow management
    controller takes long, without an admin having to reproduce the walk by hand.

    The trace goes to a file rather than to the caller's output on purpose. A run that takes long
    enough to be diagnosed is usually one that is terminated from outside with `SIGTERM`, and a
    terminated run produces no output at all: whatever it would have printed dies with it. The
    file is written as the run progresses, so it survives that termination and still shows where
    the time went.

    The file lives in the same per-user, `0700` directory as the cache database, and is created
    with `0600` and `O_NOFOLLOW`, so a symlink planted at a predictable path under a shared
    temporary directory cannot redirect the write (CWE-59/CWE-377, the same reasoning as
    `db_sqlite.get_db_dir()`).

    Repeated runs append, so a flapping check can be left tracing for several cycles and compared
    across them; a header line separates the runs. Once the file has grown past
    `TRACE_MAX_BYTES` this refuses instead of appending.

    ### Parameters
    - **path** (`str`, optional): Directory to place the trace file in. Defaults to the system
      temporary directory.
    - **filename** (`str`, optional): Name of the trace file (a plain basename).
      Defaults to `TRACE_FILENAME`.

    ### Returns
    - **tuple** (`bool`, `str`):
      - `(True, path)` with the absolute path of the trace file on success. Tell the admin where
        it is: a trace nobody can find is not a diagnostic.
      - `(False, error)` if the file cannot be opened, so a `--verbose` run that silently traces
        nowhere is impossible.

    ### Example
    >>> success, trace_path = start_trace()
    >>> success
    True
    """
    if _TRACE['fd'] is not None:
        return True, _TRACE['path']
    if filename in ('.', '..') or os.path.basename(filename) != filename:
        return False, f'Refusing unsafe trace filename: {filename!r}'
    if not path:
        path = disk.get_tmpdir()
    # Reuse the hardened per-user directory the cache database already lives in, so the trace
    # inherits its ownership and permission checks instead of repeating them here.
    success, trace_dir = db_sqlite.get_db_dir(path)
    if not success:
        return False, trace_dir
    trace_path = os.path.join(trace_dir, filename)
    try:
        size = os.path.getsize(trace_path)
    except OSError:
        size = 0
    if size > TRACE_MAX_BYTES:
        return False, (
            f'Trace file {trace_path} has grown past {human.bytes2human(TRACE_MAX_BYTES)}, '
            f'refusing to append. Move it away to start a new one.'
        )
    try:
        # O_NOFOLLOW: refuse to open a symlink sitting at the trace path. O_APPEND: several
        # Redfish checks on the same host trace into the same file, and append-mode writes of
        # this size do not interleave. 0o600: the trace names hosts and URLs.
        fd = os.open(
            trace_path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
    except OSError as e:
        return False, f'Cannot open trace file {trace_path}: {e}'

    _TRACE['fd'] = fd
    _TRACE['path'] = trace_path
    _TRACE['started'] = time.now(as_type='float')
    _TRACE['requests'] = 0
    _TRACE['seconds'] = 0.0
    atexit.register(_trace_summary)

    # Identify the run: which check, which version of it, which version of this library, and the
    # process id, so lines from Redfish checks tracing concurrently into this file can be told
    # apart.
    main_module = sys.modules.get('__main__')
    check = os.path.basename(getattr(main_module, '__file__', '') or 'unknown')
    check_version = getattr(main_module, '__version__', '') or 'unknown'
    _trace(
        'start',
        f'{check} v{check_version}, lib/redfish.py v{__version__}. Columns: timestamp, pid, '
        f'seconds since this run started, event, detail',
    )
    return True, trace_path


def _fetch_json(what, url_string, timeout=8, retries=0, **kwargs):
    """Fetch JSON through `url.fetch_json()`, timing and tracing the call.

    Every request this module makes goes through here, so the trace sees all of them and the
    timing is measured in exactly one place. With the trace off this adds one `if` to the call.

    `url.fetch_json()` retries internally, so the measured duration covers all `retries + 1`
    attempts. Both numbers are traced alongside it, which is what makes a long line readable: a
    request logged as `timeout=8 retries=10` that took 88 s spent them being retried, while one
    that took 88 s at `retries=0` was answered slowly by the controller. Note that `timeout` is
    an httpx per-phase timeout, not a deadline for the whole request, so a controller that keeps
    dribbling out a large response can exceed it without ever tripping it.

    ### Parameters
    - **what** (`str`): Short label for the trace, naming what is being read (e.g. `collection`).
    - **url_string** (`str`): The URL to fetch.
    - **timeout**, **retries**, **kwargs**: Forwarded to `url.fetch_json()`.

    ### Returns
    - **tuple** (`bool`, `dict` | `list` | `str`): Whatever `url.fetch_json()` returned.
    """
    if _TRACE['fd'] is None:
        result = url.fetch_json(url_string, timeout=timeout, retries=retries, **kwargs)
        if _should_renew(what, result) and _renew_auth(kwargs.get('header')):
            result = url.fetch_json(
                url_string, timeout=timeout, retries=retries, **kwargs
            )
        return result

    method = kwargs.get('method') or ('POST' if kwargs.get('data') else 'GET')
    started = time.now(as_type='float')
    result = url.fetch_json(url_string, timeout=timeout, retries=retries, **kwargs)
    if _should_renew(what, result) and _renew_auth(kwargs.get('header')):
        result = url.fetch_json(url_string, timeout=timeout, retries=retries, **kwargs)
    elapsed = time.now(as_type='float') - started

    _TRACE['requests'] += 1
    _TRACE['seconds'] += elapsed
    kind = _TRACE['by_kind'].setdefault(what, [0, 0.0])
    kind[0] += 1
    kind[1] += elapsed

    success, payload = result
    if success:
        # Size of the parsed document re-serialized, not the size on the wire: the wire size is
        # not handed back by `fetch_json()` without switching every caller to `extended=True`,
        # which would change the code path being measured. It is the right order of magnitude for
        # spotting the response that is slow because it is large.
        try:
            size = human.bytes2human(len(json.dumps(payload)))
        except (TypeError, ValueError):
            size = 'n/a'
        outcome = f'ok {size}'
    else:
        # `url.fetch_json()` appends ' while fetching <url>' to its errors. The URL is already
        # this line's last column, so strip the repetition and keep the line readable.
        outcome = f'FAILED {str(payload).split(" while fetching ")[0]}'
    _trace(
        'request',
        f'{elapsed:7.3f}s  {method:<4} {what:<10} timeout={timeout} retries={retries}  '
        f'{outcome}  {url_string}',
    )
    return result


def _cache_read(cache_key, cache_expire, cache_filename):
    """Return the cached JSON value stored under `cache_key`, or `None` on a miss.

    Returns `None` when caching is off (`cache_expire` is `0`) or the key is absent, so callers
    treat both the same and fetch. A stored value is deserialized from JSON before it is returned.
    """
    if not cache_expire:
        return None
    cached = cache.get(cache_key, filename=cache_filename)
    return json.loads(cached) if cached else None


def _cache_write(data, cache_key, cache_expire, cache_filename):
    """Store `data` as JSON under `cache_key` for `cache_expire` seconds, when caching is on.

    A no-op when caching is off (`cache_expire` is `0`) or `data` is not a JSON-serializable
    container, so a failed fetch never poisons the cache.
    """
    if cache_expire and isinstance(data, (dict, list)):
        cache.set(
            cache_key,
            json.dumps(data),
            time.now() + cache_expire,
            filename=cache_filename,
        )


# The "Status" property is common to many Redfish schema, and contains:
#
#   Health: This represents the health state of this resource in the absence
#           of its dependent resources
#   * Critical  A critical condition exists that requires immediate attention.
#   * OK        Normal.
#   * Warning   A condition exists that requires attention
#
#   HealthRollup: This represents the overall health state from the view of this
#                 resource
#   * Critical  A critical condition exists that requires immediate attention.
#   * OK        Normal.
#   * Warning   A condition exists that requires attention.
#
#   State:
#   * Absent                This function or resource is not present or not detected.
#   * Deferring             The element will not process any commands but will queue new
#                           requests.
#   * Disabled              This function or resource has been disabled.
#   * Enabled               This function or resource has been enabled.
#   * InTest                This function or resource is undergoing testing.
#   * Quiesced              The element is enabled but only processes a restricted set of
#                           commands.
#   * StandbyOffline        This function or resource is enabled, but awaiting an external action to
#                           activate it.
#   * StandbySpare          This function or resource is part of a redundancy set and is awaiting a
#                           failover or other external action to activate it.
#   * Starting              This function or resource is starting.
#   * UnavailableOffline    This function or resource is present but cannot be used.
#   * Updating              The element is updating and may be unavailable or degraded.


def build_url(base_url, odata_id):
    """
    Build an absolute Redfish URL from the operator-supplied base URL and a server-supplied
    `@odata.id` link, always taking scheme and host from the base URL.

    Redfish responses reference sub-resources by an `@odata.id` field that is expected to be a
    server-relative path such as `/redfish/v1/Systems/1`. Concatenating it onto the base URL
    without validation lets a malicious or compromised controller inject a different authority
    (for example an `@host` userinfo prefix that turns `https://bmc` + `@evil/x` into
    `https://bmc@evil/x`), turning the next authenticated request into a server-side request
    forgery that also forwards the Redfish auth header to the attacker-chosen host
    (CWE-918/CWE-20). This helper rejects any `@odata.id` that is not a single-slash-rooted
    relative path and pins scheme and host to `base_url`, so a response can never redirect the
    request to another host.

    ### Parameters
    - **base_url** (`str`): The operator-supplied Redfish base URL, e.g. `https://bmc`.
    - **odata_id** (`str`): The `@odata.id` value taken from the controller's response.

    ### Returns
    - **tuple** (`bool`, `str`):
      - `(True, url)` with the safe absolute URL on success.
      - `(False, error)` if `odata_id` is not a server-relative path.

    ### Example
    >>> build_url('https://bmc', '/redfish/v1/Systems/1')
    (True, 'https://bmc/redfish/v1/Systems/1')
    >>> build_url('https://bmc', '@evil.example.com/x')
    (False, "Refusing non-relative Redfish @odata.id link: '@evil.example.com/x'")
    """
    if (
        not isinstance(odata_id, str)
        or not odata_id.startswith('/')
        or odata_id.startswith('//')
    ):
        return False, f'Refusing non-relative Redfish @odata.id link: {odata_id!r}'
    parts = urllib.parse.urlsplit(base_url)
    return True, f'{parts.scheme}://{parts.netloc}{odata_id}'


def fetch_collection(
    collection_url,
    expand=DEFAULT_EXPAND,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Fetch a Redfish collection, asking the controller to inline its members in one request.

    A Redfish collection (for example `Sensors`, `Memory`, `Drives` or `FirmwareInventory`) lists
    its members as bare `@odata.id` references, so reading every member classically costs one
    request for the collection plus one request per member. On a controller with dozens of members
    that fan-out dominates the runtime and, on a slow management controller, can exceed the
    caller's own timeout.

    This helper appends the Redfish `$expand` query `expand` (default: one level of subordinate
    members), which asks the controller to return the full member objects inline. When the
    controller honours it, the whole collection is read in a single request; callers detect the
    inlined members with `is_member_expanded()` and skip the per-member requests. When the
    controller rejects `$expand` (some implementations answer with an HTTP error), this helper
    transparently retries the plain request, so the returned document is the same either way, just
    without the inlined members.

    Callers pass the `expand` suffix that `get_expand_suffix()` derived from the controller's
    advertised support, so a single request inlines as much of the subtree as the controller can.

    When `cache_expire` is non-zero the parsed collection is cached under `redfish-<collection_url>`
    (keyed by the plain URL, not the `$expand` variant) and reused by any sibling consumer
    reading the same collection within the window, so identical reads across a host's Redfish
    consumers hit the cache instead of the controller. A failed fetch is never cached.

    ### Parameters
    - **collection_url** (`str`): The absolute URL of the collection resource, as produced by
      `build_url()`. Must not already carry a query string.
    - **expand** (`str`, optional): The `$expand` query suffix to append (default `DEFAULT_EXPAND`).
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **tuple** (`bool`, `dict` | `str`):
      - `(True, collection)` with the parsed collection document on success. Its `Members` may or
        may not be expanded, depending on controller support.
      - `(False, error)` if the collection cannot be read even without `$expand`.

    ### Example
    >>> success, collection = fetch_collection(
    ...     'https://bmc/redfish/v1/Chassis/1U/Sensors'
    ... )
    >>> members = collection.get('Members', [])
    """
    cache_key = f'redfish-{collection_url}'
    cached = _cache_read(cache_key, cache_expire, cache_filename)
    if cached is not None:
        _trace('cache', f'hit   collection  {collection_url}')
        return True, cached
    _trace('cache', f'miss  collection  {collection_url}')
    # `expand` is the `$expand` query suffix (default: one level of subordinate members). It is
    # derived from the controller's advertised expand support by `get_expand_suffix()`, so it is
    # our own literal and cannot smuggle in a different authority the way an `@odata.id` could.
    success, collection = _fetch_json(
        'collection',
        f'{collection_url}{expand}',
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        retries=retries,
    )
    if not (success and isinstance(collection, dict)):
        # controller rejected or could not answer the $expand query: read it plainly
        _trace(
            'expand',
            f'the $expand request failed, falling back to a plain request. Everything this '
            f'collection holds now costs one request per member: {collection_url}',
        )
        success, collection = _fetch_json(
            'plain',
            collection_url,
            header=header,
            insecure=insecure,
            no_proxy=no_proxy,
            timeout=timeout,
            retries=retries,
        )
    if success and isinstance(collection, dict):
        members = collection.get('Members', [])
        if isinstance(members, list):
            inlined = len(
                [m for m in members if isinstance(m, dict) and is_member_expanded(m)]
            )
            _trace(
                'members',
                f'{len(members)} members, {inlined} inlined by the controller, '
                f'{len(members) - inlined} still to fetch one by one: {collection_url}',
            )
        _cache_write(collection, cache_key, cache_expire, cache_filename)
        return True, collection
    return success, collection


def fetch_members(
    members,
    base_url,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Return every member reference of a Redfish collection as a fully populated dict.

    A collection lists its members as reference stubs (`{"@odata.id": "..."}`). With the Redfish
    `$expand` query (see `fetch_collection()`) the controller inlines the full member objects
    instead. This helper accepts either form and normalizes it: members that already arrived
    expanded are returned untouched, and members that are still bare references are fetched
    individually. It also accepts inline reference arrays that are not part of a collection's
    `Members` list, such as a storage member's `Drives` array.

    Each follow-up request goes through `build_url()`, so a malicious or compromised controller
    cannot redirect it to another host (see `build_url()` for the SSRF rationale).

    When `cache_expire` is non-zero each fetched member is cached under `redfish-<member_url>` and
    reused by any sibling consumer that reads the same member within the window. On a controller
    without `$expand` support several consumers otherwise re-fetch the same members every cycle,
    so this is what keeps a fleet of Redfish consumers from hammering the controller. Already-inlined members are not
    re-cached (they came from an already-cached collection), and a failed fetch is never cached.

    ### Parameters
    - **members** (`list`): The member references, e.g. `collection.get('Members', [])` or a
      storage member's `Drives` list. Each item is a dict, expanded or a bare `@odata.id` stub.
    - **base_url** (`str`): The operator-supplied Redfish base URL, used to pin the host of every
      follow-up request.
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **tuple** (`bool`, `list` | `str`):
      - `(True, [member_dict, ...])` on success (the list is empty when `members` is empty).
      - `(False, error)` if a bare reference is malformed or cannot be fetched.

    ### Example
    >>> success, collection = fetch_collection(
    ...     'https://bmc/redfish/v1/Chassis/1U/Sensors'
    ... )
    >>> success, sensors = fetch_members(collection.get('Members', []), 'https://bmc')
    """
    result = []
    for member in members:
        if not isinstance(member, dict):
            continue
        if is_member_expanded(member):
            # the controller already inlined this member via $expand
            result.append(member)
            continue
        # bare reference: fetch the member individually, pinning the host
        success, member_url = build_url(base_url, member.get('@odata.id'))
        if not success:
            return False, member_url
        cache_key = f'redfish-{member_url}'
        member_data = _cache_read(cache_key, cache_expire, cache_filename)
        if member_data is not None:
            _trace('cache', f'hit   member      {member_url}')
        if member_data is None:
            _trace('cache', f'miss  member      {member_url}')
            success, member_data = _fetch_json(
                'member',
                member_url,
                header=header,
                insecure=insecure,
                no_proxy=no_proxy,
                timeout=timeout,
                retries=retries,
            )
            if not success or not isinstance(member_data, dict):
                return False, member_data
            _cache_write(member_data, cache_key, cache_expire, cache_filename)
        result.append(member_data)
    return True, result


def fetch_resource(
    resource_url,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Fetch a single Redfish resource by URL, optionally serving and filling a shared cache.

    Unlike `fetch_collection()` this adds no `$expand` query; it is for reading an individual
    resource such as the service root a caller inspects to detect the controller vendor. When
    `cache_expire` is non-zero the parsed document is cached under `redfish-<resource_url>` and
    reused by any sibling consumer that reads the same URL within the window, so identical reads
    across a host's Redfish consumers hit the cache instead of the controller. A failed fetch is
    never cached.

    ### Parameters
    - **resource_url** (`str`): The absolute URL of the resource.
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **tuple** (`bool`, `dict` | `str`):
      - `(True, resource)` with the parsed resource document on success.
      - `(False, error)` if the resource cannot be read.

    ### Example
    >>> success, root = fetch_resource('https://bmc/redfish/v1/')
    """
    cache_key = f'redfish-{resource_url}'
    cached = _cache_read(cache_key, cache_expire, cache_filename)
    if cached is not None:
        _trace('cache', f'hit   resource    {resource_url}')
        return True, cached
    _trace('cache', f'miss  resource    {resource_url}')
    success, resource = _fetch_json(
        'resource',
        resource_url,
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        retries=retries,
    )
    if success and isinstance(resource, dict):
        _cache_write(resource, cache_key, cache_expire, cache_filename)
    return success, resource


# What this run authenticated with, so a request that comes back "401 Unauthorized" can log in
# again without every caller having to thread the credentials through. `header` is the very dict
# the caller passes to the fetch helpers: renewing updates it in place, so the requests that
# follow carry the new token too.
_AUTH = {
    'args': None,
    'cache_expire': 0,
    'cache_filename': CACHE_FILENAME,
    'token_key': None,  # nosec B105 - the cache key naming the token, not a credential
    # False once renewing has been tried, or once the controller has shown that the credentials
    # themselves are rejected, in which case logging in again would only repeat the refusal.
    'renewable': True,
}

# Requests that are themselves part of logging in. A 401 on one of these means the credentials
# are wrong, not that a token went stale, so renewing on them would log in forever.
_AUTH_REQUEST_KINDS = ('login', 'sessionsvc')


def _is_unauthorized(payload):
    """Say whether a failed fetch failed because the controller rejected the credentials.

    `url.fetch_json()` reports an HTTP error as the string `HTTP error "401 Unauthorized" while
    fetching ...`, which is what this recognizes. It is deliberately narrow: any other failure
    (a timeout, a connection refused, a 500) must not trigger a new login.

    The unit tests pin this against a real 401 from `url.fetch_json()`, so a change to its error
    wording is caught there rather than silently disabling token renewal.
    """
    return isinstance(payload, str) and payload.startswith('HTTP error "401 ')


def _should_renew(what, result):
    """Say whether a fetch result warrants logging in again and retrying.

    Only a 401 does, only on a request that is not itself part of logging in, and only while
    renewing still stands a chance (see `_AUTH['renewable']`).
    """
    return (
        _AUTH['renewable']
        and not result[0]
        and what not in _AUTH_REQUEST_KINDS
        and _is_unauthorized(result[1])
    )


def _renew_auth(header):
    """Log in again after a 401 and update `header` in place. Returns `True` if it can be retried.

    A cached session token outlives its usefulness the moment the controller drops the session,
    which it does on a reboot, when its session pool is evicted, or when an admin clears the
    sessions by hand. Every consumer on that host then presents a token the controller no longer
    knows and fails with a 401 until the cache entry expires. Renewing on the spot turns that
    outage into a single extra login.

    Only ever renews once per run: with wrong credentials every request would come back 401, and
    retrying each of them would hammer the controller with logins instead of failing quickly.
    """
    if not _AUTH['renewable'] or _AUTH['args'] is None or not isinstance(header, dict):
        return False
    _AUTH['renewable'] = False
    _trace(
        'auth',
        'the controller rejected the session token, so it dropped the session behind it. '
        'Logging in again and retrying the request',
    )
    # Drop the stale token so this run, and every sibling consumer reading the same cache, stops
    # presenting it.
    if _AUTH['cache_expire'] and _AUTH['token_key']:
        cache.set(
            _AUTH['token_key'],
            '',
            time.now() - 1,
            filename=_AUTH['cache_filename'],
        )
    fresh = get_auth_header(
        _AUTH['args'],
        cache_expire=_AUTH['cache_expire'],
        cache_filename=_AUTH['cache_filename'],
    )
    if not fresh:
        return False
    # Replace whichever scheme the header carried: a renewal may come back as Basic auth when the
    # controller can no longer create a session, and leaving a dead X-Auth-Token beside it would
    # have the controller reject the retry too.
    header.pop('X-Auth-Token', None)
    header.pop('Authorization', None)
    header.update(fresh)
    return True


def _session_url(base_url, result):
    """Return the absolute URL of the session a login just created, or `''`.

    Redfish names the new session in the `Location` response header, and most controllers repeat
    it as `@odata.id` in the body. Either value comes from the controller, so neither is trusted:
    only the path is taken from it and the scheme and host are pinned to `base_url` by
    `build_url()`. Without that, a compromised controller could answer a login with
    `Location: https://evil.example.com/x` and have the follow-up `DELETE` carry the session
    token there (CWE-918, the same reasoning as `build_url()`).

    ### Parameters
    - **base_url** (`str`): The operator-supplied Redfish base URL.
    - **result** (`dict`): The extended `url.fetch_json()` result of the login request.

    ### Returns
    - **str**: The absolute session URL, or `''` if the controller named none.
    """
    if not isinstance(result, dict):
        return ''
    # lib.url lower-cases all response header names (RFC 9110, section 5.1).
    candidates = [result.get('response_header', {}).get('location', '')]
    body = result.get('response_json')
    if isinstance(body, dict):
        candidates.append(body.get('@odata.id', ''))
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        # Take the path only, so an absolute URL naming another host cannot survive.
        success, session_url = build_url(
            base_url, urllib.parse.urlsplit(candidate).path
        )
        if success:
            return session_url
    return ''


def _delete_session(session_url, token, args):
    """Hand a Redfish session back to the controller, so it stops occupying a slot.

    A controller keeps a session until its own `SessionTimeout` expires it, which is typically far
    longer than the interval at which consumers log in. Without this, every login leaves its
    predecessor behind and a host's consumers accumulate sessions until the controller's pool is
    full, at which point new logins fail and every consumer falls back to Basic auth (and gets
    slower). Deleting the previous session on the way in keeps exactly one open.

    Failures are ignored on purpose: this is housekeeping, and a controller that refuses the
    `DELETE` (or has already expired the session itself) must not turn a working run into an
    UNKNOWN. It is given no retries and never blocks a run for long.

    ### Parameters
    - **session_url** (`str`): Absolute URL of the session, as `_session_url()` pinned it.
    - **token** (`str`): The session's own token, which is what authorizes deleting it.
    - **args** (object): must provide `INSECURE`, `NO_PROXY` and `TIMEOUT`.

    ### Returns
    - **bool**: `True` if the controller confirmed the deletion.
    """
    if not (session_url and token):
        return False
    success, _ = url.fetch(
        session_url,
        header={'Accept': 'application/json', 'X-Auth-Token': token},
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
        method='DELETE',
    )
    # Neutral wording on purpose: this runs both for a predecessor's session on the way in and
    # for this run's own session on the way out.
    _trace(
        'auth',
        f'{"handed back" if success else "could not hand back"} the session {session_url}',
    )
    return success


def _drop_previous_session(args, cache_expire, cache_filename):
    """Delete the session a previous run left behind, before a new one is created.

    The run that created a session is long gone by the time its token expires, so it cannot clean
    up after itself. Instead the session's URL and token are cached (see `get_auth_header()`) for
    as long as the controller would keep the session, and the next run to log in deletes it. The
    cache entry is dropped either way, so a session that cannot be deleted is not retried forever.
    """
    if not cache_expire:
        return
    session_key = f'redfish-{args.URL}-{args.USERNAME}-session'
    stored = cache.get(session_key, filename=cache_filename)
    if not stored:
        return
    # Expire the entry first: whatever happens to the DELETE, this session is not ours to
    # retry, and leaving the entry would have every later run attempt it again.
    cache.set(session_key, '', time.now() - 1, filename=cache_filename)
    try:
        previous = json.loads(stored)
    except ValueError:
        return
    if isinstance(previous, dict):
        _delete_session(previous.get('uri', ''), previous.get('token', ''), args)


def _remember_session(args, session_url, token, ttl, cache_expire, cache_filename):
    """Remember a session so the next run can hand it back (see `_drop_previous_session()`).

    Stored under its own key rather than with the token, because the two have different lifetimes:
    the token entry expires when the token should stop being reused, while this one has to outlive
    it, up to the point where the controller would drop the session on its own.
    """
    if not (cache_expire and session_url and token):
        return
    cache.set(
        f'redfish-{args.URL}-{args.USERNAME}-session',
        json.dumps({'uri': session_url, 'token': token}),
        time.now() + ttl,
        filename=cache_filename,
    )


def get_auth_header(args, cache_expire=0, cache_filename=CACHE_FILENAME):
    """
    Build the authentication header for Redfish API requests, reusing a cached session token.

    Redfish supports two authentication schemes: HTTP Basic auth (credentials are sent on every
    request) and session-based auth (a token is obtained once from the SessionService and then
    presented as `X-Auth-Token`). Some management controllers create and log a new internal
    session for every Basic-auth request, which floods their session table or audit log. To avoid
    that, this function establishes a session once and, when `cache_expire` is non-zero, caches the
    token under `redfish-<URL>-<USERNAME>-token` so this run's later requests and the sibling
    Redfish checks on the host present the same token instead of each creating a new session.

    It degrades gracefully: when a session cannot be created (e.g. the implementation does not
    offer the SessionService) it falls back to HTTP Basic auth, and when no credentials are given
    (e.g. against an anonymous mockup) it returns an empty header. Only the session token is cached;
    the Basic and empty headers carry no token.

    The cached token's lifetime follows the controller's own `SessionTimeout` (an inactivity
    timeout in seconds, read back from the SessionService) minus a `TIMEOUT`-sized safety margin,
    so a token is reused for as long as the session behind it lives. `cache_expire` does not cap
    it: that setting keeps fetched *data* fresh, while a token stays valid until the session ends,
    and capping it there meant a new login (and a new session) every `cache_expire` seconds. When
    caching is off (`cache_expire` is `0`) the SessionService is not probed, since there is no
    lifetime to bound.

    Should the controller drop the session anyway (a reboot, an evicted session pool, an admin
    clearing sessions), the next request comes back "401 Unauthorized". That is handled where the
    request is made: the stale token is dropped from the cache, this function is called again, and
    the request is retried once. See `_renew_auth()`.

    Each new session is preceded by handing the previous one back to the controller, so a host's
    checks keep one session open rather than one per login until the controller expires them.

    ### Parameters
    - **args** (object): must provide `URL`, `USERNAME`, `PASSWORD`, `INSECURE`, `NO_PROXY` and
      `TIMEOUT`. An optional `RETRIES` is honoured for the login, capped at `MAX_LOGIN_RETRIES`.
    - **cache_expire** (`int`, optional): Token cache lifetime cap in seconds; `0` (default) fetches
      a fresh session and does not cache the token.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **dict**: a header fragment to merge into the request headers, one of
      `{'X-Auth-Token': '...'}`, `{'Authorization': 'Basic ...'}` or `{}`.

    ### Example
    >>> header = {'Accept': 'application/json'}
    >>> header.update(get_auth_header(args, cache_expire=300))
    """
    if not (args.USERNAME and args.PASSWORD):
        _trace('auth', 'no credentials given, requesting anonymously')
        return {}

    token_key = f'redfish-{args.URL}-{args.USERNAME}-token'
    # Remember the inputs so a request that comes back 401 can log in again on its own.
    _AUTH['args'] = args
    _AUTH['cache_expire'] = cache_expire
    _AUTH['cache_filename'] = cache_filename
    _AUTH['token_key'] = token_key
    if cache_expire:
        cached_token = cache.get(token_key, filename=cache_filename)
        if cached_token:
            _trace('auth', 'reusing the session token from the cache, no login needed')
            return {'X-Auth-Token': cached_token}

    # About to create a session, so hand back the one a previous run left open first. A
    # controller's session pool is small, and without this every login adds to it.
    _drop_previous_session(args, cache_expire, cache_filename)

    # A caller's full retry budget is meant for reads. A login leaves a session behind on the
    # controller even when the client gives up on it, so it gets a capped budget of its own.
    login_retries = min(getattr(args, 'RETRIES', 0), MAX_LOGIN_RETRIES)
    _trace(
        'auth',
        f'no usable session token in the cache, logging in with up to {login_retries + 1} '
        f'attempt(s)',
    )
    # no cached token: create a new session via the SessionService
    success, result = _fetch_json(
        'login',
        f'{args.URL}/redfish/v1/SessionService/Sessions',
        data={'UserName': args.USERNAME, 'Password': args.PASSWORD},
        encoding='serialized-json',
        extended=True,
        header={'Accept': 'application/json', 'Content-Type': 'application/json'},
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
        retries=login_retries,
        method='POST',
    )
    # lib.url lower-cases all response header names (RFC 9110, section 5.1).
    token = ''
    session_url = ''
    if success and isinstance(result, dict):
        token = result.get('response_header', {}).get('x-auth-token', '')
        session_url = _session_url(args.URL, result)
    elif _is_unauthorized(result):
        # The controller refused the credentials themselves, so a later 401 on a read is not a
        # stale token and logging in again would only repeat this refusal.
        _AUTH['renewable'] = False
        _trace('auth', 'the controller refused these credentials')
    if token:
        if cache_expire:
            # Bound the cached token's lifetime by the controller's own inactivity
            # timeout (SessionTimeout, in seconds) so a sibling consumer never reuses
            # the token after the controller would already have dropped the
            # session. cache_expire caps it from above.
            token_ttl = cache_expire
            # Deliberately without retries: this probe only refines the token's cache lifetime,
            # and a caller's budget of 10 would spend ten timeouts on a value the fallback below
            # supplies anyway.
            success, result = _fetch_json(
                'sessionsvc',
                f'{args.URL}/redfish/v1/SessionService',
                encoding='serialized-json',
                header={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'X-Auth-Token': token,
                },
                insecure=args.INSECURE,
                no_proxy=args.NO_PROXY,
                timeout=args.TIMEOUT,
            )
            session_timeout = 0
            if success and isinstance(result, dict):
                try:
                    session_timeout = int(result.get('SessionTimeout') or 0)
                except (TypeError, ValueError):
                    session_timeout = 0
            if session_timeout > 0:
                # Keep the token for as long as the controller keeps the session, less a
                # TIMEOUT-sized margin so a token cached at the very edge of the window still
                # reaches the controller before it drops the session. Never drop below one
                # second.
                #
                # `cache_expire` deliberately does not cap this. It exists to keep fetched
                # *data* fresh, but a token is not data that goes stale: it stays valid until
                # the session ends. Capping the token at `cache_expire` forced a fresh login,
                # and therefore a fresh session, every `cache_expire` seconds, so a controller
                # accumulated one session per interval for as long as its own SessionTimeout
                # lasted. A token that outlives its session is caught by the 401 handling in
                # `_renew_auth()` instead.
                token_ttl = max(session_timeout - args.TIMEOUT, 1)
            cache.set(token_key, token, time.now() + token_ttl, filename=cache_filename)
            # Remember the session for as long as the controller would keep it, so the next run
            # to log in can hand it back. This has to outlive the token entry above: once that
            # expires nobody presents the token any more, but the session is still open.
            _remember_session(
                args,
                session_url,
                token,
                session_timeout or token_ttl,
                cache_expire,
                cache_filename,
            )
            _trace(
                'auth',
                f'logged in, caching the session token for {token_ttl}s (the controller '
                f'reports SessionTimeout {session_timeout or "unknown"}s)',
            )
        else:
            # Caching is off, so this session is this run's alone and nothing will ever reuse
            # it. Hand it back when the process ends instead of leaving it to occupy a slot
            # until the controller's own timeout expires it.
            atexit.register(_delete_session, session_url, token, args)
            _trace(
                'auth',
                'logged in, not caching the token (caching is off). The session is handed back '
                'when this check ends',
            )
        return {'X-Auth-Token': token}

    # session creation failed: fall back to HTTP Basic auth
    _trace(
        'auth',
        'the login did not return a token, falling back to HTTP Basic. Every request now '
        'carries the credentials, and a controller that opens an internal session per request '
        'answers all of them more slowly. Nothing is cached, so the next run logs in again',
    )
    encoded = txt.to_text(
        base64.b64encode(txt.to_bytes(f'{args.USERNAME}:{args.PASSWORD}'))
    )
    return {'Authorization': f'Basic {encoded}'}


def get_chassis(redfish):
    """
    Extract chassis information from a Redfish API response.

    This function retrieves specific chassis details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish chassis data.

    ### Returns
    - **dict**: A dictionary containing the following chassis details:
      - **AssetTag** (`str`): The asset tag of the chassis.
      - **ChassisType** (`str`): The type of the chassis.
      - **Id** (`str`): The ID of the chassis.
      - **IndicatorLED** (`str`): The status of the indicator LED.
      - **Manufacturer** (`str`): The manufacturer of the chassis.
      - **Model** (`str`): The model of the chassis.
      - **PartNumber** (`str`): The part number of the chassis.
      - **PowerState** (`str`): The power state of the chassis (e.g., "On").
      - **SerialNumber** (`str`): The serial number of the chassis.
      - **SKU** (`str`): The SKU of the chassis.
      - **Sensors_@odata.id** (`str`): The sensors' OData ID.
      - **Status_State** (`str`): The state of the chassis (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the chassis (e.g., "OK").
      - **Status_HealthRollup** (`str`): The health rollup status of the chassis (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'AssetTag': '12345',
    ...     'ChassisType': 'Rackmount',
    ...     'Id': '1',
    ...     'PowerState': 'On',
    ... }
    >>> get_chassis(redfish_data)
    {'AssetTag': '12345', 'ChassisType': 'Rackmount', 'Id': '1', 'PowerState': 'On', ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_KEYS}
    for output_key, (parent_key, child_key) in CHASSIS_NESTED_KEYS.items():
        data[output_key] = redfish.get(parent_key, {}).get(child_key, '')
    return data


def get_chassis_power_powercontrol(redfish):
    """
    Extract power control (overall power consumption) information from a Redfish API response.

    The legacy Power resource exposes one or more `PowerControl` entries that report the aggregate
    power consumption of the chassis. This function projects a single such entry into a flat
    dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing a single Redfish `PowerControl` entry.

    ### Returns
    - **dict**: A dictionary containing the following power control details:
      - **MemberId** (`str`): The identifier of the power control entry.
      - **Name** (`str`): The name of the power control entry.
      - **PowerCapacityWatts** (`str`): The total power capacity in watts.
      - **PowerConsumedWatts** (`str`): The currently consumed power in watts.
      - **Status_State** (`str`): The state of the power control entry (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the power control entry (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Name': 'System Power Control',
    ...     'PowerConsumedWatts': 344,
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_chassis_power_powercontrol(redfish_data)
    {'Name': 'System Power Control', 'PowerConsumedWatts': 344, ..., 'Status_State': 'Enabled', ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_POWER_CONTROL_KEYS}

    for out_key, path in CHASSIS_POWER_CONTROL_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_chassis_power_powersupplies(redfish):
    """
    Extract power supply information from a Redfish API response.

    This function retrieves specific power supply details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish power supply data.

    ### Returns
    - **dict**: A dictionary containing the following power supply details:
      - **FirmwareVersion** (`str`): The firmware version of the power supply.
      - **LastPowerOutputWatts** (`str`): The last reported power output in watts.
      - **LineInputVoltage** (`str`): The input voltage of the power supply.
      - **LineInputVoltageType** (`str`): The type of input voltage.
      - **Manufacturer** (`str`): The manufacturer of the power supply.
      - **Model** (`str`): The model of the power supply.
      - **PartNumber** (`str`): The part number of the power supply.
      - **PowerCapacityWatts** (`str`): The power capacity of the power supply in watts.
      - **PowerSupplyType** (`str`): The type of power supply.
      - **SerialNumber** (`str`): The serial number of the power supply.
      - **SparePartNumber** (`str`): The spare part number of the power supply.
      - **Status_State** (`str`): The state of the power supply (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the power supply (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'FirmwareVersion': '1.0',
    ...     'LastPowerOutputWatts': 200,
    ...     'PowerCapacityWatts': 500,
    ... }
    >>> get_chassis_power_powersupplies(redfish_data)
    {'FirmwareVersion': '1.0', 'LastPowerOutputWatts': 200, 'PowerCapacityWatts': 500, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_POWER_KEYS}
    if data['LastPowerOutputWatts'] in ('', None):
        data['LastPowerOutputWatts'] = redfish.get('PowerOutputWatts', '')

    for output_key, (parent_key, child_key) in CHASSIS_POWER_NESTED_KEYS.items():
        data[output_key] = redfish.get(parent_key, {}).get(child_key, '')

    return data


def get_chassis_power_voltages(redfish):
    """
    Extract power voltage information from a Redfish API response.

    This function retrieves specific power voltage details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish power voltage data.

    ### Returns
    - **dict**: A dictionary containing the following power voltage details:
      - **LowerThresholdCritical** (`str`): The critical lower threshold voltage.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold voltage.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold voltage.
      - **Name** (`str`): The name of the voltage.
      - **PhysicalContext** (`str`): The physical context of the voltage.
      - **ReadingVolts** (`str`): The current voltage reading.
      - **UpperThresholdCritical** (`str`): The critical upper threshold voltage.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold voltage.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold voltage.
      - **Status_State** (`str`): The state of the voltage (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the voltage (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'LowerThresholdCritical': 10,
    ...     'ReadingVolts': 12,
    ...     'UpperThresholdCritical': 15,
    ... }
    >>> get_chassis_power_voltages(redfish_data)
    {'LowerThresholdCritical': 10, 'ReadingVolts': 12, 'UpperThresholdCritical': 15, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_VOLTAGE_KEYS}

    for output_key, (parent_key, child_key) in CHASSIS_VOLTAGE_NESTED_KEYS.items():
        data[output_key] = redfish.get(parent_key, {}).get(child_key, '')

    return data


def get_chassis_sensors(redfish):
    """
    Extract sensor information from a Redfish API response.

    This function retrieves specific sensor details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish sensor data.

    ### Returns
    - **dict**: A dictionary containing the following sensor details:
      - **Id** (`str`): The ID of the sensor.
      - **Name** (`str`): The name of the sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **Reading** (`str`): The current reading of the sensor.
      - **ReadingRangeMax** (`str`): The maximum reading range of the sensor.
      - **ReadingRangeMin** (`str`): The minimum reading range of the sensor.
      - **ReadingUnits** (`str`): The units of the sensor reading.
      - **Thresholds_LowerCaution** (`str`): The lower caution threshold for the sensor.
      - **Thresholds_LowerCritical** (`str`): The lower critical threshold for the sensor.
      - **Thresholds_UpperCaution** (`str`): The upper caution threshold for the sensor.
      - **Thresholds_UpperCritical** (`str`): The upper critical threshold for the sensor.
      - **Status_State** (`str`): The state of the sensor (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the sensor (e.g., "OK").
      - **Status_HealthRollup** (`str`): The health rollup status of the sensor (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Id': 'sensor1',
    ...     'Reading': 75,
    ...     'ReadingRangeMax': 100,
    ...     'Thresholds_LowerCaution': 30,
    ... }
    >>> get_chassis_sensors(redfish_data)
    {'Id': 'sensor1', 'Reading': 75, 'ReadingRangeMax': 100, 'Thresholds_LowerCaution': 30, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_SENSOR_KEYS}

    for out_key, path in CHASSIS_SENSOR_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_chassis_thermal_fans(redfish):
    """
    Extract thermal fan information from a Redfish API response.

    This function retrieves specific thermal fan details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal fan data.

    ### Returns
    - **dict**: A dictionary containing the following thermal fan details:
      - **FanName** (`str`): The name of the fan.
      - **HotPluggable** (`str`): Indicates if the fan is hot pluggable.
      - **LowerThresholdCritical** (`str`): The critical lower threshold for the fan's reading.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold for the fan's reading.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold for the fan's
         reading.
      - **Name** (`str`): The name of the sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **Reading** (`str`): The current reading of the fan.
      - **ReadingUnits** (`str`): The units of the fan's reading.
      - **SensorNumber** (`str`): The number of the fan's sensor.
      - **UpperThresholdCritical** (`str`): The critical upper threshold for the fan's reading.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold for the fan's reading.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold for the fan's
         reading.
      - **Status_State** (`str`): The state of the fan (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the fan (e.g., "OK").

    ### Example
    >>> redfish_data = {'FanName': 'Fan1', 'Reading': 80, 'UpperThresholdCritical': 100}
    >>> get_chassis_thermal_fans(redfish_data)
    {'FanName': 'Fan1', 'Reading': 80, 'UpperThresholdCritical': 100, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_FAN_KEYS}

    for out_key, path in CHASSIS_FAN_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    # vendor quirk: Dell, Fujitsu and Huawei report fan speed in RPM under
    # "ReadingRPM"; HP and Lenovo report a percentage. Normalize both onto
    # Reading / ReadingUnits so get_perfdata() and the table see one shape.
    if redfish.get('ReadingRPM') is not None or redfish.get('ReadingUnits') == 'RPM':
        reading = redfish.get('ReadingRPM')
        data['Reading'] = redfish.get('Reading', '') if reading is None else reading
        data['ReadingUnits'] = 'RPM'
    elif redfish.get('ReadingUnits') == 'Percent':
        data['ReadingUnits'] = '%'

    return data


def get_chassis_thermal_redundancy(redfish):
    """
    Extract thermal redundancy information from a Redfish API response.

    This function retrieves specific thermal redundancy details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal redundancy data.

    ### Returns
    - **dict**: A dictionary containing the following thermal redundancy details:
      - **Mode** (`str`): The mode of the thermal redundancy.
      - **Name** (`str`): The name of the thermal redundancy.
      - **Status_State** (`str`): The state of the thermal redundancy (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the thermal redundancy (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Mode': 'Active',
    ...     'Name': 'Thermal Redundancy',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_chassis_thermal_redundancy(redfish_data)
    {'Mode': 'Active', 'Name': 'Thermal Redundancy', 'Status_State': 'Enabled', 'Status_Health': 'OK'}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_THERMAL_REDUNDANCY_KEYS}

    for out_key, path in CHASSIS_THERMAL_REDUNDANCY_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_chassis_thermal_temperatures(redfish):
    """
    Extract thermal temperature information from a Redfish API response.

    This function retrieves specific thermal temperature details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal temperature data.

    ### Returns
    - **dict**: A dictionary containing the following thermal temperature details:
      - **LowerThresholdCritical** (`str`): The critical lower threshold temperature.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold temperature.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold temperature.
      - **Name** (`str`): The name of the thermal temperature sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **ReadingCelsius** (`str`): The current temperature reading in Celsius.
      - **UpperThresholdCritical** (`str`): The critical upper threshold temperature.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold temperature.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold temperature.
      - **Status_State** (`str`): The state of the thermal sensor (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the thermal sensor (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'LowerThresholdCritical': '10',
    ...     'LowerThresholdFatal': '5',
    ...     'LowerThresholdNonCritical': '15',
    ...     'Name': 'Thermal Sensor',
    ...     'ReadingCelsius': '22',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_chassis_thermal_temperatures(redfish_data)
    {'LowerThresholdCritical': '10', 'LowerThresholdFatal': '5', 'LowerThresholdNonCritical': '15', 'Name': 'Thermal Sensor', 'ReadingCelsius': '22', 'Status_State': 'Enabled', 'Status_Health': 'OK'}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_THERMAL_TEMP_KEYS}

    for out_key, path in CHASSIS_THERMAL_TEMP_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_expand_suffix(
    base_url,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Return the deepest Redfish `$expand` query the controller advertises, as a URL suffix.

    Reading the service root `/redfish/v1` once, this inspects
    `ProtocolFeaturesSupported.ExpandQuery` and builds the most generic `$expand` suffix the
    controller supports, so a single request inlines as much of a collection's subtree as possible
    (see `fetch_collection()`). `ExpandAll` selects the `*` operator (subordinate resources and
    links, so linked resources such as a storage controller's `Drives` are inlined too); otherwise
    the `.` operator (subordinate resources only) is used. `Levels`/`MaxLevels` add a `$levels`
    clause, capped at `MAX_EXPAND_LEVELS`.

    When `cache_expire` is non-zero the derived suffix is cached under `redfish-expand-<base_url>`
    and reused by the sibling Redfish consumers on the host within the window, so the service
    root is probed once per cycle instead of by every one of them. On any failure (root not readable, no expand
    support advertised) it returns `DEFAULT_EXPAND`; `fetch_collection()` falls back to a plain
    request should the controller reject even that.

    ### Parameters
    - **base_url** (`str`): The operator-supplied Redfish base URL, e.g. `https://bmc`.
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **str**: A `$expand` query suffix such as `?$expand=*($levels=1)`, or `DEFAULT_EXPAND` when
      the controller's support is unknown.
    """
    expand_key = f'redfish-expand-{base_url}'
    if cache_expire:
        cached = cache.get(expand_key, filename=cache_filename)
        if cached:
            _trace('expand', f'reusing the cached $expand suffix {cached!r}')
            return cached
    suffix = DEFAULT_EXPAND
    success, root = _fetch_json(
        'root',
        f'{base_url}/redfish/v1',
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        retries=retries,
    )
    expand = {}
    if success and isinstance(root, dict):
        features = root.get('ProtocolFeaturesSupported', {})
        if isinstance(features, dict):
            expand = features.get('ExpandQuery', {}) or {}
    if isinstance(expand, dict) and (expand.get('ExpandAll') or expand.get('NoLinks')):
        # `*` inlines subordinate resources and links (e.g. Drives); `.` only subordinate resources
        operator = '*' if expand.get('ExpandAll') else '.'
        if expand.get('Levels'):
            levels = min(int(expand.get('MaxLevels', 1) or 1), MAX_EXPAND_LEVELS)
            suffix = f'?$expand={operator}($levels={levels})'
        else:
            suffix = f'?$expand={operator}'
    _trace(
        'expand',
        f'the controller advertises ExpandQuery {expand or "nothing"}, using {suffix!r}',
    )
    if cache_expire:
        cache.set(
            expand_key, suffix, time.now() + cache_expire, filename=cache_filename
        )
    return suffix


def get_manager(redfish):
    """
    Retrieves manager (BMC) details from a Redfish API response.

    This function processes a Redfish manager resource (e.g., a BMC, iLO, or iDRAC) and extracts
    the attributes relevant for health monitoring and identification.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish manager data, typically a single member
      of the `Managers` collection.

    ### Returns
    - **dict**: A dictionary containing the following manager details:
      - `FirmwareVersion`: The firmware version of the manager.
      - `Id`: The unique identifier of the manager.
      - `ManagerType`: The type of the manager (e.g., "BMC").
      - `Model`: The model of the manager.
      - `Name`: The name of the manager.
      - `PowerState`: The power state of the manager (e.g., "On").
      - `UUID`: The UUID of the manager.
      - `Status_State`: The state of the manager (e.g., "Enabled").
      - `Status_Health`: The health status of the manager (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the manager (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'FirmwareVersion': '1.45',
    ...     'ManagerType': 'BMC',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_manager(redfish_data)
    {'FirmwareVersion': '1.45', 'ManagerType': 'BMC', ..., 'Status_State': 'Enabled', ...}
    """
    data = {key: redfish.get(key, '') for key in MANAGER_KEYS}

    for out_key, path in MANAGER_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_manager_logservices_sel_entries(
    redfish, match=None, ignore=None, cutoff_epoch=0
):
    """
    Fetch and format SEL (System Event Log) entries from the Redfish API.

    Processes each entry by severity and formats the non-OK ones into a message string, returning
    the worst state across them. Entries can be filtered and aged out before they contribute:

    - **ignore**: drop entries whose `Message` matches any of these compiled regular expressions.
    - **match**: when given, keep only entries whose `Message` matches at least one of these
      compiled regular expressions.
    - **cutoff_epoch**: when non-zero, drop (and count) entries whose `Created` timestamp is older
      than this Unix epoch, so a long-since resolved event no longer keeps the state non-OK.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing the Redfish log entries under the 'Members' key.
    - **match** (`list`, optional): Compiled regular expressions; keep only matching messages.
    - **ignore** (`list`, optional): Compiled regular expressions; drop matching messages.
    - **cutoff_epoch** (`int` or `float`, optional): Drop entries created before this epoch.
      `0` (default) disables aging.

    ### Returns
    - **tuple**:
      - **msg** (`str`): A formatted string of the reported entries (created time, message, state).
      - **state** (`int`): The worst state across the reported entries:
        - `STATE_OK` (0): nothing to report.
        - `STATE_WARN` (1): some entries are warnings.
        - `STATE_CRIT` (2): some entries are critical.
      - **aged_out** (`int`): How many non-OK entries were suppressed because they were older than
        `cutoff_epoch`.

    ### Example
    >>> redfish_data = {
    ...     'Members': [
    ...         {
    ...             'Created': '2021-08-01',
    ...             'Message': 'Temperature is high',
    ...             'Severity': 'Critical',
    ...         },
    ...         {
    ...             'Created': '2021-08-02',
    ...             'Message': 'Fan speed normal',
    ...             'Severity': 'OK',
    ...         },
    ...     ]
    ... }
    >>> get_manager_logservices_sel_entries(redfish_data)
    ('* 2021-08-01: Temperature is high [CRITICAL]\n', 2, 0)
    """
    lines = []
    state = STATE_OK
    aged_out = 0
    utc = time.get_timezone('UTC')
    for entry in redfish.get('Members', []):
        severity = entry.get('Severity', '').lower()
        if severity == 'ok':
            continue
        message = entry.get('Message', '')
        # --ignore: drop entries whose message matches any ignore pattern
        if ignore and any(p.search(message) for p in ignore):
            continue
        # --match: keep only entries whose message matches a match pattern
        if match and not any(p.search(message) for p in match):
            continue
        created = entry.get('Created', '')
        # aging: drop (and count) entries older than the cutoff. A naive
        # timestamp is read as UTC, which is what controllers commonly report.
        if cutoff_epoch and created:
            try:
                entry_epoch = time.timestr2epoch(created, pattern='iso8601', tzinfo=utc)
            except ValueError:
                # undateable entry: keep it rather than silently suppress it
                entry_epoch = None
            if entry_epoch is not None and entry_epoch < cutoff_epoch:
                aged_out += 1
                continue
        msg_state = SEVERITY_TO_STATE.get(severity, STATE_OK)
        lines.append(
            '* {}: {}{}'.format(created, message, base.state2str(msg_state, prefix=' '))
        )
        state = base.get_worst(state, msg_state)
    return '\n'.join(lines) + ('\n' if lines else ''), state, aged_out


def get_perfdata(data, key='Reading'):
    """
    Retrieve the performance data for a specific key from the provided data.

    This function extracts performance-related values such as the reading value, thresholds, and
    range from the provided dictionary. It formats this data and returns a performance data string,
    suitable for monitoring.

    ### Parameters
    - **data** (`dict`): A dictionary containing performance data and related information.
    - **key** (`str`, optional): The key in the dictionary whose value should be extracted.
      Defaults to `'Reading'`.

    ### Returns
    - **str**: A formatted string containing performance data in the format:
      `'label=value[unit];[warn];[crit];[min];[max]'`, or an empty string if the required data is invalid or missing.

    ### Example
    >>> data = {
    ...     'Name': 'Temperature Sensor 1',
    ...     'PhysicalContext': 'Chassis',
    ...     'Reading': 75.0,
    ...     'ReadingUnits': '%',
    ...     'Thresholds_UpperCaution': 80,
    ...     'Thresholds_UpperCritical': 90,
    ...     'ReadingRangeMin': 0,
    ...     'ReadingRangeMax': 100,
    ... }
    >>> get_perfdata(data)
    'Chassis_Temperature_Sensor_1=75.0%;80;90;0;100'
    """
    value = data.get(key)
    if not isinstance(value, (int, float)):
        return ''

    name = data.get('Name', '')
    physical_context = data.get('PhysicalContext', '')
    uom = '%' if data.get('ReadingUnits') == '%' else None
    warn = data.get('Thresholds_UpperCaution') or None
    crit = data.get('Thresholds_UpperCritical') or None
    _min = data.get('ReadingRangeMin') or None
    _max = data.get('ReadingRangeMax') or None

    label = f'{physical_context}_{name}'.replace(' ', '_')
    return base.get_perfdata(label, value, uom, warn, crit, _min, _max)


def get_sensor_state(data, key='Reading'):
    """
    Determine the state of a Redfish sensor according to status, health, thresholds, and range.

    This function evaluates the sensor reading in the following order:

    1. **Status_State**
       If `data['Status_State']` is not `'Enabled'` or `'Quiesced'`, the sensor is considered OK.
    2. **Status_HealthRollup / Status_Health**
       - Returns STATE_CRIT if either is `'Critical'`.
       - Returns STATE_WARN if either is `'Warning'`.
    3. **Thresholds** (with user-defined overrides)
       Checks in this sequence for any defined thresholds:
       - **User-defined critical** (`Thresholds_LowerCriticalUser`, `Thresholds_UpperCriticalUser`) → STATE_CRIT
       - **Default critical**      (`Thresholds_LowerCritical`,     `Thresholds_UpperCritical`)     → STATE_CRIT
       - **User-defined caution**  (`Thresholds_LowerCautionUser`,  `Thresholds_UpperCautionUser`)  → STATE_WARN
       - **Default caution**       (`Thresholds_LowerCaution`,      `Thresholds_UpperCaution`)      → STATE_WARN
       Otherwise, if any thresholds were present but none breached, returns STATE_OK.
    4. **ReadingRange** (last-resort sanity check)
       If both `ReadingRangeMin` and `ReadingRangeMax` are defined and differ, returns STATE_WARN
       if the reading lies outside that range; otherwise STATE_OK.
       A range whose min equals its max has zero width and cannot describe a valid operating
       window. Some implementations report identical min/max (often 255) as a sentinel for
       "not available", "no limit defined" or "unsupported for this sensor type". Treating that
       as a real range would flag every reading outside that single point, so it is ignored.
    5. **Default**
       If no other checks apply, returns STATE_OK.

    ### Parameters
    - **data** (`dict`): Sensor data containing keys such as:
        - `'Reading'` (float or numeric string)
        - `'Status_State'`, `'Status_HealthRollup'`, `'Status_Health'`
        - Default thresholds: `'Thresholds_LowerCritical'`, `'Thresholds_UpperCritical'`,
          `'Thresholds_LowerCaution'`, `'Thresholds_UpperCaution'`
        - User thresholds: `'Thresholds_LowerCriticalUser'`, `'Thresholds_UpperCriticalUser'`,
          `'Thresholds_LowerCautionUser'`, `'Thresholds_UpperCautionUser'`
        - Reading ranges: `'ReadingRangeMin'`, `'ReadingRangeMax'`.
    - **key** (`str`, optional): The key in `data` whose value is the sensor reading.
      Defaults to `'Reading'`.

    ### Returns
    - **int**: One of:
        - `STATE_OK`   (0)
        - `STATE_WARN` (1)
        - `STATE_CRIT` (2)

    ### Example
    >>> sample = {
    ...     'Reading': 95.0,
    ...     'Status_State': 'Enabled',
    ...     'Status_Health': '',
    ...     'Status_HealthRollup': '',
    ...     'Thresholds_UpperCriticalUser': 85,
    ...     'Thresholds_UpperCritical': 90,
    ...     'Thresholds_UpperCaution': 80,
    ...     'Thresholds_LowerCritical': 10,
    ...     'Thresholds_LowerCaution': 20,
    ... }
    >>> get_sensor_state(sample)
    2  # STATE_CRIT (reading > user-defined upper critical)
    """

    # helper to parse floats, treating '', None, or bad strings as None
    def _parse(val):
        if val in (None, ''):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    # read the actual sensor reading
    raw = data.get(key)
    try:
        reading = float(raw)
    except (TypeError, ValueError):
        return STATE_OK

    # get redfish's states first
    if data.get('Status_State') not in ('Enabled', 'Quiesced'):
        return STATE_OK

    for field in ('Status_HealthRollup', 'Status_Health'):
        value = data.get(field)
        if value:
            value = value.lower()
            if value == 'critical':
                return STATE_CRIT
            if value == 'warning':
                return STATE_WARN

    # parse thresholds
    low_caut = _parse(data.get('Thresholds_LowerCaution'))
    low_caut_usr = _parse(data.get('Thresholds_LowerCautionUser'))
    low_crit = _parse(data.get('Thresholds_LowerCritical'))
    low_crit_usr = _parse(data.get('Thresholds_LowerCriticalUser'))
    up_caut = _parse(data.get('Thresholds_UpperCaution'))
    up_caut_usr = _parse(data.get('Thresholds_UpperCautionUser'))
    up_crit = _parse(data.get('Thresholds_UpperCritical'))
    up_crit_usr = _parse(data.get('Thresholds_UpperCriticalUser'))

    # if *any* thresholds are defined, use threshold logic
    if any(
        t is not None
        for t in (
            low_caut,
            low_caut_usr,
            low_crit,
            low_crit_usr,
            up_caut,
            up_caut_usr,
            up_crit,
            up_crit_usr,
        )
    ):
        # critical bounds first
        # (user-defined thresholds exist too and should normally override the default
        # thresholds if present)
        if (low_crit_usr is not None and reading < low_crit_usr) or (
            up_crit_usr is not None and reading > up_crit_usr
        ):
            return STATE_CRIT

        if (low_crit is not None and reading < low_crit) or (
            up_crit is not None and reading > up_crit
        ):
            return STATE_CRIT

        # then caution bounds
        if (low_caut_usr is not None and reading < low_caut_usr) or (
            up_caut_usr is not None and reading > up_caut_usr
        ):
            return STATE_WARN

        if (low_caut is not None and reading < low_caut) or (
            up_caut is not None and reading > up_caut
        ):
            return STATE_WARN

        # otherwise we're inside all defined thresholds
        return STATE_OK

    # we're using ReadingRangeMin/Max purely as a last-resort sanity check,
    # since Redfish doesn't specify health semantics for that. A zero-width range
    # (min == max) is treated as "no range defined" (see docstring step 4).
    range_min = _parse(data.get('ReadingRangeMin'))
    range_max = _parse(data.get('ReadingRangeMax'))
    if range_min is not None and range_max is not None and range_min != range_max:
        if reading < range_min or reading > range_max:
            return STATE_WARN
        return STATE_OK

    # nothing defined to check against
    return STATE_OK


def get_state(data):
    """
    Determine the state of an entity based on its health and status.

    This function checks the `Status_State` and `Status_HealthRollup` values in the provided data
    dictionary and returns a state based on these values. It assigns `STATE_CRIT` if the status or
    health rollup indicates a critical state, `STATE_WARN` for warning states, or `STATE_OK` if no
    critical or warning states are found.

    ### Parameters
    - **data** (`dict`): A dictionary containing the status and health information of the entity
      (e.g., `Status_State`, `Status_Health`, `Status_HealthRollup`).

    ### Returns
    - **int**: The state of the entity, which can be:
      - `STATE_OK` (0): If the entity is in a normal or healthy state.
      - `STATE_WARN` (1): If the entity's health or status indicates a warning.
      - `STATE_CRIT` (2): If the entity's health or status indicates a critical state.

    ### Example
    >>> data = {
    ...     'Status_State': 'Enabled',
    ...     'Status_Health': 'Warning',
    ...     'Status_HealthRollup': 'Critical',
    ... }
    >>> get_state(data)
    2  # STATE_CRIT
    """
    if data.get('Status_State') not in ('Enabled', 'Quiesced'):
        return STATE_OK

    for field in ('Status_HealthRollup', 'Status_Health'):
        value = data.get(field)
        if value:
            value = value.lower()
            if value == 'critical':
                return STATE_CRIT
            if value == 'warning':
                return STATE_WARN

    return STATE_OK


def get_systems(redfish):
    """
    Retrieves system information from the Redfish API response.

    This function processes a Redfish API response to extract system details such as BIOS version,
    host name, manufacturer, model, processor summary, power state, and system health status.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing system-related
      information such as BIOS version, processor details, and status information.

    ### Returns
    - **dict**: A dictionary containing the following system details:
      - `BiosVersion`: The BIOS version.
      - `HostName`: The system's host name.
      - `Id`: The unique identifier for the system.
      - `IndicatorLED`: The system's indicator LED state.
      - `Manufacturer`: The manufacturer of the system.
      - `Model`: The model of the system.
      - `PowerState`: The current power state of the system (e.g., "On").
      - `ProcessorSummary_Count`: The number of processors.
      - `ProcessorSummary_LogicalProcessorCount`: The number of logical processors.
      - `ProcessorSummary_Model`: The model of the processor.
      - `SerialNumber`: The system's serial number.
      - `SKU`: The system's SKU (Stock Keeping Unit).
      - `Storage_@odata.id`: The OData ID for the system's storage.
      - `Status_State`: The system's status state (e.g., "Enabled").
      - `Status_Health`: The system's health status (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the system.

    ### Example
    >>> redfish_data = {
    ...     'BiosVersion': '1.0.0',
    ...     'HostName': 'System1',
    ...     'Id': '12345',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ...     'ProcessorSummary': {
    ...         'Count': 2,
    ...         'LogicalProcessorCount': 4,
    ...         'Model': 'Intel Xeon',
    ...     },
    ...     'PowerState': 'On',
    ... }
    >>> get_systems(redfish_data)
    {
        'BiosVersion': '1.0.0',
        'HostName': 'System1',
        'Id': '12345',
        'IndicatorLED': '',
        'Manufacturer': '',
        'Model': '',
        'PowerState': 'On',
        'ProcessorSummary_Count': 2,
        'ProcessorSummary_LogicalProcessorCount': 4,
        'ProcessorSummary_Model': 'Intel Xeon',
        'SerialNumber': '',
        'SKU': '',
        'Storage_@odata.id': '',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {key: redfish.get(key, '') for key in SYSTEMS_KEYS}

    for out_key, path in SYSTEMS_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_ethernetinterfaces(redfish):
    """
    Retrieves Ethernet interface details from a Redfish API response.

    This function processes a Redfish Ethernet interface resource and extracts the attributes
    relevant for health monitoring and identification, such as MAC address, link status, and speed.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish Ethernet interface data, typically a
      single member of an `EthernetInterfaces` collection.

    ### Returns
    - **dict**: A dictionary containing the following Ethernet interface details:
      - `Description`: A description of the interface.
      - `FQDN`: The fully qualified domain name of the interface.
      - `FullDuplex`: Whether the interface operates in full-duplex mode.
      - `HostName`: The host name configured on the interface.
      - `Id`: The unique identifier of the interface.
      - `LinkStatus`: The link status of the interface (e.g., "LinkUp").
      - `MACAddress`: The currently configured MAC address.
      - `Name`: The name of the interface.
      - `PermanentMACAddress`: The permanent (factory) MAC address.
      - `SpeedMbps`: The link speed in megabits per second.
      - `Status_State`: The state of the interface (e.g., "Enabled").
      - `Status_Health`: The health status of the interface (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the interface (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'MACAddress': '12:44:6A:3B:04:11',
    ...     'LinkStatus': 'LinkUp',
    ...     'SpeedMbps': 1000,
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_ethernetinterfaces(redfish_data)
    {'MACAddress': '12:44:6A:3B:04:11', 'LinkStatus': 'LinkUp', 'SpeedMbps': 1000, ...}
    """
    data = {key: redfish.get(key, '') for key in ETHERNET_KEYS}

    for out_key, path in ETHERNET_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_memory(redfish):
    """
    Retrieves memory module (DIMM) details from a Redfish API response.

    This function processes a Redfish memory resource and extracts the attributes relevant for
    health monitoring and identification, such as capacity, type, speed, manufacturer, and status.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish memory data, typically a single member
      of the `Memory` collection.

    ### Returns
    - **dict**: A dictionary containing the following memory details:
      - `BaseModuleType`: The form factor of the module (e.g., "RDIMM").
      - `CapacityMiB`: The capacity in human-readable format (converted from mebibytes).
      - `ErrorCorrection`: The error correction scheme (e.g., "MultiBitECC").
      - `Id`: The unique identifier of the memory module.
      - `Location_ServiceLabel`: The service label of the slot (e.g., "DIMM 1").
      - `Manufacturer`: The manufacturer of the module.
      - `MemoryDeviceType`: The device type (e.g., "DDR4").
      - `MemoryType`: The memory media type (e.g., "DRAM").
      - `Name`: The name of the module.
      - `OperatingSpeedMhz`: The operating speed in megahertz.
      - `PartNumber`: The part number of the module.
      - `RankCount`: The number of ranks.
      - `SerialNumber`: The serial number of the module.
      - `Status_State`: The state of the module (e.g., "Enabled").
      - `Status_Health`: The health status of the module (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the module (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'CapacityMiB': 32768,
    ...     'MemoryDeviceType': 'DDR4',
    ...     'Name': 'DIMM Slot 1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_memory(redfish_data)
    {'CapacityMiB': '32.0GiB', 'MemoryDeviceType': 'DDR4', 'Name': 'DIMM Slot 1', ...}
    """
    data = {key: redfish.get(key, '') for key in MEMORY_KEYS}

    for out_key, path in MEMORY_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    # the vendor is detected from the member's own Oem block, so the projection
    # stays self-contained (dict in, dict out)
    vendor = get_vendor(redfish)

    # vendor quirk: some controllers report the module size as "SizeMB"; Dell
    # iDRAC 8 even reports decimal MB instead of binary MiB, so a value that is
    # not a clean MiB multiple is converted back to a MiB count.
    capacity = redfish.get('SizeMB') or redfish.get('CapacityMiB')
    if capacity:
        capacity = int(capacity)
        if vendor == 'dell' and capacity % 1024 != 0:
            capacity = round(capacity * 1024**2 / 1000**2)
        data['CapacityMiB'] = human.bytes2human(capacity * 1024 * 1024)
    else:
        data['CapacityMiB'] = ''

    # vendor quirk: when the standard Status block is empty, fold the
    # OEM-specific status field into Status_State / Status_Health.
    oem = redfish.get('Oem') or {}
    oem_block = next(iter(oem.values()), {}) if isinstance(oem, dict) else {}
    if not isinstance(oem_block, dict):
        oem_block = {}

    oem_state = ''
    if vendor == 'hpe':
        oem_state = oem_block.get('DIMMStatus', '')
    elif vendor == 'fujitsu' and oem_block.get('SignalStatus'):
        oem_state = oem_block.get('SignalStatus', '')
        # Fujitsu reports the health verdict separately in LegacyStatus
        legacy = oem_block.get('LegacyStatus')
        if legacy:
            data['Status_Health'] = (
                'OK' if legacy.lower() in MEMORY_OEM_HEALTHY_HEALTH else 'Critical'
            )
    elif redfish.get('DIMMStatus'):
        oem_state = redfish.get('DIMMStatus', '')

    if oem_state:
        if oem_state in MEMORY_OEM_ABSENT_STATES:
            data['Status_State'] = 'Absent'
        elif oem_state in MEMORY_OEM_HEALTHY_STATES:
            data['Status_State'] = 'Enabled'
            if not data['Status_Health']:
                data['Status_Health'] = 'OK'
        else:
            # an unrecognized operational value means the module needs attention
            data['Status_State'] = 'Enabled'
            if data['Status_Health'] in ('', 'OK'):
                data['Status_Health'] = 'Critical'

    return data


def get_systems_processors(redfish):
    """
    Retrieves processor (CPU) details from a Redfish API response.

    This function processes a Redfish processor resource and extracts the attributes relevant for
    health monitoring and identification, such as model, core count, speed, and status.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish processor data, typically a single
      member of the `Processors` collection.

    ### Returns
    - **dict**: A dictionary containing the following processor details:
      - `Id`: The unique identifier of the processor.
      - `InstructionSet`: The instruction set (e.g., "x86-64").
      - `Manufacturer`: The manufacturer of the processor.
      - `MaxSpeedMHz`: The maximum clock speed in megahertz.
      - `Model`: The model of the processor.
      - `Name`: The name of the processor.
      - `ProcessorArchitecture`: The architecture (e.g., "x86").
      - `ProcessorType`: The type of processor (e.g., "CPU", "FPGA").
      - `Socket`: The socket the processor is installed in.
      - `TotalCores`: The number of cores.
      - `TotalThreads`: The number of threads.
      - `Location_ServiceLabel`: The service label of the socket (e.g., "CPU 1").
      - `Status_State`: The state of the processor (e.g., "Enabled").
      - `Status_Health`: The health status of the processor (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the processor (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Model': 'Multi-Core Intel(R) Xeon(R) processor 7xxx Series',
    ...     'Socket': 'CPU 1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_processors(redfish_data)
    {'Model': 'Multi-Core Intel(R) Xeon(R) processor 7xxx Series', 'Socket': 'CPU 1', ...}
    """
    data = {key: redfish.get(key, '') for key in PROCESSOR_KEYS}

    for out_key, path in PROCESSOR_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_storage(redfish):
    """
    Retrieves storage system information from the Redfish API response.

    This function processes a Redfish API response to extract storage-related system details such
    as the storage description, number of drives, storage ID, name, and health status.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing storage-related
      information such as description, status, and health.

    ### Returns
    - **dict**: A dictionary containing the following storage system details:
      - `Description`: A description of the storage system.
      - `Drives@odata.count`: The number of drives in the storage system.
      - `Id`: The unique identifier for the storage system.
      - `Name`: The name of the storage system.
      - `Status_State`: The status state of the storage system (e.g., "Enabled").
      - `Status_Health`: The health status of the storage system (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the storage system.

    ### Example
    >>> redfish_data = {
    ...     'Description': 'RAID Storage',
    ...     'Drives@odata.count': 5,
    ...     'Id': '6789',
    ...     'Name': 'StorageSystem1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ... }
    >>> get_systems_storage(redfish_data)
    {
        'Description': 'RAID Storage',
        'Drives@odata.count': 5,
        'Id': '6789',
        'Name': 'StorageSystem1',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {key: redfish.get(key, '') for key in SYSTEMS_STORAGE_KEYS}

    for out_key, path in SYSTEMS_STORAGE_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_storage_drives(redfish):
    """
    Retrieves storage drive details from the Redfish API response.

    This function processes the Redfish API response to extract information about storage drives,
    including attributes such as capacity, encryption status, failure prediction, speed, and other
    properties.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing details about
      storage drives such as capacity, health status, and manufacturer.

    ### Returns
    - **dict**: A dictionary containing the following storage drive details:
      - `BlockSizeBytes`: The block size of the storage drive in bytes.
      - `CapableSpeedGbs`: The capable speed of the drive in gigabits per second (Gbps).
      - `CapacityBytes`: The capacity of the drive in human-readable format (converted from bytes).
      - `Description`: A description of the storage drive.
      - `EncryptionAbility`: The encryption ability status of the storage drive.
      - `EncryptionStatus`: The current encryption status of the storage drive.
      - `FailurePredicted`: A boolean indicating whether failure of the drive is predicted.
      - `HotspareType`: The type of hot spare (if any) associated with the drive.
      - `Id`: The unique identifier for the storage drive.
      - `Manufacturer`: The manufacturer of the storage drive.
      - `MediaType`: The type of media used by the storage drive (e.g., SSD, HDD).
      - `Model`: The model of the storage drive.
      - `Name`: The name of the storage drive.
      - `NegotiatedSpeedGbs`: The negotiated speed of the drive in gigabits per second (Gbps).
      - `PartNumber`: The part number of the storage drive.
      - `PowerOnHours`: The number of hours the drive has been powered on.
      - `PredictedMediaLifeLeftPercent`: The predicted remaining life of the storage media in
         percentage.
      - `Protocol`: The protocol used by the storage drive (e.g., SATA, NVMe).
      - `Revision`: The revision number of the storage drive.
      - `RotationSpeedRPM`: The rotational speed of the drive (if applicable) in revolutions per
         minute (RPM).
      - `SerialNumber`: The serial number of the storage drive.
      - `WriteCacheEnabled`: A boolean indicating whether write cache is enabled on the drive.
      - `Status_State`: The state of the storage drive (e.g., "Enabled").
      - `Status_Health`: The health status of the storage drive (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the storage drive (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'CapacityBytes': 500000000000,
    ...     'Description': 'SSD Drive',
    ...     'Manufacturer': 'Samsung',
    ...     'Model': '970 EVO',
    ...     'SerialNumber': '1234567890',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ... }
    >>> get_systems_storage_drives(redfish_data)
    {
        'CapacityBytes': '500.0 GB',
        'Description': 'SSD Drive',
        'Manufacturer': 'Samsung',
        'Model': '970 EVO',
        'SerialNumber': '1234567890',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {key: redfish.get(key, '') for key in SYSTEMS_STORAGE_DRIVES_KEYS}

    for out_key, path in SYSTEMS_STORAGE_DRIVES_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    capacity = redfish.get('CapacityBytes')
    data['CapacityBytes'] = human.bytes2human(capacity) if capacity else ''

    # vendor quirk: drive temperature is not a standard Drive property. HPE
    # SmartStorage exposes "CurrentTemperatureCelsius"; other vendors put it in
    # their OEM block as TemperatureCelsius / TemperatureC. Expose it (in
    # degrees Celsius) so it can be trended as a gauge.
    oem = redfish.get('Oem') or {}
    oem_block = next(iter(oem.values()), {}) if isinstance(oem, dict) else {}
    if not isinstance(oem_block, dict):
        oem_block = {}
    temperature = (
        redfish.get('CurrentTemperatureCelsius')
        or oem_block.get('TemperatureCelsius')
        or oem_block.get('TemperatureC')
    )
    data['Temperature'] = temperature if isinstance(temperature, (int, float)) else ''

    return data


def get_systems_storage_volumes(redfish):
    """
    Retrieves volume (logical drive) details from a Redfish API response.

    This function processes a Redfish volume resource and extracts the attributes relevant for
    health monitoring and identification, such as capacity, RAID type, and status.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish volume data, typically a single member
      of a `Volumes` collection.

    ### Returns
    - **dict**: A dictionary containing the following volume details:
      - `CapacityBytes`: The capacity of the volume in human-readable format (converted from bytes).
      - `Encrypted`: Whether the volume is encrypted.
      - `Id`: The unique identifier of the volume.
      - `Name`: The name of the volume.
      - `RAIDType`: The RAID type of the volume (e.g., "RAID1").
      - `VolumeType`: The volume type (deprecated in favor of `RAIDType`).
      - `Status_State`: The state of the volume (e.g., "Enabled").
      - `Status_Health`: The health status of the volume (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the volume (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'CapacityBytes': 1000000000000,
    ...     'Name': 'Virtual Disk 0',
    ...     'RAIDType': 'RAID1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_storage_volumes(redfish_data)
    {'CapacityBytes': '931.3GiB', 'Name': 'Virtual Disk 0', 'RAIDType': 'RAID1', ...}
    """
    data = {key: redfish.get(key, '') for key in VOLUME_KEYS}

    for out_key, path in VOLUME_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    capacity = redfish.get('CapacityBytes')
    data['CapacityBytes'] = human.bytes2human(capacity) if capacity else ''

    return data


def get_updateservice_firmwareinventory(redfish):
    """
    Retrieves firmware inventory details from a Redfish API response.

    This function processes a Redfish software inventory resource (a firmware component) and
    extracts the attributes relevant for version reporting and health monitoring.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish firmware data, typically a single member
      of the `FirmwareInventory` collection.

    ### Returns
    - **dict**: A dictionary containing the following firmware details:
      - `Id`: The unique identifier of the firmware component.
      - `Manufacturer`: The manufacturer of the firmware component.
      - `Name`: The name of the firmware component.
      - `ReleaseDate`: The release date of the firmware.
      - `SoftwareId`: The software identifier.
      - `Updateable`: Whether the component can be updated through the update service.
      - `Version`: The installed firmware version.
      - `Status_State`: The state of the firmware component (e.g., "Enabled").
      - `Status_Health`: The health status of the firmware component (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the firmware component (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Name': 'Contoso BIOS Firmware',
    ...     'Version': 'P79 v1.45',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_updateservice_firmwareinventory(redfish_data)
    {'Name': 'Contoso BIOS Firmware', 'Version': 'P79 v1.45', ..., 'Status_State': 'Enabled', ...}
    """
    data = {key: redfish.get(key, '') for key in FIRMWARE_KEYS}

    for out_key, path in FIRMWARE_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_vendor(redfish):
    """
    Retrieves the vendor information from the Redfish API response.

    This function checks for the 'Vendor' key in the Redfish API response. If it's not found,
    it looks in the  'Oem' dictionary for the first key and uses that as the vendor. If no vendor
    information is available, it returns 'generic'.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing information about
      the system, including vendor details.

    ### Returns
    - **str**: The vendor name in lowercase, or 'generic' if no vendor information is found.

    ### Example
    >>> redfish_data = {
    ...     'Vendor': 'DELL',
    ... }
    >>> get_vendor(redfish_data)
    'dell'

    >>> redfish_data = {
    ...     'Oem': {'SomeOtherVendor': 'details'},
    ... }
    >>> get_vendor(redfish_data)
    'someothervendor'

    >>> redfish_data = {}
    >>> get_vendor(redfish_data)
    'generic'
    """
    vendor = redfish.get('Vendor')
    if not vendor:
        oem = redfish.get('Oem') or {}
        vendor = next(iter(oem), '')
    return vendor.lower() if vendor else 'generic'


def is_member_expanded(member):
    """
    Report whether a Redfish collection member arrived fully populated or as a bare reference.

    A collection normally lists its members as reference stubs (`{"@odata.id": "..."}`). With the
    Redfish `$expand` query the controller inlines the full member object instead. A member counts
    as expanded once it carries at least one property beyond the OData annotation keys (those
    starting with `@odata`), because a real resource always exposes fields such as `Id`, `Name` or
    `Status`. Used by `fetch_members()` to decide whether a follow-up request is still needed.

    ### Parameters
    - **member** (`dict`): A single entry from a collection's `Members` list (or an inline
      reference array).

    ### Returns
    - **bool**: `True` if the member is already populated, `False` if it is a bare reference.

    ### Example
    >>> is_member_expanded({'@odata.id': '/redfish/v1/Chassis/1U/Sensors/0'})
    False
    >>> is_member_expanded(
    ...     {'@odata.id': '/redfish/v1/Chassis/1U/Sensors/0', 'Reading': 22.5}
    ... )
    True
    """
    if not isinstance(member, dict):
        return False
    return any(not key.startswith('@odata') for key in member)
