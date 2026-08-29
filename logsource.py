#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Reads a log incrementally, wherever it is kept: a file on disk, a systemd unit in the
journal, or the log of a container.

Anything that watches a log answers the same three questions on every run, and each storage
answers them differently: where the lines come from, where the previous run stopped, and
whether that stored position still means anything after the log was rotated, truncated or
rewritten. This module answers all three behind one call and hands back an opaque position to
store until the next run.

How exactly a position can be expressed differs per storage, and that difference is reported
rather than hidden. A file is resumed at a byte offset and a unit at a journal cursor, so
neither repeats nor loses a line. A container log only offers a timestamp, and the engines
treat it inclusively, so an entry written in the very same instant as the last one read can
come back twice. A consumer that cannot afford a repeated line reads `fidelity` and
deduplicates where it says so.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082903'

import collections
import datetime
import os
import re
import stat

from . import disk, shell, txt
from . import time as lftime

# A position either names the exact spot the previous run stopped at, or only
# approximates it. See the module docstring.
FIDELITY_APPROXIMATE = 'approximate'
FIDELITY_EXACT = 'exact'

KIND_CONTAINER = 'container'
KIND_FILE = 'file'
KIND_JOURNALD = 'journald'

DEFAULT_TIMEOUT = 8

# Prefixes that name where a log is kept. Anything else is a path, which is why
# a Windows drive letter (`C:\log\app.log`) is read as one.
_SOURCE_PREFIXES = {
    'docker': KIND_CONTAINER,
    'kubectl': KIND_CONTAINER,
    'podman': KIND_CONTAINER,
    'systemd': KIND_JOURNALD,
}


# What a syslog daemon or journald puts in front of the message an application
# wrote: a time, the host, and the identifier with the process id. Both spellings
# of the time, because a file written by rsyslog carries the traditional one and
# `journalctl --output=short-iso` carries ISO 8601.
_SYSLOG_PREFIX_REGEX = re.compile(
    r"""^(?:
        [A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}   # Aug 29 11:15:53
        |\d{4}-\d{2}-\d{2}[T\ ]\d{2}:\d{2}:\d{2}\S*   # 2026-08-29T11:15:53+0200
    )
    \s+\S+                                            # the host
    \s+(?P<identifier>[^\s:\[]+)(?:\[\d+\])?:\s          # sshd-session[1234]:
    """,
    re.VERBOSE,
)


def count_within(lines, since, parse_line=None, key=None):
    """
    Count the lines written at or after a moment, optionally per source.

    What a log holds and what happened lately are two different numbers, and a consumer that
    alerts on how often something arrives needs the second one. A window over the whole log
    would keep reporting a burst that ended hours ago.

    Where the lines name who caused them, the total is not the number to judge by either.
    Six failures from one address within ten minutes is somebody working on this host; six
    failures from six addresses is the background of an open network going past, and only the
    first is worth reporting. `key` turns the count into the largest a single source reached,
    which is also the quantity an intrusion prevention system counts before it blocks one, so
    thresholds derived from such a system compare against the same thing.

    ### Parameters
    - **lines** (`iterable` of `str`): The log lines to count.
    - **since** (`datetime.datetime`): The start of the window, naive and in local time.
    - **parse_line** (`callable`, optional): Handed to `timestamp()`.
    - **key** (`callable`, optional):
      Takes a line and returns what caused it - an address, an account, whatever the format
      offers - or None where the line names nothing. Lines returning None are counted
      together as one source, so a burst of unattributable lines still shows up. Without it
      the lines are not grouped and `count` is the plain total.

    ### Returns
    - **dict**:
        - `busiest` (`str | None`): The source that reached `count`. None without `key`, and
          None where the lines that reached it name no source.
        - `count` (**int**): The number to judge by: the total, or with `key` the largest any
          single source reached.
        - `sources` (**int**): How many distinct sources were seen. 0 without `key`.
        - `total` (**int**): Every line within the window, whatever its source.
        - `undated` (**int**): Lines carrying no timestamp either reader could find.

    ### Notes
    - The undated ones are reported separately rather than counted in or silently dropped,
      because a source whose format leaves the timestamp out would otherwise read as a quiet
      one and never raise anything.

    ### Example
    >>> count_within(lines, datetime.now() - timedelta(minutes=10))
    {'busiest': None, 'count': 37, 'sources': 0, 'total': 37, 'undated': 1}
    >>> count_within(lines, datetime.now() - timedelta(minutes=10), key=peer_of)
    {'busiest': '198.51.100.7', 'count': 12, 'sources': 9, 'total': 37, 'undated': 1}
    """
    buckets = collections.Counter()
    total = 0
    undated = 0
    for line in lines:
        logged_at = timestamp(line, parse_line)
        if logged_at is None:
            undated += 1
        elif logged_at >= since:
            total += 1
            if key:
                buckets[key(line)] += 1
    busiest = None
    count = total
    if key and buckets:
        busiest, count = buckets.most_common(1)[0]
    return {
        'busiest': busiest,
        'count': count,
        'sources': len([name for name in buckets if name is not None]),
        'total': total,
        'undated': undated,
    }


