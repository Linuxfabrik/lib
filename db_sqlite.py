#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""Library for accessing SQLite databases.

This is one typical use case of this library (taken from `disk-io`):

>>> conn = lib.base.coe(lib.db_sqlite.connect(filename='disk-io.db'))
>>> lib.base.coe(lib.db_sqlite.create_table(conn, definition, drop_table_first=False))
>>> lib.base.coe(lib.db_sqlite.create_index(conn, 'name'))  # optional

>>> lib.base.coe(lib.db_sqlite.insert(conn, data))
>>> lib.base.coe(lib.db_sqlite.cut(conn, max=args.COUNT * len(disks)))
>>> lib.base.coe(lib.db_sqlite.commit(conn))

>>> result = lib.base.coe(lib.db_sqlite.select(conn,
        'SELECT * FROM perfdata WHERE name = :name ORDER BY timestamp DESC LIMIT 2',
        {'name': disk}

>>> lib.db_sqlite.close(conn)
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082501'

import csv
import functools
import hashlib
import os
import re
import sqlite3
import stat

from . import disk, time, txt

# Substrings identifying an `sqlite3.OperationalError` that means the on-disk schema no longer
# matches what this release reads or writes, for example because a plugin gained or lost a column
# between two versions. Discarding the database is the correct recovery here: the next run
# rebuilds a valid cache from scratch.
#
# `OperationalError` covers far more than that, though. A lock held by a concurrent plugin run
# ("database is locked"), a full or read-only disk, an I/O error or a broken SQL statement all
# raise it as well, and deleting the file there destroys a healthy cache, possibly one another
# process is still using. Those errors are reported to the caller and leave the database alone.
#
# "no such table" is deliberately absent: a table that does not exist yet is the normal state on
# the first run, and `create_table()` uses `IF NOT EXISTS`, so nothing has to be discarded to
# recover. Matching it would let one plugin's first query wipe the tables of every other plugin
# sharing the default database file.
#
# SQLite words the arity error differently when the statement names its columns ("3 values for 2
# columns"), and that spelling is absent as well. `insert()` and `replace()` build the column list
# and the bind list from one and the same dict, so the counts cannot disagree and the message is
# unreachable from here.
SCHEMA_ERRORS = (
    'has no column named',
    'no such column',
    'values were supplied',  # "table t has 2 columns but 3 values were supplied"
)

# Matched before `SCHEMA_ERRORS` and always treated as harmless. A WITHOUT ROWID table has no
# `rowid` column, so `cut()` fails against one with "no such column: rowid". That schema is what
# the caller asked for, not a mismatch between releases, but the `no such column` entry above
# would otherwise match it and delete a perfectly healthy database.
#
# SQLite accepts `oid` and `_rowid_` as names for the same column, and prefixes the name with the
# table, the alias and possibly the database when the query qualifies it ("no such column:
# main.t.rowid", see `lookupName()` in SQLite's `resolve.c`), so every spelling has to be
# recognized. A real column that happens to be named `oid` and disappeared between two releases is
# covered by this too and no longer discards the database, which is the safe direction to err in:
# deleting a healthy cache is worse than keeping a stale one for one more run.
#
# A few statements report the name in double quotes instead ("no such column: \"rowid\"", see
# `renameColumnFunc()` in SQLite's `alter.c`). This library never emits those, but the quotes are
# optional in the pattern so a caller's own SQL is judged the same way.
HEALTHY_SCHEMA_ERROR_RE = re.compile(
    r'no such column: "?(?:.*\.)?(?:rowid|oid|_rowid_)"?'
)

# Substrings identifying an `sqlite3.IntegrityError` (SQLITE_CONSTRAINT, SQLITE_MISMATCH) that
# means the on-disk schema no longer matches the data being written, for example a NOT NULL column
# a newer or older release no longer fills.
#
# The other constraint violations are not schema problems at all. A UNIQUE or PRIMARY KEY conflict
# is an ordinary data condition that a plugin hits on a healthy cache, and `replace()` exists to
# resolve exactly that; CHECK and FOREIGN KEY violations and "datatype mismatch" say something
# about the row, not about the file.
INTEGRITY_SCHEMA_ERRORS = ('not null constraint failed',)

# Substrings identifying a database file that is unusable no matter what is queried. These
# describe the file, not the statement, so they are matched for every exception class rather
# than for one in particular: the first three arrive as a plain `sqlite3.DatabaseError`
# (SQLITE_CORRUPT and SQLITE_NOTADB), while a schema format number the release cannot read is
# reported as SQLITE_ERROR and therefore as an `OperationalError` (`sqlite3LockAndPrepare()` in
# SQLite's `prepare.c`). Matching that one by exception class alone would keep an unusable file
# forever and let every following run fail the same way.
CORRUPT_ERRORS = (
    'database disk image is malformed',
    'file is not a database',
    'malformed database schema',
    'unsupported file format',
)


def __filter_str(s, charclass='a-zA-Z0-9_'):
    """
    Filter a string to keep only allowed characters.

    This function removes all characters from a string except those matching the allowed
    character class. By default, it allows only alphanumeric characters (`a-z`, `A-Z`, `0-9`)
    and underscores (`_`), making the output safe for use in variable names, table names,
    index names, and similar identifiers.

    ### Parameters
    - **s** (`str`):
      The input string to sanitize.
    - **charclass** (`str`, optional):
      A regex character class defining allowed characters.
      Defaults to `'a-zA-Z0-9_'`.

    ### Returns
    - **str**:
      A sanitized string containing only characters matching the allowed character class.

    ### Notes
    - Useful for cleaning user input before using it in database object names or variable names.
    - The function uses regular expressions for filtering.

    ### Example
    >>> __filter_str('user@example.ch')
    'userexamplech'

    >>> __filter_str('project-123', charclass='a-zA-Z0-9')
    'project123'
    """
    regex = f'[^{charclass}]'
    return re.sub(regex, '', s)


def __sha1sum(string):
    """
    Calculate the SHA-1 hash of a given string.

    This function encodes the input as bytes (if necessary) and returns its SHA-1 checksum
    as a hexadecimal string.

    ### Parameters
    - **string** (`str`):
      The input string to hash.

    ### Returns
    - **str**:
      The SHA-1 hash of the input string, represented as a 40-character hexadecimal string.

    ### Notes
    - Internally, the input is safely converted to bytes before hashing using `txt.to_bytes()`.
    - SHA-1 produces a fixed-size 160-bit (20-byte) hash, commonly used for checksums and
      identifiers.

    ### Example
    >>> __sha1sum('linuxfabrik')
    '74301e766db4a4006ec1fbd6e031760e7e322223'
    """
    return hashlib.sha1(txt.to_bytes(string), usedforsecurity=False).hexdigest()


@functools.lru_cache(maxsize=128)
def __compile_regex(expr):
    """
    Compile and cache a regular expression used by the `REGEXP` SQL function.

    A `REGEXP` comparison is evaluated once per row, always with the same pattern. Caching the
    compiled pattern mirrors what SQLite's own `regexp()` implementation does by stashing the
    compiled expression via `sqlite3_set_auxdata()`. SQLite's cache holds one pattern per
    prepared statement and is dropped as soon as the pattern argument changes, whereas this one
    is process-wide and keeps the last 128 patterns for as long as the process runs.

    ### Parameters
    - **expr** (`str`):
      The regular expression pattern.

    ### Returns
    - **re.Pattern**:
      The compiled pattern.

    ### Example
    >>> __compile_regex('^abc').search('abcdef') is not None
    True
    """
    return re.compile(expr)


def __quote_ident(name):
    """
    Quote an SQL identifier (a table, index or column name) for use in a statement.

    Values are always passed as bind parameters, but identifiers cannot be bound and have to be
    interpolated into the statement text. Quoting them makes an identifier that contains SQL
    syntax inert instead of executable, and additionally allows names that are SQLite keywords
    (`select`) or start with a digit.

    ### Parameters
    - **name** (`str`):
      The identifier to quote.

    ### Returns
    - **str**:
      The identifier wrapped in double quotes, with embedded double quotes doubled.

    ### Example
    >>> __quote_ident('perfdata')
    '"perfdata"'

    >>> __quote_ident('a) VALUES (99); --')
    '"a) VALUES (99); --"'
    """
    escaped = str(name).replace('"', '""')
    return f'"{escaped}"'


def __quote_ident_list(column_list):
    """
    Quote every column of a comma-separated column list.

    ### Parameters
    - **column_list** (`str`):
      A comma-separated list of column names, for example `'col1, col2'`.

    ### Returns
    - **str**:
      The same list with every column quoted, for example `'"col1","col2"'`.

    ### Example
    >>> __quote_ident_list('host_id, service_id')
    '"host_id","service_id"'
    """
    return ','.join(
        __quote_ident(col.strip()) for col in column_list.split(',') if col.strip()
    )


def __unquote_ident(part, closing_quote):
    """
    Read the leading quoted identifier out of `part` and return its plain name.

    The inverse of `__quote_ident()`, used to recover a column name from a column definition. A
    quoted name may contain spaces and commas, so it cannot be taken apart with `split()`.

    ### Parameters
    - **part** (`str`):
      A string starting with an opening quote character, for example `'"a b" TEXT'`.
    - **closing_quote** (`str`):
      The quote character that ends the identifier. Equal to the opening one for `"`, `'` and
      `` ` ``, but `]` for the `[name]` form.

    ### Returns
    - **str**:
      The identifier without its quotes. If the closing quote is missing, everything after the
      opening one is returned.

    ### Notes
    - Inside a quoted identifier SQLite reads a doubled quote character as one literal character,
      so `"a""b"` is the column `a"b`. The `[...]` form has no such escape and ends at the first
      `]`.

    ### Example
    >>> __unquote_ident('"a b" TEXT', '"')
    'a b'

    >>> __unquote_ident('"a""b" TEXT', '"')
    'a"b'
    """
    opening_quote = part[0]
    doubling_escapes = closing_quote == opening_quote
    name = ''
    i = 1
    while i < len(part):
        char = part[i]
        if char == closing_quote:
            if not doubling_escapes or part[i + 1 : i + 2] != closing_quote:
                break
            i += 1  # skip the second quote of the pair and keep one literal character
        name += char
        i += 1
    return name


def __table_columns(conn, table):
    """
    Return the column names of `table` as reported by the database itself.

    Used to reject a column name before it reaches a statement. SQLite resolves a double-quoted
    token that matches no column to a string literal instead of raising "no such column" (the
    double-quoted string misfeature, see `lookupName()` in SQLite's `resolve.c`). A misspelled
    column would therefore index or group by a constant, silently and successfully. The
    misfeature cannot be switched off on the SQLite 3.26 that RHEL 8 ships, because the
    `SQLITE_DQS` build option only arrived in 3.29, and it is enabled in the builds CPython links
    against anyway.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **table** (`str`):
      Name of the table to inspect.

    ### Returns
    - **list** of `str`:
      The column names, or an empty list if the table does not exist or cannot be inspected.

    ### Example
    >>> __table_columns(conn, 'perfdata')
    ['name', 'timestamp', 'rx_bytes']
    """
    # `table_xinfo` rather than `table_info`: the latter omits the hidden columns of a virtual
    # table, and from SQLite 3.31.0 on the generated columns too. SQLite selects and indexes
    # those like any other column, so validating against `table_info` would reject a name that
    # is perfectly usable. `table_xinfo` needs SQLite 3.26.0, hence the fallback.
    # Both pragmas yield (cid, name, type, notnull, dflt_value, pk), `table_xinfo` plus `hidden`.
    for pragma in ('table_xinfo', 'table_info'):
        try:
            rows = conn.execute(f'PRAGMA {pragma}({__quote_ident(table)});').fetchall()
        except sqlite3.Error:
            continue
        # An unknown pragma is not an error in SQLite, it silently returns no rows: the pragma
        # lookup in `pragma.c` jumps straight to the end when the name is unknown, and the
        # documentation states that "no error messages are generated if an unknown pragma is
        # used". Returning here unconditionally would therefore end the loop with an empty result
        # on a build without `table_xinfo` and never try `table_info`, turning the validation off
        # instead of falling back. Every existing table has at least one column, so an empty
        # result means "ask the next pragma".
        if rows:
            return [row[1] for row in rows]
    # Both pragmas came back empty. Usually that means the table does not exist yet, but an
    # unreadable file produces the same answer: both carry SQLite's `NeedSchema` flag and load
    # the schema first, and the `except` above swallows the resulting error. Either way the
    # callers skip their validation and let the statement itself report what is wrong, which is
    # the safe direction: SQLite's own message is more accurate than a guess made here.
    return []


def __is_unusable_db(e):
    """
    Decide whether an `sqlite3` exception means the database file has to be discarded.

    Only a schema that no longer matches this release, or an unreadable file, justify deleting the
    database. Everything else (a lock held by a concurrent plugin run, a full or read-only disk, an
    I/O error, a broken statement, a failing user-defined function, a value the caller may not
    store, a row that violates a constraint) is transient, a caller bug or ordinary data: the cache
    is fine and has to survive.

    ### Parameters
    - **e** (`Exception`):
      The exception raised by the failed statement.

    ### Returns
    - **bool**:
      `True` if the database file is unusable and should be removed, `False` otherwise.

    ### Example
    >>> __is_unusable_db(sqlite3.OperationalError('no such column: foo'))
    True

    >>> __is_unusable_db(sqlite3.OperationalError('database is locked'))
    False

    >>> __is_unusable_db(sqlite3.OperationalError('no such column: t.rowid'))
    False

    >>> __is_unusable_db(sqlite3.IntegrityError('UNIQUE constraint failed: t.a'))
    False

    >>> __is_unusable_db(sqlite3.OperationalError('unsupported file format'))
    True
    """
    msg = str(e).lower()

    # Checked first and independently of the exception class, because a broken file is a broken
    # file whichever statement stumbled over it. See `CORRUPT_ERRORS` for why the class alone
    # does not identify these.
    if any(pattern in msg for pattern in CORRUPT_ERRORS):
        return True

    # `sqlite3.DataError` is raised for SQLITE_TOOBIG only ("string or blob too big"). That is a
    # value the caller must not store, and says nothing about the file. Checked before
    # `DatabaseError`, of which it is a subclass.
    if isinstance(e, sqlite3.DataError):
        return False
    if isinstance(e, sqlite3.IntegrityError):
        return any(pattern in msg for pattern in INTEGRITY_SCHEMA_ERRORS)
    if isinstance(e, sqlite3.OperationalError):
        if HEALTHY_SCHEMA_ERROR_RE.fullmatch(msg):
            return False
        return any(pattern in msg for pattern in SCHEMA_ERRORS)
    # A `DatabaseError` that names none of the `CORRUPT_ERRORS` says nothing specific about the
    # file, so the database is kept and the caller decides what to do.
    return False


def __handle_db_error(conn, e, sql, data=None, delete_db=True):
    """
    Turn an `sqlite3` exception into this library's error tuple, deleting the database first if
    the file turned out to be unusable.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      The connection the statement was executed on.
    - **e** (`Exception`):
      The exception raised by the failed statement.
    - **sql** (`str`):
      The statement that failed, included in the error message.
    - **data** (`dict` or `tuple`, optional):
      The bind parameters of the failed statement, included in the error message when given.
    - **delete_db** (`bool`, optional):
      Whether deleting an unusable database file is allowed at all. Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `str`):
      Always `False` plus an error message describing the failure.

    ### Notes
    - The message wording is part of this library's contract: the plugin documentation and
      several plugin unit tests match on `Operational Error: <sqlite message>, Query: ...`.
    """
    if delete_db and __is_unusable_db(e):
        rm_db(conn)

    suffix = '' if data is None else f', Data: {data}'
    if isinstance(e, sqlite3.OperationalError):
        return False, f'Operational Error: {e}, Query: {sql}{suffix}'
    if isinstance(e, (sqlite3.DataError, sqlite3.IntegrityError)):
        return False, f'Integrity Error: {e}, Query: {sql}{suffix}'
    return False, f'Query failed: {sql}, Error: {e}{suffix}'


def close(conn):
    """
    Close a SQLite database connection safely.

    This function attempts to close an open database connection.
    It does not automatically commit any uncommitted changes — if you close the connection
    without calling `commit()` first, any uncommitted changes will be lost.

    ### Parameters
    - **conn** (`sqlite3.Connection` or compatible):
      An active database connection object.

    ### Returns
    - **bool**:
      - `True` if the connection was closed successfully.
      - `False` if an exception occurred during closing.

    ### Notes
    - Always call `commit()` manually before calling `close()` if you want to save changes.
    - Exceptions during closing are caught and handled silently.

    ### Example
    >>> close(conn)
    True
    """
    try:
        conn.close()
        return True
    except Exception:
        return False


def commit(conn):
    """
    Commit any pending changes to the SQLite database.

    This function saves (commits) all changes made during the current database session.
    If committing fails, an error message is returned.

    ### Parameters
    - **conn** (`sqlite3.Connection` or compatible):
      An active database connection object.

    ### Returns
    - **tuple** (`bool`, `str or None`):
      - First element (`bool`): `True` if the commit succeeded, `False` if it failed.
      - Second element (`str` or `None`):
        - `None` on success.
        - Error message (`str`) describing the failure if commit fails.

    ### Notes
    - Always commit before closing the connection if you want to preserve changes.
    - Exceptions during commit are caught and returned as part of the result.

    ### Example
    >>> success, error = commit(conn)
    >>> if not success:
    >>>     print(error)
    >>> else:
    >>>     print("Changes committed successfully.")
    """
    try:
        conn.commit()
        return True, None
    except Exception as e:
        return False, f'Commit failed: {e}'


def compute_load(conn, sensorcol, datacols, count, table='perfdata'):
    """
    Calculate per-second load metrics based on historical data in a SQLite table.

    This function calculates `Load1` (over the last 1 interval) and `Loadn` (over the last `count` intervals)
    for one or more sensors, based on timestamped performance data.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **sensorcol** (`str`):
      Column name that identifies the sensor (e.g., `'interface'`).
    - **datacols** (`list` of `str`):
      List of columns for which to calculate per-second loads (e.g., `['tx_bytes', 'rx_bytes']`).
    - **count** (`int`):
      Number of historical entries to use for calculating `Loadn`. Must be at least 2, because
      both metrics are a difference between two rows.
    - **table** (`str`, optional):
      Name of the table containing the performance data.
      Defaults to `'perfdata'`.

    ### Returns
    - **tuple** (`bool`, `list or bool or str`):
      - First element (`bool`): `True` if the calculation succeeded, `False` if a database error occurred.
      - Second element:
        - A `list` of dictionaries containing per-sensor load values on success. Only the
          sensors that already have `count` entries appear in it.
        - `False` if not one sensor has enough data yet.
        - Error message (`str`) on database failure.

    ### Notes
    - The table must contain a `timestamp` column (UNIX epoch seconds).
    - A sensor whose counter is lower than it was is left out too. The counter did not
      go backwards, it started over, and no rate can be computed across a restart.
    - A sensor with fewer than `count` entries is left out of the result rather than
      blanking out the whole call. Sensors come and go while a consumer runs (an interface
      is brought up, a virtual machine is started), and one of them being new is no reason
      to stop reporting the ones that have been measured all along. A consumer that wants
      to name them compares the sensors it asked about with the ones it got back.
    - Results include:
      - `<column>1`: Load computed between the two most recent entries.
      - `<column>n`: Load computed between the most recent and the oldest of `count` entries.
    - Load values are calculated as delta per second.
    - The table name is quoted, so keywords and names containing punctuation work.
    - A `count` below 2 is rejected instead of raising further down.

    ### Example
    Calculate loads for `tx_bytes` and `rx_bytes` over 5 intervals:
    >>> compute_load(
    ...     conn,
    ...     sensorcol='interface',
    ...     datacols=['tx_bytes', 'rx_bytes'],
    ...     count=5,
    ...     table='perfdata',
    ... )

    Example output:

        [
            {
                'interface': 'mgmt1',
                'tx_bytes1': 6906,
                'rx_bytes1': 10418,
                'tx_bytesn': 7442,
                'rx_bytesn': 10871
            },
            ...
        ]
    """
    # Both metrics compare two rows: `Load1` the two most recent ones, `Loadn` the most recent
    # against the `count`-th. With fewer than two there is nothing to compare, and `perfdata[1]`
    # below would raise IndexError out of a function that otherwise always returns a tuple.
    if count < 2:
        return False, f'Computing a load needs a count of at least 2, got {count}'

    # See __table_columns(): an unknown sensor column would silently become a string literal
    # instead of raising, so every sensor would look identical.
    known = __table_columns(conn, table)
    if known and sensorcol not in known:
        return False, f'No such column {sensorcol} in table {table}'

    quoted_table = __quote_ident(table)
    quoted_sensorcol = __quote_ident(sensorcol)

    sql = (
        f'SELECT DISTINCT {quoted_sensorcol} FROM {quoted_table} '  # nosec B608
        f'ORDER BY {quoted_sensorcol} ASC;'
    )
    success, sensors = select(conn, sql)
    if not success:
        return False, sensors
    if len(sensors) == 0:
        return True, False

    load = []

    for sensor in sensors:
        sensor_name = sensor[sensorcol]
        # A fixed bind name, not the column name: `sensorcol` may legitimately contain characters
        # that are not valid in a `:placeholder`.
        success, perfdata = select(
            conn,
            f'SELECT * FROM {quoted_table} WHERE {quoted_sensorcol} = :sensorvalue '  # nosec B608
            f'ORDER BY timestamp DESC;',
            data={'sensorvalue': sensor_name},
        )
        if not success:
            return False, perfdata
        # Not enough history for this sensor yet. Skip it and keep going: a sensor
        # that appeared a moment ago must not blank out the ones that have been
        # measured all along.
        if len(perfdata) < count:
            continue

        load1_delta = perfdata[0]['timestamp'] - perfdata[1]['timestamp']
        loadn_delta = perfdata[0]['timestamp'] - perfdata[count - 1]['timestamp']

        # A counter that is lower than it was did not go backwards, it started over:
        # the machine was restarted, the service reloaded, the host rebooted. There is
        # no rate to be had from that, and inventing one is worse than saying nothing.
        # Negated it would report a busy sensor as idle, and taken as an absolute value
        # it would report a spike that never happened; either way an alert follows that
        # nobody can explain. The sensor is left out instead, which the caller already
        # handles because a sensor without enough history is left out too, and it
        # returns of its own accord once the samples from before the restart have aged
        # out of the window.
        if any(
            perfdata[0][key] < perfdata[index][key]
            for key in datacols
            if key in perfdata[0]
            for index in (1, count - 1)
        ):
            continue

        tmp = {sensorcol: sensor_name}
        for key in datacols:
            if key in perfdata[0]:
                tmp[f'{key}1'] = (
                    (perfdata[0][key] - perfdata[1][key]) / load1_delta
                    if load1_delta
                    else 0
                )
                tmp[f'{key}n'] = (
                    (perfdata[0][key] - perfdata[count - 1][key]) / loadn_delta
                    if loadn_delta
                    else 0
                )
        load.append(tmp)

    if not load:
        return True, False
    return True, load


class __DbConnection(sqlite3.Connection):
    """
    A `sqlite3.Connection` that remembers the file it was opened from.

    `rm_db()` has to know which file to delete, and asking the connection with
    `PRAGMA database_list` only answers reliably on SQLite 3.39.0 and later. Before that the
    pragma carried the `NeedSchema` flag and loaded the schema first (dropped in SQLite commit
    `f2a777fa5d`), so on a corrupt or non-database file it fails with the very error that made
    the caller want to discard the file, leaving it in place forever. A plain
    `sqlite3.Connection` is a C type without an attribute dictionary and cannot carry the path,
    hence this subclass.

    ### Notes
    - `db_path` is a class attribute, so reading it is safe even if a connection never got its
      own value assigned.
    """

    db_path = ''


def connect(path='', filename='', timeout=5.0):
    """
    Connect to a SQLite database file.

    This function establishes a connection to a SQLite database file.
    If no path is provided, a temporary directory is used.
    If no filename is provided, the default filename `'linuxfabrik-monitoring-plugins-sqlite.db'`
    is used.

    ### Parameters
    - **path** (`str`, optional):
      Path to the directory containing the database file.
      Defaults to the system temporary directory (e.g., `/tmp`).
    - **filename** (`str`, optional):
      Name of the database file.
      Defaults to `'linuxfabrik-monitoring-plugins-sqlite.db'`.
    - **timeout** (`float`, optional):
      Seconds to wait for a lock held by another process before giving up with
      `database is locked`. Defaults to `5.0`. Raise it when several checks share one database
      file and run concurrently.

    ### Returns
    - **tuple** (`bool`, `Connection or str`):
      - First element (`bool`): `True` if connection succeeded, `False` if it failed.
      - Second element (`Connection` or `str`):
        - Database connection object on success.
        - Error message string on failure.

    ### Notes
    - On POSIX systems the database is stored in a per-user, `0700`-protected subdirectory of the
      temporary directory (see `get_db_dir()`), not directly in the shared, world-writable `/tmp`.
      This isolates each user's databases and prevents symlink attacks on the predictable paths
      (CWE-377, GHSA-r35r-fpx2-jgr4).
    - The connection uses a `Row` factory, allowing rows to behave like dictionaries.
    - The connection registers a `REGEXP` SQL function for regular expression support. It is
      registered as deterministic where the runtime supports it (Python 3.8 and SQLite 3.8.3),
      and without that flag otherwise, so the connection also works on RHEL 8's default Python.
    - Always check the returned success flag before using the connection.

    ### Example
    >>> success, conn = connect()
    >>> if success:
    >>> # Use conn
    >>>     pass
    >>> else:
    >>>     print(conn)
    """
    success, db = get_db_path(path=path, filename=filename)
    if not success:
        return False, db

    try:
        conn = sqlite3.connect(db, timeout=timeout, factory=__DbConnection)
        conn.db_path = db
        conn.row_factory = sqlite3.Row
        conn.text_factory = str
        # `deterministic=True`: the same pattern and string always yield the same result, so
        # SQLite may use REGEXP in partial indexes and generated columns, and may cache results.
        # The keyword needs Python 3.8 and SQLite 3.8.3; below that it raises `TypeError`
        # respectively `sqlite3.NotSupportedError`. Neither says anything about the database, so
        # register the function without the optimization rather than failing the connection.
        try:
            conn.create_function('REGEXP', 2, regexp, deterministic=True)
        except (TypeError, sqlite3.NotSupportedError):
            conn.create_function('REGEXP', 2, regexp)
        return True, conn
    except Exception as e:
        return False, f'Connecting to DB {db} failed, Error: {e}'


def create_index(
    conn,
    column_list,
    table='perfdata',
    unique=False,
    delete_db_on_operational_error=True,
):
    """
    Create an index on one or more columns in a SQLite table.

    This function creates a (unique or non-unique) index on the specified columns of a table.
    If the database structure has changed and an `OperationalError` occurs, the database file
    can optionally be deleted automatically.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **column_list** (`str`):
      A comma-separated list of columns to index, for example `'col1, col2'`.
    - **table** (`str`, optional):
      The table name. Defaults to `'perfdata'`.
    - **unique** (`bool`, optional):
      If `True`, creates a unique index.
      If `False`, creates a standard (non-unique) index. Defaults to `False`.
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a schema mismatch between releases).
      Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if the operation succeeded, `False` if it failed.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - The table name is sanitized to only allow safe characters.
    - The index name is automatically generated as `idx_<sha1sum>`, based on the table name, the
      column names and whether the index is unique. A unique and a non-unique index over the
      same columns are therefore two separate indices.
    - Index creation uses `IF NOT EXISTS` to avoid errors if the index already exists.

    ### Example
    >>> create_index(conn, 'hostname, service')
    (True, True)

    >>> create_index(conn, 'timestamp', table='logs', unique=True)
    (True, True)
    """
    requested = [col.strip() for col in column_list.split(',') if col.strip()]

    # An unknown column would be quoted into the statement and then resolved to a string literal
    # by SQLite instead of raising, leaving a useless index over a constant behind. Only validate
    # when the table is already there; otherwise let SQLite report "no such table" itself.
    known = __table_columns(conn, table)
    if known:
        unknown = [col for col in requested if col not in known]
        if unknown:
            return False, (
                f'Cannot index unknown column(s) {", ".join(unknown)} of table {table}'
            )

    # Normalize the column list before hashing it, so 'a, b' and 'a,b' describe the same index
    # instead of creating two identical ones.
    columns = ','.join(requested)
    # `unique` is part of the name because `IF NOT EXISTS` below turns the statement into a
    # no-op once an index of that name exists. Hashing only table and columns would let a
    # UNIQUE index requested after a plain one report success without ever being created, and
    # the caller would rely on a constraint that is not there.
    #
    # The parts are joined with a character that cannot occur in an identifier, so table `ab`
    # with column `c` and table `a` with columns `b,c` do not hash to the same name.
    index_key = '\0'.join((table, columns, str(int(unique))))
    index_name = f'idx_{__sha1sum(index_key)}'
    unique_kw = 'UNIQUE ' if unique else ''
    sql = (
        f'CREATE {unique_kw}INDEX IF NOT EXISTS {__quote_ident(index_name)} '
        f'ON {__quote_ident(table)} ({__quote_ident_list(column_list)});'
    )

    c = conn.cursor()
    try:
        c.execute(sql)
        return True, True
    except sqlite3.Error as e:
        return __handle_db_error(conn, e, sql, delete_db=delete_db_on_operational_error)
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}'


def create_table(
    conn,
    definition,
    table='perfdata',
    drop_table_first=False,
    delete_db_on_operational_error=True,
):
    """
    Create a database table if it does not exist.

    This function creates a table in the SQLite database based on the given column definition.
    Optionally, the table can be dropped first if it already exists.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **definition** (`str`):
      Column definitions for the table, e.g., `'col1 TEXT, col2 INTEGER NOT NULL'`.
    - **table** (`str`, optional):
      Name of the table to create. Defaults to `'perfdata'`.
    - **drop_table_first** (`bool`, optional):
      If `True`, drops the table before creating it. Defaults to `False`.
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a file that is not a database at all).
      Defaults to `True`. Passed on to the `drop_table()` call as well.

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if the table was created successfully, `False` if an
        error occurred.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - The table name is quoted, so keywords and names containing punctuation work.
    - `definition` is inserted into the statement verbatim, because a column definition is SQL
      and not a value that could be bound. It must therefore come from the caller's own code and
      never from input the caller does not control.
    - If `drop_table_first=True`, the function will attempt to drop the existing table before
      creating it.
    - The table creation uses `IF NOT EXISTS` to avoid errors if the table already exists.
    - This is usually the first statement a plugin runs, so it is also where an unusable
      database file first shows up. Such a file is discarded here, and the next run starts from
      a healthy one.

    ### Example
    Create a new table with three columns:
    >>> create_table(conn, 'a TEXT, b TEXT, c INTEGER NOT NULL', table='test')

    Resulting SQL:

        CREATE TABLE IF NOT EXISTS "test" (a TEXT, b TEXT, c INTEGER NOT NULL);
    """
    if drop_table_first:
        success, result = drop_table(
            conn,
            table,
            delete_db_on_operational_error=delete_db_on_operational_error,
        )
        if not success:
            return success, result

    sql = f'CREATE TABLE IF NOT EXISTS {__quote_ident(table)} ({definition});'

    c = conn.cursor()
    try:
        c.execute(sql)
        return True, True
    except sqlite3.Error as e:
        return __handle_db_error(conn, e, sql, delete_db=delete_db_on_operational_error)
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}'


