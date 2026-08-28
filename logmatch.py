#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Remembers what was found in a log, so a finding keeps counting after the run that saw it.

A log is read once. The line that reported a failed backup is gone from the next run's input,
and a consumer that only judged what it just read would report the failure once and then go
quiet, which is the one thing a monitored system must not do. So a finding has to outlive the
run that saw it, and something has to decide when it stops counting. This module keeps that
decision, and the state behind it, in one place.

Alongside the findings, the state database keeps the read position of the log, the one
`logsource.read()` hands back, because both belong to the same consumer instance and have to
be written and thrown away together.

A finding stops counting in one of two ways. It ages out, once it has been around longer than
the consumer's alarm duration, which suits anything that resolves itself. Or somebody
acknowledges it on the monitoring server, which suits anything that does not, and is what
`service_acknowledged()` asks about.

Which occurrences count as the same finding is the consumer's decision, and it is made through
the key. A consumer that re-reads its whole source on every run, a kernel ring buffer for
example, gives repeated occurrences the same key through `key()`, so acknowledging one silences
it for good instead of letting the unchanged source raise it again on the next run. A consumer
that reads its source incrementally lets `record()` generate the key, so every occurrence is its
own finding and a line that turns up again after an acknowledgement is reported again.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082801'

import datetime
import hashlib
import json
import uuid

from . import db_sqlite, icinga, time

DEFAULT_RETENTION = 30  # days
DEFAULT_TABLE = 'findings'

_DEFINITION = """
    key         TEXT NOT NULL PRIMARY KEY,
    line        TEXT NOT NULL,
    state       INTEGER NOT NULL,
    first_seen  TIMESTAMP NOT NULL,
    last_seen   TIMESTAMP NOT NULL,
    acked_at    TIMESTAMP
"""

POSITION_TABLE = 'positions'

_POSITION_DEFINITION = """
    source      TEXT NOT NULL PRIMARY KEY,
    position    TEXT NOT NULL
"""


def _timestamp(delta=None):
    """Render a point in time as a sortable string.

    Stored as text rather than as a `datetime`, because sqlite3 deprecated the adapter that
    converts one as of Python 3.12. Microsecond ISO 8601 sorts and compares lexically, so
    ordering and the cutoff comparisons stay correct in SQL without it.
    """
    moment = time.now(as_type='datetime')
    if delta is not None:
        moment -= delta
    return moment.isoformat(sep=' ')


def _write(conn, findings, table, acknowledged=False):
    """Record findings, keeping what an earlier run already knew about each of them."""
    now = _timestamp()
    for finding in findings:
        item = finding.get('key') or uuid.uuid4().hex
        success, existing = db_sqlite.select(
            conn,
            f'SELECT * FROM {table} WHERE key = :key',
            {'key': item},
            fetchone=True,
        )
        if not success:
            return False, existing
        acked_at = existing.get('acked_at') if existing else None
        row = {
            'acked_at': now if acknowledged else acked_at,
            'first_seen': existing.get('first_seen') if existing else now,
            'key': item,
            'last_seen': now,
            'line': finding.get('line', ''),
            'state': finding.get('state', 1),
        }
        success, result = db_sqlite.replace(conn, row, table=table)
        if not success:
            return False, result
    return db_sqlite.commit(conn)


def acknowledge(conn, findings, table=DEFAULT_TABLE):
    """
    Mark findings as acknowledged, so they stop counting.

    A finding that is not on record yet is recorded as it is acknowledged, so a consumer that
    only ever writes on an acknowledgement does not have to record everything it sees first.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An open connection from `connect()`.
    - **findings** (`iterable` of `dict`):
      The findings to acknowledge, in the shape `record()` takes. Rows from `pending()` can be
      passed straight back in.
    - **table** (`str`, optional): Table to write to. Defaults to `'findings'`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**None | str**): None on success, otherwise an error message string.

    ### Notes
    - An acknowledged finding is kept rather than deleted, because a consumer that re-reads its
      whole source finds the same line again on the next run and has to recognize it as one that
      was already dealt with. `prune()` is what eventually removes it.

    ### Example
    >>> lib.base.coe(lib.logmatch.acknowledge(conn, pending_findings))
    """
    return _write(conn, findings, table, acknowledged=True)