def syslog_identifier(line):
    """
    Return the identifier a log transport wrote in front of a line, or None.

    That is the program name a syslog daemon or journald puts between the host and the
    message, without the process id: `sshd` in `Aug 29 11:15:53 host sshd[1]: ...`. A consumer
    reading the journal of a unit needs it to tell the application's own lines from the ones
    systemd writes about the unit ("Starting ...", "Started ..."), which are about the service
    rather than from it.

    ### Parameters
    - **line** (`str`): One line of a log.

    ### Returns
    - **str | None**: The identifier, or None where the line carries no transport prefix.

    ### Example
    >>> syslog_identifier('Aug 29 11:15:53 host sshd[1]: Server listening on 0.0.0.0.')
    'sshd'

    >>> syslog_identifier('[28-Aug-2026 15:20:15] ERROR: failed') is None
    True
    """
    match = _SYSLOG_PREFIX_REGEX.match(line)
    if not match:
        return None
    return match.group('identifier')


def sort_by_time(lines, parse_line=None):
    """
    Return the lines in the order they were written, whichever log each of them came from.

    A consumer reading several logs as one window holds them one log after the other, so the
    newest line of the first log sits in the middle: "the last line" is then not the newest
    one, and reporting it as the latest event names something days old. Sorting once puts that
    right for everything built on the order - the line a summary quotes as the last, and the
    order a listing renders in.

    A line whose time cannot be read keeps its place relative to the other unreadable ones and
    sorts before everything dated, because the alternative - guessing a time for it - would
    move it somewhere it does not belong.

    ### Parameters
    - **lines** (`iterable` of `str`): The lines, in the order they were read.
    - **parse_line** (`callable`, optional): Handed to `timestamp()` for a format it cannot
      read on its own.

    ### Returns
    - **list** of `str`: The lines, oldest first.

    ### Example
    >>> sort_by_time(['Aug 29 11:15:53 h x[1]: b', 'Aug 28 11:15:53 h x[1]: a'])[0][:6]
    'Aug 28'
    """
    decorated = []
    for index, line in enumerate(lines):
        moment = timestamp(line, parse_line)
        decorated.append((moment is not None, moment, index, line))
    # Naive and aware values cannot be compared, so the sort runs over the naive
    # form of each: an offset moves a line by hours at worst, a `TypeError`
    # takes the whole check down.
    if len({moment.tzinfo is None for _, moment, _, _ in decorated if moment}) > 1:
        decorated = [
            (dated, moment.replace(tzinfo=None) if moment else None, index, line)
            for dated, moment, index, line in decorated
        ]
    decorated.sort(key=lambda item: (item[0], item[1] or datetime.datetime.min, item[2]))
    return [line for _, _, _, line in decorated]


def strip_syslog_prefix(line):
    """
    Return what an application wrote, without the prefix a log transport put in front of it.

    The same event reaches a consumer twice where a file and the journal of the same unit are
    both read, and in two different prefixes: `Aug 29 11:15:53 host sshd[1]: ...` from what
    rsyslog wrote, `2026-08-29T11:15:53+0200 host sshd[1]: ...` from `journalctl`. What
    follows the prefix is byte for byte the same, which is what makes it comparable.

    ### Parameters
    - **line** (`str`): One line of a log.

    ### Returns
    - **str**: The message, or the line unchanged where it carries no such prefix - which is
      what an application writing its own timestamps into a file of its own does.

    ### Example
    >>> strip_syslog_prefix('Aug 29 11:15:53 host sshd[1]: Server listening on 0.0.0.0.')
    'Server listening on 0.0.0.0.'

    >>> strip_syslog_prefix('[28-Aug-2026 15:20:15] ERROR: failed to ptrace(ATTACH)')
    '[28-Aug-2026 15:20:15] ERROR: failed to ptrace(ATTACH)'
    """
    return _SYSLOG_PREFIX_REGEX.sub('', line, count=1)


def covered_window(line_groups, parse_line=None):
    """
    Return the earliest and the latest moment a set of logs was written in.

    A consumer reporting on a window of a log has to say which stretch of time that window
    covers, because the line count alone does not: on a busy host the same 30000 lines reach
    back hours, on a quiet one months.

    Each group is one log, and only its ends are read rather than every line, which keeps the
    cost at two parses per log however long it is. Taking the ends of the whole set instead
    would be wrong as soon as there is more than one: the logs arrive one after the other, so
    the newest line of the first one sits in the middle rather than at the end.

    ### Parameters
    - **line_groups** (`iterable` of `iterable` of `str`): One iterable of lines per log, each
      in the order the log holds them.
    - **parse_line** (`callable`, optional): Handed to `timestamp()` for a format it cannot
      read on its own.

    ### Returns
    - **tuple**:
        - tuple[0] (**datetime.datetime | None**): The earliest moment found, or None where no
          line carries a time.
        - tuple[1] (**datetime.datetime | None**): The latest moment found, or None.

    ### Example
    >>> covered_window([['Aug 29 11:15:53 host sshd[1]: Accepted publickey for alice']])[0].hour
    11
    """
    moments = []
    for lines in line_groups:
        lines = list(lines)
        for candidate in (lines, reversed(lines)):
            for line in candidate:
                moment = timestamp(line, parse_line)
                if moment is not None:
                    moments.append(moment)
                    break
    if not moments:
        return None, None
    # Compared as they are only where they agree on being aware or naive: a log
    # written with a UTC offset next to one written without cannot be ordered,
    # and guessing an offset would move a line by hours.
    if len({moment.tzinfo is None for moment in moments}) > 1:
        moments = [moment.replace(tzinfo=None) for moment in moments]
    return min(moments), max(moments)


