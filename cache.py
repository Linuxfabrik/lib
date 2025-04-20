#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Simple Cache in the form of a Key-Value Store (KVS) like Redis, based on
SQLite, optionally supporting expiration of keys. No detailed error handling
here. If the cache does not work, we (currently) don't report the reason and
simply return `False`.

>>> cache.get('session-key')
False
>>> cache.set('session-key', '123abc', expire=time.now() + 5)
True
>>> cache.get('session-key')
u'123abc'
>>> time.sleep(6)
>>> cache.get('session-key')
False
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'

from . import time
from . import db_sqlite


def get(key, as_dict=False, path='', filename='linuxfabrik-monitoring-plugins-cache.db'):
    """
    Retrieve a value from the cache database by key.

    This function connects to a local SQLite cache database, retrieves a record based on
    the provided key, and returns either the value or the full record, depending on options.
    Expired records are automatically cleaned up.

    ### Parameters
    - **key** (`str`): The search key to look up in the cache.
    - **as_dict** (`bool`, optional): If `True`, return the full database record as a dictionary  
      (`key`, `value`, and `timestamp`).  
      If `False`, return only the `value`. Defaults to `False`.
    - **path** (`str`, optional): Path to the directory containing the cache database.
      Defaults to an empty string (current directory).
    - **filename** (`str`, optional): Name of the cache database file.
      Defaults to `'linuxfabrik-monitoring-plugins-cache.db'`.

    ### Returns
    - **str**, **dict**, or **bool**: 
      - If `as_dict=False` (default): returns the cached `value` (`str`).
      - If `as_dict=True`: returns the full record (`dict`).
      - Returns `False` if the key is not found, expired, or on failure.

    ### Notes
    - If the key exists but has expired (based on its `timestamp`), it is deleted and `False` 
      is returned.
    - All expired keys are cleaned up on lookup when an expired key is found.
    - On database connection or query failure, `False` is returned.

    ### Example
    >>> get('hostname')
    'server01.example.com'

    >>> get('session_data', as_dict=True)
    {'key': 'session_data', 'value': 'xyz', 'timestamp': 9999999999}

    >>> get('non_existing_key')
    False
    """
    success, conn = db_sqlite.connect(path=path, filename=filename)
    if not success:
        return False

    try:
        success, result = db_sqlite.select(
            conn,
            sql='SELECT key, value, timestamp FROM cache WHERE key = :key;',
            data={'key': key},
            fetchone=True
        )
        if not success or not result:
            return False

        # Check if the key has expired
        now = time.now()
        if result['timestamp'] != 0 and result['timestamp'] <= now:
            # Clean up all expired entries
            db_sqlite.delete(
                conn,
                sql='DELETE FROM cache WHERE timestamp <= :now;',
                data={'now': now}
            )
            db_sqlite.commit(conn)
            return False

        return result if as_dict else result['value']

    finally:
        db_sqlite.close(conn)


def set(key, value, expire=0, path='', filename='linuxfabrik-monitoring-plugins-cache.db'):  # pylint: disable=W0622
    """
    Set a key-value pair in the cache database, optionally with an expiration timestamp.

    This function connects to a local SQLite cache database, ensures the required table and index
    exist, and inserts or replaces the given key with its associated value. Expiration can be
    controlled by setting a Unix timestamp.

    ### Parameters
    - **key** (`str`): The cache key to set. Keys must be unique.
    - **value** (`str`): The value to associate with the key. Always stored as a string.
    - **expire** (`int`, optional): The expiration Unix timestamp in seconds.
      If `0` (default), the key never expires.
    - **path** (`str`, optional): Path to the directory containing the cache database.
      Defaults to an empty string (current directory).
    - **filename** (`str`, optional): Name of the cache database file.
      Defaults to `'linuxfabrik-monitoring-plugins-cache.db'`.

    ### Returns
    - **bool**:
      - `True` if the operation succeeded.
      - `False` if the database connection, table creation, index creation, insert, or commit
        failed.

    ### Notes
    - If the key already exists, its value and expiration are overwritten.
    - The `cache` table and a unique index on `key` are automatically created if missing.
    - Expiration must be enforced manually during retrieval (`get()`), not automatically here.

    ### Example
    >>> set('hostname', 'server01.example.com')
    True

    >>> set('session_data', 'xyz', expire=1710000000)
    True
    """
    success, conn = db_sqlite.connect(path=path, filename=filename)
    if not success:
        return False

    try:
        # Ensure the cache table and unique index exist
        table_definition = '''
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            timestamp   INT NOT NULL
        '''
        success, _ = db_sqlite.create_table(conn, table_definition, table='cache')
        if not success:
            return False

        success, _ = db_sqlite.create_index(conn, column_list='key', table='cache', unique=True)
        if not success:
            return False

        # Insert or replace the value
        data = {
            'key': key,
            'value': value,
            'timestamp': expire,
        }
        success, _ = db_sqlite.replace(conn, data, table='cache')
        if not success:
            return False

        # Commit the transaction
        success, _ = db_sqlite.commit(conn)
        return success

    finally:
        db_sqlite.close(conn)