def cut(conn, table='perfdata', _max=5, delete_db_on_operational_error=True):
    """
    Keep only the latest records in a SQLite table, based on `rowid`.

    This function deletes older rows from a table, keeping only the most recent `_max` entries
    according to the SQLite built-in `rowid`. Useful for maintaining lightweight, capped tables.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **table** (`str`, optional):
      Name of the table to prune. Defaults to `'perfdata'`.
    - **_max** (`int`, optional):
      Number of most recent records to keep. Must be a non-negative `int`. Defaults to `5`.
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a schema mismatch between releases).
      Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if deletion succeeded, `False` if it failed.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - The function relies on the implicit `rowid` column for ordering. A `WITHOUT ROWID` table
      normally has no such column and cannot be pruned this way; the call reports
      `no such column: rowid` and leaves the database alone. If such a table declares a real
      column named `rowid`, the name resolves to that column and the table is pruned by it.
    - The table name is quoted, so keywords and names containing punctuation work.
    - If an `OperationalError` occurs (e.g., due to schema mismatch), the database file can
      be deleted automatically.
    - Uses `LIMIT -1 OFFSET :_max` to delete everything after the most recent `_max` records.
    - Anything but a non-negative `int` is rejected, because SQLite would delete every row while
      reporting success.

    ### Example
    >>> cut(conn, table='logs', _max=1000)
    (True, True)
    """
    # SQLite skips no row at all for a non-positive OFFSET: `codeOffset()` in `select.c` emits
    # an `OP_IfPos` on the offset register, which only decrements and jumps while the value is
    # greater than zero. A negative `_max` therefore deletes every row instead of keeping some,
    # and still reports success.
    #
    # Rejecting only negative numbers is not enough, because SQLite does not reject a string
    # either: `OP_MustBeInt` first applies numeric affinity (`applyAffinity()` in `vdbe.c`), so
    # `'-5'` becomes the integer -5 and empties the table just the same. Only a real `int` is
    # accepted therefore, and `bool` is excluded because `True` as a row count is a caller bug,
    # not a request to keep one row. A value SQLite cannot use at all (`None`, a non-integral
    # float, a blob) would be caught by `OP_MustBeInt` with "datatype mismatch", but is rejected
    # here as well so every unusable value fails the same way.
    if isinstance(_max, bool) or not isinstance(_max, int) or _max < 0:
        return False, f'Refusing to cut table {table} to an invalid size: {_max!r}'

    table = __quote_ident(table)

    # `LIMIT -1` means "no limit" (see SQLite's select.c), so the subquery yields every row after
    # the `_max` most recent ones.
    # `table` is quoted above, `_max` is bound.
    sql = f"""
        DELETE FROM {table}
        WHERE rowid IN (
            SELECT rowid FROM {table}
            ORDER BY rowid DESC
            LIMIT -1 OFFSET :_max
        );
    """  # nosec B608

    c = conn.cursor()
    try:
        c.execute(sql, {'_max': _max})
        return True, True
    except sqlite3.Error as e:
        return __handle_db_error(conn, e, sql, delete_db=delete_db_on_operational_error)
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}'


