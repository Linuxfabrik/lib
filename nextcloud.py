#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Nextcloud related functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026061201'

import json
import os
import shlex
import shutil

from . import disk, shell


def run_occ(path, cmd, _format='json'):
    """
    Run a Nextcloud `occ` command as the owner of `config/config.php`.

    The function locates the PHP interpreter on the system and invokes `occ` explicitly as
    `php <occ> <cmd>`, running via `sudo -u` under the numeric UID that owns
    `config/config.php`. Calling PHP directly avoids relying on `occ` being marked executable
    or on its shebang resolving to a working interpreter, which is not always the case on
    hardened or SCL-based installations.

    ### Parameters
    - **path** *(str | os.PathLike)*:
      Absolute path to the root of the Nextcloud installation (directory that contains `occ` and
      `config/`).
    - **cmd** *(str)*:
      The `occ` subcommand and arguments to execute (e.g., `"status"`, `"user:list --output=json"`).
    - **_format** *(str, optional)*:
      Expected output format. Use `"json"` to parse `stdout` as JSON and return a Python object,
      or any other value (e.g., `"text"`) to return the raw string output. Defaults to `"json"`.

    ### Returns
    - **tuple[bool, Any]**:
      - On success: `(True, result)` where `result` is a Python object if `_format == "json"`,
        otherwise a trimmed `str` of `stdout`.
      - On failure: `(False, error)` where `error` is the captured `stderr` text or an error
        message.

    ### Notes
    - PHP is resolved via `shutil.which('php')`. If no `php` binary is found in `PATH`, the
      call fails with a descriptive error.
    - Requires passwordless or otherwise configured `sudo` permissions for `sudo -u <uid>` to
      succeed.
    - The command runs as the numeric UID of `config/config.php`’s owner, not by username.
      On some systems, shells require escaping `#` in `sudo -u \\#<uid>`.
    - If JSON parsing fails while `_format == "json"`, the function returns
      `(False, "ValueError: No JSON object could be decoded")`.

    ### Example
    >>> ok, result = run_occ('/var/www/nextcloud', 'status', _format='json')
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
            'reachable for the user running the plugin.'
        )

    # get the owner of config.php
    user = disk.get_owner(os.path.join(path, 'config/config.php'))
    occ = os.path.join(path, 'occ')
    # Run occ as the numeric UID of the config.php owner. `sudo -u '#<uid>'` selects
    # the user by UID; the `#` only needs escaping for a shell, which we do not use.
    sudo_cmd = ['sudo', '-u', f'#{user}', php, occ, *shlex.split(cmd)]

    success, result = shell.shell_exec(sudo_cmd)
    stdout, stderr, rc = result

    # Prefer the return code to decide success/failure, not stderr presence
    if not success or rc != 0:
        cmd_display = ' '.join(sudo_cmd)
        return False, f'Error running `{cmd_display}`: rc={rc}\n{stderr or stdout}'

    # If we expect JSON, try to parse it; otherwise return text
    if str(_format).lower() == 'json':
        try:
            # If bytes, decode first; json.loads also accepts bytes, but being explicit helps
            data = json.loads(
                stdout.decode() if isinstance(stdout, (bytes, bytearray)) else stdout
            )
            return True, data
        except json.JSONDecodeError as e:
            # Fall back to text with a clear error
            return False, f'JSON decode error: {e}\nRaw stdout:\n{stdout}'
    else:
        text = (
            stdout.decode().strip()
            if isinstance(stdout, (bytes, bytearray))
            else stdout.strip()
        )
        return True, text
