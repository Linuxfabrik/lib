#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Library for accessing MySQL/MariaDB servers.
"""

import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pymysql')

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

import sys

from .globals import STATE_UNKNOWN
try:
    import pymysql.cursors
except ImportError as e:
    print('Python module "pymysql" is not installed.')
    sys.exit(STATE_UNKNOWN)


def check_select_privileges(conn):
    success, result = select(
        conn,
        'select version() as version;',
        fetchone=True,
    )
    if not success or len(result) < 1:
        return (False, 'You probably did not get enough privileges for running SELECT statements.')
    return (True, result)


def close(conn):
    """This closes the database connection.
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


def connect(mysql_connection, **kwargs):
    """Connect to a MySQL/MariaDB. `mysql_connection` has to be a dict.

    >>> mysql_connection = {
        'defaults_file':  args.DEFAULTS_FILE,
        'defaults_group': args.DEFAULTS_GROUP,
        'timeout':        args.TIMEOUT,
    }
    >>> conn = connect(mysql_connection)
    """
    # https://pymysql.readthedocs.io/en/latest/modules/connections.html
    try:
        conn = pymysql.connect(
            read_default_file=mysql_connection.get('defaults_file', None),
            read_default_group=mysql_connection.get('defaults_group', 'client'),
            cursorclass=mysql_connection.get('cursorclass', pymysql.cursors.DictCursor),
            connect_timeout=mysql_connection.get('timeout', 3),
            **kwargs,
        )
    except Exception as e:
        return (False, 'Connecting to DB failed, Error: {}'.format(e))
    return (True, conn)


def get_engines(conn):
    """Returns a dict like `{'have_myisam': 'YES', 'have_innodb': 'YES'}`

     `have_*` status variables for engines are deprecated and are removed since MySQL 5.6,
    so use SHOW ENGINES and set corresponding old style variables.
    Also works around MySQL bug #59393 wrt. skip-innodb
    """
    engines = {}
    sql = 'show engines'
    success, result = select(conn, sql)
    for line in result:
        engine = line['Engine'].lower()
        if line['Engine'] == 'federated' or line['Engine'] == 'blackhole':
            engine += '_engine'
        elif line['Engine'] == 'berkeleydb':
            engine = 'bdb'
        engines['have_{}'.format(engine)] = 'YES' if line['Support'] == 'DEFAULT' else line['Support']

    return engines


def lod2dict(_vars):
    """Converts a list of simple {'key': 'value'} dictionaries to a
    {'key1': 'value1', 'key2': 'value2'} dictionary.

    Special keys like "Variable_name" which you get from a `SHOW VARIABLES;` sql statement
    are translated in a special way like so:
    [{'Variable_name': 'a', 'Value': 'b'}, {'Variable_name': 'c', 'Value': 'd'}]
    results in
    {'a': 'b', 'c': 'd'}
    """
    myvar = {}
    for row in _vars:
        try:
            myvar[row['Variable_name']] = row['Value']
        except:
            for key, value in row.items():
                myvar[key] = value
    return myvar


def select(conn, sql, data={}, fetchone=False):
    """The SELECT statement is used to query the database. The result of a
    SELECT is zero or more rows of data where each row has a fixed number
    of columns. A SELECT statement does not make any changes to the
    database.
    """
    with conn.cursor() as cursor:
        try:
            if data:
                cursor.execute(sql, (data,))
            else:
                cursor.execute(sql)
            if fetchone:
                return (True, cursor.fetchone())
            return (True, cursor.fetchall())
        except Exception as e:
            return (False, 'Query failed: {}, Error: {}, Data: {}'.format(sql, e, data))
