#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Library for accessing SQLite databases.

This is one typical use case of this library (taken from `disk-io`):

>>> conn = lib.base.coe(lib.db_sqlite.connect(filename='disk-io.db'))
>>> lib.base.coe(lib.db_sqlite.create_table(conn, definition, drop_table_first=False))
>>> lib.base.coe(lib.db_sqlite.create_index(conn, 'name'))   # optional

>>> lib.base.coe(lib.db_sqlite.insert(conn, data))
>>> lib.base.coe(lib.db_sqlite.cut(conn, max=args.COUNT*len(disks)))
>>> lib.base.coe(lib.db_sqlite.commit(conn))

>>> result = lib.base.coe(lib.db_sqlite.select(conn,
        'SELECT * FROM perfdata WHERE name = :name ORDER BY timestamp DESC LIMIT 2',
        {'name': disk}

>>> lib.db_sqlite.close(conn)
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042102'

import csv
import hashlib
import os
import re
import sqlite3

from . import disk
from . import txt


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
    return hashlib.sha1(txt.to_bytes(string)).hexdigest()


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
    >>> compute_load(conn, sensorcol='interface', datacols=['tx_bytes', 'rx_bytes'], count=5, table='perfdata')

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

    sql = f'SELECT DISTINCT {sensorcol} FROM {table} ORDER BY {sensorcol} ASC;'
    success, sensors = select(conn, sql)
    if not success:
        return False, sensors
    if len(sensors) == 0:
        return True, False

    load = []

    for sensor in sensors:
        sensor_name = sensor[sensorcol]
        success, perfdata = select(
            conn,
            f'SELECT * FROM {table} WHERE {sensorcol} = :{sensorcol} ORDER BY timestamp DESC;',
            data={sensorcol: sensor_name}
        )
        if not success:
            return False, perfdata
        if len(perfdata) < count:
            return True, False

        load1_delta = perfdata[0]['timestamp'] - perfdata[1]['timestamp']
        loadn_delta = perfdata[0]['timestamp'] - perfdata[count-1]['timestamp']

        tmp = {sensorcol: sensor_name}
        for key in datacols:
            if key in perfdata[0]:
                tmp[f'{key}1'] = (perfdata[0][key] - perfdata[1][key]) / load1_delta if load1_delta else 0
                tmp[f'{key}n'] = (perfdata[0][key] - perfdata[count-1][key]) / loadn_delta if loadn_delta else 0
        load.append(tmp)

    return True, load


def connect(path='', filename=''):
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

    ### Returns
    - **tuple** (`bool`, `Connection or str`):
      - First element (`bool`): `True` if connection succeeded, `False` if it failed.
      - Second element (`Connection` or `str`):
        - Database connection object on success.
        - Error message string on failure.

    ### Notes
    - The connection uses a `Row` factory, allowing rows to behave like dictionaries.
    - The connection registers a `REGEXP` SQL function for regular expression support.
    - Always check the returned success flag before using the connection.

    ### Example
    >>> success, conn = connect()
    >>> if success:
    >>>     # Use conn
    >>>     pass
    >>> else:
    >>>     print(conn)
    """
    def get_filename(path='', filename=''):
        """Helper to build the absolute path to the SQLite database file."""
        if not path:
            path = disk.get_tmpdir()
        if not filename:
            filename = 'linuxfabrik-monitoring-plugins-sqlite.db'
        return os.path.join(path, filename)

    db = get_filename(path, filename)

    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.text_factory = str
        conn.create_function('REGEXP', 2, regexp)
        return True, conn
    except Exception as e:
        return False, f'Connecting to DB {db} failed, Error: {e}'


def create_index(conn, column_list, table='perfdata', unique=False, delete_db_on_operational_error=True):
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
      If `True`, deletes the database file when an `OperationalError` occurs.
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
    index_name = f"idx_{__sha1sum(table + column_list)}"
    if unique:
        sql = f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON "{table}" ({column_list});'
    else:
        sql = f'CREATE INDEX IF NOT EXISTS {index_name} ON "{table}" ({column_list});'

    c = conn.cursor()
    try:
        c.execute(sql)
        return True, True
    except sqlite3.OperationalError as e:
        if delete_db_on_operational_error:
            rm_db(conn)
        return False, f'Operational Error: {e}, Query: {sql}'
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

    sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({definition});'

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
      If `True`, deletes the database file when an `OperationalError` occurs.
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
    table = __filter_str(table)

    sql = f'''
        DELETE FROM {table}
        WHERE rowid IN (
            SELECT rowid FROM {table}
            ORDER BY rowid DESC
            LIMIT -1 OFFSET :_max
        );
    '''

    c = conn.cursor()
    try:
        c.execute(sql, {'_max': _max})
        return True, True
    except sqlite3.OperationalError as e:
        if delete_db_on_operational_error:
            rm_db(conn)
        return False, f'Operational Error: {e}, Query: {sql}'
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
      If `True`, deletes the database file when an `OperationalError` occurs.
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
        if data:
            rowcount = c.execute(sql, data).rowcount
        else:
            rowcount = c.execute(sql).rowcount
        return True, rowcount
    except sqlite3.OperationalError as e:
        if delete_db_on_operational_error:
            rm_db(conn)
        return False, f'Operational Error: {e}, Query: {sql}, Data: {data}'
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
    sql = f'DROP TABLE IF EXISTS "{table}";'

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
    - Data types, constraints (e.g., `PRIMARY KEY`, `NOT NULL`) are ignored.
    - Whitespace and commas are used as separators.

    ### Example
    >>> get_colnames('date TEXT PRIMARY KEY, count FLOAT, name TEXT')
    ['date', 'count', 'name']
    """
    return [col.strip().split()[0] for col in col_definition.split(',') if col.strip()]


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
    success, result = select(conn, sql)

    if not success:
        return success, result

    # Extract just the table names
    table_names = [row['name'] for row in result]
    return True, table_names


def import_csv(conn, filename, table='data', fieldnames=None, skip_header=False, delimiter=',', quotechar='"', newline='', chunksize=1000):
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
        with open(filename, newline=newline) as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
            i = 0
            for csv_row in reader:
                if skip_header and not skipped:
                    skipped = True
                    continue
                if all(s.strip() == '' for s in csv_row):
                    continue
                data = dict(zip(new_fieldnames, csv_row))
                insert(conn, data, table)
                i += 1
                if i > 0 and i % chunksize == 0:
                    commit(conn)
            commit(conn)
        return True, True

    except csv.Error as e:
        return False, f'CSV error in file {filename}, line {reader.line_num}: {e}'
    except IOError as e:
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
      If `True`, deletes the database file when an `OperationalError` occurs.
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
    >>> insert(conn, {'hostname': 'server1', 'service': 'http', 'status': 0}, table='status')
    (True, True)
    """
    table = __filter_str(table)

    keys = ','.join(data.keys())
    binds = ','.join(f':{key}' for key in data.keys())
    sql = f'INSERT INTO "{table}" ({keys}) VALUES ({binds});'

    c = conn.cursor()
    try:
        c.execute(sql, data)
        return True, True
    except sqlite3.OperationalError as e:
        if delete_db_on_operational_error:
            rm_db(conn)
        return False, f'Operational Error: {e}, Query: {sql}, Data: {data}'
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}, Data: {data}'


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
    - Regular expressions use Python's `re` module syntax.
    - Commonly used in queries like:
      `SELECT * FROM table WHERE column REGEXP 'pattern'`.

    ### Example
    >>> regexp('^abc', 'abcdef')
    True

    >>> regexp('xyz$', 'abcdef')
    False
    """
    if item is None:
        return False
    reg = re.compile(expr)
    return reg.search(item) is not None


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
      If `True`, deletes the database file when an `OperationalError` occurs.
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
    >>> replace(conn, {'hostname': 'server1', 'service': 'http', 'status': 0}, table='status')
    (True, True)
    """
    table = __filter_str(table)

    keys = ','.join(data.keys())
    binds = ','.join(f':{key}' for key in data.keys())
    sql = f'REPLACE INTO "{table}" ({keys}) VALUES ({binds});'

    c = conn.cursor()
    try:
        c.execute(sql, data)
        return True, True
    except sqlite3.OperationalError as e:
        if delete_db_on_operational_error:
            rm_db(conn)
        return False, f'Operational Error: {e}, Query: {sql}, Data: {data}'
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
    - Useful when the database schema has changed and `OperationalError` occurs
      (e.g., after updates).
    - Only the `main` database file is deleted (ignores attached databases).
    - Any errors from file deletion are handled externally (through `disk.rm_file()`).

    ### Example
    >>> rm_db(conn)
    True
    """
    for id_, name, filename in conn.execute('PRAGMA database_list'):
        if name == 'main' and filename:
            close(conn)
            disk.rm_file(filename)
            break
    return True


def select(conn, sql, data=None, fetchone=False, as_dict=True, delete_db_on_operational_error=True):
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
      If `True`, deletes the database file when an `OperationalError` occurs.
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

    except sqlite3.OperationalError as e:
        if delete_db_on_operational_error:
            rm_db(conn)
        return False, f'Operational Error: {e}, Query: {sql}, Data: {data}'
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}, Data: {data}'
