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
__version__ = '2026102401'


import os
import shlex
import shutil
import subprocess  # nosec B404 - this library is the subprocess helper
import time

from . import txt

# This module tells Windows apart with `os.name == 'nt'` and deliberately not with
# `base.WINDOWS`: importing `base` for one constant would load all of it, and its own
# imports, into every consumer of the shell helper.

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
    The exception is a command that takes another command as one string and splits
    it itself, such as rsync's `--rsh`, which honours the same quotes.

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
        The value to check. A `str`, `bytes` or path-like object is checked by its text,
        any other value passes through unchanged.
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
    # bytes and path-like objects reach argv as they are, so they are checked as well
    if isinstance(value, (str, bytes, os.PathLike)):
        text = os.fsdecode(value)
        if text.startswith('-'):
            return False, f'Refusing {name} that starts with "-": {text}'
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


class _OutputTooLarge(Exception):
    """A command printed more than the caller allows. `cap` is the limit it went past."""

    def __init__(self, cap):
        super().__init__(cap)
        self.cap = cap


def _limits(max_bytes):
    """Return the caps for standard output and standard error as a pair, or `None` if
    `max_bytes` is not something `shell_exec()` takes: `None`, an integer of at least 1
    (a cap for each stream), or a pair of those (stdout, stderr), `None` leaving a stream
    open. A `bool` is no number here, and nothing else is accepted."""
    if isinstance(max_bytes, (tuple, list)):
        if len(max_bytes) != 2:
            return None
        limits = tuple(max_bytes)
    else:
        limits = (max_bytes, max_bytes)
    for limit in limits:
        if limit is None:
            continue
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            return None
    return limits


def _size(size):
    """A cap in words: whole MiB as `4 MiB`, a larger one with one decimal, less as bytes."""
    mib = 1024 * 1024
    if size < mib:
        return f'{size} bytes'
    if size % mib == 0:
        return f'{size // mib} MiB'
    return f'{size / mib:.1f} MiB'


