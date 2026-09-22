#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Communicates with the Shell on Linux and Windows."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026092201'


import os
import shlex
import shutil
import subprocess  # nosec B404 - this library is the subprocess helper

from . import txt

# How long a killed command is given to actually die before `shell_exec()` reports the
# timeout without it. Long enough for a process that can act on the signal, short enough
# that one which cannot does not extend the caller's deadline in any meaningful way.
_KILL_GRACE = 1

RETC_SSHPASS = {
    1: 'Invalid command line argument',
    2: 'Conflicting arguments given',
    3: 'General runtime error',
    4: 'Unrecognized response from ssh (parse error)',
    5: 'Invalid/incorrect password',
    6: 'Host public key is unknown. sshpass exits without confirming the new key.',
    7: 'IP public key changed. sshpass exits without confirming the new key.',
}


def quote_cli_value(value):
    """
    Quote a value for a command line that a person is going to run.

    For a command a consumer *prints* rather than executes: a remediation hint, a
    reproduction step, a copy-pasteable follow-up. Such a command is executed by a
    shell eventually, the reader's own, so every value interpolated into it has to
    survive that shell as a single word. A value carrying a space, a quote, a
    semicolon or a backtick otherwise turns one printed command into two, and the
    second one is written by whoever controls the value. That the consumer never runs
    the command itself is what makes this easy to overlook.

    Values that reach a command as an argument list instead are quoted by nothing and
    need nothing: `shell_exec()` passes them verbatim. Use `safe_cli_value()` there.

    Parameters
    ----------
    value : any
        The value to quote. Anything that is not a string is
        converted to one first, so a number or a path object can be passed as it is.

    Returns
    -------
    str
        The value as a single shell word, quoted where it has to be.

    Notes
    -----
    - POSIX shell quoting. A command meant for `cmd.exe` or PowerShell needs different
      quoting and this is the wrong helper for it.
    - Quoting keeps a hostile value from becoming a second command, it does not make
      it a sensible one. Where a value has a known shape, validate it as well.

    Examples
    --------
    >>> quote_cli_value('www.example.com')
    'www.example.com'

    >>> quote_cli_value('a b; rm -rf /')
    "'a b; rm -rf /'"
    """
    return shlex.quote(str(value))


