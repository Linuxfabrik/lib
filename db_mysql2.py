#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Library for accessing MySQL/MariaDB servers.

For details have a look at
https://dev.mysql.com/doc/connector-python/en/
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020050101'

try:
    import mysql.connector
except ImportError as e:
    print('Python module "mysql.connector" is not installed.')
    exit(3)

import base2
import disk2

if base2.version(mysql.connector.__version__) < base2.version('2.0.0'):
    try:
        import MySQLdb.cursors
    except ImportError as e:
        print('Python module "MySQLdb.cursors" is not installed.')
        exit(3)


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


def connect(mysql_connection):
    """Connect to a MySQL/MariaDB. `mysql_connection` has to be a dict.

    >>> mysql_connection = {
    ...     'user':               args2.USERNAME,
    ...     'password':           args2.PASSWORD,
    ...     'host':               args2.HOSTNAME,
    ...     'database':           args2.DATABASE,
    ...     'raise_on_warnings':  True
    ... }
    >>> conn = connect(mysql_connection)
    """

    try:
        conn = mysql.connector.connect(**mysql_connection)
    except Exception as e:
        return(False, 'Connecting to DB failed, Error: {}'.format(e))
    return (True, conn)


def select(conn, sql, data={}, fetchone=False):
    """The SELECT statement is used to query the database. The result of a
    SELECT is zero or more rows of data where each row has a fixed number
    of columns. A SELECT statement does not make any changes to the
    database.
    """

    if base2.version(mysql.connector.__version__) >= base2.version('2.0.0'):
        cursor = conn.cursor(dictionary=True)
    else:
        cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    try:
        if data:
            cursor.execute(sql, data)
        else:
            cursor.execute(sql)
        if fetchone:
            return (True, [cursor.fetchone()])
        return (True, cursor.fetchall())
    except Exception as e:
        return(False, 'Query failed: {}, Error: {}, Data: {}'.format(sql, e, data))
