#!/usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Microsoft PowerShell related functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026070301'

import subprocess  # nosec B404 - required to run PowerShell on Windows targets

from . import txt


def run_ps(cmd):
    """
    Run a PowerShell command and return its results.

    This function invokes `powershell -Command <cmd>` via `subprocess.run`
    and returns the return code and decoded streams. It is synchronous
    (blocking) and relies on PowerShell being available on PATH
    (Windows PowerShell or PowerShell 7+). No external libraries are required.

    ### Parameters
    - **cmd** (`str`): The PowerShell command to execute (passed as a single string
      to the `-Command` argument).

    ### Returns
    - **dict**: A result dictionary with:
      - `retc` (`int`): Process return code (`0` indicates success).
      - `stdout` (`str`): Decoded standard output.
      - `stderr` (`str`): Decoded standard error.

    ### Notes
    - Output decoding is performed via `txt.to_text(...)`.
    - Exceptions are caught and converted to a result with `retc=1`,
      empty `stdout`, and `stderr` containing the formatted exception text.
    - No timeout is applied; the call will block until the command exits.
    - `stderr` is not merged into `stdout`.

    ### Example
    >>> run_ps('Get-Process')
    {
        'retc': 0,
        'stdout': '...process list...',
        'stderr': ''
    }
    """
    try:
        # cmd is admin-provided from the Icinga check config; PATH-based powershell
        # lookup is intentional so the hook works across Windows installs
        result = subprocess.run(  # nosec B603 B607
            ['powershell', '-Command', cmd], capture_output=True
        )
        return {
            #'args': result.args,
            'retc': result.returncode,
            # Decode as UTF-8 with a Latin-1 fallback rather than surrogateescape, so a
            # non-UTF-8 byte does not crash later when the caller prints the result to
            # stdout (Linuxfabrik/lib#256).
            'stdout': txt.to_text(result.stdout, errors='strict_or_latin1'),
            'stderr': txt.to_text(result.stderr, errors='strict_or_latin1'),
        }
    except Exception as e:
        return {
            'retc': 1,
            'stdout': '',
            'stderr': txt.exception2text(e),
        }