def cut_per_sensor(
    conn,
    sensorcol,
    _max=5,
    table='perfdata',
    delete_db_on_operational_error=True,
):
    """
    Keep only the latest records **per sensor** in a SQLite table.

    `cut()` trims a table to a total number of rows, which is only ever correct when
    one sensor owns the table. As soon as several do, whichever of them is written
    most often evicts the history of the others, and a caller that wanted `_max`
    samples of each is left with fewer or none. Multiplying `cut()`'s `_max` by the
    number of sensors does not repair that: it assumes every sensor is written
    equally often, which stops being true the moment the same check runs twice over
    the same cache (a manual run next to the scheduled one) or the set of sensors
    changes between runs.

    ### Parameters
    - **conn** (`sqlite3.Connection`): An active database connection object.
    - **sensorcol** (`str`): Column that identifies the sensor, for example
      `'interface'` or `'name'`.
    - **_max** (`int`, optional): Number of rows to keep per sensor. Defaults to 5.
    - **table** (`str`, optional): Name of the table. Defaults to `'perfdata'`.
    - **delete_db_on_operational_error** (`bool`, optional): Delete the database file
      on `sqlite3.OperationalError`. Defaults to True.

    ### Returns
    - **tuple** (`bool`, `bool` or `str`):
      - `(True, True)` on success.
      - `(False, error_message)` on failure.

    ### Notes
    - The table must contain a `timestamp` column. Rows are ranked newest first, with
      `rowid` breaking a tie, so two samples sharing a timestamp keep a deterministic
      order.
    - Deliberately written without a window function, so it also runs on the SQLite
      versions shipped with older distributions.

    ### Example
    Keep the five newest samples of every interface:
    >>> cut_per_sensor(conn, sensorcol='interface', _max=5)
    """
    if _max < 1:
        return False, f'Keeping rows per sensor needs a _max of at least 1, got {_max}'

    known = __table_columns(conn, table)
    if known and sensorcol not in known:
        return False, f'No such column {sensorcol} in table {table}'

    quoted_table = __quote_ident(table)
    quoted_sensorcol = __quote_ident(sensorcol)

    # Delete every row that already has `_max` newer rows of the same sensor.
    # `table` and `sensorcol` are quoted above, `_max` is bound.
    sql = f"""
        DELETE FROM {quoted_table}
        WHERE rowid IN (
            SELECT a.rowid FROM {quoted_table} a
            WHERE (
                SELECT COUNT(*) FROM {quoted_table} b
                WHERE b.{quoted_sensorcol} = a.{quoted_sensorcol}
                  AND (
                    b.timestamp > a.timestamp
                    OR (b.timestamp = a.timestamp AND b.rowid > a.rowid)
                  )
            ) >= :_max
        );
    """  # nosec B608

    c = conn.cursor()
    try:
        c.execute(sql, {'_max': _max})
        return True, True
    except sqlite3.Error as e:
        return __handle_db_error(conn, e, sql, delete_db=delete_db_on_operational_error)
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}'


