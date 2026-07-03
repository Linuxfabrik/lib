#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Communicates with the Shell on Linux and Windows."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026070301'


import os
import shutil
import subprocess  # nosec B404 - this library is the subprocess helper

from . import txt

RETC_SSHPASS = {
    1: 'Invalid command line argument',
    2: 'Conflicting arguments given',
    3: 'General runtime error',
    4: 'Unrecognized response from ssh (parse error)',
    5: 'Invalid/incorrect password',
    6: 'Host public key is unknown. sshpass exits without confirming the new key.',
    7: 'IP public key changed. sshpass exits without confirming the new key.',
}


def shell_exec(
    cmd, env=None, stdin='', cwd=None, timeout=None, lc_all='C', run_as=None
):
    """
    Execute a command in a subprocess, given as a list of arguments (argv).

    The command is always run with `shell=False`, so no shell is involved: arguments are passed
    verbatim to the executable and are never interpreted for pipes (`|`), redirection, globbing,
    variable expansion or any other shell metacharacter. This makes the helper safe to call with
    untrusted argument values: a value like `|reboot|` or `; rm -rf /` ends up as one literal
    argument, not as a command.

    Because there is no shell, `cmd` must be a list (argv). Passing a string raises `TypeError`.
    Build the command as a list, for example `['df', '--human-readable', mountpoint]`, where
    `mountpoint` may be untrusted. A genuine pipeline (`a | b`) has to be expressed in code by
    running the stages and connecting them explicitly, or by post-processing the first command's
    output; it can no longer be expressed as a shell string.

    ### Parameters
    - **cmd** (`list`):
      The command to execute, as a list of arguments (argv), e.g. `['ls', '-l', '/tmp']`.
      The first element is the program, the rest are its arguments.
    - **env** (`dict`, optional):
      A dictionary of environment variables to merge with the current OS environment.
      Defaults to the current environment.
    - **stdin** (`str`, optional):
      A string to pass as standard input to the command. Defaults to an empty string.
    - **cwd** (`str`, optional):
      Working directory in which to execute the command. Defaults to None (current directory).
    - **timeout** (`int` or `float`, optional):
      Maximum time (in seconds) to allow the command to run. If exceeded, the process is
      terminated. Defaults to None (no timeout).
    - **lc_all** (`str`, optional):
      Value to set for the `LC_ALL` environment variable, forcing command output locale.
      Defaults to `'C'` (POSIX "C" locale, i.e., English).
    - **run_as** (`str`, optional):
      Local user name to run the command as. The command is wrapped so it runs as that
      user with the user's session runtime directory exported
      (`sudo -u <user> env XDG_RUNTIME_DIR=/run/user/<uid> ...`), which per-user session
      services such as rootless Podman or `systemctl --user` need in order to find the
      right session when invoked from root or another account. The caller must already
      be allowed to `sudo -u <user>` (root is, by default). When `run_as` is set and no
      `cwd` is given, `cwd` defaults to `/` so `sudo` can chdir as the target user
      without a harmless warning. An unknown user yields `(False, error_message)`.
      Defaults to None (run as the current user). Unix-only.

    ### Returns
    - **tuple**:
      - On success:
        `(True, (stdout, stderr, return_code))`
        - **stdout** (`str`): Standard output of the command (decoded to text).
        - **stderr** (`str`): Standard error of the command (decoded to text).
        - **return_code** (`int`): Exit status of the command.
      - On failure:
        `(False, error_message)` — a string describing the error.

    ### Notes
    - The environment is merged with `env` and always includes `LC_ALL=<lc_all>`, forcing output
      to the specified locale.
    - Exceptions such as `OSError`, `ValueError`, or other execution errors during process
      creation are caught and reported as `(False, <error message>)`.
    - If the process exceeds the specified `timeout`, it is killed, and the function returns
      `(False, "Timeout after <timeout> seconds.")`.
    """
    if not isinstance(cmd, (list, tuple)):
        raise TypeError(
            'shell_exec() requires cmd as a list of arguments '
            f'(for example ["df", "-h"]), got {type(cmd).__name__}.'
        )

    if run_as:
        import pwd  # Unix-only; per-user session switching does not apply on Windows

        try:
            uid = pwd.getpwnam(run_as).pw_uid
        except KeyError:
            return False, f'Unknown user: {run_as}'
        cmd = [
            'sudo',
            '-u',
            run_as,
            'env',
            f'XDG_RUNTIME_DIR=/run/user/{uid}',
            *cmd,
        ]
        if cwd is None:
            cwd = '/'

    env = {**os.environ.copy(), **(env or {})}
    env['LC_ALL'] = lc_all

    try:
        p = subprocess.Popen(  # nosec B603 - shell=False, cmd is an argv list, no shell interpretation
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            shell=False,
            cwd=cwd,
        )
    except (OSError, ValueError, Exception) as e:
        return False, f'Error "{e}" while calling command "{cmd}"'

    try:
        stdout, stderr = p.communicate(
            input=txt.to_bytes(stdin) if stdin else None,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        return False, f'Timeout after {timeout} seconds.'

    # Decode the captured bytes. On Windows, console programs (query, schtasks,
    # w32tm, ...) write their piped output in the OEM / console output code page
    # (e.g. cp437, cp850), not UTF-8 and not the ANSI code page, so a username
    # like "müller" would otherwise be mangled (Linuxfabrik/monitoring-plugins#681).
    if os.name == 'nt':
        encoding = _windows_output_encoding()
        return True, (
            txt.to_text(stdout, encoding=encoding, errors='replace'),
            txt.to_text(stderr, encoding=encoding, errors='replace'),
            p.returncode,
        )
    # On Unix decode as UTF-8, but fall back to Latin-1 on invalid bytes instead of
    # surrogateescape: a lone surrogate decodes fine here but crashes later when the
    # plugin re-encodes the message for stdout (Linuxfabrik/lib#256).
    return True, (
        txt.to_text(stdout, errors='strict_or_latin1'),
        txt.to_text(stderr, errors='strict_or_latin1'),
        p.returncode,
    )


def _windows_output_encoding():
    """
    Best-effort code page name for decoding a Windows subprocess's piped output.

    Console programs emit their pipe output in the OEM / console output code page, not UTF-8 and
    not the ANSI code page (`chcp 65001` has no effect on a pipe; see PEP 528). Prefer the console
    output code page, fall back to the OEM code page when the process has no console (for example
    when run headless by a monitoring agent), and fall back to UTF-8 if neither is available.

    ### Returns
    - **str**: A Python codec name such as `'cp437'`, or `'utf-8'` as a last resort.
    """
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        code_page = kernel32.GetConsoleOutputCP() or kernel32.GetOEMCP()
        if code_page:
            return f'cp{code_page}'
    except (OSError, AttributeError, ValueError):
        pass
    return 'utf-8'


def safe_cli_value(value, name='value'):
    """
    Reject a value that a called program could misinterpret as an option.

    Building a command as an argument list (argv) and running it with `shell_exec()` prevents
    shell injection, but it does not stop a value that starts with `-` from being picked up as an
    *option* by the program being run, for example an ssh destination `-oProxyCommand=...` (remote
    code execution) or a `ping` target `-f` (flood). Use this for values that reach a command as a
    positional argument or as a command target, where option-style values have no legitimate
    meaning. Values that are bound to an explicit option (`--name=<value>` or `-H <value>`) do not
    need this guard.

    ### Parameters
    - **value** (`any`): The value to check. Non-string values pass through unchanged.
    - **name** (`str`, optional): Human-readable name used in the error message. Defaults to
      `'value'`.

    ### Returns
    - **tuple**: `(True, value)` if the value is safe, else `(False, error_message)`. The shape
      is suitable for `lib.base.coe()`.

    ### Example
    >>> host = lib.base.coe(lib.shell.safe_cli_value(args.HOSTNAME, '--hostname'))
    """
    if isinstance(value, str) and value.startswith('-'):
        return False, f'Refusing {name} that starts with "-": {value}'
    return True, value


def which(name):
    """
    Locate an executable in the system PATH, like the `which` command.

    Thin wrapper around `shutil.which()` so callers do not need to import it
    directly and the lookup stays consistent across consumers.

    ### Parameters
    - **name** (`str`): Program name to look for (e.g. `lynis`).

    ### Returns
    - **str or None**: The absolute path to the executable, or `None` if it is
      not found in PATH.

    ### Example
    >>> which('sh')
    '/usr/bin/sh'
    """
    return shutil.which(name)