def parse(source):
    """
    Split a log source specification into the storage it names and the target within it.

    ### Parameters
    - **source** (`str`):
      Either a path to a file, or a prefixed target: `systemd:UNITNAME` for a unit in the
      journal, and `docker:NAME`, `kubectl:NAME` or `podman:NAME` for the log of a container.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the source could be read, otherwise False.
        - tuple[1] (**tuple | str**):
          - If successful, a `(kind, engine, target)` tuple. `kind` is one of `KIND_CONTAINER`,
            `KIND_FILE` or `KIND_JOURNALD`. `engine` names the container engine and is None for
            everything else. `target` is the path, the unit name or the container name.
          - If unsuccessful, an error message string.

    ### Example
    >>> parse('/var/log/messages')
    (True, ('file', None, '/var/log/messages'))
    >>> parse('systemd:sshd')
    (True, ('journald', None, 'sshd'))
    >>> parse('podman:database')
    (True, ('container', 'podman', 'database'))
    """
    if not source or not isinstance(source, str):
        return False, 'No log source given.'
    prefix, separator, target = source.partition(':')
    kind = _SOURCE_PREFIXES.get(prefix) if separator else None
    if kind is None:
        return True, (KIND_FILE, None, source)
    target = target.strip()
    if not target:
        return False, f'Log source "{source}" names no target.'
    return True, (kind, prefix if kind == KIND_CONTAINER else None, target)


# Enough of the head of a file to tell two lines of text apart, which is all the
# fingerprint has to do here.
_FINGERPRINT_LENGTH = 256


def _is_rewritten(filename, fingerprint, length):
    """Tell whether the head of a file still matches the fingerprint of the previous run.

    The head is the part that appending does not touch, so it identifies the file: it changes
    only once the file has become a different one. Hashes exactly as many bytes as were hashed
    back then, so appending to a file whose head was shorter than the fingerprint does not look
    like a rewrite.
    """
    if not length:
        # The file was empty on the previous run, so there is nothing to compare
        # against, and nothing to miss either: an offset of 0 stays valid no
        # matter what was written since.
        return True, False
    success, result = disk.get_fingerprint(filename, length=length)
    if not success:
        return False, result
    current, hashed = result
    if hashed < length:
        # the file no longer holds the bytes that were hashed last time, so it
        # must have been truncated
        return True, True
    return True, current != fingerprint


# What a log rotator appends to the name of the file it moved aside. Everything
# it can produce is made of digits and separators, whether it counts generations
# (`.1`) or stamps a date (`-20260828`, `-2026-08-28`), so a name carrying a
# letter is somebody's backup copy and not a rotation.
_ROTATED_SUFFIX_REGEX = re.compile(r'^[-.][-_.0-9]*[0-9][-_.0-9]*$')

# Compression a rotator applies to what it moved aside, and the module that
# reads it back. A rotator can be told to use something else (zstd, for
# example); such a file simply does not look like a rotation here and is left
# alone rather than read as binary noise.
_COMPRESSION_MODULES = {
    '.bz2': 'bz2',
    '.gz': 'gzip',
    '.xz': 'lzma',
}


def _open_log_file(path):
    """Open a log file for reading in binary, decompressing it where its name says so.

    The module that reads a compression is imported here rather than at the top, because a
    Python can be built without one, and that must not keep this module from being imported at
    all.
    """
    for suffix, module_name in _COMPRESSION_MODULES.items():
        if not path.endswith(suffix):
            continue
        try:
            module = __import__(module_name)
        except ImportError:
            return False, (
                f'Cannot read "{path}": this Python has no `{module_name}` module.'
            )
        try:
            return True, module.open(path, mode='rb')
        except OSError as e:
            return False, f'I/O error "{e.strerror}" while reading {path}'
    try:
        return True, open(path, mode='rb')
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while reading {path}'


def _rotated_files(path, count):
    """Return the files a rotator moved aside from `path`, the oldest of them first.

    Ordering is by modification time rather than by name, because the two naming schemes a
    rotator uses disagree about which name is the newest: a counted generation is renamed
    upwards on every rotation while a dated one never moves. Compressing a rotated file keeps
    its modification time, so the order holds either way.

    Only a regular file is considered, and a symlink is not followed, so nothing that was
    dropped into the log directory can widen what the caller reads.
    """
    directory = os.path.dirname(path) or '.'
    base = os.path.basename(path)
    candidates = []
    try:
        entries = os.listdir(directory)
    except OSError:
        # A directory that cannot be listed simply yields no predecessor. The
        # file itself is read on its own and reports its own trouble.
        return []
    for name in entries:
        if not name.startswith(base) or name == base:
            continue
        suffix = name[len(base) :]
        for compression in _COMPRESSION_MODULES:
            if suffix.endswith(compression):
                suffix = suffix[: -len(compression)]
                break
        if not _ROTATED_SUFFIX_REGEX.match(suffix):
            continue
        candidate = os.path.join(directory, name)
        try:
            candidate_stat = os.lstat(candidate)
        except OSError:
            continue
        if not stat.S_ISREG(candidate_stat.st_mode):
            continue
        candidates.append((candidate_stat.st_mtime, candidate))
    # newest first to pick the `count` most recent, then reversed so their lines
    # arrive in the order they were written
    candidates.sort(reverse=True)
    return [candidate for _, candidate in reversed(candidates[:count])]