def delete(conn, sql, data=None, delete_db_on_operational_error=True):
    """
    Execute a DELETE command against a SQLite table.

    This function deletes records from a table based on the given SQL DELETE statement.
    If no WHERE clause is provided, all records are deleted.
    Parameter binding is supported for safety.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **sql** (`str`):
      The SQL DELETE statement to execute.
      Use placeholders (`:key`) for parameterized queries.
    - **data** (`dict`, optional):
      Dictionary of parameters to bind to the SQL statement.
      Defaults to an empty dict (no parameters).
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a schema mismatch between releases).
      Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `int or str`):
      - First element (`bool`): `True` if the delete succeeded, `False` if it failed.
      - Second element (`int` or `str`):
        - Number of rows affected (`int`) on success.
        - Error message (`str`) on failure.

    ### Notes
    - If the WHERE clause is omitted, all rows in the table will be deleted.
    - Always use a WHERE clause carefully to avoid unintended full table deletion.
    - On schema-related `OperationalError`, the database file can be deleted automatically.

    ### Example
    Delete records older than a specific timestamp:
    >>> sql = 'DELETE FROM logs WHERE timestamp < :cutoff'
    >>> data = {'cutoff': 1700000000}
    >>> delete(conn, sql, data)
    (True, 42)
    """
    if data is None:
        data = {}

    c = conn.cursor()
    try:
        rowcount = c.execute(sql, data).rowcount if data else c.execute(sql).rowcount
        return True, rowcount
    except sqlite3.Error as e:
        return __handle_db_error(
            conn, e, sql, data=data, delete_db=delete_db_on_operational_error
        )
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}, Data: {data}'


