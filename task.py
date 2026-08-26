#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

"""Runs work under a deadline that holds even when the work cannot be interrupted.

A call that waits on a network filesystem does not fail when the server behind it goes
away, it blocks, and on Linux it blocks in a sleep the kernel does not let a signal
handler, a thread or an alarm cut short. `statvfs()`, `stat()`, `pathconf()` and every
read and write below such a mount point behave that way. Wrapping them in a timeout
inside the same process therefore does nothing: the process is in the kernel and does not
come back to run the timeout.

The way out is to make the call somewhere the caller can dispose of, so the work runs in
a child process and the deadline is enforced by killing that child. The sleep ends on any
signal that would terminate the process anyway, which is what makes the kill work.

Every job is started before the first one is waited for, and they share a single
deadline, so ten unreachable mount points take as long as one instead of ten times as
long. One child process is started per job.

Where `os.fork()` does not exist, the jobs are simply run in the calling process. The
uninterruptible sleep this guards against is a Linux behaviour; elsewhere the guard has
nothing to protect against and would only cost a process per job.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082601'

import json
import os
import select
import signal
import time

from . import txt

# What a job's result is replaced with when it did not finish in time, as opposed to one
# that finished by raising. Callers that treat the two differently compare against this.
TIMEOUT = 'did not answer in time'

# How much a single job may hand back. A job is expected to return a small summary, and
# a caller cannot be left buffering without limit because a job went wrong.
MAX_RESULT_BYTES = 8 * 1024 * 1024

# What a job is given back when it produced more than MAX_RESULT_BYTES.
_TOO_LARGE = f'the answer was larger than {MAX_RESULT_BYTES} bytes'

# What a job is given back when nothing readable came out of it.
_UNREADABLE = 'the answer could not be read'


def run(func, timeout=8):
    """
    Run one callable under a deadline.

    Shorthand for `run_each()` with a single job. See there for what a callable may
    return and how failures are reported.

    ### Parameters
    - **func** (`callable`): Takes no arguments. Its return value has to be
      JSON-serialisable.
    - **timeout** (`int` or `float`, optional): Seconds the callable is given. Defaults
      to 8.

    ### Returns
    - **tuple**:
      - On success: `(True, result)` - whatever `func` returned.
      - On failure: `(False, error_message)`. The message is `TIMEOUT` when the deadline
        passed, and the exception text when the callable raised.

    ### Example
    >>> run(lambda: os.statvfs('/mnt/data').f_bfree, timeout=5)
    (True, 3244913)
    """
    return run_each([(None, func)], timeout)[None]


def run_each(jobs, timeout=8):
    """
    Run every callable under one shared deadline, each in a process of its own.

    All jobs are started before the first one is waited for, so the whole batch takes at
    most `timeout` seconds no matter how many of them never come back.

    A job's return value travels back as JSON, which is what makes it survive the process
    boundary, so it has to consist of the types JSON can carry. Returning `None` is the
    right answer for a job that only has to succeed or fail.

    A job that raises is reported as a failure with the exception text. A job that misses
    the deadline is reported as a failure with `TIMEOUT`, so the two can be told apart:
    the first means the work was done and the answer was no, the second means no answer
    was reached at all.

    ### Parameters
    - **jobs** (`list` of `tuple`): `(key, callable)` pairs. The key identifies the job in
      the result and can be any hashable value. The callable takes no arguments and
      returns something JSON-serialisable.
    - **timeout** (`int` or `float`, optional): Seconds the whole batch is given.
      Defaults to 8. A value of zero or less gives no job any time, so every one of them
      is reported as `TIMEOUT`.

    ### Returns
    - **dict**: One entry per job, keyed by its key, each value a
      `(True, result)` or `(False, error_message)` tuple.

    ### Example
    >>> jobs = [(mp, lambda mp=mp: os.statvfs(mp).f_bfree) for mp in ('/', '/mnt/data')]
    >>> run_each(jobs, timeout=5)
    {'/': (True, 3244913), '/mnt/data': (False, 'did not answer in time')}
    """
    if not jobs:
        return {}

    if not hasattr(os, 'fork'):
        results = {}
        for key, func in jobs:
            try:
                results[key] = (True, func())
            except Exception as e:
                results[key] = (False, str(e))
        return results

    started = time.time()
    results = {}
    pending = {}
    # Read ends the parent already holds. A child inherits them and closes them right
    # away, so that no child keeps another job's pipe alive.
    inherited = []

    for key, func in jobs:
        try:
            read_fd, write_fd = os.pipe()
        except OSError as e:
            results[key] = (False, str(e))
            continue
        try:
            pid = os.fork()
        except OSError as e:
            os.close(read_fd)
            os.close(write_fd)
            results[key] = (False, str(e))
            continue
        if pid == 0:
            _work(func, read_fd, write_fd, inherited)
        os.close(write_fd)
        inherited.append(read_fd)
        pending[read_fd] = {
            'chunks': [],
            'key': key,
            'oversized': False,
            'pid': pid,
            'size': 0,
        }

    poller = select.poll()
    for read_fd in pending:
        poller.register(read_fd, select.POLLIN)

    while pending:
        remaining = started + timeout - time.time()
        if remaining <= 0:
            break
        # poll() takes milliseconds, and a value that rounds down to zero would turn the
        # wait into a busy loop, so it never goes below one.
        for read_fd, _ in poller.poll(max(1, int(remaining * 1000))):
            job = pending[read_fd]
            chunk = os.read(read_fd, 65536)
            if chunk:
                # An answer can be larger than a pipe holds, which makes the child wait
                # for the parent to read, so a descriptor is read until its end.
                if job['oversized']:
                    continue
                job['chunks'].append(chunk)
                job['size'] += len(chunk)
                if job['size'] > MAX_RESULT_BYTES:
                    # keep draining so the child can finish instead of waiting for
                    # a reader that stopped, but throw the answer away
                    job['chunks'] = []
                    job['oversized'] = True
                continue
            del pending[read_fd]
            poller.unregister(read_fd)
            os.close(read_fd)
            os.waitpid(job['pid'], 0)
            results[job['key']] = (
                (False, _TOO_LARGE) if job['oversized'] else _decode(job['chunks'])
            )

    for read_fd, job in pending.items():
        os.kill(job['pid'], signal.SIGKILL)
        os.waitpid(job['pid'], 0)
        os.close(read_fd)
        results[job['key']] = (False, TIMEOUT)
    return results


def _decode(chunks):
    """
    Turn what a child wrote back into a `(True, result)` or `(False, error_message)`
    tuple.
    """
    try:
        answer = json.loads(txt.to_text(b''.join(chunks)))
    except Exception:
        return False, _UNREADABLE
    if not isinstance(answer, dict) or 'ok' not in answer:
        return False, _UNREADABLE
    if not answer['ok']:
        return False, str(answer.get('error', _UNREADABLE))
    return True, answer.get('value')


def _work(func, read_fd, write_fd, inherited):
    """
    Run one job in the child process and leave. Never returns.

    The child answers with `{"ok": ...}` either way, so that a job which raised is told
    apart from one that never came back. It leaves through `os._exit()`, which skips
    cleanup handlers and buffered output, so it can neither emit anything of its own nor
    run any of the caller's remaining code.
    """
    for fd in inherited:
        try:
            os.close(fd)
        except OSError:
            pass
    try:
        os.close(read_fd)
    except OSError:
        pass
    try:
        answer = {'ok': True, 'value': func()}
    except Exception as e:
        answer = {'ok': False, 'error': str(e)}
    try:
        os.write(write_fd, txt.to_bytes(json.dumps(answer)))
    except Exception:
        pass
    os._exit(0)
