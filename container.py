#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library holds what every consumer of a container engine has to get right the
same way: what to report when the engine command comes back with nothing usable.

The engine is reached through its command-line client, and that client fails in two
very different ways. Either the caller is not allowed to talk to the engine, which is
a problem of how the check was deployed and says nothing at all about the engine, or
the engine is not there or does not answer, which is the outage a consumer exists to
report. Deciding that per consumer is how one of them ends up waking somebody at
night over a missing group membership, so the decision is made here once.

Typical use case:
```python
    success, result = lib.shell.shell_exec(['docker', 'ps', '--format={{json .}}'])
    if not success:
        lib.base.oao(*lib.container.get_engine_error(result))
    stdout, stderr, retc = result
    if retc != 0:
        lib.base.oao(*lib.container.get_engine_error(stderr, stdout))
```
"""

import re

from . import txt
from .globals import STATE_CRIT, STATE_UNKNOWN

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082901'

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