def drop_table(conn, table='perfdata', delete_db_on_operational_error=True):
    """
    Drop a table from the SQLite database.

    This function removes a table and all associated indices and triggers from the database.
    If the table does not exist, no error is raised.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **table** (`str`, optional):
      Name of the table to drop.
      Defaults to `'perfdata'`.
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a file that is not a database at all).
      Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if the operation succeeded, `False` if an error occurred.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - The table name is quoted, so keywords and names containing punctuation work.
    - Dropping a table is permanent: all table data, indices, and triggers are permanently deleted.
    - The statement uses `DROP TABLE IF EXISTS` to avoid errors if the table is missing.

    ### Example
    >>> drop_table(conn, table='logs')
    (True, True)
    """
    sql = f'DROP TABLE IF EXISTS {__quote_ident(table)};'

    c = conn.cursor()
    try:
        c.execute(sql)
        return True, True
    except sqlite3.Error as e:
        return __handle_db_error(conn, e, sql, delete_db=delete_db_on_operational_error)
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}'


def get_colnames(col_definition):
    """
    Extract a list of column names from a SQL column definition.

    This function parses a SQL-style column definition string and returns a list
    of column names, ignoring types and constraints.

    ### Parameters
    - **col_definition** (`str`):
      A string defining columns in SQL format, e.g., `'col1 TEXT, col2 INTEGER NOT NULL'`.

    ### Returns
    - **list** (`list` of `str`):
      A list of extracted column names.

    ### Notes
    - Only the first word of each column definition is considered the column name.
    - Column constraints (`PRIMARY KEY`, `NOT NULL`) and data types are ignored.
    - Splitting happens on top-level commas only, so a comma inside a type (`DECIMAL(10,2)`) or
      inside a quoted default value does not start a new column.
    - Table-level constraints (`PRIMARY KEY (a, b)`, `UNIQUE`, `CHECK`, `FOREIGN KEY`,
      `CONSTRAINT`) are not columns and are skipped.
    - Quoted column names are returned unquoted. All four SQLite quoting styles are understood:
      `"name"`, `'name'`, `` `name` `` and `[name]`. A doubled quote character inside a quoted
      name is one literal character, as SQLite reads it.

    ### Example
    >>> get_colnames('date TEXT PRIMARY KEY, count FLOAT, name TEXT')
    ['date', 'count', 'name']

    >>> get_colnames('id INT, price DECIMAL(10,2), PRIMARY KEY (id, price)')
    ['id', 'price']

    >>> get_colnames('"a""b" TEXT')
    ['a"b']
    """
    # Table constraints share the column-definition list but do not name a column.
    table_constraints = ('CHECK', 'CONSTRAINT', 'FOREIGN', 'PRIMARY', 'UNIQUE')
    quotes = {'"': '"', "'": "'", '`': '`', '[': ']'}

    parts = []
    current = ''
    depth = 0
    closing = None
    for char in col_definition:
        if closing:
            current += char
            if char == closing:
                closing = None
            continue
        if char in quotes:
            closing = quotes[char]
            current += char
            continue
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(current)
            current = ''
            continue
        current += char
    parts.append(current)

    colnames = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part[0] in quotes:
            colnames.append(__unquote_ident(part, quotes[part[0]]))
            continue
        name = part.split()[0]
        if name.upper() in table_constraints:
            continue
        colnames.append(name)
    return colnames


def get_db_dir(path):
    """
    Return a per-user subdirectory of `path` that is safe for storing SQLite databases,
    creating it if necessary.

    SQLite databases are stored at predictable paths under the system temporary directory so the
    data is found again on the next run. On a shared POSIX `/tmp`, that predictable path lets a
    local attacker pre-create a symlink there and redirect writes to an arbitrary file. For a
    process running as root (e.g. via sudo) this turns into an arbitrary-write primitive (CWE-377,
    GHSA-r35r-fpx2-jgr4). To prevent this, all databases are kept inside a directory owned by the
    current user with `0700` permissions, and the directory is rejected if anything about it looks
    tampered with.

    ### Parameters
    - **path** (`str`):
      The base directory (typically the system temporary directory) in which to create the
      per-user subdirectory.

    ### Returns
    - **tuple** (`bool`, `str`):
      - First element (`bool`): `True` on success, `False` on failure.
      - Second element (`str`):
        - The absolute path to the secure subdirectory on success.
        - An error message describing the failure otherwise.

    ### Notes
    - `os.geteuid()` does not exist on Windows, where the temporary directory is already per-user
      rather than a shared, world-writable location. There the base `path` is returned unchanged.
    - The directory is validated with `os.lstat()` so a symlink planted at its path is detected
      instead of being followed.

    ### Example
    >>> get_db_dir('/tmp')
    (True, '/tmp/linuxfabrik-monitoring-plugins-uid1000')
    """
    # On Windows the temp dir is already per-user; the shared-/tmp hardening below does not apply.
    if not hasattr(os, 'geteuid'):
        return True, path

    euid = os.geteuid()
    db_dir = os.path.join(path, f'linuxfabrik-monitoring-plugins-uid{euid}')

    # Reject a pre-existing symlink outright: makedirs(exist_ok=True) would either follow it
    # (when it resolves to a directory) or fail with a confusing "File exists" (when it dangles).
    # Either way it must not be used. os.path.islink() does not follow the link.
    if os.path.islink(db_dir):
        return False, f'DB directory {db_dir} is a symlink, refusing to use it'

    try:
        # 0o700: only the owner may access the directory. An existing directory is fine and gets
        # validated below; any other error (e.g. an unwritable temp dir) aborts the connection.
        os.makedirs(db_dir, mode=0o700, exist_ok=True)
    except OSError as e:
        return False, f'Creating DB directory {db_dir} failed, Error: {e}'

    # lstat() does not follow symlinks, so a symlink planted at db_dir is caught here instead of
    # silently redirecting every database to the attacker's target.
    try:
        st = os.lstat(db_dir)
    except OSError as e:
        return False, f'Inspecting DB directory {db_dir} failed, Error: {e}'

    if not stat.S_ISDIR(st.st_mode):
        return False, f'DB directory {db_dir} is not a directory, refusing to use it'
    if st.st_uid != euid:
        return False, f'DB directory {db_dir} has the wrong owner, refusing to use it'
    if st.st_mode & 0o077:
        return False, f'DB directory {db_dir} is too permissive, refusing to use it'

    return True, db_dir