def _communicate_bounded(p, stdin, timeout, limits, cmd, state):
    """Like `Popen.communicate()`, but a stream that grows past its cap stops the read.

    Returns `(stdout, stderr)` as bytes, raises `subprocess.TimeoutExpired` where
    `communicate()` would, and `_OutputTooLarge` when a stream is over its cap. The caller
    kills the command. Output is taken in pieces and never held beyond the cap plus one
    piece, which is the point: `communicate()` keeps everything a runaway command prints.
    Both pipes are read at the same time, so a command that fills one while the other is
    full does not block.
    """
    deadline = None if timeout is None else time.monotonic() + timeout
    if os.name == 'nt':
        return _communicate_bounded_threads(
            p, stdin, deadline, timeout, limits, cmd, state
        )
    import selectors  # POSIX: the pipes are plain file descriptors

    chunks = {'out': [], 'err': []}
    sizes = {'out': 0, 'err': 0}
    caps = dict(zip(('out', 'err'), limits))
    selector = selectors.DefaultSelector()
    selector.register(p.stdout, selectors.EVENT_READ, 'out')
    selector.register(p.stderr, selectors.EVENT_READ, 'err')
    pending = memoryview(stdin) if stdin else None
    position = 0
    if pending is not None:
        os.set_blocking(p.stdin.fileno(), False)
        selector.register(p.stdin, selectors.EVENT_WRITE, 'in')
    elif p.stdin is not None:
        p.stdin.close()
    try:
        while selector.get_map():
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise subprocess.TimeoutExpired(cmd, timeout)
            for key, _ in selector.select(remaining):
                if key.data == 'in':
                    try:
                        position += os.write(
                            key.fd, pending[position : position + 65536]
                        )
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        position = len(pending)
                    if position >= len(pending):
                        selector.unregister(p.stdin)
                        p.stdin.close()
                    continue
                data = os.read(key.fd, 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                chunks[key.data].append(data)
                sizes[key.data] += len(data)
                if caps[key.data] is not None and sizes[key.data] > caps[key.data]:
                    raise _OutputTooLarge(caps[key.data])
        remaining = None if deadline is None else max(deadline - time.monotonic(), 0)
        p.wait(timeout=remaining)
    finally:
        selector.close()
        # `communicate()` closes the pipes it read, and so does this
        p.stdout.close()
        p.stderr.close()
    return b''.join(chunks['out']), b''.join(chunks['err'])


def _communicate_bounded_threads(p, stdin, deadline, timeout, limits, cmd, state):
    """`_communicate_bounded()` for Windows, where a pipe cannot be waited on with
    `select()`: a thread per pipe, polled from here. The threads are daemons and end with
    the caller, as the ones of `communicate()` do. The thread that feeds standard input is
    handed back in `state['feeder']`, so the caller can tell whether it is still writing,
    and the pipes with the thread that reads each of them in `state['pumps']`, for
    `_close_finished_pipes()`."""
    import threading  # only here: nothing else of this module needs it

    chunks = {'out': bytearray(), 'err': bytearray()}
    too_large = []

    def pump(stream, key, cap):
        while True:
            data = stream.read1(65536)
            if not data:
                return
            chunks[key].extend(data)
            if cap is not None and len(chunks[key]) > cap:
                too_large.append(cap)
                return

    def feed():
        try:
            p.stdin.write(stdin)
        except OSError:
            pass
        finally:
            try:
                p.stdin.close()
            except OSError:
                pass

    threads = [
        threading.Thread(target=pump, args=(p.stdout, 'out', limits[0]), daemon=True),
        threading.Thread(target=pump, args=(p.stderr, 'err', limits[1]), daemon=True),
    ]
    state['pumps'] = ((p.stdout, threads[0]), (p.stderr, threads[1]))
    if stdin:
        state['feeder'] = threading.Thread(target=feed, daemon=True)
        threads.append(state['feeder'])
    elif p.stdin is not None:
        p.stdin.close()
    for thread in threads:
        thread.start()
    while any(thread.is_alive() for thread in threads):
        if too_large:
            raise _OutputTooLarge(too_large[0])
        if deadline is not None and time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(cmd, timeout)
        time.sleep(0.02)
    if too_large:
        raise _OutputTooLarge(too_large[0])
    remaining = None if deadline is None else max(deadline - time.monotonic(), 0)
    p.wait(timeout=remaining)
    return bytes(chunks['out']), bytes(chunks['err'])


def _close_finished_pipes(state):
    """Close the pipes of a command that the Windows reader took the output from, as
    `communicate()` does, so none is left to the garbage collector. Only a pipe whose reading
    thread has ended is closed: closing one under a blocked `read1()` waits for the lock
    that read holds (see `_kill()`), and the thread ends with the caller. Nothing to do on
    POSIX, where `_communicate_bounded()` closes them itself and `state` is empty."""
    for pipe, thread in state.get('pumps', ()):
        if not thread.is_alive():
            try:
                pipe.close()
            except OSError:
                pass


def _feeding(state):
    """Whether the thread that writes standard input of the command is still at it."""
    feeder = state.get('feeder')
    return feeder is not None and feeder.is_alive()


def _kill(p, keep_stdin=False):
    """Kill a command and let go of it, without waiting for ever on a child that cannot
    die: it is reaped as far as `_KILL_GRACE` allows and its pipes are closed. With
    `keep_stdin`, standard input stays open: a thread is still writing to it, and closing a
    pipe under a blocked write is what a Windows caller must not do. The write ends with the
    process."""
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
    #
    # Not stdout and stderr on Windows. There communicate() reads them in daemon
    # threads that are still blocked in read() after a timeout, and closing a pipe
    # waits for the lock that read holds (`ENTER_BUFFERED` in CPython's
    # Modules/_io/bufferedio.c). A child that inherited the pipes, a program
    # started from a PowerShell command for example, kept them open, and a call
    # with `timeout=3` returned after 29 seconds. Measured with Python 3.13 on
    # Windows Server 2025. The threads end with the caller.
    pipes = (p.stdin,) if os.name == 'nt' else (p.stdin, p.stdout, p.stderr)
    if keep_stdin:
        pipes = tuple(pipe for pipe in pipes if pipe is not p.stdin)
    for pipe in pipes:
        try:
            if pipe is not None:
                pipe.close()
        except OSError:
            pass


def shell_exec(
    cmd,
    env=None,
    stdin='',
    cwd=None,
    timeout=None,
    lc_all='C',
    run_as=None,
    run_as_session=True,
    max_bytes=None,
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
    max_bytes : int or tuple, optional
        The most the command may print, in bytes: one number for standard output and
        standard error each, or `(stdout, stderr)`; `None` for one of the two leaves it open.
        Both are read as they come, and a command that goes past its cap is killed and
        reported as `(False, 'The output of <program> exceeded <N> MiB.')`, instead of
        being held in memory until it ends. A value that is none of these, a `bool`, a number
        below 1 or a tuple of another length for example, is refused with
        `(False, message)` before the command is started. Defaults to None, which reads
        everything the command prints, as before.

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
      not end up in it. A program that does not exist is reported as
      `Command "<program>" not found (<strerror>). ...`.
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
    limits = None
    if max_bytes is not None:
        # before anything is started: a value that is refused later would leave a child
        # behind
        limits = _limits(max_bytes)
        if limits is None:
            return False, (
                'max_bytes must be None, an integer of at least 1, or a pair of those '
                f'(stdout, stderr), not {max_bytes!r}.'
            )

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
    except FileNotFoundError as e:
        # Popen raises the same error for a working directory that does not exist, and
        # names that directory then.
        if cwd is not None and e.filename == cwd:
            return False, f'Error "{e}" while calling command "{program}"'
        # A missing program is the most common reason a command cannot be started, so it
        # is named in words that say what to do. `strerror` stays in the message for
        # callers that recognize this case by it. The file that is missing can also be
        # the `sudo` that `run_as` puts in front; any other name is not trusted to be
        # free of arguments and falls back to the program.
        missing = e.filename if e.filename in (cmd[0], program) else program
        return False, (
            f'Command "{missing}" not found ({e.strerror}). Install it, or make sure '
            f'it is in the PATH of the account running this.'
        )
    except (OSError, ValueError, Exception) as e:
        # Name the program only, never its arguments. An argument list carries
        # credentials in forms no redaction knows by name (`ipmitool -P <password>`,
        # `redis-cli -a <password>`, `snmpget -c <community>`), and this message is
        # routinely printed as part of a result, which is exactly the case where the
        # program is missing and every argument would otherwise be shown.
        return False, f'Error "{e}" while calling command "{program}"'

    state = {}  # what the Windows reader hands back, see _communicate_bounded_threads()
    try:
        if max_bytes is None:
            stdout, stderr = p.communicate(
                input=txt.to_bytes(stdin) if stdin else None,
                timeout=timeout,
            )
        else:
            try:
                stdout, stderr = _communicate_bounded(
                    p,
                    txt.to_bytes(stdin) if stdin else None,
                    timeout,
                    limits,
                    cmd,
                    state,
                )
            except (subprocess.TimeoutExpired, _OutputTooLarge):
                raise
            except BaseException:
                # whatever else goes wrong, the command it was reading from does not
                # outlive the call
                _kill(p, keep_stdin=_feeding(state))
                _close_finished_pipes(state)
                raise
    except subprocess.TimeoutExpired:
        _kill(p, keep_stdin=_feeding(state))
        _close_finished_pipes(state)
        return False, f'Timeout after {timeout} seconds.'
    except _OutputTooLarge as e:
        _kill(p, keep_stdin=_feeding(state))
        _close_finished_pipes(state)
        return False, f'The output of {program} exceeded {_size(e.cap)}.'

    _close_finished_pipes(state)

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
