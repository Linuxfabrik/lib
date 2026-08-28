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
__version__ = '2026082802'

import collections
import os
import re
import stat

from . import disk, shell, txt

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
        return False, f'I/O error "{e.strerror}" while reading {path}'
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
    try:
        with open(path, mode='rb') as handle:
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
    if retc != 0:
        return False, (
            f'`{" ".join(cmd)}` exited with error ({retc}, {stderr.strip()}).'
        )
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
