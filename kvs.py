#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020032602'

import lib.base
import lib.db

# Simple Key-Value Store (KVS), like Redis 
# No error handling here. If KVS does not work for any reason, we (currently) don't care and don't report it.


# Set key to hold the string value. If key already holds a value, it is overwritten, including the expire timestamp in seconds.
# expire: Set the specified expire unix timestamp, in seconds. If 0, key never expires.
def set(key, value, expire=0):
    success, conn = lib.db.connect(filename='linuxfabrik-plugin-kvs.db')
    if not success:
        return False

    definition = '''
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            timestamp   INT NOT NULL
        '''
    success, result = lib.db.create_table(conn, definition, table='kvs')
    if not success:
        lib.db.close(conn)
        return False

    success, result = lib.db.create_index(conn, column_list='key', table='kvs', unique=True)
    if not success:
        lib.db.close(conn)
        return False

    data = {
        'key': key,
        'value': value,
        'timestamp': expire,
    }
    success, result = lib.db.replace(conn, data, table='kvs')
    if not success:
        lib.db.close(conn)
        return False
    
    success, result = lib.db.commit(conn)
    lib.db.close(conn)
    if not success:
        return False

    return True


# Get the value of key. If the key does not exist, False is returned.
def get(key):
    success, conn = lib.db.connect(filename='linuxfabrik-plugin-kvs.db')
    if not success:
        return False

    success, result = lib.db.select(conn, 
        'SELECT key, value, timestamp FROM kvs WHERE key = :key',
        {'key': key}
    )
    lib.db.close(conn)
    if not success:
        return False

    if not result or result == None or (result[2] != 0 and int(result[2]) - lib.base.now() < 0):
        return False
    else:
        # return the value
        return result[1]

    return False