def get_db_path(path='', filename=''):
    """
    Return the absolute path of the SQLite database `filename`, resolving the same secured
    per-user directory that `connect()` uses.

    Use this whenever a caller needs the on-disk location of a database it opens through
    `connect()` (for example to seed, migrate or remove the file), so the path is built in exactly
    one place instead of being reconstructed by every caller.

    ### Parameters
    - **path** (`str`, optional):
      Directory to resolve the database in. Defaults to the system temporary directory.
    - **filename** (`str`, optional):
      Name of the database file. Defaults to `'linuxfabrik-monitoring-plugins-sqlite.db'`.

    ### Returns
    - **tuple** (`bool`, `str`):
      - First element (`bool`): `True` on success, `False` on failure.
      - Second element (`str`):
        - The absolute path to the database file on success.
        - An error message describing the failure otherwise.

    ### Example
    >>> get_db_path(filename='example.db')
    (True, '/tmp/linuxfabrik-monitoring-plugins-uid1000/example.db')
    """
    if not path:
        path = disk.get_tmpdir()
    if not filename:
        filename = 'linuxfabrik-monitoring-plugins-sqlite.db'
    # Confine the database to the secured per-user directory: a filename must be
    # a plain basename. Reject anything that carries a path separator, a
    # parent-directory reference or an absolute path, so a caller-supplied name
    # cannot traverse out of the directory get_db_dir() just hardened.
    if filename in ('.', '..') or os.path.basename(filename) != filename:
        return False, f'Refusing unsafe database filename: {filename!r}'
    success, db_dir = get_db_dir(path)
    if not success:
        return False, db_dir
    return True, os.path.join(db_dir, filename)


def get_tables(conn):
    """
    List all user-defined tables in the SQLite database.

    This function retrieves the names of all tables in the database, excluding the ones SQLite
    keeps for itself under the reserved `'sqlite_'` prefix (`sqlite_sequence`, `sqlite_stat1`
    and friends).

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.

    ### Returns
    - **tuple** (`bool`, `list or str`):
      - First element (`bool`): `True` if the query succeeded, `False` if it failed.
      - Second element (`list` or `str`):
        - A list of table names (`str`) on success.
        - An error message (`str`) on failure.

    ### Notes
    - The filter goes by name, so it covers exactly the `sqlite_` prefix that SQLite reserves for
      itself. The shadow tables an extension creates for a virtual table are ordinary tables with
      ordinary names (`<name>_content` and `<name>_segments` for FTS, `<name>_node` for R-Tree,
      and so on) and are returned like any other table.
    - Only the `main` database is listed. Temporary tables live in `sqlite_temp_master` and
      attached databases have their own `sqlite_master`, so neither shows up here.
    - Views are not tables and are not returned either.
    - Internally calls the `select()` helper function.

    ### Example
    >>> success, tables = get_tables(conn)
    >>> if success:
    >>>     print(tables)  # ['users', 'orders', 'logs']
    >>> else:
    >>>     print(tables)
    """
    # `ESCAPE '_'` makes the doubled underscore a literal one. Without it `_` is a LIKE wildcard
    # matching any single character, so a user table named `sqliteXfoo` would be hidden as well.
    # SQLite's own shell writes the pattern without the escape and does hide such a table; the
    # extra strictness here is deliberate, because a user table is never ours to hide.
    sql = (
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite__%' ESCAPE '_';"
    )
    success, result = select(conn, sql, as_dict=False)

    if not success:
        return success, result

    # Extract just the table names (first column from each row)
    table_names = [row[0] for row in result]
    return True, table_names


def import_csv(
    conn,
    filename,
    table='data',
    fieldnames=None,
    skip_header=False,
    delimiter=',',
    quotechar='"',
    newline='',
    chunksize=1000,
    encoding='utf-8',
):
    """
    Import a CSV file into a SQLite table.

    This function reads a CSV file and inserts its data into the specified SQLite table.
    Field names for the table are taken from the provided `fieldnames` string, not from
    the CSV header. Supports importing large files efficiently by committing in chunks.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **filename** (`str`):
      Path to the CSV file to import.
    - **table** (`str`, optional):
      Name of the table to import into.
      Defaults to `'data'`.
      If `None`, uses a sanitized version of the filename as the table name.
    - **fieldnames** (`str`, optional):
      A SQL-style column definition string, e.g., `'col1 TEXT, col2 FLOAT'`.
      Used to create the table.
      Must match the number of columns in the CSV.
    - **skip_header** (`bool`, optional):
      If `True`, skip the first line of the CSV file. Defaults to `False`.
    - **delimiter** (`str`, optional):
      Field delimiter used in the CSV file. Defaults to `','`.
    - **quotechar** (`str`, optional):
      Character used to quote fields in the CSV file. Defaults to `'"'`.
    - **newline** (`str`, optional):
      Newline control when opening the file. Defaults to `''`.
    - **chunksize** (`int`, optional):
      Number of rows after which a database commit occurs. Defaults to `1000`.
    - **encoding** (`str`, optional):
      Character encoding of the CSV file. Defaults to `'utf-8'`.

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if import succeeded, `False` if it failed.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - This function creates the destination table before import, replacing it if it exists.
    - Field names are taken from `fieldnames`, not from the CSV header.
    - `fieldnames` reaches `CREATE TABLE` verbatim (see `create_table()`), so it must come from
      the caller's own code and never from input the caller does not control.
    - Supports importing large CSVs efficiently by committing in chunks.
    - Does not use the SQLite CLI tool to avoid dependency and version issues.
    - Automatically skips empty rows during import.
    - Catches CSV parsing errors, I/O errors, and unexpected exceptions.
    - The import aborts on the first row that cannot be inserted, reporting the offending line.
      The database is kept so the caller can inspect the partial import.

    ### Example
    >>> import_csv(
    ...     conn,
    ...     'examples/EXAMPLE01.csv',
    ...     table='data',
    ...     fieldnames='date TEXT PRIMARY KEY, count FLOAT, name TEXT',
    ...     skip_header=True,
    ... )
    (True, True)
    """
    if table is None:
        table = __filter_str(filename)

    skipped = False

    # Create the table
    success, result = create_table(conn, fieldnames, table=table, drop_table_first=True)
    if not success:
        return success, result

    new_fieldnames = get_colnames(fieldnames)

    try:
        with open(filename, newline=newline, encoding=encoding) as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
            i = 0
            for csv_row in reader:
                if skip_header and not skipped:
                    skipped = True
                    continue
                if all(s.strip() == '' for s in csv_row):
                    continue
                data = dict(zip(new_fieldnames, csv_row))
                # `delete_db_on_operational_error=False`: a bad row says nothing about the
                # database, which this function just created. Removing it here would also close
                # the connection and turn every following row into a misleading
                # "Cannot operate on a closed database".
                success, result = insert(
                    conn, data, table, delete_db_on_operational_error=False
                )
                if not success:
                    commit(conn)
                    return (
                        False,
                        f'Import of {filename} failed in line {reader.line_num}: {result}',
                    )
                i += 1
                if i > 0 and i % chunksize == 0:
                    commit(conn)
            commit(conn)
        return True, True

    except csv.Error as e:
        return False, f'CSV error in file {filename}, line {reader.line_num}: {e}'
    except OSError as e:
        return False, f'I/O error "{e.strerror}" while opening or reading {filename}'
    except Exception as e:
        return False, f'Unknown error opening or reading {filename}:\n{e}'


