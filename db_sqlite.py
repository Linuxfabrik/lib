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
__version__ = '2023082301'

import csv
import hashlib
import os
import re
import sqlite3

from . import disk
from . import txt


def __filter_str(s, charclass='a-zA-Z0-9_'):
    """Stripping everything except alphanumeric chars and '_' from a string -
    chars that are allowed everywhere in variables, database table or index names, etc.

    >>> __filter_str('user@example.ch')
    'userexamplech'
    """
    regex = '[^{}]'.format(charclass)
    return re.sub(regex, "", s)


def __sha1sum(string):
    """Returns a sha1-encoded string.

    >>> __sha1sum('linuxfabrik')
    '74301e766db4a4006ec1fbd6e031760e7e322223'
    """
    return hashlib.sha1(txt.to_bytes(string)).hexdigest()


def close(conn):
    """This closes the database connection. Note that this does not
    automatically call commit(). If you just close your database connection
    without calling commit() first, your changes will be lost.
    """
    try:
        conn.close()
    except:
        pass
    return True


def commit(conn):
    """Save (commit) any changes.
    """
    try:
        conn.commit()
    except Exception as e:
        return(False, 'Error: {}'.format(e))
    return (True, None)


def connect(path='', filename=''):
    """Connect to a SQLite database file. If path is ommitted, the
    temporary directory is used. If filename is ommitted,
    `linuxfabrik-monitoring-plugins-sqlite.db` is used.
    """
    def get_filename(path='', filename=''):
        """Returns a path including filename to a sqlite database file.

        Parameters
        ----------
        path : str, optional
            Path to the db file. Default: the tmpdir, `/tmp` for example
        filename : str, optional
            Filename of the db file. Default: linuxfabrik-monitoring-plugins-sqlite.db

        Returns
        -------
        str
            The absolute path to the db file, for example
            '/tmp/linuxfabrik-monitoring-plugins-sqlite.db'
        """

        if not path:
            path = disk.get_tmpdir()
        if not filename:
            filename = 'linuxfabrik-monitoring-plugins-sqlite.db'
        return os.path.join(path, filename)

    db = get_filename(path, filename)
    try:
        conn = sqlite3.connect(db, timeout=1)
        # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
        conn.row_factory = sqlite3.Row
        # https://stackoverflow.com/questions/3425320/sqlite3-programmingerror-you-must-not-use-8-bit-bytestrings-unless-you-use-a-te
        conn.text_factory = str
        conn.create_function("REGEXP", 2, regexp)
    except Exception as e:
        return(False, 'Connecting to DB {} failed, Error: {}'.format(db, e))
    return (True, conn)


def create_index(conn, column_list, table='perfdata', unique=False):
    """Creates one index on a list of/one database column/s.
    """
    table = __filter_str(table)

    index_name = 'idx_{}'.format(__sha1sum(table + column_list))
    c = conn.cursor()
    if unique:
        sql = 'CREATE UNIQUE INDEX IF NOT EXISTS {} ON "{}" ({});'.format(
            index_name, table, column_list
            )
    else:
        sql = 'CREATE INDEX IF NOT EXISTS {} ON "{}" ({});'.format(
            index_name, table, column_list
            )
    try:
        c.execute(sql)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}'.format(sql, e))

    return (True, True)


def create_table(conn, definition, table='perfdata', drop_table_first=False):
    """Create a database table.

    >>> create_table('test', 'a,b,c INTEGER NOT NULL')
    results in 'CREATE TABLE "test" (a TEXT, b TEXT, c INTEGER NOT NULL)'
    """
    table = __filter_str(table)

    # create table if it does not exist
    if drop_table_first:
        success, result = drop_table(conn, table)
        if not success:
            return (success, result)

    c = conn.cursor()
    sql = 'CREATE TABLE IF NOT EXISTS "{}" ({});'.format(table, definition)
    try:
        c.execute(sql)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}'.format(sql, e))

    return (True, True)


def cut(conn, table='perfdata', _max=5):
    """Keep only the latest "_max" records, using the sqlite built-in "rowid".
    """
    table = __filter_str(table)

    c = conn.cursor()
    sql = '''DELETE FROM {table} WHERE rowid IN (
                SELECT rowid FROM {table} ORDER BY rowid DESC LIMIT -1 OFFSET :_max
            );'''.format(table=table)
    try:
        c.execute(sql, (_max, ))
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}'.format(sql, e))

    return (True, True)