def _read_file(path, position, allowed_roots, max_lines, rotated):
    """Read the lines a file grew by since `position`, detecting rotation and rewrites."""
    if allowed_roots and not disk.is_within(path, allowed_roots):
        return False, (
            f'Refusing to read "{path}": resolved path is outside the allowed roots '
            f'({", ".join(allowed_roots)}); bind-mount it into one of them if intended.'
        )
    try:
        file_stat = os.stat(path)
    except OSError as e:
        failure = f'I/O error "{e.strerror}" while reading {path}'
        if any(character in path for character in '*?['):
            # A shell that found nothing to expand hands the pattern on
            # unchanged, and a caller who meant a set of files then sees a
            # missing file with an odd name. Saying that a source is one file
            # beats letting them hunt for a typo that is not there.
            failure += (
                ' - a wildcard is not expanded here, every file is its own source.'
            )
        return False, failure
    inode = str(file_stat.st_ino)
    # Fingerprint before reading rather than after: should the file be rewritten
    # in between, the stored fingerprint is the older one, so the next run
    # rescans the file instead of missing what was written in the meantime.
    success, result = disk.get_fingerprint(path, length=_FINGERPRINT_LENGTH)
    if not success:
        return False, result
    fingerprint, fingerprint_length = result

    stored_offset = position.get('offset', 0) if position else 0
    offset = stored_offset
    restarted = False
    if position:
        # A state written before the position carried a kind may hold the inode
        # with INTEGER affinity and read back as int, so compare as strings.
        if str(position.get('inode')) != inode or file_stat.st_size < offset:
            # rotated, replaced, or truncated below where we stopped
            offset = 0
        elif position.get('fingerprint'):
            success, rewritten = _is_rewritten(
                path,
                position.get('fingerprint'),
                position.get('length', 0),
            )
            if not success:
                return False, rewritten
            if rewritten:
                # An application that rewrites its log from the beginning
                # (`> logfile` instead of `>> logfile`) keeps the inode, and if
                # the new content is at least as long as what was read last
                # time, the size does not shrink either. Only the head tells us
                # that everything after our offset is gone.
                offset = 0
        # Resetting a position that was 0 anyway loses nothing, so it is not a
        # restart the consumer has to hear about.
        restarted = offset == 0 and stored_offset != 0

    # A cap is applied to the lines that are kept, not to the lines that are
    # read: the offset still advances to the end, so a run that hits the cap
    # drops the oldest of the new lines instead of re-reading them forever.
    # Rotated predecessors share the same deque, so the cap keeps the most
    # recent lines across all of them rather than per file.
    lines = collections.deque(maxlen=max_lines) if max_lines else []
    read = 0
    notices = []
    rotated_read = []
    for predecessor in _rotated_files(path, rotated) if rotated else []:
        if allowed_roots and not disk.is_within(predecessor, allowed_roots):
            notices.append(f'"{predecessor}" is outside the allowed roots')
            continue
        success, handle = _open_log_file(predecessor)
        if not success:
            notices.append(handle)
            continue
        try:
            with handle:
                for line in handle:
                    read += 1
                    lines.append(
                        txt.to_text(line, errors='strict_or_latin1').rstrip('\r\n')
                    )
        except OSError as e:
            notices.append(f'I/O error "{e.strerror}" while reading {predecessor}')
            continue
        rotated_read.append(predecessor)
    # Through the decompressor where the name says the file is compressed, the
    # way a rotated predecessor is read: a caller that names a rotated file
    # directly would otherwise be handed the compressed bytes as text and told
    # that the application never wrote a line. `seek()` and `tell()` on such a
    # handle count uncompressed bytes, so the position keeps its meaning.
    success, handle = _open_log_file(path)
    if not success:
        return False, handle
    try:
        with handle:
            handle.seek(offset)
            for line in handle:
                read += 1
                lines.append(
                    txt.to_text(line, errors='strict_or_latin1').rstrip('\r\n')
                )
            offset = handle.tell()
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while reading {path}'
    return True, {
        'fidelity': FIDELITY_EXACT,
        'kind': KIND_FILE,
        'label': path,
        'lines': list(lines),
        # Nothing reads a file but us, so the only thing to pass on is a rotated
        # predecessor that was asked for and could not be read.
        'notice': (
            'Skipped a rotated file: ' + '; '.join(notices) + '.' if notices else ''
        ),
        'position': {
            'fingerprint': fingerprint,
            'inode': inode,
            'kind': KIND_FILE,
            'length': fingerprint_length,
            'offset': offset,
        },
        'restarted': restarted,
        'rotated': rotated_read,
        'truncated': read > len(lines),
    }


# journalctl prints the cursor of the last entry on a line of its own when asked
# for it with --show-cursor.
_JOURNALD_CURSOR_PREFIX = '-- cursor: '


