#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

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
__version__ = '2026080901'

from . import db_sqlite, time


def get(
    key,
    as_dict=False,
    allow_stale=False,
    path='',
    filename='linuxfabrik-monitoring-plugins-cache.db',
):
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
    - **allow_stale** (`bool`, optional): If `True`, an expired record is returned instead of
      being deleted, and no cleanup is performed. Defaults to `False`.
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
    - `allow_stale` exists for the case where the authoritative source is unreachable and an
      outdated answer beats no answer at all. The expired entry then survives the lookup, so a
      source that stays down for days does not leave the caller with an empty cache. Ask for it
      only after the refresh has actually failed, and read the record with `as_dict=True`: its
      `timestamp` is the moment the entry expired, which is what tells the caller how old the
      value is and lets it say so.
    - On database connection or query failure, `False` is returned.

    ### Example
    >>> get('hostname')
    'server01.example.com'

    >>> get('session_data', as_dict=True)
    {'key': 'session_data', 'value': 'xyz', 'timestamp': 9999999999}

    >>> get('non_existing_key')
    False

    >>> get('checksums', as_dict=True, allow_stale=True)  # endpoint is down
    {'key': 'checksums', 'value': '...', 'timestamp': 1710000000}
    """
    success, conn = db_sqlite.connect(path=path, filename=filename)
    if not success:
        return False

    try:
        success, result = db_sqlite.select(
            conn,
            sql='SELECT key, value, timestamp FROM cache WHERE key = :key;',
            data={'key': key},
            fetchone=True,
        )
        if not success or not result:
            return False

        # Check if the key has expired. `timestamp` is the "expires at" Unix
        # epoch set via `set(expire=...)`. We treat the entry as valid up to
        # and including that timestamp (strict-less-than), so a key with
        # expire=now+5 is still served at now+5 and first becomes expired at
        # now+6. This matches HTTP Cache-Control max-age and Redis EXPIRE.
        now = time.now()
        if not allow_stale and result['timestamp'] != 0 and result['timestamp'] < now:
            # Clean up all expired entries
            db_sqlite.delete(
                conn,
                sql='DELETE FROM cache WHERE timestamp < :now;',
                data={'now': now},
            )
            db_sqlite.commit(conn)
            return False

        return result if as_dict else result['value']

    finally:
        db_sqlite.close(conn)


def prune(before=None, path='', filename='linuxfabrik-monitoring-plugins-cache.db'):
    """
    Delete expired entries from the cache database.

    `get()` already removes expired entries as it comes across them, which is enough for a
    cache whose keys stay the same over time. Where the key carries a version, a release or
    another identifier that moves on, the entry left behind by the previous one is never
    looked up again and never cleaned up either. Pruning is how that cache stays bounded.

    ### Parameters
    - **before** (`int`, optional): Delete entries that expired before this Unix timestamp.
      Defaults to now, which deletes everything currently expired. Pass an earlier timestamp
      to keep recently expired entries, which is what a caller that serves stale values
      during an outage (`get(allow_stale=True)`) needs in order to still have something to
      serve.
    - **path** (`str`, optional): Path to the directory containing the cache database.
      Defaults to an empty string (current directory).
    - **filename** (`str`, optional): Name of the cache database file.
      Defaults to `'linuxfabrik-monitoring-plugins-cache.db'`.

    ### Returns
    - **bool**: `True` if the delete succeeded, `False` on any database failure.

    ### Notes
    - Entries stored without an expiry (`set(expire=0)`) are never pruned.
    - Prune after a successful refresh, not before one. Dropping the old copy while the
      source is unreachable is how a cache ends up empty exactly when it is needed.

    ### Example
    >>> prune()
    True

    >>> prune(before=time.now() - 30 * 86400)  # keep a month of expired entries
    True
    """
    if before is None:
        before = time.now()

    success, conn = db_sqlite.connect(path=path, filename=filename)
    if not success:
        return False

    try:
        success, _ = db_sqlite.delete(
            conn,
            sql='DELETE FROM cache WHERE timestamp != 0 AND timestamp < :before;',
            data={'before': before},
        )
        if not success:
            return False
        success, _ = db_sqlite.commit(conn)
        return success

    finally:
        db_sqlite.close(conn)


def set(
    key, value, expire=0, path='', filename='linuxfabrik-monitoring-plugins-cache.db'
):  # pylint: disable=W0622
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
        table_definition = """
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            timestamp   INT NOT NULL
        """
        success, _ = db_sqlite.create_table(conn, table_definition, table='cache')
        if not success:
            return False

        success, _ = db_sqlite.create_index(
            conn, column_list='key', table='cache', unique=True
        )
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