def delete(conn, sql, data={}):
    """The DELETE command removes records from a table. If the WHERE
    clause is not present, all records in the table are deleted. If a
    WHERE clause is supplied, then only those rows for which the WHERE
    clause boolean expression is true are deleted. Rows for which the
    expression is false or NULL are retained.
    """
    c = conn.cursor()

    try:
        if data:
            return (True, c.execute(sql, data).rowcount)
        return (True, c.execute(sql).rowcount)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}, Data: {}'.format(sql, e, data))


def drop_table(conn, table='perfdata'):
    """The DROP TABLE statement removes a table added with the CREATE TABLE
    statement. The name specified is the table name. The dropped table is
    completely removed from the database schema and the disk file. The
    table can not be recovered. All indices and triggers associated with the
    table are also deleted.
    """
    table = __filter_str(table)

    c = conn.cursor()
    sql = 'DROP TABLE IF EXISTS "{}";'.format(table)

    try:
        c.execute(sql)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}'.format(sql, e))

    return (True, True)


def get_colnames(col_definition):
    """Get list of coumn names from a column definition statement.

    >>> get_colnames('date TEXT PRIMARY KEY, count FLOAT, name TEXT)
    ['date', 'count', 'name']
    """
    return [''.join(col.split()[:1]) for col in col_definition.split(',')]


def import_csv(conn, filename, table='data', fieldnames=None, skip_header=False, delimiter=',', quotechar='"', newline='', chunksize=1000):
    """Import a given CSV file (given by `filename) into a table. `fieldnames` dnoes not have
    to match the first header row (if any).

    >>> import_csv(conn, 'examples/EXAMPLE01.csv', table='data',
                   fieldnames='date TEXT PRIMARY KEY, count FLOAT, name TEXT',


    This function doesn't use the sqlite command line tool for various reasons:
    * One more dependency to install on a server.
    * Some capabilities depend on its version (skipping header row, for example, which is not available in rhel8-).
    * Not as flexible as we are when it comes to using quotes, guessing column types or handling escaping errors.
    """
    if table is None:
        table = __filter_str(filename)

    # can't use our `disk.read_csv()`, because we want to be able to import large files in chunks
    # and maybe want to be open to do some magic on the way
    skipped = False
    # create the "data" table
    # TODO: if fieldnames=None, then create some on our own: "col1", "col2", ...
    success, result = create_table(conn, fieldnames, table=table, drop_table_first=True)
    if not success:
        return (success, result)
    # get pure column names from CREATE statement (`fieldnames`):
    # 'date TEXT PRIMARY KEY, count FLOAT, name TEXT' => ['date', 'count', 'name']
    new_fieldnames = get_colnames(fieldnames)
    try:
        with open(filename, newline=newline) as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
            i = 0
            for csv_row in reader:
                # skip header if wanted
                if skip_header and not skipped:
                    skipped = True
                    continue
                # check if row is empty
                if all(s == '' or s.isspace() for s in csv_row):
                    continue
                # use dictionary keys from CREATE statement, not that from CSV
                data = dict(zip(new_fieldnames, csv_row))
                # INSERT INTO database table
                insert(conn, data, table)
                # COMMIT and clear memory in chunks
                i += 1
                if i > 0 and i % chunksize == 0:
                    commit(conn)
            commit(conn)
    except csv.Error as e:
        return (False, 'CSV error in file {}, line {}: {}'.format(filename, reader.line_num, e))
    except IOError as e:
        return (False, 'I/O error "{}" while opening or reading {}'.format(e.strerror, filename))
    except Exception as e:
        return (False, 'Unknown error opening or reading {}:\n{}'.format(filename, e))
    return (True, True)


def insert(conn, data, table='perfdata'):
    """Insert a row of values (has to be a dict).
    """
    table = __filter_str(table)

    c = conn.cursor()
    sql = 'INSERT INTO "{}" (COLS) VALUES (VALS);'.format(table)

    keys, binds = '', ''
    for key in data.keys():
        keys += '{},'.format(key)
        binds += ':{},'.format(key)
    keys = keys[:-1]
    binds = binds[:-1]
    sql = sql.replace('COLS', keys).replace('VALS', binds)

    try:
        c.execute(sql, data)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}, Data: {}'.format(sql, e, data))

    return (True, True)


def regexp(expr, item):
    """The SQLite engine does not support a REGEXP implementation by default. This has to be
    done by the client.
    For Python, you have to implement REGEXP using a Python function at runtime.
    https://stackoverflow.com/questions/5365451/problem-with-regexp-python-and-sqlite/5365533#5365533
    """
    reg = re.compile(expr)
    return reg.search(item) is not None


