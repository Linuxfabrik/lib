#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Build the command-line arguments that point restic at a repository and its
password, in a way that is safe for a process running with more privileges than
whoever chose the values (for example root via sudo).
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026102401'

import json
import os
import urllib.parse

from . import disk

# Global options that keep a read-only command from writing anything. Without a lock,
# restic creates nothing in the repository, so a `locks/` entry the caller planted as
# a symlink is never written through; without the cache, restic creates nothing below
# its cache directory, whose subdirectory it names after the ID in the repository's
# `config`, which it does not validate (`cache.New()` joins it into the path,
# internal/restic/config.go and internal/global/global.go, verified against restic
# 0.19.1). `check`, `snapshots` and `stats` honour both.
READ_ONLY_ARGS = ('--no-cache', '--no-lock')

# The backends restic recognises by their prefix (internal/backend/location). Any other
# location is a path in the local filesystem.
_REMOTE_SCHEMES = frozenset(
    ('azure', 'b2', 'gs', 'rclone', 'rest', 's3', 'sftp', 'swift')
)


def _trusted_file_arg(option, path, owners):
    """Return `['--<option>=<resolved path>']` for a file nobody but root and
    `owners` can change, or `(False, message)`.
    """
    if owners is None:
        owners = [os.geteuid()] if hasattr(os, 'geteuid') else []
    success, resolved = disk.resolve_trusted_path(path, owners=owners)
    if not success:
        # One answer for every refusal: the reason `resolve_trusted_path()` gives
        # names the first component it could not examine, which would tell the
        # caller what exists below a directory only root may list.
        return False, (
            f'Refusing `{path}` for --{option}: it has to exist, and nobody but root '
            'and the account running restic may be able to change it or any '
            'directory above it.'
        )
    return True, [f'--{option}={resolved}']


