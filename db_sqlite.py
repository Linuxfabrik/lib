#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This is one typical use case of this library (from `disk-io`):

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

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020042901'

import disk

import os
import sqlite3


def close(conn):
    # We can close the connection if we are done with it.
    # Just be sure any changes have been committed or they will be lost.
    try:
        conn.close()
    except:
        pass
    return True


def commit(conn):
    # Save (commit) any changes
    try:
        conn.commit()
    except Exception as e:
        return(False, 'Committing to DB failed, Error: '.format(e))
    return (True, None)


def connect(path='', filename=''):

    def get_filename(path='', filename=''):
        """Returns a path including filename to a sqlite database file.

        Parameters
        ----------
        path : str, optional
            Path to the db file. Default: the tmpdir, `/tmp` for example
        filename : str, optional
            Filename of the db file. Default: linuxfabrik-plugins.db

        Returns
        -------
        str
            The absolute path to the db file, for example
            '/tmp/linuxfabrik-plugins.db'
        """

        if not path:
            path = disk.get_tmpdir()
        if not filename:
            filename = 'linuxfabrik-plugins.db'
        return os.path.join(path, filename)

    db = get_filename(path, filename)
    try:
        conn = sqlite3.connect(db, timeout=1)
        # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
        conn.row_factory = sqlite3.Row
    except Exception as e:
        return(False, 'Connecting to DB {} failed, Error: '.format(db, e))
    return (True, conn)


def create_index(conn, column_list, table='perfdata', unique=False):
    index_name = 'idx_{}_{}'.format(table, column_list.replace(',', '_').replace(' ', ''))
    c = conn.cursor()
    if unique:
        sql = 'CREATE UNIQUE INDEX IF NOT EXISTS {} ON "{}" ({});'.format(index_name, table, column_list)
    else:
        sql = 'CREATE INDEX IF NOT EXISTS {} ON "{}" ({});'.format(index_name, table, column_list)

    try:
        c.execute(sql)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}'.format(sql, e))

    return (True, True)


# create_table('test', 'a,b,c') results in
# CREATE TABLE "test" (a TEXT, b TEXT, c TEXT)
def create_table(conn, definition, table='perfdata', drop_table_first=False):
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


def cut(conn, table='perfdata', max=5):
    # keep only the latest "max" records, using the sqlite built-in "rowid"
    c = conn.cursor()
    sql = '''DELETE FROM {} WHERE rowid IN (
                SELECT rowid FROM {} ORDER BY rowid DESC LIMIT -1 OFFSET :max
            )'''.format(table, table)
    try:
        c.execute(sql, (max, ))
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}'.format(sql, e))

    return (True, True)


def drop_table(conn, table='perfdata'):
    c = conn.cursor()
    sql = 'DROP TABLE IF EXISTS "{}";'.format(table)

    try:
        c.execute(sql)
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}'.format(sql, e))

    return (True, True)


def insert(conn, data, table='perfdata'):
    # insert a row of data (values from a dictionary)
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


def replace(conn, data, table='perfdata'):
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


def select(conn, sql, data={}, fetchone=False):
    c = conn.cursor()

    try:
        if data:
            c.execute(sql, data)
        else:
            c.execute(sql)
        # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
        if fetchone:
            return (True, [dict(row) for row in c.fetchall()][0])
        else:
            return (True, [dict(row) for row in c.fetchall()])
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}, Data: {}'.format(sql, e, data))


def compute_load(conn, sensorcol, datacols, count, table='perfdata'):
    """Calculates Load1 and Loadn (n = count). Load is caclulated as a "per second" number.

    The Perfdata table must have a "timestamp" column.

    >>> compute_load(conn, sensorcol='interface', datacols=['tx_bytes', 'rx_bytes'], count=5, table='perfdata')

    Returns
    -------
    list
        [{'interface': u'mgmt1', 'tx_bytes1': 6906, 'rx_bytes1': 10418, 'rx_bytesn': 10871, 'tx_bytesn': 7442},
         {...},
        ]
    """

    # count the number of different sensors in the perfdata table
    sql = 'SELECT DISTINCT {} FROM {} ORDER BY {} ASC'.format(sensorcol, table, sensorcol)
    success, sensors = select(conn, sql)
    if not success:
        return (False, sensors)
    if len(sensors) == 0:
        return (True, False)
    sensor_count = len(sensors)

    load = []

    # calculate
    for sensor in sensors:
        # get all historical data, ordered by sensor, and within that newest data first
        sensor_name = sensor[sensorcol]
        success, perfdata = select(conn,
            'SELECT * FROM {} WHERE {} = :{} ORDER BY {} ASC, timestamp DESC'.format(table, sensorcol, sensorcol, sensorcol),
            data={sensorcol: sensor_name})
        if not success:
            return (False, perfdata)

        # not enough data to compute load
        if len(perfdata) < count:
            return (True, False)

        # Perfdata:
        # [{'interface': u'mgmt1', 'tx_bytes': 102893695, 'rx_bytes': 161048380, 'timestamp': 1588162358}, {'interface': u'mgmt1', 'tx_bytes': 102584221, 'rx_bytes': 160618067, 'timestamp': 1588162316}, {'interface': u'mgmt1', 'tx_bytes': 102468643, 'rx_bytes': 160488612, 'timestamp': 1588162308}, {'interface': u'mgmt1', 'tx_bytes': 102083130, 'rx_bytes': 159909476, 'timestamp': 1588162252}, {'interface': u'mgmt1', 'tx_bytes': 102028610, 'rx_bytes': 159864155, 'timestamp': 1588162250}]

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
