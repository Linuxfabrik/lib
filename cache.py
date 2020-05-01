#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Simple Cache in the form of a Key-Value Store (KVS) like Redis, based on
SQLite, optionally supporting expiration of keys. No detailed error handling
here. If the cache does not work, we (currently) don't report the reason and
simply return `False`.

>>> cache.get('session-key')
False
>>> cache.set('session-key', '123abc', expire=int(time.time()) + 5)
True
>>> cache.get('session-key')
u'123abc'
>>> time.sleep(6)
>>> cache.get('session-key')
False
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020043001'

import base
import db_sqlite


def get(key):
    """Get the value of key. If the key does not exist, `False` is returned.

    Parameters
    ----------
    key : str
        The search key.

    Returns
    -------
    str or bool
        The value that belongs to the key, `False` if not found or on
        failure.
    """

    success, conn = db_sqlite.connect(filename='linuxfabrik-plugin-cache.db')
    if not success:
        return False

    success, result = db_sqlite.select(
        conn,
        sql='SELECT key, value, timestamp FROM cache WHERE key = :key',
        data={'key': key}, fetchone=True
    )
    db_sqlite.close(conn)
    if not success:
        return False

    if not result or \
        result is None or \
        (result['timestamp'] != 0 and result['timestamp'] - base.now() < 0):
        # nothing found, or result has expired
        return False

    # return the value
    return result['value']


def set(key, value, expire=0):
    """Set key to hold the string value.

    Keys have to be unique. If the key already holds a value, it is
    overwritten, including the expire timestamp in seconds.

    Parameters
    ----------
    key : str
        The key.
    value : str
        The value. Always stored as string.
    expire : int
        Set the expire unix timestamp, in seconds. If 0 (default), key never
        expires.

    Returns
    -------
    bool
        `True` on success, `False` on failure.
    """

    success, conn = db_sqlite.connect(filename='linuxfabrik-plugin-cache.db')
    if not success:
        return False

    definition = '''
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            timestamp   INT NOT NULL
        '''
    success, result = db_sqlite.create_table(conn, definition, table='cache')
    if not success:
        db_sqlite.close(conn)
        return False

    success, result = db_sqlite.create_index(conn, column_list='key', table='cache', unique=True)
    if not success:
        db_sqlite.close(conn)
        return False

    data = {
        'key': key,
        'value': value,
        'timestamp': expire,
    }
    success, result = db_sqlite.replace(conn, data, table='cache')
    if not success:
        db_sqlite.close(conn)
        return False

    success, result = db_sqlite.commit(conn)
    db_sqlite.close(conn)
    if not success:
        return False

    return True