def connect(name, instance='', path=''):
    """
    Open the state database of one consumer instance and create its table.

    Two services watching the same log for different things must not share a state database, or
    each would report the other's findings and move the other's position. The `instance` is what
    keeps them apart, and `instance_id()` derives one from whatever decides which lines a
    consumer flags.

    ### Parameters
    - **name** (`str`):
      Name of the consumer, used in the file name, for example `'logfile'`.
    - **instance** (`str`, optional):
      Distinguishes several instances of the same consumer. Defaults to `''`, for a consumer
      that only ever runs once per host.
    - **path** (`str`, optional):
      Directory to keep the database in. Defaults to `''`, which is the per-user temp directory.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**sqlite3.Connection | str**): The connection, or an error message string.

    ### Example
    >>> instance = lib.logmatch.instance_id({'pattern': args.PATTERN})
    >>> conn = lib.base.coe(lib.logmatch.connect('logfile', instance))
    """
    filename = f'linuxfabrik-monitoring-plugins-{name}'
    if instance:
        filename += f'-{instance}'
    success, conn = db_sqlite.connect(filename=f'{filename}.db', path=path)
    if not success:
        return False, conn
    for definition, table in (
        (_DEFINITION, DEFAULT_TABLE),
        (_POSITION_DEFINITION, POSITION_TABLE),
    ):
        success, result = db_sqlite.create_table(
            conn,
            definition,
            table=table,
            drop_table_first=False,
        )
        if not success:
            return False, result
    return True, conn


def get_position(conn, source):
    """
    Return the read position stored for a log source, or None if there is none yet.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An open connection from `connect()`.
    - **source** (`str`):
      What the position belongs to. Use the source as the consumer was configured with it, not
      as it resolved on this run, so a log whose file name carries the current date keeps its
      position across the change of day.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**dict | None | str**):
          The stored position, None where the source has none yet, otherwise an error message
          string.

    ### Notes
    - A stored position that cannot be read back is reported as None rather than as an error, so
      a state database written by an incompatible version costs one re-read instead of taking
      the consumer down.

    ### Example
    >>> position = lib.base.coe(lib.logmatch.get_position(conn, args.FILENAME))
    >>> result = lib.base.coe(lib.logsource.read(args.FILENAME, position=position))
    """
    success, row = db_sqlite.select(
        conn,
        f'SELECT position FROM {POSITION_TABLE} WHERE source = :source',
        {'source': source},
        fetchone=True,
    )
    if not success:
        return False, row
    if not row:
        return True, None
    try:
        return True, json.loads(row['position'])
    except (TypeError, ValueError):
        return True, None