def _read_journald(unit, position, max_lines, since, timeout):
    """Read the entries a unit logged since `position`, resuming at a journal cursor."""
    cursor = position.get('cursor') if position else None
    cmd = [
        'journalctl',
        '--no-pager',
        '--output=short-iso',
        '--show-cursor',
        # Every value is bound to its option with `=`, so a unit name starting
        # with `-` cannot be picked up as an option of journalctl itself.
        f'--unit={unit}',
    ]
    if cursor:
        cmd.append(f'--after-cursor={cursor}')
    elif since:
        cmd.append(f'--since={since}')
    else:
        # Without a stored position and without a window the caller named, the
        # current boot is the one bounded answer that needs no clock arithmetic.
        cmd.append('--boot')
    if max_lines:
        cmd.append(f'--lines={max_lines}')
    success, result = shell.shell_exec(cmd, timeout=timeout)
    if not success:
        return False, result
    stdout, stderr, retc = result
    if retc != 0 and stderr.strip():
        return False, (
            f'`{" ".join(cmd)}` exited with error ({retc}, {stderr.strip()}).'
        )
    # An exit code with nothing said about it means the journal holds nothing for
    # this unit rather than that the read went wrong: `--show-cursor` exits 1 on a
    # unit that logged nothing since the boot, because there is no cursor to
    # print, and journalctl says so on standard output only ("-- No entries --").
    # Failing here would put a permanent WARNING on every host with a quiet unit.
    # Measured against systemd 239 on Rocky 8.
    lines = []
    for line in stdout.splitlines():
        if line.startswith(_JOURNALD_CURSOR_PREFIX):
            # Keep the previous cursor when journalctl prints none, which is what
            # it does when the unit logged nothing at all since last time.
            cursor = line[len(_JOURNALD_CURSOR_PREFIX) :].strip() or cursor
            continue
        if line.startswith('-- '):
            # journalctl frames its output with informational lines such as
            # `-- No entries --` and `-- Boot ... --`. With --output=short-iso
            # every real entry starts with its timestamp, so a line starting
            # with `-- ` is never one of them.
            continue
        lines.append(line)
    notice = stderr.strip()
    if notice and not lines:
        # journalctl says on stderr, and with an exit code of 0, that it is only
        # showing what the caller is allowed to see. Where that leaves nothing at
        # all, returning an empty result would report a quiet log on a host whose
        # log simply cannot be read, which is the worst answer a check can give.
        # Verified against systemd 257 on Debian 13, where an account outside the
        # `adm` and `systemd-journal` groups sees no system entries at all.
        return False, (
            f'Read no entries of `systemd:{unit}`, and journalctl reported: {notice} '
            f'Run with elevated privileges, or add the account to the `adm` or '
            f'`systemd-journal` group.'
        )
    return True, {
        'fidelity': FIDELITY_EXACT,
        'kind': KIND_JOURNALD,
        'label': f'systemd:{unit}',
        'lines': lines,
        # What journalctl said next to the entries it did return, so a consumer
        # can pass on a partial read instead of presenting it as a whole one.
        'notice': notice,
        'position': {'cursor': cursor, 'kind': KIND_JOURNALD},
        # A cursor whose entry has rotated out of the journal makes journalctl
        # resume at the closest one it still holds, without saying so, so there
        # is nothing here that could be reported as a restart.
        'restarted': False,
        # Neither storage has a rotation of its own a caller could ask for.
        'rotated': [],
        'truncated': bool(max_lines) and len(lines) >= max_lines,
    }


# `<engine> logs --timestamps` prefixes every line with an RFC 3339 timestamp.
# Verified against podman 5 on Fedora 44, which renders it in local time with an
# explicit offset (`2026-08-28T15:30:26.241557000+02:00`) rather than in UTC.
_CONTAINER_TIMESTAMP_REGEX = re.compile(
    r'^(\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-][\d:]+)) ?'
)


def _read_container(engine, target, position, max_lines, since, timeout):
    """Read the lines a container logged since `position`, resuming at a timestamp."""
    success, target = shell.safe_cli_value(target, 'container name')
    if not success:
        return False, target
    last = position.get('timestamp') if position else None
    start = last or since
    cmd = [engine, 'logs', '--timestamps']
    if start:
        # kubectl spells the same thing differently: its own `--since` takes a
        # duration, and only `--since-time` takes a timestamp.
        cmd.append(
            f'--since-time={start}' if engine == 'kubectl' else f'--since={start}'
        )
    if max_lines:
        cmd.append(f'--tail={max_lines}')
    cmd.append(target)
    success, result = shell.shell_exec(cmd, timeout=timeout)
    if not success:
        return False, result
    stdout, stderr, retc = result
    if retc != 0:
        return False, (
            f'`{" ".join(cmd)}` exited with error ({retc}, {stderr.strip()}).'
        )
    # An application in a container commonly logs to stderr, so both streams are
    # log content. A failure of the engine itself is caught by the exit code
    # above and never reaches this point.
    entries = []
    stamp = last or ''
    for line in stdout.splitlines() + stderr.splitlines():
        match = _CONTAINER_TIMESTAMP_REGEX.match(line)
        if match:
            stamp = match.group(1)
            line = line[match.end() :]
        # A line the engine did not stamp keeps the stamp of the one before it,
        # so it stays next to the entry it belongs to instead of sorting away.
        entries.append((stamp, line))
    # The two streams are read one after the other, so put them back into the
    # order they were written in. Every timestamp of one run carries the same
    # UTC offset, which makes a lexical sort chronological.
    entries.sort(key=lambda entry: entry[0])
    if last:
        # `--since` is inclusive, verified against podman 5: asking for the
        # timestamp of the last line read returns that very line again. Dropping
        # it here is what keeps the repeat away, rather than moving the stored
        # timestamp on, which would skip an entry written in the same instant.
        entries = [entry for entry in entries if entry[0] > last]
    return True, {
        'fidelity': FIDELITY_APPROXIMATE,
        'kind': KIND_CONTAINER,
        'label': f'{engine}:{target}',
        'lines': [line for _, line in entries],
        # An engine writes its diagnostics to the same stream the container logs
        # to, so there is no way to tell them apart and nothing to report here.
        'notice': '',
        'position': {
            'kind': KIND_CONTAINER,
            'timestamp': entries[-1][0] if entries else last,
        },
        'restarted': False,
        # Neither storage has a rotation of its own a caller could ask for.
        'rotated': [],
        'truncated': bool(max_lines) and len(entries) >= max_lines,
    }


