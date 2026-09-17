#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library holds what every consumer of a container engine has to get right the
same way: how long to wait for the engine, and what to report when the engine command
comes back with nothing usable.

The engine is reached through its command-line client, and that client fails in two
very different ways. Either the caller is not allowed to talk to the engine, which is
a problem of how the check was deployed and says nothing at all about the engine, or
the engine is not there or does not answer, which is the outage a consumer exists to
report. Deciding that per consumer is how one of them ends up waking somebody at
night over a missing group membership, so the decision is made here once.

Typical use case:
```python
    started = lib.time.now(as_type='float')
    cmd = ['docker', 'ps', '--format={{json .}}']
    success, result = lib.container.run(cmd, 8, started)
    if not success:
        lib.base.oao(*result)
    stdout, stderr, retc = result
    if retc != 0:
        lib.base.oao(*lib.container.get_engine_error(stderr, stdout))
```
"""

import math
import re

from . import shell, time, txt
from .globals import STATE_CRIT, STATE_UNKNOWN, STATE_WARN

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026091701'

# What the client puts in front of the answer it got. The CLI wraps every answer of
# the engine in "Error response from daemon:", and a swarm control plane adds a gRPC
# status of its own, so the readable sentence sits behind two prefixes:
# `Error response from daemon: rpc error: code = Unknown desc = The swarm does not
# have a leader. ...`
DAEMON_ERROR_PREFIX = 'Error response from daemon: '
RPC_STATUS_REGEX = re.compile(r'^rpc error: code = \S+ desc = ')

# A swarm task container is named `<service>.<slot or node id>.<task id>`, and the
# task id is 25 base36 characters (swarmkit `identity.NewID`). Only that suffix is
# cut off, so a container somebody named `backup.daily` keeps the name they gave it,
# and two such containers do not collapse into one row. The id changes with every
# rescheduling, so anything keyed on the full name (a table row, a performance data
# label, a graph) starts over with it.
TASK_ID_REGEX = re.compile(r'\.[0-9a-z]{25}$')


def _as_text(value):
    """
    Return what a client wrote as text, whatever it was handed over as.

    A caller passes on what it got from the client, and that is `None` where the
    client wrote nothing, `bytes` where it was read without decoding, and `str`
    everywhere else. `None` becomes an empty string rather than the word "None",
    which would otherwise be printed as if the client had said it, and bytes are
    decoded the way any other output of a foreign command is.
    """
    if value is None:
        return ''
    if isinstance(value, bytes):
        return txt.to_text(value, errors='strict_or_latin1')
    return str(value)


def get_engine_error(stderr, stdout='', fallback_state=STATE_CRIT):
    """
    Return `(message, state)` for a command that could not reach the container engine.

    A refused permission is a problem of how the consumer is deployed, not of the
    engine: the engine answers other callers just fine, this one is only not allowed
    to ask. Nothing can be said about the engine in that case, so it is reported as
    UNKNOWN together with what to do about it. Everything else, a socket that is not
    there or an engine that does not answer, is an outage and carries
    `fallback_state`.

    ### Parameters
    - **stderr** (`str`, `bytes` or `None`): What the client wrote to its standard
      error. `None` and undecoded bytes are accepted, because that is what a caller
      passing a command result straight through has.
    - **stdout** (`str`, `bytes` or `None`, optional): What it wrote to its standard
      output. Some clients put the reason there. Defaults to `''`.
    - **fallback_state** (`int`, optional): The state to report for a failure that is
      not a refused permission. Defaults to `STATE_CRIT`. A consumer that cannot say
      anything about the engine either way passes `STATE_UNKNOWN`.

    ### Returns
    - **tuple**: `(message, state)`, ready to be handed to `lib.base.oao()`.

    ### Example
    >>> get_engine_error('permission denied while trying to connect')
    ('No permission to talk to the container engine, ...', 3)
    """
    text = f'{_as_text(stderr)}\n{_as_text(stdout)}'.strip()
    if 'permission denied' in text.lower():
        return (
            'No permission to talk to the container engine, so nothing can be said'
            ' about it. Run the check as root, or deploy the sudoers file that ships'
            f' with the plugins.\n{text}',
            STATE_UNKNOWN,
        )
    return (text, fallback_state)


def _is_finite_number(value):
    """
    Return True for an int or float that is neither a bool, NaN nor infinite.

    A bool is an int to Python, and NaN or infinity compare in ways that silently turn a
    budget into no budget at all, so none of them is accepted as a number of seconds.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


# How much of a command a message quotes before it leaves out the remaining arguments.
COMMAND_DISPLAY_LENGTH = 100