def insert(conn, data, table='perfdata', delete_db_on_operational_error=True):
    """
    Insert a row of values into a SQLite table.

    This function inserts a new record into the specified table.
    The data must be provided as a dictionary, where keys are column names
    and values are the corresponding field values.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **data** (`dict`):
      A dictionary where each key is a column name and each value is the value to insert.
    - **table** (`str`, optional):
      Name of the table to insert into.
      Defaults to `'perfdata'`.
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a schema mismatch between releases).
      Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if the insert succeeded, `False` if it failed.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - The table name is quoted, so keywords and names containing punctuation work.
    - Field names and values are safely parameterized to prevent SQL injection.
    - If an `OperationalError` occurs (e.g., due to a schema mismatch), the database can optionally
      be deleted automatically.

    ### Example
    >>> insert(
    ...     conn,
    ...     {'hostname': 'server1', 'service': 'http', 'status': 0},
    ...     table='status',
    ... )
    (True, True)
    """
    # Column names are quoted, not bound: SQLite cannot bind an identifier, so a key carrying SQL
    # syntax would otherwise end up as executable text. Values use positional binds, which also
    # keeps keys working that are not valid `:placeholder` names.
    if data:
        keys = ','.join(__quote_ident(key) for key in data)
        binds = ','.join('?' for _ in data)
        sql = f'INSERT INTO {__quote_ident(table)} ({keys}) VALUES ({binds});'  # nosec B608
    else:
        # An empty dict has no column list to build. `DEFAULT VALUES` is SQLite's spelling for a
        # row made up entirely of column defaults; the alternative `() VALUES ()` is a syntax
        # error.
        sql = f'INSERT INTO {__quote_ident(table)} DEFAULT VALUES;'  # nosec B608

    c = conn.cursor()
    try:
        c.execute(sql, tuple(data.values()))
        return True, True
    except sqlite3.Error as e:
        return __handle_db_error(
            conn, e, sql, data=data, delete_db=delete_db_on_operational_error
        )
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}, Data: {data}'


def per_second_deltas(filename, name, counters):
    """
    Persist cumulative counters in a local SQLite cache and return their
    per-second deltas vs. the previous run.

    Generic helper for the "delta of cumulative counters between runs"
    pattern. Works for any cumulative counter that needs to be reported as
    a per-second rate: /proc and /sys byte counters (disk I/O, network
    traffic, file descriptors), database status counters, application
    metrics. Lets a check plugin emit per-second rates as perfdata instead
    of `uom='c'` continuous counters (per CONTRIBUTING.md), so Grafana
    panels do not need their own `non_negative_difference()` workaround.

    The cache table schema is derived from the keys of `counters`: each
    key becomes an `INT NOT NULL` column alongside the bookkeeping columns
    `name TEXT NOT NULL` and `timestamp INT NOT NULL`. The table is kept
    to the two most recent rows per `name`, so several names can share one
    cache file without pruning each other's baseline. If the schema changes
    between releases (the caller adds or removes a counter), the helper
    drops and rebuilds the table once; the previous baseline is lost but
    the next run produces a valid delta again.

    ### Parameters
    - **filename** (`str`):
      SQLite cache filename, e.g. `'linuxfabrik-monitoring-plugins-<plugin>.db'`.
      Lives under `$TEMP`. Pick a per-plugin name so caches do not collide.
    - **name** (`str`):
      Sample identifier stored in the `name` column (e.g. the plugin
      name). Lets multiple checks share a single cache file when
      convenient, but typically one name per filename.
    - **counters** (`dict[str, int]`):
      Mapping from counter name to cumulative counter value. Characters
      outside `[a-zA-Z0-9_]` are stripped for the database column, so
      `rx-bytes` is stored in a column `rxbytes`. The returned mapping
      keeps the names as passed in. Pick names that already match
      `[a-zA-Z0-9_]+` so two counters cannot collapse onto one column.

    ### Returns
    - **dict[str, float]**: `{counter_name: per_second_rate}` on success.
    - **None**: fewer than 2 samples recorded yet (fresh install or
      cache wiped), counter reset detected (delta < 0; happens on
      restart of the monitored service or any `FLUSH`-style reset),
      zero or negative time delta, or any SQLite operation failed.

    ### Example
    Network traffic rates from `/proc/net/dev`:

    >>> rates = lib.db_sqlite.per_second_deltas(
    ...     'linuxfabrik-monitoring-plugins-net.db',
    ...     'eth0',
    ...     {'rx_bytes': 1_073_741_824, 'tx_bytes': 524_288_000},
    ... )
    >>> if rates is not None:
    ...     perfdata += lib.base.get_perfdata(
    ...         'rx_bytes_per_second',
    ...         rates['rx_bytes'],
    ...         uom='B',
    ...         _min=0,
    ...     )
    ...     perfdata += lib.base.get_perfdata(
    ...         'tx_bytes_per_second',
    ...         rates['tx_bytes'],
    ...         uom='B',
    ...         _min=0,
    ...     )
    """
    ok, conn = connect(filename=filename)
    if not ok:
        return None

    # Map every caller-supplied counter name to the column name actually used in the table, so the
    # CREATE and the INSERT below agree. Sanitizing only the CREATE would build a column `rxbytes`
    # for a counter named `rx-bytes` and then insert into `rx-bytes`, which fails on every run and
    # leaves the helper returning None forever.
    columns = {col: __filter_str(col) for col in counters}

    col_defs = ['name TEXT NOT NULL', 'timestamp INT NOT NULL']
    col_defs.extend(f'{column} INT NOT NULL' for column in columns.values())
    definition = ', '.join(col_defs)

    ok, _ = create_table(conn, definition, drop_table_first=False)
    if not ok:
        close(conn)
        return None
    create_index(conn, 'name')

    row = {'name': name, 'timestamp': time.now()}
    for col, column in columns.items():
        row[column] = counters[col]
    # Pass `delete_db_on_operational_error=False` so a schema mismatch leaves
    # the connection open. We then drop+recreate the table ourselves below;
    # the default `True` would `rm_db(conn)` (close + delete) and break the
    # subsequent drop_table() with "Cannot operate on a closed database".
    ok, _ = insert(conn, row, delete_db_on_operational_error=False)
    if not ok:
        # Schema mismatch from a previous release (different counter
        # columns or NOT NULL constraints). Rebuild the table from the
        # current schema; we lose the previous baseline but auto-recover on
        # the next run. `delete_db_on_operational_error=False` throughout,
        # for the same reason as the insert above: removing the database
        # closes the connection and every following step would fail with
        # "Cannot operate on a closed database".
        drop_table(conn, delete_db_on_operational_error=False)
        ok, _ = create_table(
            conn,
            definition,
            drop_table_first=False,
            delete_db_on_operational_error=False,
        )
        if not ok:
            close(conn)
            return None
        create_index(conn, 'name')
        ok, _ = insert(conn, row, delete_db_on_operational_error=False)
        if not ok:
            close(conn)
            return None

    # Not `cut()`: that keeps the newest rows of the whole table. Two callers sharing one cache
    # file under different names would leave each other with a single row, and a delta needs
    # two. Prune per name instead. The `rowid DESC` tie-break keeps the pair deterministic when
    # two samples share a timestamp, which `cut()` got from ordering by `rowid` alone.
    delete(
        conn,
        """
        DELETE FROM perfdata
        WHERE name = :name
          AND rowid NOT IN (
            SELECT rowid FROM perfdata
            WHERE name = :name
            ORDER BY timestamp DESC, rowid DESC
            LIMIT 2
          );
        """,
        {'name': name},
    )
    commit(conn)

    ok, rows = select(
        conn,
        """
        SELECT *
        FROM perfdata
        WHERE name = :name
        ORDER BY timestamp DESC, rowid DESC
        """,
        {'name': name},
    )
    close(conn)
    if not ok or len(rows) < 2:
        return None

    timestamp_diff = rows[0]['timestamp'] - rows[1]['timestamp']
    if timestamp_diff <= 0:
        return None

    # Keyed by the caller's counter names, not by the sanitized column names, so the caller reads
    # the result back with the keys it passed in.
    rates = {}
    for col, column in columns.items():
        delta = rows[0][column] - rows[1][column]
        if delta < 0:
            # counter reset (server restart, FLUSH STATUS)
            return None
        rates[col] = delta / timestamp_diff
    return rates