def read(
    source,
    position=None,
    allowed_roots=None,
    max_lines=None,
    rotated=0,
    since=None,
    timeout=DEFAULT_TIMEOUT,
):
    """
    Read the lines a log grew by since the previous run.

    Hands back the lines together with an opaque position. Store that position and pass it in
    again on the next run, and only what was written in between comes back. Pass none, and the
    log is read from a starting point that `since` and `max_lines` bound.

    Rotation, truncation and a rewrite in place are recognized for a file, and the file is then
    read from its beginning with `restarted` set, because everything after the stored offset is
    gone. The other storages have no equivalent, which is why `restarted` is never set for them.

    ### Parameters
    - **source** (`str`):
      Where the log is kept. Either a path to a file, or a prefixed target: `systemd:UNITNAME`,
      `docker:NAME`, `kubectl:NAME` or `podman:NAME`. See `parse()`.
    - **position** (`dict`, optional):
      The `position` of the previous call, or None to start fresh. A position taken from
      another storage than the one `source` names is ignored rather than misread.
    - **allowed_roots** (`iterable` of `str`, optional):
      Directories a file source is allowed to resolve into. A path outside them is refused
      instead of read. Applies to file sources only, and confines nothing when left at None,
      which is why anything running with elevated privileges should name them.
    - **max_lines** (`int`, optional):
      At most this many lines are returned, the most recent ones. The position still advances
      past everything that was there, so the lines a cap dropped do not come back on the next
      run. Defaults to None, which is no cap. Where rotated files are read as well, the cap
      applies to all of them together rather than to each one.
    - **rotated** (`int`, optional):
      How many rotated predecessors of a file source to read ahead of it, most recent first.
      Defaults to 0, which reads the file alone. Only a read that has no `position` honours
      this, because a caller that resumes where it stopped has seen those lines already. See
      the notes on which files count as a predecessor.
    - **since** (`str`, optional):
      Where to start when there is no position: a timestamp for a container, and anything
      `journalctl --since` accepts for a unit, for example `-8h`. Ignored for a file, which
      always starts at its beginning. Defaults to None, which reads the current boot of a unit
      and the whole log of a container.
    - **timeout** (`int`, optional):
      Seconds to wait for `journalctl` or the container engine. Defaults to 8. Not used for a
      file, which is read directly.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the log could be read, otherwise False.
        - tuple[1] (**dict | str**): If unsuccessful, an error message string. If successful, a
          dict:
          - `fidelity` (`str`): `FIDELITY_EXACT` if the position names the exact spot the run
            stopped at, `FIDELITY_APPROXIMATE` if a line can repeat across runs.
          - `kind` (`str`): the storage the lines came from.
          - `label` (`str`): the source in words, for a consumer that reports where it read.
          - `lines` (`list` of `str`): the new lines, without their line endings, and for a
            container without the timestamp the engine prefixes them with.
          - `notice` (`str`): what the source said about the read itself rather than about what
            was logged, for example that it only showed what the caller is allowed to see.
            Empty where there is nothing to report. A source that says so and returns nothing
            at all fails instead, because an empty result would read as a quiet log.
          - `position` (`dict`): to store and pass back on the next call.
          - `restarted` (`bool`): True if the stored position had become meaningless and the
            source was read from its beginning, so the lines are not only the new ones.
          - `rotated` (`list` of `str`): the rotated files that were read ahead of the source,
            in the order their lines appear. Empty unless `rotated` asked for them.
          - `truncated` (`bool`): True if `max_lines` dropped lines from the result.

    ### Notes
    - The position is a plain dict of strings and numbers, so it serializes to JSON and fits in
      a single column of a state database.
    - A consumer that stores the position has to survive not finding one, because the first run
      after deploying it has none, and so has the run after the log was rotated. Reading a whole
      log at once is what `max_lines` and `since` are there to bound.
    - A file is read in binary and decoded as UTF-8, falling back to Latin-1 for the whole line
      on any invalid byte, so a log that is not valid UTF-8 is reported rather than raising at
      the point where the result is printed.
    - A predecessor is a regular file in the same directory whose name is the source's plus a
      suffix of digits and separators, as a rotator writes it (`error.log.1`,
      `error.log-20260828`), optionally compressed with gzip, xz or bzip2. Ordering is by
      modification time, so both a counted and a dated scheme come out chronologically. A
      symlink is never followed, a rotator told to compress with something else is left alone,
      and a rotator configured to move its output to another directory is out of reach. One
      that could not be read is named in `notice` instead of failing the whole call, so the
      live file is still reported.

    ### Example
    >>> success, result = read('/var/log/messages', allowed_roots=['/var/log'])
    >>> success, result = read('/var/log/messages', max_lines=30000, rotated=1)
    >>> success, result = read('systemd:sshd', position=stored, since='-8h')
    >>> success, result = read('podman:database', position=stored, max_lines=1000)
    """
    success, result = parse(source)
    if not success:
        return False, result
    kind, engine, target = result
    if position and position.get('kind') and position.get('kind') != kind:
        # The source changed shape, a file became a unit for example. The stored
        # position says nothing about the new one, so start over rather than
        # read a byte offset as a timestamp.
        position = None
    if kind == KIND_CONTAINER:
        return _read_container(engine, target, position, max_lines, since, timeout)
    if kind == KIND_JOURNALD:
        return _read_journald(target, position, max_lines, since, timeout)
    # A caller that resumes where it stopped has seen the predecessors already,
    # and the position it gets back describes the live file alone, so there
    # would be no way to remember how much of a predecessor was consumed.
    return _read_file(
        target, position, allowed_roots, max_lines, 0 if position else rotated
    )