def run(cmd, timeout, started=None, run_as=None):
    """
    Run a container engine client within what is left of a time budget.

    A consumer that asks the engine several things in one run has one budget for all of
    them, not one per command: three commands that each get the full timeout can take
    three times as long as the caller was promised. Each command therefore gets what is
    left of `timeout` since `started`. An engine that does not answer in time is a
    warning, not an outage, because the engine is there and only slow. The exit code of
    the client is not judged here, since what a non-zero one means differs between
    commands; hand it to `get_engine_error()` or evaluate it yourself.

    ### Parameters
    - **cmd** (`list` or `tuple`): The command and its arguments.
    - **timeout** (`int` or `float`): The budget in seconds, counted from `started`.
    - **started** (`float`, optional): When the budget began, as returned by
      `time.now(as_type='float')`. Defaults to now, which gives this command the
      whole budget.
    - **run_as** (`str`, optional): Run the client as this user, for an engine that
      keeps the containers of every user apart. Defaults to the current user.

    ### Returns
    - **tuple** (`bool`, `tuple`):
      - `(True, (stdout, stderr, retc))` once the client has run, whatever its exit
        code.
      - `(False, (message, state))` otherwise, ready to be handed to `lib.base.oao()`:
        `STATE_WARN` when the budget ran out, `STATE_UNKNOWN` when the client could not
        be started or the arguments are unusable.

    ### Notes
    - A budget that is already spent does not start the client at all.
    - The message names the whole budget, not what was left of it, because that is the
      value the operator configured.
    - A long command is quoted up to about 100 characters, whole arguments only, and
      the message says how many arguments were left out.

    ### Example
    >>> started = time.now(as_type='float')
    >>> run(['podman', 'info', '--format', 'json'], 8, started, run_as='rocketchat')
    (True, ('{...}', '', 0))
    """
    if not isinstance(cmd, (list, tuple)) or not cmd:
        return False, (
            'The command must be a non-empty list of arguments.',
            STATE_UNKNOWN,
        )
    if not _is_finite_number(timeout) or timeout <= 0:
        return False, (
            f'The timeout must be a positive number, got {timeout!r}.',
            STATE_UNKNOWN,
        )
    if started is None:
        started = time.now(as_type='float')
    if not _is_finite_number(started):
        return False, (
            f'The start of the budget must be a number, got {started!r}.',
            STATE_UNKNOWN,
        )

    # a command that inspects every container or image carries hundreds of ids, which
    # would push everything else off the first line of the message
    parts = [_as_text(part) for part in cmd]
    command = parts[0]
    for index, part in enumerate(parts[1:], start=1):
        if len(command) + 1 + len(part) > COMMAND_DISPLAY_LENGTH:
            command += f' ... ({len(parts) - index} more)'
            break
        command += f' {part}'
    user_note = f' (user: `{run_as}`)' if run_as else ''
    timed_out = (
        f'Timeout after {timeout}s while running `{command}`{user_note}.',
        STATE_WARN,
    )

    remaining = started + timeout - time.now(as_type='float')
    if remaining <= 0:
        return False, timed_out
    success, result = shell.shell_exec(list(cmd), run_as=run_as, timeout=remaining)
    if success:
        return True, result
    if _as_text(result).startswith('Timeout after'):
        return False, timed_out
    return False, (_as_text(result), STATE_UNKNOWN)


def strip_daemon_error(message):
    """
    Reduce the answer of a container engine to the sentence somebody can act on.

    ### Parameters
    - **message** (`str`, `bytes` or `None`): What the client wrote, typically its
      standard error.

    ### Returns
    - **str**: The message with the client's prefixes removed, on a single line.

    ### Example
    >>> strip_daemon_error(
    ...     'Error response from daemon: rpc error: code = Unknown desc = '
    ...     'The swarm does not have a leader.'
    ... )
    'The swarm does not have a leader.'
    """
    message = ' '.join(_as_text(message).split())
    message = message.replace(DAEMON_ERROR_PREFIX, '', 1)
    return RPC_STATUS_REGEX.sub('', message)


def strip_task_id(name):
    """
    Return the name of a container without the task id a swarm appended to it.

    ### Parameters
    - **name** (`str`, `bytes` or `None`): The name as the engine reports it.

    ### Returns
    - **str**: The name without the trailing task id. A name that carries none is
      returned unchanged.

    ### Example
    >>> strip_task_id('traefik_traefik.2.1idw12p2yqpxutlzkcwign4at')
    'traefik_traefik.2'

    >>> strip_task_id('backup.daily')
    'backup.daily'
    """
    return TASK_ID_REGEX.sub('', _as_text(name))