# Python's codec for the OEM code page of the running Windows (cp437, cp850, ...).
_OEM_CODEC = 'oem'


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

    Parameters
    ----------
    value : any
        The value to check. Non-string values pass through unchanged.
    name : str, optional
        Human-readable name used in the error message. Defaults to
        `'value'`.

    Returns
    -------
    tuple
        `(True, value)` if the value is safe, else `(False, error_message)`. The shape
        is suitable for `lib.base.coe()`.

    Examples
    --------
    >>> host = lib.base.coe(lib.shell.safe_cli_value(args.HOSTNAME, '--hostname'))
    """
    if isinstance(value, str) and value.startswith('-'):
        return False, f'Refusing {name} that starts with "-": {value}'
    return True, value


def _decode_windows_output(raw):
    """
    Decode what a program on Windows wrote into a pipe.

    There is no one code page to ask for. `net.exe` writes the OEM code page into a
    pipe whatever the console says, while `cmd.exe` and PowerShell follow the console
    output code page. Icinga 2 sets that one to UTF-8 (`SetConsoleOutputCP(65001)` in
    `DaemonCommand::Run()`) and its plugins inherit the console, so under the agent the
    same user "müller" arrives as `0x81` from one program and as `0xC3 0xBC` from the
    other, and in an interactive session as `0x81` from both. Measured with Icinga 2
    v2.16.5 on Windows Server 2025 (`net user`, `net localgroup` and `query user` write
    the OEM code page, `cmd /c echo` and `powershell` follow the console). Non-ASCII text in an OEM code page is practically never valid
    UTF-8, so trying UTF-8 strictly first and falling back to the OEM code page reads
    both (Linuxfabrik/monitoring-plugins#681). `chcp 65001` does not help: it changes
    the console, which is not where a pipe gets its encoding from.

    Parameters
    ----------
    raw : bytes
        The captured output.

    Returns
    -------
    str
        The decoded text. A byte the OEM code page does not define becomes
        U+FFFD instead of an exception.
    """
    try:
        return txt.to_text(raw, encoding='utf-8', errors='strict')
    except UnicodeDecodeError:
        return txt.to_text(raw, encoding=_OEM_CODEC, errors='replace')


def shell_exec(
    cmd,
    env=None,
    stdin='',
    cwd=None,
    timeout=None,
    lc_all='C',
    run_as=None,
    run_as_session=True,
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

    Parameters
    ----------
    cmd : list
        The command to execute, as a list of arguments (argv), e.g. `['ls', '-l', '/tmp']`.
        The first element is the program, the rest are its arguments.
    env : dict, optional
        A dictionary of environment variables to merge with the current OS environment.
        An entry whose value is None removes that variable from the child's environment
        rather than setting it, which is the only way to run a command *without* a
        variable this process exports. Defaults to the current environment.
    stdin : str, optional
        A string to pass as standard input to the command. Defaults to an empty string.
    cwd : str, optional
        Working directory in which to execute the command. Defaults to None (current directory).
    timeout : int or float, optional
        Maximum time (in seconds) to allow the command to run. If exceeded, the process is
        terminated. Defaults to None (no timeout).
    lc_all : str, optional
        Value to set for the `LC_ALL` environment variable, forcing command output locale.
        Defaults to `'C'` (POSIX "C" locale, i.e., English).
    run_as : str, optional
        Local user name to run the command as. The command is wrapped so it runs as that
        user with the user's session runtime directory exported
        (`sudo --user <user> env XDG_RUNTIME_DIR=/run/user/<uid> ...`), which per-user session
        services such as rootless Podman or `systemctl --user` need in order to find the
        right session when invoked from root or another account. The caller must already
        be allowed to `sudo --user <user>` (root is, by default). When `run_as` is set and no
        `cwd` is given, `cwd` defaults to `/` so `sudo` can chdir as the target user
        without a harmless warning. An unknown user yields `(False, error_message)`.
        Defaults to None (run as the current user). Unix-only.
    run_as_session : bool, optional
        Only meaningful together with `run_as`. When False, the command is wrapped as
        `sudo --user <user> ...` without the session runtime directory, so what `sudo` sees is
        exactly the program and the arguments the caller passed. A sudo rule that spells
        out the permitted command with its exact arguments (the safe way to grant one
        specific command instead of an interpreter with free arguments) only matches that
        plain form; the session wrapper turns the permitted program into `env` and makes
        the rule miss. Leave it at True wherever a per-user session service such as
        rootless Podman or `systemctl --user` has to be reached. Defaults to True.

    Returns
    -------
    tuple
        - On success:
          `(True, (stdout, stderr, return_code))`

          - **stdout** (`str`): Standard output of the command (decoded to text).
          - **stderr** (`str`): Standard error of the command (decoded to text).
          - **return_code** (`int`): Exit status of the command.
        - On failure:
          `(False, error_message)` — a string describing the error.

    Notes
    -----
    - The environment is merged with `env`, entries set to None are removed from it, and it
      always includes `LC_ALL=<lc_all>`, forcing output to the specified locale.
    - Exceptions such as `OSError`, `ValueError`, or other execution errors during process
      creation are caught and reported as `(False, <error message>)`. The message names
      the program, never its arguments, so a credential passed on the command line does
      not end up in it.
    - If the process exceeds the specified `timeout`, it is killed, and the function returns
      `(False, "Timeout after <timeout> seconds.")`. The call returns even where the kill
      cannot take effect: a command blocked on storage that has gone away sits in an
      uninterruptible sleep, takes the signal and does not act on it until the storage
      answers again. Such a child outlives the call as an orphan, which is the price of
      holding the deadline; the caller gets its answer on time either way.
    """
    if not isinstance(cmd, (list, tuple)):
        raise TypeError(
            'shell_exec() requires cmd as a list of arguments '
            f'(for example ["df", "-h"]), got {type(cmd).__name__}.'
        )
    # The program the caller asked for, before `run_as` puts `sudo` in front of it.
    program = cmd[0] if cmd else ''

    if run_as:
        import pwd  # Unix-only; per-user session switching does not apply on Windows

        try:
            uid = pwd.getpwnam(run_as).pw_uid
        except KeyError:
            return False, f'Unknown user: {run_as}'
        session = ['env', f'XDG_RUNTIME_DIR=/run/user/{uid}'] if run_as_session else []
        cmd = ['sudo', '--user', run_as, *session, *cmd]
        if cwd is None:
            cwd = '/'

    # A value of None removes the variable instead of setting it. Merging on its own
    # cannot express that, and a caller sometimes has to hand a command an environment
    # *without* a variable this process exports - a credential that was rejected and is
    # deliberately dropped for the next attempt, above all, where leaving it in place
    # would repeat the same failure.
    env = {**os.environ, **(env or {})}
    env = {key: value for key, value in env.items() if value is not None}
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
        # Name the program only, never its arguments. An argument list carries
        # credentials in forms no redaction knows by name (`ipmitool -P <password>`,
        # `redis-cli -a <password>`, `snmpget -c <community>`), and this message is
        # routinely printed as part of a result, which is exactly the case where the
        # program is missing and every argument would otherwise be shown.
        return False, f'Error "{e}" while calling command "{program}"'

    try:
        stdout, stderr = p.communicate(
            input=txt.to_bytes(stdin) if stdin else None,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        p.kill()
        try:
            # Reaping the child is what turns the kill into a finished process, but it
            # must not become a second wait without an end. A command that blocks on
            # storage that has gone away - `lvs` while one PV does not answer, `df` on a
            # dead network mount - sits in an uninterruptible sleep, where it takes the
            # signal and still cannot act on it. Verified on Rocky 10 / kernel 6.12
            # against a suspended device-mapper device: without a bound, a call with
            # `timeout=5` never returned. Give the kill a moment to land and hand the
            # timeout back either way; the orphan ends when its storage answers again.
            #
            # Wait for the process, not for its pipes. A grandchild the command left
            # behind keeps the pipes open after the command itself is gone, and
            # reading them until the end left the killed command unreaped: a zombie
            # for as long as the caller runs. `wait()` with a timeout polls the process
            # alone (`waitpid(WNOHANG)`, CPython `Popen._wait()`), so it is bounded the
            # same way.
            p.wait(timeout=_KILL_GRACE)
        except subprocess.TimeoutExpired:
            pass
        # Let go of the pipes rather than leaving them open for the lifetime of the
        # caller. An orphan writing into them gets EPIPE the next time it runs, which
        # is one more thing that ends it.
        for pipe in (p.stdin, p.stdout, p.stderr):
            try:
                if pipe is not None:
                    pipe.close()
            except OSError:
                pass
        return False, f'Timeout after {timeout} seconds.'

    # Decode the captured bytes. On Windows a program picks the code page of its
    # piped output itself, see _decode_windows_output().
    if os.name == 'nt':
        return True, (
            _decode_windows_output(stdout),
            _decode_windows_output(stderr),
            p.returncode,
        )
    # On Unix decode as UTF-8, but fall back to Latin-1 on invalid bytes instead of
    # surrogateescape: a lone surrogate decodes fine here but crashes later when the
    # caller re-encodes the message for stdout (Linuxfabrik/lib#256).
    return True, (
        txt.to_text(stdout, errors='strict_or_latin1'),
        txt.to_text(stderr, errors='strict_or_latin1'),
        p.returncode,
    )


def which(name):
    """
    Locate an executable in the system PATH, like the `which` command.

    Thin wrapper around `shutil.which()` so callers do not need to import it
    directly and the lookup stays consistent across consumers.

    Parameters
    ----------
    name : str
        Program name to look for (e.g. `lynis`).

    Returns
    -------
    str or None
        The absolute path to the executable, or `None` if it is
        not found in PATH.

    Examples
    --------
    >>> which('sh')
    '/usr/bin/sh'
    """
    return shutil.which(name)
