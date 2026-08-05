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
__version__ = '2026080501'

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
SCHEMA_ERRORS = (
    'has no column named',
    'no such column',
    'no such table',
    'values were supplied',  # "table t has 2 columns but 3 values were supplied"
)

# Substrings identifying a database file that is unusable no matter what is queried. sqlite3
# reports these as a plain `sqlite3.DatabaseError`, not as an `OperationalError`, so the case
# where discarding the file is most clearly right needs to be matched separately.
CORRUPT_ERRORS = (
    'database disk image is malformed',
    'file is not a database',
    'malformed database schema',
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
    compiled expression via `sqlite3_set_auxdata()`.

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


def __table_columns(conn, table):
    """
    Return the column names of `table` as reported by the database itself.

    Used to reject a column name before it reaches a statement. SQLite resolves a double-quoted
    token that matches no column to a string literal instead of raising "no such column" (the
    double-quoted string misfeature, see `resolveExprStep()` in SQLite's `resolve.c`). A
    misspelled column would therefore index or group by a constant, silently and successfully.

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
    try:
        rows = conn.execute(f'PRAGMA table_info({__quote_ident(table)});').fetchall()
    except sqlite3.Error:
        return []
    # PRAGMA table_info yields (cid, name, type, notnull, dflt_value, pk).
    return [row[1] for row in rows]


def __is_unusable_db(e):
    """
    Decide whether an `sqlite3` exception means the database file has to be discarded.

    Only a schema that no longer matches this release, a constraint or data mismatch, or an
    unreadable file justify deleting the database. Everything else (a lock held by a concurrent
    plugin run, a full or read-only disk, an I/O error, a broken statement, a failing user-defined
    function) is transient or a caller bug: the cache is fine and has to survive.

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
    """
    # A constraint or data error (for example a NOT NULL column that a newer or older release no
    # longer writes) means the on-disk schema no longer matches the data being written.
    if isinstance(e, (sqlite3.DataError, sqlite3.IntegrityError)):
        return True

    msg = str(e).lower()
    if isinstance(e, sqlite3.OperationalError):
        return any(pattern in msg for pattern in SCHEMA_ERRORS)
    if isinstance(e, sqlite3.DatabaseError):
        return any(pattern in msg for pattern in CORRUPT_ERRORS)
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
      Number of historical entries to use for calculating `Loadn`.
    - **table** (`str`, optional):
      Name of the table containing the performance data.
      Defaults to `'perfdata'`.

    ### Returns
    - **tuple** (`bool`, `list or bool or str`):
      - First element (`bool`): `True` if the calculation succeeded, `False` if a database error occurred.
      - Second element:
        - A `list` of dictionaries containing per-sensor load values on success.
        - `False` if there is not enough data to compute the load.
        - Error message (`str`) on database failure.

    ### Notes
    - The table must contain a `timestamp` column (UNIX epoch seconds).
    - Data must exist for each sensor with at least `count` historical entries.
    - Results include:
      - `<column>1`: Load computed between the two most recent entries.
      - `<column>n`: Load computed between the most recent and the oldest of `count` entries.
    - Load values are calculated as delta per second.
    - Table names are sanitized to allow only safe characters.

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
    table = __filter_str(table)

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
        if len(perfdata) < count:
            return True, False

        load1_delta = perfdata[0]['timestamp'] - perfdata[1]['timestamp']
        loadn_delta = perfdata[0]['timestamp'] - perfdata[count - 1]['timestamp']

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

    return True, load


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
    - The connection registers a `REGEXP` SQL function for regular expression support.
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
        conn = sqlite3.connect(db, timeout=timeout)
        conn.row_factory = sqlite3.Row
        conn.text_factory = str
        # `deterministic=True`: the same pattern and string always yield the same result, so
        # SQLite may use REGEXP in partial indexes and generated columns, and may cache results.
        conn.create_function('REGEXP', 2, regexp, deterministic=True)
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
    - The index name is automatically generated as `idx_<sha1sum>`, based on table and column names.
    - Index creation uses `IF NOT EXISTS` to avoid errors if the index already exists.

    ### Example
    >>> create_index(conn, 'hostname, service')
    (True, True)

    >>> create_index(conn, 'timestamp', table='logs', unique=True)
    (True, True)
    """
    table = __filter_str(table)
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
    index_name = f'idx_{__sha1sum(table + columns)}'
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


def create_table(conn, definition, table='perfdata', drop_table_first=False):
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

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if the table was created successfully, `False` if an
        error occurred.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - The table name is sanitized to allow only safe characters.
    - If `drop_table_first=True`, the function will attempt to drop the existing table before
      creating it.
    - The table creation uses `IF NOT EXISTS` to avoid errors if the table already exists.

    ### Example
    Create a new table with three columns:
    >>> create_table(conn, 'a TEXT, b TEXT, c INTEGER NOT NULL', table='test')

    Resulting SQL:

        CREATE TABLE IF NOT EXISTS "test" (a TEXT, b TEXT, c INTEGER NOT NULL);
    """
    table = __filter_str(table)

    if drop_table_first:
        success, result = drop_table(conn, table)
        if not success:
            return success, result

    sql = f'CREATE TABLE IF NOT EXISTS {__quote_ident(table)} ({definition});'

    c = conn.cursor()
    try:
        c.execute(sql)
        return True, True
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
      Number of most recent records to keep. Defaults to `5`.
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
    - The function relies on the implicit `rowid` column for ordering.
    - The table name is sanitized to allow only safe characters.
    - If an `OperationalError` occurs (e.g., due to schema mismatch), the database file can
      be deleted automatically.
    - Uses `LIMIT -1 OFFSET :_max` to delete everything after the most recent `_max` records.

    ### Example
    >>> cut(conn, table='logs', _max=1000)
    (True, True)
    """
    table = __quote_ident(__filter_str(table))

    # `LIMIT -1` means "no limit" (see SQLite's select.c), so the subquery yields every row after
    # the `_max` most recent ones.
    # `table` is filtered and quoted above, `_max` is bound.
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


def drop_table(conn, table='perfdata'):
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

    ### Returns
    - **tuple** (`bool`, `bool or str`):
      - First element (`bool`): `True` if the operation succeeded, `False` if an error occurred.
      - Second element (`bool` or `str`):
        - `True` on success.
        - Error message (`str`) describing the failure.

    ### Notes
    - The table name is sanitized to allow only safe characters.
    - Dropping a table is permanent: all table data, indices, and triggers are permanently deleted.
    - The statement uses `DROP TABLE IF EXISTS` to avoid errors if the table is missing.

    ### Example
    >>> drop_table(conn, table='logs')
    (True, True)
    """
    table = __filter_str(table)
    sql = f'DROP TABLE IF EXISTS {__quote_ident(table)};'

    c = conn.cursor()
    try:
        c.execute(sql)
        return True, True
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
    - Quoted column names are returned unquoted.

    ### Example
    >>> get_colnames('date TEXT PRIMARY KEY, count FLOAT, name TEXT')
    ['date', 'count', 'name']

    >>> get_colnames('id INT, price DECIMAL(10,2), PRIMARY KEY (id, price)')
    ['id', 'price']
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
            # A quoted name may contain spaces, so it cannot be taken apart with split().
            end = part.find(quotes[part[0]], 1)
            colnames.append(part[1:end] if end > 0 else part[1:])
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

    This function retrieves the names of all tables in the database,
    excluding SQLite internal tables (e.g., those starting with `'sqlite_'`).

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
    - Only user-created tables are returned.
    - Tables created internally by SQLite (e.g., for indices or schema tracking) are excluded.
    - Internally calls the `select()` helper function.

    ### Example
    >>> success, tables = get_tables(conn)
    >>> if success:
    >>>     print(tables)  # ['users', 'orders', 'logs']
    >>> else:
    >>>     print(tables)
    """
    sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
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
    - Table names are sanitized to allow only safe characters.
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
    table = __filter_str(table)

    # Column names are quoted, not bound: SQLite cannot bind an identifier, so a key carrying SQL
    # syntax would otherwise end up as executable text. Values use positional binds, which also
    # keeps keys working that are not valid `:placeholder` names.
    keys = ','.join(__quote_ident(key) for key in data)
    binds = ','.join('?' for _ in data)
    sql = f'INSERT INTO {__quote_ident(table)} ({keys}) VALUES ({binds});'  # nosec B608

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
    to the two most recent rows. If the schema changes between releases
    (the caller adds or removes a counter), the helper drops and rebuilds
    the table once; the previous baseline is lost but the next run
    produces a valid delta again.

    ### Parameters
    - **filename** (`str`):
      SQLite cache filename, e.g. `'linuxfabrik-monitoring-plugins-<plugin>.db'`.
      Lives under `$TEMP`. Pick a per-plugin name so caches do not collide.
    - **name** (`str`):
      Sample identifier stored in the `name` column (e.g. the plugin
      name). Lets multiple checks share a single cache file when
      convenient, but typically one name per filename.
    - **counters** (`dict[str, int]`):
      Mapping from column name to cumulative counter value. Column names
      must match `[a-zA-Z0-9_]+`; other characters get stripped by
      `__filter_str()`.

    ### Returns
    - **dict[str, float]**: `{column_name: per_second_rate}` on success.
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

    col_defs = ['name TEXT NOT NULL', 'timestamp INT NOT NULL']
    for col in counters:
        col_defs.append(f'{__filter_str(col)} INT NOT NULL')
    definition = ', '.join(col_defs)

    ok, _ = create_table(conn, definition, drop_table_first=False)
    if not ok:
        close(conn)
        return None
    create_index(conn, 'name')

    row = {'name': name, 'timestamp': time.now()}
    row.update(counters)
    # Pass `delete_db_on_operational_error=False` so a schema mismatch leaves
    # the connection open. We then drop+recreate the table ourselves below;
    # the default `True` would `rm_db(conn)` (close + delete) and break the
    # subsequent drop_table() with "Cannot operate on a closed database".
    ok, _ = insert(conn, row, delete_db_on_operational_error=False)
    if not ok:
        # Schema mismatch from a previous release (different counter
        # columns or NOT NULL constraints). Rebuild the table from the
        # current schema; we lose the previous baseline but auto-recover on
        # the next run.
        drop_table(conn)
        ok, _ = create_table(conn, definition, drop_table_first=False)
        if not ok:
            close(conn)
            return None
        create_index(conn, 'name')
        ok, _ = insert(conn, row, delete_db_on_operational_error=False)
        if not ok:
            close(conn)
            return None

    cut(conn, _max=2)
    commit(conn)

    ok, rows = select(
        conn,
        """
        SELECT *
        FROM perfdata
        WHERE name = :name
        ORDER BY timestamp DESC
        """,
        {'name': name},
    )
    close(conn)
    if not ok or len(rows) < 2:
        return None

    timestamp_diff = rows[0]['timestamp'] - rows[1]['timestamp']
    if timestamp_diff <= 0:
        return None

    rates = {}
    for col in counters:
        delta = rows[0][col] - rows[1][col]
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
    - **bool**:
      `True` if the regular expression matches the string, `False` otherwise.

    ### Notes
    - Must be registered on the SQLite connection using `create_function('REGEXP', 2, regexp)`.
    - SQLite passes the pattern as the first and the value as the second argument: `X REGEXP Y`
      is evaluated as `regexp(Y, X)`.
    - Regular expressions use Python's `re` module syntax.
    - Values that are not TEXT (INTEGER, REAL, BLOB) are converted to text first, the same way
      SQLite's own `regexp()` implementation applies `sqlite3_value_text()` to its argument.
      Without that conversion, matching against a numeric column raises inside the function and
      the whole query fails.
    - `NULL` never matches.
    - Commonly used in queries like:
      `SELECT * FROM table WHERE column REGEXP 'pattern'`.

    ### Example
    >>> regexp('^abc', 'abcdef')
    True

    >>> regexp('xyz$', 'abcdef')
    False

    >>> regexp('^9', 9000)
    True
    """
    if item is None:
        return False
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
    - `REPLACE` first deletes the existing conflicting row, then attempts to insert the new one.
    - If any constraint violation (e.g., `NOT NULL`) occurs during the second step, the operation
      aborts and rolls back.
    - Field names and values are safely parameterized to prevent SQL injection.
    - Table names are sanitized to allow only safe characters.

    ### Example
    >>> replace(
    ...     conn,
    ...     {'hostname': 'server1', 'service': 'http', 'status': 0},
    ...     table='status',
    ... )
    (True, True)
    """
    table = __filter_str(table)

    # See insert(): identifiers are quoted, values are bound positionally.
    keys = ','.join(__quote_ident(key) for key in data)
    binds = ','.join('?' for _ in data)
    sql = f'REPLACE INTO {__quote_ident(table)} ({keys}) VALUES ({binds});'

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
    - Only the `main` database file is deleted (ignores attached databases).
    - The connection is closed in every case, including for in-memory databases, which have no
      file to delete.
    - Any errors from file deletion are handled externally (through `disk.rm_file()`).

    ### Example
    >>> rm_db(conn)
    True
    """
    # `PRAGMA database_list` yields (seq, name, file); `file` is empty for an in-memory database.
    filename = ''
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