def read_many(
    sources,
    allowed_roots=None,
    dedup_key=None,
    max_lines=None,
    rotated=0,
    since=None,
    timeout=DEFAULT_TIMEOUT,
):
    """
    Read several logs as one window.

    An application does not always keep what it has to say in one file. A web server writes a
    log per virtual host next to the one it writes about itself, and an administrator watching
    a service may want the file and the unit read together. Reading them one call at a time and
    stitching the results together is the same work every time, and getting it slightly wrong
    is easy: the same file named twice, or reached once by its own path and once through a
    symlink, would count everything in it twice.

    For a consumer that reads a window rather than resumes where it stopped, which is why this
    takes no position; `read()` is the one to use for reading a log incrementally.

    ### Parameters
    - **sources** (`iterable` of `str`): What to read, each as `read()` takes it.
    - **allowed_roots** (`iterable` of `str`, optional): Handed to `read()` for every source.
    - **dedup_key** (`callable`, optional): Called with one line and returning what identifies
      the event in it, for example its time and the message without the prefix a log transport
      put in front of it (`strip_syslog_prefix()`). A line of a later source whose key a line
      of an earlier one already produced is dropped, which is what keeps a file and the journal
      of the same unit from counting the same event twice. Lines of one and the same source are
      never dropped against each other: an application repeating a message is what a rate is
      counted from. Without it nothing is dropped.
    - **max_lines** (`int`, optional):
      At most this many lines **per source**, the most recent ones. A window over several logs
      is therefore at most this many times the number of sources, which is what keeps one busy
      log from crowding out a quiet one that had the interesting line.
    - **rotated** (`int`, optional): Handed to `read()` for every source.
    - **since** (`str`, optional): Handed to `read()` for every source.
    - **timeout** (`int`, optional): Handed to `read()` for every source, each in its own right.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if at least one source could be read, otherwise False.
        - tuple[1] (**dict | str**): If unsuccessful, a message naming what went wrong with
          each source. If successful, a dict:
          - `lines` (`list` of `str`): Every source's lines, in the order the sources were
            given.
          - `duplicates` (`int`): How many lines `dedup_key` identified as an event an
            earlier source had already delivered. 0 without `dedup_key`.
          - `failed` (`list` of `str`): One message per source that could not be read at all.
            A source that failed is skipped rather than fatal, because a log an application
            has not written yet is normal where several are read - but the window then has a
            hole in it, which is a different matter from `notice` and is reported apart from
            it for that reason.
          - `notice` (`str`): What the sources said about the read itself rather than about
            what they hold, for a consumer to pass on.
          - `sources` (`list` of `dict`): What `read()` returned per source that could be read,
            in the same order, so a consumer can name each one and what came from it.
          - `truncated` (`bool`): Whether any source stopped at `max_lines`.

    ### Notes
    - A source named twice is read once, and so is one reached by two paths that resolve to the
      same file.

    ### Example
    >>> success, result = read_many(
    ...     ['/var/log/httpd/error_log', 'systemd:httpd.service']
    ... )
    """
    lines = []
    notices = []
    failures = []
    read_sources = []
    seen = set()
    seen_keys = set()
    duplicates = 0
    for source in sources:
        success, parsed = parse(source)
        if not success:
            failures.append(parsed)
            continue
        kind, _, target = parsed
        # A file is identified by where it resolves to, so naming it twice, or
        # reaching it once directly and once through a symlink, reads it once.
        identity = os.path.realpath(target) if kind == KIND_FILE else source
        if identity in seen:
            continue
        seen.add(identity)
        success, result = read(
            source,
            allowed_roots=allowed_roots,
            max_lines=max_lines,
            rotated=rotated,
            since=since,
            timeout=timeout,
        )
        if not success:
            failures.append(result)
            continue
        kept = result['lines']
        if dedup_key is not None:
            # Against the sources read so far, never against this one itself, so
            # an application repeating a message keeps being counted as often as
            # it repeated it.
            kept = []
            keys = []
            for line in result['lines']:
                key = dedup_key(line)
                if key in seen_keys:
                    duplicates += 1
                    continue
                keys.append(key)
                kept.append(line)
            seen_keys.update(keys)
        lines.extend(kept)
        if result['notice']:
            notices.append(result['notice'])
        read_sources.append(result)
    if not read_sources:
        return False, ' '.join(failures) if failures else 'No log source given.'
    return True, {
        'duplicates': duplicates,
        'failed': failures,
        'lines': lines,
        'notice': ' '.join(notices),
        'sources': read_sources,
        'truncated': any(item['truncated'] for item in read_sources),
    }