def regexp(expr, item):
    """
    Implement REGEXP functionality for SQLite queries.

    SQLite does not support the REGEXP operator by default.
    This function enables REGEXP support by providing a Python implementation
    that can be registered with a SQLite connection.

    ### Parameters
    - **expr** (`str`):
      The regular expression pattern to match.
    - **item** (`str`):
      The string to test against the regular expression.

    ### Returns
    - **bool** or **None**:
      `True` if the regular expression matches the string, `False` if it does not, and `None`
      (SQL `NULL`) if either argument is `NULL`.

    ### Notes
    - Must be registered on the SQLite connection using `create_function('REGEXP', 2, regexp)`.
    - SQLite passes the pattern as the first and the value as the second argument: `X REGEXP Y`
      is evaluated as `regexp(Y, X)`.
    - Regular expressions use Python's `re` module syntax. That is deliberately not the syntax of
      SQLite's own `regexp()`, whose NFA engine knows no backreferences, no lookaround and no
      lazy quantifiers, matches a newline with `.`, and recognizes `$` only at the very end of a
      pattern. A pattern written for one of the two does not necessarily mean the same in the
      other.
    - Arguments that are not TEXT (INTEGER, REAL, BLOB) are converted to text first, both the
      pattern and the value, the same way SQLite's own `regexp()` implementation applies
      `sqlite3_value_text()` to both of its arguments. Without that conversion, matching against
      a numeric column raises inside the function and the whole query fails. The conversion is
      Python's, not SQLite's, so the text form of a REAL can differ from what SQLite itself would
      render (`1e+20` versus `1.0e+20`). Anchor a pattern on the stored digits rather than on an
      exponent notation.
    - A `NULL` pattern or value yields `NULL`, not `False`, matching SQLite's own `regexp()`,
      which leaves its result unset for a `NULL` argument. The difference is visible in a negated
      comparison: `WHERE NOT (col REGEXP 'x')` skips a `NULL` row, whereas `False` would select
      it.
    - A pattern that does not compile aborts the query with the generic
      `OperationalError: user-defined function raised exception`; Python does not pass the
      reason on, unlike SQLite's own `regexp()`, which reports the compile error itself. That
      message matches none of the patterns this library treats as a broken database, so the
      cached database survives a bad pattern.
    - Commonly used in queries like:
      `SELECT * FROM table WHERE column REGEXP 'pattern'`.

    ### Example
    >>> regexp('^abc', 'abcdef')
    True

    >>> regexp('xyz$', 'abcdef')
    False

    >>> regexp('^9', 9000)
    True

    >>> regexp(9, 9000)
    True
    """
    if expr is None or item is None:
        return None
    # Both arguments get the same treatment, so `__compile_regex()` is always keyed on a string.
    if isinstance(expr, bytes):
        expr = expr.decode('utf-8', 'replace')
    elif not isinstance(expr, str):
        expr = str(expr)
    if isinstance(item, bytes):
        item = item.decode('utf-8', 'replace')
    elif not isinstance(item, str):
        item = str(item)
    return __compile_regex(expr).search(item) is not None


def replace(conn, data, table='perfdata', delete_db_on_operational_error=True):
    """
    Insert or replace a row in a SQLite table.

    This function uses the SQLite `REPLACE INTO` statement, which works like
    `INSERT`, but if a UNIQUE or PRIMARY KEY constraint violation occurs, it first deletes
    the existing row and then inserts the new row.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **data** (`dict`):
      A dictionary where each key is a column name and each value is the value to insert.
    - **table** (`str`, optional):
      Name of the table to operate on.
      Defaults to `'perfdata'`.
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a schema mismatch between releases).
      Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if the operation succeeded, `False` if it failed.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - `REPLACE` deletes the existing conflicting row, then inserts the new one.
    - `NOT NULL` and `CHECK` constraints are evaluated before that, on the row being inserted, so
      a violation aborts without anything having been deleted.
    - `REPLACE` changes what a `NOT NULL` violation means: a column that has a `DEFAULT` gets the
      default value silently instead of raising, and only a `NOT NULL` column without a `DEFAULT`
      aborts with `NOT NULL constraint failed`. Do not rely on `replace()` to reject a `None`.
    - An abort rolls back the statement, not an enclosing transaction. Everything committed or
      written before it stays.
    - Deleting the conflicting row fires `DELETE` triggers only when `PRAGMA recursive_triggers`
      is on, and honours `ON DELETE` foreign key actions only when `PRAGMA foreign_keys` is on.
      Both are off by default in Python's `sqlite3` and this library does not turn them on, so a
      row is normally replaced without either taking effect.
    - Field names and values are safely parameterized to prevent SQL injection.
    - The table name is quoted, so keywords and names containing punctuation work.

    ### Example
    >>> replace(
    ...     conn,
    ...     {'hostname': 'server1', 'service': 'http', 'status': 0},
    ...     table='status',
    ... )
    (True, True)
    """
    # See insert(): identifiers are quoted, values are bound positionally, and an empty dict falls
    # back to `DEFAULT VALUES`.
    if data:
        keys = ','.join(__quote_ident(key) for key in data)
        binds = ','.join('?' for _ in data)
        sql = f'REPLACE INTO {__quote_ident(table)} ({keys}) VALUES ({binds});'  # nosec B608
    else:
        sql = f'REPLACE INTO {__quote_ident(table)} DEFAULT VALUES;'  # nosec B608

    c = conn.cursor()
    try:
        c.execute(sql, tuple(data.values()))
        return True, True
    except sqlite3.Error as e:
        return __handle_db_error(
            conn, e, sql, data=data, delete_db=delete_db_on_operational_error
        )
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}, Data: {data}'


def rm_db(conn):
    """
    Delete the SQLite database file associated with a connection.

    This function retrieves the file path of the SQLite database from the active connection,
    closes the connection, and deletes the database file from disk.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.

    ### Returns
    - **bool**:
      Always returns `True`.

    ### Notes
    - Useful when the on-disk database turns out to be unusable, for example because its schema
      no longer matches what the current release writes.
    - Only the `main` database is deleted (attached databases are ignored). Its rollback
      journal, write-ahead log and shared-memory index (`-journal`, `-wal`, `-shm`) go with it,
      because they describe a database that no longer exists.
    - Works on a connection opened by `connect()` even when the file is too corrupt for SQLite
      to answer questions about it. A connection the caller opened itself is queried with
      `PRAGMA database_list`, which SQLite refuses on such a file before release 3.39.0; there
      the file is left on disk.
    - The connection is closed in every case, including for in-memory databases, which have no
      file to delete.
    - Any errors from file deletion are handled externally (through `disk.rm_file()`).

    ### Example
    >>> rm_db(conn)
    True
    """
    # A connection opened by connect() knows its own path (see `__DbConnection`), which is the
    # only source that still answers when the file is corrupt. The pragma is the fallback for a
    # connection the caller opened itself; it yields (seq, name, file), with `file` empty for an
    # in-memory database.
    filename = getattr(conn, 'db_path', '')
    if not filename:
        try:
            for _, name, dbfile in conn.execute('PRAGMA database_list'):
                if name == 'main':
                    filename = dbfile
                    break
        except sqlite3.Error:
            # An unusable database may not even answer the pragma. Closing still has to happen.
            pass

    close(conn)
    if filename:
        disk.rm_file(filename)
        # A rollback journal, a write-ahead log or its shared-memory index describes a database
        # that no longer exists. SQLite does not read the data back from them once the main file
        # is gone, so leaving them behind only litters the per-user temporary directory. This
        # library never enables WAL itself, but a caller may. `rm_file()` reports a missing file
        # instead of raising, so unlinking one that was never there costs nothing.
        for suffix in ('-journal', '-shm', '-wal'):
            disk.rm_file(filename + suffix)
    return True


def select(
    conn,
    sql,
    data=None,
    fetchone=False,
    as_dict=True,
    delete_db_on_operational_error=True,
):
    """
    Execute a SELECT query against a SQLite database.

    This function runs a SQL SELECT statement and retrieves zero or more rows of data.
    It supports optional parameter binding, returning results either as dictionaries
    or as default SQLite row objects.

    ### Parameters
    - **conn** (`sqlite3.Connection`):
      An active database connection object.
    - **sql** (`str`):
      The SQL SELECT statement to execute.
      Use placeholders (`:key`) for parameterized queries.
    - **data** (`dict`, optional):
      Dictionary of parameters to bind to the SQL query.
      Defaults to an empty dict (no parameters).
    - **fetchone** (`bool`, optional):
      If `True`, fetch only the first row.
      If `False` (default), fetch all rows.
    - **as_dict** (`bool`, optional):
      If `True`, return results as a list of dictionaries.
      If `False`, return raw SQLite row objects. Defaults to `True`.
    - **delete_db_on_operational_error** (`bool`, optional):
      If `True`, deletes the database file when the on-disk database turns out
      to be unusable (e.g. a schema mismatch between releases).
      Defaults to `True`.

    ### Returns
    - **tuple** (`bool`, `list or dict or str`):
      - First element (`bool`): `True` if the query succeeded, `False` if it failed.
      - Second element (`list`, `dict`, or `str`):
        - A list of rows, or a single row if `fetchone=True`.
        - Error message (`str`) on failure.

    ### Notes
    - Results are returned as dictionaries if `as_dict=True`.
    - If no results are found when `fetchone=True`, returns an empty list `[]`.
    - On schema-related `OperationalError`, the database file can optionally be deleted.

    ### Example
    >>> sql = 'SELECT hostname, service FROM status WHERE status = :status'
    >>> data = {'status': 0}
    >>> success, rows = select(conn, sql, data)
    >>> if success:
    >>>     for row in rows:
    >>>         print(row['hostname'], row['service'])
    >>> else:
    >>>     print(rows)
    """
    if data is None:
        data = {}

    c = conn.cursor()
    try:
        if data:
            c.execute(sql, data)
        else:
            c.execute(sql)

        rows = c.fetchall()

        if as_dict:
            rows = [dict(row) for row in rows]

        if fetchone:
            return True, rows[0] if rows else []

        return True, rows

    except sqlite3.Error as e:
        return __handle_db_error(
            conn, e, sql, data=data, delete_db=delete_db_on_operational_error
        )
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}, Data: {data}'