def replace(conn, data, table='perfdata'):
    """The REPLACE command is an alias for the "INSERT OR REPLACE" variant
    of the INSERT command. When a UNIQUE or PRIMARY KEY constraint violation
    occurs, it does the following:

    * First, delete the existing row that causes a constraint violation.
    * Second, insert a new row.

    In the second step, if any constraint violation e.g., NOT NULL
    constraint occurs, the REPLACE statement will abort the action and roll
    back the transaction.
    """
    table = __filter_str(table)

    c = conn.cursor()
    sql = 'REPLACE INTO "{}" (COLS) VALUES (VALS);'.format(table)

    keys, binds = '', ''
    for key in data.keys():
        keys += '{},'.format(key)
        binds += ':{},'.format(key)
    keys = keys[:-1]
    binds = binds[:-1]
    sql = sql.replace('COLS', keys).replace('VALS', binds)

    try:
        c.execute(sql, data)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}, Data: {}'.format(sql, e, data))

    return (True, True)


def select(conn, sql, data={}, fetchone=False, as_dict=True):
    """The SELECT statement is used to query the database. The result of a
    SELECT is zero or more rows of data where each row has a fixed number
    of columns. A SELECT statement does not make any changes to the
    database.
    """
    c = conn.cursor()

    try:
        if data:
            c.execute(sql, data)
        else:
            c.execute(sql)
        # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
        if as_dict:
            if fetchone:
                try:
                    return (True, [dict(row) for row in c.fetchall()][0])
                except IndexError:
                    return (True, [])
            return (True, [dict(row) for row in c.fetchall()])
        if fetchone:
            return (True,  c.fetchone())
        return (True, c.fetchall())
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}, Data: {}'.format(sql, e, data))


def get_tables(conn):
    """List all tables in a database.
    """
    sql = "SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';"
    return select(conn, sql)


def compute_load(conn, sensorcol, datacols, count, table='perfdata'):
    """Calculates Load1 and Loadn (n = count). Load is caclulated as a
    "per second" number.

    The Perfdata table must have a "timestamp" column.

    >>> compute_load(conn, sensorcol='interface', datacols=['tx_bytes',
                     'rx_bytes'], count=5, table='perfdata')

    Returns
    -------
    list
        [{'interface': u'mgmt1', 'tx_bytes1': 6906, 'rx_bytes1': 10418,
          'rx_bytesn': 10871, 'tx_bytesn': 7442},
         {...},
        ]
    """
    table = __filter_str(table)

    # count the number of different sensors in the perfdata table
    sql = 'SELECT DISTINCT {sensorcol} FROM {table} ORDER BY {sensorcol} ASC;'.format(
        sensorcol=sensorcol, table=table
        )
    success, sensors = select(conn, sql)
    if not success:
        return (False, sensors)
    if len(sensors) == 0:
        return (True, False)

    load = []

    # calculate
    for sensor in sensors:
        # get all historical data, ordered by sensor, and within that newest data first
        sensor_name = sensor[sensorcol]
        success, perfdata = select(
            conn,
            'SELECT * FROM {table} WHERE {sensorcol} = :{sensorcol} '
            'ORDER BY timestamp DESC;'.format(
                table=table, sensorcol=sensorcol
            ),
            data={sensorcol: sensor_name})
        if not success:
            return (False, perfdata)

        # not enough data to compute load
        if len(perfdata) < count:
            return (True, False)

        # Perfdata:
        # [{'interface': u'mgmt1', 'tx_bytes': 102893695, 'timestamp': 1588162358}, ...

        # perfdata[0]:       newest/current entry
        # perfdata[1]:       one entry before, load1 = ([0] - [1])/seconds
        # perfdata[count-1]: oldest entry, loadn = ([0] - [n])/seconds

        load1_delta = perfdata[0]['timestamp'] - perfdata[1]['timestamp']
        loadn_delta = perfdata[0]['timestamp'] - perfdata[count-1]['timestamp']
        tmp = {}
        tmp[sensorcol] = sensor_name
        for key in datacols:
            if key in perfdata[0]:
                if load1_delta != 0:
                    tmp[key + '1'] = (perfdata[0][key] - perfdata[1][key]) / load1_delta
                else:
                    tmp[key + '1'] = 0
                if loadn_delta != 0:
                    tmp[key + 'n'] = (perfdata[0][key] - perfdata[count-1][key]) / loadn_delta
                else:
                    tmp[key + 'n'] = 0
        load.append(tmp)

    return (True, load)
