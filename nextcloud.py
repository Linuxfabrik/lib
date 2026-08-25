#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library collects some Nextcloud related functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082501'

import json
import os
import shlex
import shutil

from . import disk, shell


def run_occ(path, cmd, _format='json', timeout=None):
    """
    Run a Nextcloud `occ` command as the owner of `config/config.php`.

    The function locates the PHP interpreter on the system and invokes `occ` explicitly as
    `php <occ> --no-warnings <cmd>`. Calling PHP directly avoids relying on `occ` being
    marked executable or on its shebang resolving to a working interpreter, which is not
    always the case on hardened or SCL-based installations.

    Nextcloud's `console.php` aborts unless the calling process runs under the UID that
    owns `config/config.php`. If the current process is not that owner, the command is
    prefixed with `sudo -u '#<uid>'`; if it already is, `sudo` is skipped, so no sudoers
    entry is needed and the call also works in containers that ship without `sudo`.

    ### Parameters
    - **path** *(str | os.PathLike)*:
      Absolute path to the root of the Nextcloud installation (directory that contains `occ` and
      `config/`).
    - **cmd** *(str)*:
      The `occ` subcommand and arguments to execute (e.g., `"status"`, `"user:list --output=json"`).
    - **_format** *(str, optional)*:
      Use `"json"` to parse `stdout` as JSON and return a Python object, or any other value
      (e.g., `"text"`) to return the raw string output. Defaults to `"json"`.
    - **timeout** *(int | float | None, optional)*:
      Seconds to wait for `occ` before killing it. `None` (the default) waits indefinitely,
      which is what long-running commands such as `app:update` need.

    ### Returns
    - **tuple[bool, Any]**:
      - On success: `(True, result)` where `result` is a Python object if `_format == "json"`,
        otherwise a trimmed `str` of `stdout`.
      - On failure: `(False, error)` where `error` is a message describing the failed
        precondition, the failure reported by `shell.shell_exec()` (interpreter not found,
        timeout), the captured output of a non-zero exit, or the JSON decode error.

    ### Notes
    - `_format` only selects how the output is parsed. It does not add `--output=json` to the
      command; the caller has to do that. Not every `occ` command accepts that option, and the
      only valid values are `plain`, `json` and `json_pretty`. Some commands, `config:list`
      among them, already emit JSON without the option.
    - PHP is resolved via `shutil.which('php')`. If no `php` binary is found in `PATH`, the
      call fails with a descriptive error.
    - `--no-warnings` keeps Nextcloud's startup banners (missing PCNTL extension, environment
      complaints, upgrade and maintenance notices) out of the output. `console.php` writes
      several of them to stdout, where they would otherwise break JSON parsing. The option is
      global and does not silence the command's own output.
    - `occ` is run with the Nextcloud root as its working directory, which is where
      `console.php` chdirs to anyway. Doing it up front avoids the complaint it emits when the
      inherited working directory is unreadable.
    - A few failure paths inside Nextcloud print an error and exit with code 0. In JSON mode
      those are caught by the failing parse. In text mode they are indistinguishable from
      regular output, and one of them is translated, so no attempt is made to detect them.

    ### Example
    >>> ok, result = run_occ('/var/www/nextcloud', 'status --output=json')
    >>> ok
    True
    >>> isinstance(result, dict)
    True

    >>> ok, err = run_occ(
    ...     '/var/www/nextcloud', 'user:list --output=json', _format='json'
    ... )
    >>> ok in (True, False)
    True
    """
    php = shutil.which('php')
    if not php:
        return False, (
            'Could not find a `php` interpreter in PATH. Install PHP or make sure it is '
            'reachable for the user running this process.'
        )

    # get the owner of config.php
    config = os.path.join(path, 'config/config.php')
    user = disk.get_owner(config)
    if user == -1:
        return False, (
            f'Could not determine the owner of `{config}`. Make sure the path points to a '
            'Nextcloud installation and that the file is readable.'
        )

    occ = os.path.join(path, 'occ')
    # `--no-warnings` goes in front of the subcommand so it cannot be swallowed as the value
    # of a preceding optional-value option. Symfony parses global options anywhere.
    occ_cmd = [php, occ, '--no-warnings', *shlex.split(cmd)]

    # Only switch users if we are not the owner already. `sudo -u '#<uid>'` selects the user
    # by UID; the `#` only needs escaping for a shell, which we do not use. geteuid() is
    # POSIX-only, so probe for it instead of testing the platform.
    if not hasattr(os, 'geteuid') or os.geteuid() != user:
        occ_cmd = ['sudo', '-u', f'#{user}', *occ_cmd]

    success, result = shell.shell_exec(occ_cmd, cwd=path, timeout=timeout)
    # shell_exec() reports its own failures (spawn error, timeout) as (False, <message>),
    # so the result is only a triple once success is confirmed.
    if not success:
        return False, result

    stdout, stderr, rc = result

    # Prefer the return code to decide success/failure, not stderr presence
    if rc != 0:
        cmd_display = ' '.join(occ_cmd)
        return False, f'Error running `{cmd_display}`: rc={rc}\n{stderr or stdout}'

    # If we expect JSON, try to parse it; otherwise return text
    if str(_format).lower() == 'json':
        try:
            return True, json.loads(stdout)
        except json.JSONDecodeError as e:
            # Fall back to text with a clear error
            return False, f'JSON decode error: {e}\nRaw stdout:\n{stdout}'

    return True, stdout.strip()
