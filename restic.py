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
__version__ = '2026092701'

import os
import urllib.parse

from . import disk


def _trusted_file_arg(option, path, owners):
    """Return `['--<option>=<resolved path>']` for a file nobody but root and
    `owners` can change, or `(False, message)`.
    """
    if owners is None:
        owners = [os.geteuid()] if hasattr(os, 'geteuid') else []
    success, resolved = disk.resolve_trusted_path(path, owners=owners)
    if not success:
        return False, resolved
    return True, [f'--{option}={resolved}']


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
        return urllib.parse.urlsplit(repo).hostname or ''
    host = repo[5:].split(':', 1)[0]
    return host.split('@', 2)[-1]


def repo_args(repo=None, repository_file=None, owners=None):
    """Return the restic arguments that name the repository, or `(False, message)`.

    Exactly one of `repo` (the repository location itself) or `repository_file` (a
    path restic reads the location from) is used.

    A caller of a privileged consumer must not be able to make restic run a program
    of their choosing. Two of restic's backends start an external program: `rclone:`
    runs `rclone`, which the repository string configures, and `sftp:` runs `ssh`
    with the host as its first argument. The other backends (local, rest, s3, azure,
    gs, b2, swift) talk HTTP or open a path. An `sftp:` host starting with `-` is
    refused, since ssh would read it as an option. An `rclone:` location is refused
    when it comes straight from the caller, and has to be placed in a
    `repository_file` instead, which is accepted
    only where nobody but root and `owners` can change it (see
    `disk.resolve_trusted_path()`); its resolved path is what restic is given.

    Parameters
    ----------
    repo : str, optional
        The repository location, as `--repo` would carry it.
    repository_file : str, optional
        Path to a file whose first line is the repository location.
    owners : iterable of int, optional
        UIDs trusted to own `repository_file` besides root. Defaults to the current
        effective user.

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
        if scheme == 'sftp' and _sftp_host(repo).startswith('-'):
            return False, (
                'Refusing an `sftp:` repository whose host starts with "-", because '
                'ssh would read it as an option.'
            )
        return True, [f'--repo={repo}']
    return _trusted_file_arg('repository-file', repository_file, owners)
