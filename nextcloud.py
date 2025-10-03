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
__version__ = '2025100301'

import json
import os

from . import disk
from . import shell


def run_occ(path, cmd, _format='json'):
    """
    Run a Nextcloud `occ` command as the owner of `config/config.php`.

    The function determines the UID owning `config/config.php` inside the given
    Nextcloud installation, then executes `occ` via `sudo -u` using that UID.
    By default it parses JSON output if requested.

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

    >>> ok, err = run_occ('/var/www/nextcloud', 'user:list --output=json', _format='json')
    >>> ok in (True, False)
    True
    """
    # get the owner of config.php
    user = disk.get_owner(os.path.join(path, 'config/config.php'))
    occ = os.path.join(path, 'occ')
    # When running a command as a UID, many shells require
    # that the `#` be escaped with a backslash (`\`).
    sudo_cmd = f'sudo -u \\#{user} {occ} {cmd}'

    success, result = shell.shell_exec(sudo_cmd)
    stdout, stderr, rc = result

    # Prefer the return code to decide success/failure, not stderr presence
    if not success or rc != 0:
        return False, f'Error running `{sudo_cmd}`: rc={rc}\n{stderr or stdout}'

    # If we expect JSON, try to parse it; otherwise return text
    if str(_format).lower() == 'json':
        try:
            # If bytes, decode first; json.loads also accepts bytes, but being explicit helps
            data = json.loads(stdout.decode() if isinstance(stdout, (bytes, bytearray)) else stdout)
            return True, data
        except json.JSONDecodeError as e:
            # Fall back to text with a clear error
            return False, f'JSON decode error: {e}\nRaw stdout:\n{stdout}'
    else:
        text = stdout.decode().strip() if isinstance(stdout, (bytes, bytearray)) else stdout.strip()
        return True, text
