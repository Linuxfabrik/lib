#!/usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library collects some Microsoft PowerShell related functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026092702'

from . import shell


def run_ps(cmd, timeout=None):
    """
    Run a PowerShell command and return its results.

    This function invokes `powershell -Command <cmd>` through
    `lib.shell.shell_exec()` and returns the return code and decoded streams. It is
    synchronous (blocking) and relies on PowerShell being available on PATH
    (Windows PowerShell or PowerShell 7+). No external libraries are required.

    Parameters
    ----------
    cmd : str
        The PowerShell command to execute (passed as a single string
        to the `-Command` argument).
    timeout : int or float, optional
        Maximum time in seconds to allow the command to run. If exceeded,
        PowerShell is killed and the result reports the timeout. Defaults to
        None (no timeout).

    Returns
    -------
    dict
        A result dictionary with:

        - `retc` (`int`): Process return code (`0` indicates success).
        - `stdout` (`str`): Decoded standard output.
        - `stderr` (`str`): Decoded standard error.

    Notes
    -----
    - Running and decoding are those of `lib.shell.shell_exec()`: on Windows the
      output is read as UTF-8 where it is valid and in the OEM code page otherwise,
      elsewhere as UTF-8 with a Latin-1 fallback.
    - A command that cannot be started yields `retc=1`, empty `stdout` and the
      reason in `stderr`.
    - Without `timeout`, the call blocks until the command exits. With it, a
      command that runs longer yields `retc=1`, empty `stdout` and
      `Timeout after <timeout> seconds.` in `stderr`, and the call returns on time
      even when a program PowerShell started keeps the output pipes open.
    - `stderr` is not merged into `stdout`.

    Examples
    --------
    >>> run_ps('Get-Process')
    {
        'retc': 0,
        'stdout': '...process list...',
        'stderr': ''
    }
    """
    # cmd is PowerShell script text and runs as it is, so a caller must never build it
    # from untrusted input; PATH-based powershell lookup is intentional so the hook works
    # across Windows installs. shell_exec() and not subprocess.run(): on Windows, run()
    # collects the output after killing a command that timed out, without a bound, so a
    # child process of PowerShell that holds the pipes made `timeout=3` return after 29
    # seconds. Measured with Python 3.13 on Windows Server 2025.
    success, result = shell.shell_exec(['powershell', '-Command', cmd], timeout=timeout)
    if not success:
        return {
            'retc': 1,
            'stdout': '',
            'stderr': result,
        }
    stdout, stderr, retc = result
    return {
        'retc': retc,
        'stdout': stdout,
        'stderr': stderr,
    }
