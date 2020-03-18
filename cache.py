#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020031801'

import lib.utils_base
import sqlite3

# No error handling here. If cache does not work for any reason, we (currently) don't care and don't report it.


# Set key to hold the string value. If key already holds a value, it is overwritten, including the expire timestamp in seconds.
# expire: Set the specified expire unix timestamp, in seconds. If 0, key never expires.
def set_cache(key, value, expire=0):
    db = lib.utils_base.get_tmpdir() + '/linuxfabrik-plugin-cache.db'

    conn = sqlite3.connect(db, timeout=1)
    c = conn.cursor()

    # if db does not exist, create it
    try:
        # We typically use INTEGER to store UNIX timestamp which is the number of seconds since 1970-01-01 00:00:00 UTC
        c.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                ts INT NOT NULL
                );
            ''')

        # key column has to be unique
        c.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx1 
            ON cache (key);
            ''')

        c.execute('''
            REPLACE INTO cache (key, value, ts) 
            VALUES (?, ?, ?)
            ''', (key, value, expire));
        conn.commit()
        conn.close()
    except:
        return False

    return True


# Get the value of key. If the key does not exist False is returned.
def get_cache(key):
    try:
        db = lib.utils_base.get_tmpdir() + '/linuxfabrik-plugin-cache.db'

        conn = sqlite3.connect(db, timeout=1)
        c = conn.cursor()
        # The c.execute() method expects a sequence as second parameter, so use "[varname]":
        c.execute('SELECT key, value, ts FROM cache WHERE key = ?', [key])
        result = c.fetchone()
        if result == None or (result[2] != 0 and int(result[2]) - lib.utils_base.now() < 0):
            return False
        else:
            # return the value
            return result[1]
    except:
        return False
    
    return False