def instance_id(payload, length=10):
    """
    Derive a short, stable id from whatever decides which lines a consumer flags.

    The id is the same for the same payload on every run and on every host, and different as
    soon as one value in it differs, which is what makes it usable as part of a state database
    file name. Nesting, ordering and types are normalized first, so two consumers configured
    alike share an id no matter in which order the values were given.

    ### Parameters
    - **payload** (`any`):
      Anything JSON serializable, typically a dict of the parameters that select and classify
      lines. Lists are sorted, so the order they were given in does not change the id.
    - **length** (`int`, optional): How many hex characters to return. Defaults to 10.

    ### Returns
    - **str**: The id.

    ### Notes
    - Include every parameter that changes which lines are flagged, and nothing else. A
      parameter that only changes the wording of the output would split the state in two for no
      reason, and one that is left out lets two differently configured services share a state.

    ### Example
    >>> instance_id({'critical': ['fatal'], 'warning': ['error', 'warn']})
    'd41d8cd98f'
    """

    def _normalize(value):
        if isinstance(value, dict):
            return {str(k): _normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return sorted(_normalize(item) for item in value)
        return value

    serialized = json.dumps(_normalize(payload), sort_keys=True).encode('utf-8')
    return hashlib.sha256(serialized).hexdigest()[:length]


def key(line):
    """
    Derive the key of a finding from the text of its line.

    Use this where the consumer re-reads its whole source on every run, so that repeated
    occurrences of one line are one finding: acknowledging it then silences it, instead of the
    unchanged source raising it again on the very next run. Where the source is read
    incrementally, leave the key to `record()` instead, so a line that turns up again after an
    acknowledgement is reported again.

    ### Parameters
    - **line** (`str`): The line to derive a key from.

    ### Returns
    - **str**: The key.
    """
    return hashlib.sha256(line.encode('utf-8')).hexdigest()


def pending(conn, max_age=None, table=DEFAULT_TABLE):
    """
    Return the findings that still count.

    A finding counts until it is acknowledged, and, where `max_age` is given, until it has been
    around for longer than that. Ageing is measured from when a finding was first seen, not from
    when it was last seen, so a line that keeps repeating still stops counting eventually
    instead of renewing itself forever.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An open connection from `connect()`.
    - **max_age** (`int`, optional):
      Minutes a finding counts for. Defaults to None, which lets a finding count until it is
      acknowledged.
    - **table** (`str`, optional): Table to read from. Defaults to `'findings'`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**list | str**):
          On success a list of rows, each with `key`, `line`, `state`, `first_seen` and
          `last_seen`, oldest first. Otherwise an error message string.

    ### Example
    >>> findings = lib.base.coe(lib.logmatch.pending(conn, max_age=args.ALARM_DURATION))
    >>> state = lib.base.get_worst(*[item['state'] for item in findings])
    """
    sql = f'SELECT * FROM {table} WHERE acked_at IS NULL'
    data = {}
    if max_age is not None:
        sql += ' AND first_seen > :cutoff'
        data['cutoff'] = _timestamp(datetime.timedelta(minutes=max_age))
    sql += ' ORDER BY first_seen ASC'
    return db_sqlite.select(conn, sql, data, fetchone=False)


def prune(conn, retention=DEFAULT_RETENTION, table=DEFAULT_TABLE):
    """
    Drop findings nobody has seen for a while, to keep the state database bounded.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An open connection from `connect()`.
    - **retention** (`int`, optional): Days to keep a finding after it was last seen.
      Defaults to 30.
    - **table** (`str`, optional): Table to prune. Defaults to `'findings'`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**None | str**): None on success, otherwise an error message string.

    ### Notes
    - Keep the retention longer than the source itself keeps a line. Pruning an acknowledged
      finding that the source still holds makes the next run report it as new, which is exactly
      the alert the acknowledgement was meant to end.
    """
    cutoff = _timestamp(datetime.timedelta(days=retention))
    success, result = db_sqlite.delete(
        conn,
        f'DELETE FROM {table} WHERE last_seen <= :cutoff',
        {'cutoff': cutoff},
    )
    if not success:
        return False, result
    return db_sqlite.commit(conn)


def record(conn, findings, table=DEFAULT_TABLE):
    """
    Record what this run found, keeping what an earlier run already knew about it.

    A finding that is already on record keeps its `first_seen` and its acknowledgement, and only
    its `last_seen` moves, so neither ageing nor an acknowledgement is reset by the source
    reporting the same thing again.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An open connection from `connect()`.
    - **findings** (`iterable` of `dict`):
      One dict per finding, with:
      - `line` (`str`): the text to report.
      - `state` (`int`, optional): the state it stands for, for example `STATE_WARN`.
        Defaults to `STATE_WARN` (1).
      - `key` (`str`, optional): what makes two occurrences the same finding. Defaults to a
        value unique to this occurrence, which is what a consumer reading its source
        incrementally wants; pass `key(line)` where the whole source is re-read instead.
    - **table** (`str`, optional): Table to write to. Defaults to `'findings'`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**None | str**): None on success, otherwise an error message string.

    ### Example
    >>> lib.base.coe(lib.logmatch.record(conn, [{'line': line, 'state': STATE_CRIT}]))
    >>> lib.base.coe(
    ...     lib.logmatch.record(conn, [{'key': lib.logmatch.key(line), 'line': line}])
    ... )
    """
    return _write(conn, findings, table)


# What a consumer prints when it could ask about the acknowledgement, and when it
# could not. Kept here so every consumer says the same thing about the same
# situation, which is the whole reason the call lives in one place.
_NOTE_NOT_ACKNOWLEDGED = 'Note: Acknowledge this service to reset the state to OK.'
_NOTE_NO_RESULT = (
    'Note: Could not determine the acknowledgement from the monitoring server, this '
    'could be due to an incorrect service name.'
)


def suppressed(conn, table=DEFAULT_TABLE):
    """
    Return the keys of every finding that has been acknowledged.

    For a consumer that re-reads its whole source on every run, a kernel ring buffer or a time
    window of the journal for example. What such a consumer reports is what the source shows
    right now, so it filters that against this set rather than asking `pending()` for a list
    that would keep growing past what the source still holds.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An open connection from `connect()`.
    - **table** (`str`, optional): Table to read from. Defaults to `'findings'`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**set | str**): The acknowledged keys, otherwise an error message string.

    ### Notes
    - Derive the keys with `key()`, so that the same line yields the same key on the next run.
      An acknowledgement is worth nothing against a key that is unique per occurrence.

    ### Example
    >>> acknowledged = lib.base.coe(lib.logmatch.suppressed(conn))
    >>> lines = [line for line in lines if lib.logmatch.key(line) not in acknowledged]
    """
    success, rows = db_sqlite.select(
        conn,
        f'SELECT key FROM {table} WHERE acked_at IS NOT NULL',
        fetchone=False,
    )
    if not success:
        return False, rows
    return True, {row['key'] for row in rows}


def service_acknowledged(
    url,
    username,
    password,
    servicename,
    insecure=False,
    no_proxy=False,
    proxy=None,
    timeout=3,
):
    """
    Ask the monitoring server whether the service carrying this check is acknowledged.

    An acknowledgement is how an operator says "seen it, working on it" about something that
    does not resolve itself. A consumer asks here, and where the answer is yes, stops reporting
    the findings it currently holds.

    ### Parameters
    - **url** (`str`): Base API URL of the monitoring server, for example
      `https://monitoring.example.com:5665`.
    - **username** (`str`): API username.
    - **password** (`str`): API password.
    - **servicename** (`str`): Unique name of the service, in the form `hostname!service`.
    - **insecure** (`bool`, optional): Disable certificate verification. Defaults to False.
    - **no_proxy** (`bool`, optional): Ignore the proxy of the environment. Defaults to False.
    - **proxy** (`str`, optional): Proxy to use. Defaults to None.
    - **timeout** (`int`, optional): Seconds to wait for the API. Defaults to 3.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): Always True. See the notes.
        - tuple[1] (**tuple**): An `(acknowledged, note)` tuple.
          - `acknowledged` (`bool`): True if the service is acknowledged.
          - `note` (`str`): What to add to the output, empty where there is nothing to say.

    ### Notes
    - An API that cannot be reached or does not know the service is reported through `note` and
      never as a failure of this function. A check that went UNKNOWN because it could not ask
      about an acknowledgement would replace a real finding with a question about the monitoring
      server, and the finding is the more important of the two.
    - Verify the certificate wherever the server presents one that the host trusts. An
      acknowledgement lookup carries API credentials.

    ### Example
    >>> acknowledged, note = lib.base.coe(
    ...     lib.logmatch.service_acknowledged(
    ...         args.ICINGA_URL,
    ...         args.ICINGA_USERNAME,
    ...         args.ICINGA_PASSWORD,
    ...         args.ICINGA_SERVICE_NAME,
    ...         timeout=args.TIMEOUT,
    ...     )
    ... )
    """
    success, result = icinga.get_service(
        url,
        username,
        password,
        servicename=servicename,
        attrs='state,acknowledgement',
        insecure=insecure,
        no_proxy=no_proxy,
        proxy=proxy,
        timeout=timeout,
    )
    if not success:
        return True, (
            False,
            f'Note: Could not determine the acknowledgement from the monitoring '
            f'server:\n{result}.',
        )
    try:
        if result['results'][0]['attrs']['acknowledgement']:
            return True, (True, '')
    except (IndexError, KeyError, TypeError):
        return True, (False, _NOTE_NO_RESULT)
    return True, (False, _NOTE_NOT_ACKNOWLEDGED)


def set_position(conn, source, position):
    """
    Store the read position of a log source, to pass back to `logsource.read()` next run.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An open connection from `connect()`.
    - **source** (`str`): What the position belongs to. See `get_position()`.
    - **position** (`dict`): The position `logsource.read()` returned.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True on success, otherwise False.
        - tuple[1] (**None | str**): None on success, otherwise an error message string.

    ### Notes
    - Store the position even where the run found nothing, or the consumer reads the same lines
      again on the next run.
    """
    success, result = db_sqlite.replace(
        conn,
        {'position': json.dumps(position), 'source': source},
        table=POSITION_TABLE,
    )
    if not success:
        return False, result
    return db_sqlite.commit(conn)