def error_lines(stderr, limit=10):
    """Return restic's human-readable error lines from its stderr.

    Before restic 0.18 they are plain text. Since 0.18, with `--json`, each is a JSON
    object carrying the text in `message`, for example
    `{"message_type":"exit_error","code":12,"message":"Fatal: wrong password or no key
    found"}` (verified against restic 0.19.1). Both shapes come back as plain lines,
    capped at `limit`, so a damaged repository cannot flood the output.

    Parameters
    ----------
    stderr : str
        What restic wrote to stderr.
    limit : int, optional
        How many lines to return at most; the first and the last half are kept.
        Defaults to 10.

    Returns
    -------
    list of str
    """
    if not isinstance(stderr, str):
        return []
    lines = []
    for line in stderr.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            lines.append(line)
            continue
        if not isinstance(message, dict):
            # a line that merely parses as JSON, such as a number
            lines.append(line)
        elif isinstance(message.get('message'), str):
            lines.extend(
                part.strip() for part in message['message'].splitlines() if part.strip()
            )
    if len(lines) > limit:
        half = max(limit // 2, 1)
        lines = [*lines[:half], '...', *lines[-half:]]
    return lines


def password_file_arg(password_file, owners=None):
    """Return `['--password-file=<resolved path>']`, or `(False, message)`.

    A privileged consumer hands this path to restic, which opens it. A path the
    caller can change, or a symlink they can swap, would redirect that read; and a
    repository password must not be readable by an unprivileged account to begin
    with. The file is therefore accepted only where nobody but root and `owners` can
    change it, and its resolved path is used.

    Parameters
    ----------
    password_file : str
        Path to the file holding the repository password.
    owners : iterable of int, optional
        UIDs trusted to own the file besides root. Defaults to the current effective
        user.

    Returns
    -------
    tuple
          - `(True, list)` with the argument to append to the restic command.
          - `(False, message)` otherwise.
    """
    if not password_file:
        return False, 'Specify --password-file with a file that only root can change.'
    return _trusted_file_arg('password-file', password_file, owners)


def _sftp_host(repo):
    """Return the host restic hands to `ssh` for an `sftp:` repository.

    restic runs `ssh <host> [-p <port>] [-l <user>] -s sftp`, so the host is the one
    part of the location that reaches ssh as a positional argument; user and port
    follow an option and cannot become one. Mirrors `ParseConfig()` in restic's
    `internal/backend/sftp/config.go` (verified against restic 0.19.1): the URL
    form `sftp://user@host:port/path` and the form `sftp:user@host:path`, where
    everything after the second `@` is the host.
    """
    if repo[:7].lower() == 'sftp://':
        # None for a location urllib refuses: a bracketed host that is no IP address,
        # or a missing `]`. restic refuses both as well (Go's url.Parse, verified with
        # restic 0.19.1 built with Go 1.26), but a build with an older Go may not, and
        # would hand `[-oProxyCommand=...]` to ssh as `-oProxyCommand=...`.
        try:
            return urllib.parse.urlsplit(repo).hostname or ''
        except ValueError:
            return None
    host = repo[5:].split(':', 1)[0]
    return host.split('@', 2)[-1]


def repo_args(repo=None, repository_file=None, owners=None):
    """Return the restic arguments that name the repository, or `(False, message)`.

    Exactly one of `repo` (the repository location itself) or `repository_file` (a
    path restic reads the location from) is used.

    A caller of a privileged consumer must not be able to make restic run a program
    of their choosing. Two of restic's backends start an external program: `rclone:`
    runs `rclone`, which the repository string configures, and `sftp:` runs `ssh`
    with the host as its first argument. An `sftp:` host starting with `-` is
    refused, since ssh would read it as an option. An `rclone:` location is refused
    when it comes straight from the caller, and so is a `rest:` location over a Unix
    socket, which connects to a socket of the caller's choosing. They have to be
    placed in a `repository_file` instead, which is accepted only where nobody but
    root and `owners` can change it (see `disk.resolve_trusted_path()`); its resolved
    path is what restic is given.

    A local repository is a directory restic writes to: locks, and the files it
    creates there. One the caller can change, or reach through a symlink they can
    swap, would let them redirect those writes, so it is accepted on the same terms
    as `repository_file`, and its resolved path is what restic is given. The remote
    backends (rest, s3, azure, gs, b2, swift) talk HTTP. A read-only command adds
    `READ_ONLY_ARGS` on top.

    Parameters
    ----------
    repo : str, optional
        The repository location, as `--repo` would carry it.
    repository_file : str, optional
        Path to a file whose first line is the repository location.
    owners : iterable of int, optional
        UIDs trusted to own `repository_file` or a local repository besides root.
        Defaults to the current effective user.

    Returns
    -------
    tuple
          - `(True, list)` with the arguments to append to the restic command.
          - `(False, message)` otherwise.
    """
    if bool(repo) == bool(repository_file):
        return False, 'Specify exactly one of --repo and --repository-file.'
    if repo:
        scheme = repo.split(':', 1)[0].strip().lower() if ':' in repo else ''
        if scheme == 'rclone':
            return False, (
                'Refusing an `rclone:` repository given with --repo, because it can '
                'run an external program. Put the repository location into a file '
                'that only root can change and pass it with --repository-file.'
            )
        if scheme == 'rest' and '+unix:' in repo.lower():
            return False, (
                'Refusing a `rest:` repository over a Unix socket given with --repo. '
                'Put the repository location into a file that only root can change '
                'and pass it with --repository-file.'
            )
        if scheme not in _REMOTE_SCHEMES:
            # `local:/srv/repo`, or a plain path
            prefix = 'local:' if scheme == 'local' else ''
            success, result = _trusted_file_arg('repo', repo[len(prefix) :], owners)
            if not success:
                return False, result
            return True, [result[0].replace('--repo=', f'--repo={prefix}', 1)]
        if scheme == 'sftp':
            host = _sftp_host(repo)
            if host is None:
                return False, (
                    'Refusing an `sftp:` repository whose host is not a valid host '
                    'name or IP address.'
                )
            if host.startswith('-'):
                return False, (
                    'Refusing an `sftp:` repository whose host starts with "-", '
                    'because ssh would read it as an option.'
                )
        return True, [f'--repo={repo}']
    return _trusted_file_arg('repository-file', repository_file, owners)