# The timestamp a transport puts in front of what the application wrote:
# `journalctl --output=short-iso` writes `2026-08-28T17:16:18+0200 host unit[pid]:`
# and this module strips the container engine's equivalent while reading, so
# what is left to recognize here is an ISO 8601 moment at the very start of a
# line. Deliberately anchored: an ISO timestamp further along is part of the
# message, not of the line's own header.
# The hour is allowed to be padded with a space rather than with a zero, which
# is not ISO 8601 but is what MariaDB writes: `2026-08-29  6:00:21` before ten
# in the morning and `2026-08-29 15:01:47` after it. Without this a consumer
# reading such a log would find no time on any line for a third of every day.
# Verified against MariaDB 11.8.
_LINE_TIMESTAMP_REGEX = re.compile(
    r'^(\d{4}-\d{2}-\d{2}[T ][ \d]\d:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'
)

# The other timestamp a syslog daemon puts at the head of a line, the traditional
# one of RFC 3164: `Aug 28 19:34:14`, with the day padded to two columns by a
# space. Which of the two formats a host writes is up to the daemon and its
# configuration rather than up to the application, so both are read here.
# Verified against rsyslog with the configuration its package ships: 8.2102 on
# Rocky 8 and 8.2510 on Rocky 9 write this format, 8.2504 on Debian 13 writes the
# ISO one above.
_SYSLOG_TIMESTAMP_REGEX = re.compile(
    r'^([A-Z][a-z]{2}) {1,2}(\d{1,2}) (\d{2}):(\d{2}):(\d{2})(?:\s|$)'
)

# The month names of that format, read from a table rather than with `%b`,
# because `strptime()` reads them in whatever locale the process happens to be
# in, while a syslog daemon writes them in English on every host.
_SYSLOG_MONTHS = {
    'Apr': 4,
    'Aug': 8,
    'Dec': 12,
    'Feb': 2,
    'Jan': 1,
    'Jul': 7,
    'Jun': 6,
    'Mar': 3,
    'May': 5,
    'Nov': 11,
    'Oct': 10,
    'Sep': 9,
}


def _syslog_datetime(match):
    """Turn a match of `_SYSLOG_TIMESTAMP_REGEX` into a moment, or into None.

    The format carries no year, so it is inferred: a line cannot have been written in the
    future, so a date that lies ahead belongs to the year before. A day of slack absorbs a
    host whose clock runs a little behind the one that wrote the line, and a line that lands
    outside the year this leaves is reported as undated rather than mis-dated, which is all
    a format without a year can honestly say about it.
    """
    month = _SYSLOG_MONTHS.get(match.group(1))
    if month is None:
        return None
    now = datetime.datetime.now()
    earliest = now - datetime.timedelta(days=366)
    latest = now + datetime.timedelta(days=1)
    for year in (now.year, now.year - 1):
        try:
            logged_at = datetime.datetime(
                year,
                month,
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
                int(match.group(5)),
            )
        except ValueError:
            # 31 April, and 29 February in a year that has no such day. The
            # latter is why the year before is tried as well rather than only
            # when the date lies ahead.
            continue
        if earliest <= logged_at <= latest:
            return logged_at
    return None


def timestamp(line, parse_line=None):
    """
    Return the moment a log line was written, as a naive datetime in local time.

    An application that stamps its own lines is the better source, because that stamp says when
    the event happened rather than when the line reached the transport, and because a transport
    is not always there. It is also the one this module cannot know, so a consumer passes it in.
    What is read here without being told is the timestamp the transport prefixes, which is what
    stays when an application logs through syslog and leaves its own out.

    ### Parameters
    - **line** (`str`): One log line.
    - **parse_line** (`callable`, optional):
      The consumer's reader for the application's own timestamp. Takes the line and returns a
      `datetime.datetime` or None. Tried first; the transport's timestamp is the fallback.

    ### Returns
    - **datetime.datetime | None**:
      When the line was written, in local time and without a timezone attached, so it compares
      against `datetime.now()`. None where neither reader found a timestamp, which is not an
      error: a line an application wrote while starting up commonly carries none.

    ### Notes
    - A transport timestamp that carries an offset is converted to local time, so lines written
      before and after a daylight saving change stay in order.
    - Both formats a syslog daemon writes are read: the ISO 8601 moment, and the traditional
      one of RFC 3164 (`Aug 28 19:34:14`). The traditional one names no year, so the year is
      inferred from the assumption that a line was not written in the future.

    ### Example
    >>> timestamp('2026-08-28T17:16:18+0200 host httpd[20]: [ssl:error] AH02032: ...')
    datetime.datetime(2026, 8, 28, 17, 16, 18)
    >>> timestamp('Aug 28 19:34:14 host sshd[193]: Server listening on port 22.')
    datetime.datetime(2026, 8, 28, 19, 34, 14)
    """
    if parse_line:
        logged_at = parse_line(line)
        if logged_at is not None:
            return logged_at
    match = _LINE_TIMESTAMP_REGEX.match(line)
    if not match:
        match = _SYSLOG_TIMESTAMP_REGEX.match(line)
        return _syslog_datetime(match) if match else None
    try:
        # A space-padded hour is put back to what the parsers expect.
        logged_at = lftime.timestr2datetime(
            match.group(1).replace('  ', ' 0').replace('T ', 'T0'), pattern='iso8601'
        )
    except ValueError:
        return None
    if logged_at.tzinfo is not None:
        logged_at = logged_at.astimezone().replace(tzinfo=None)
    return logged_at
