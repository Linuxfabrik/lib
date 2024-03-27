#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some LibreNMS related functions that are
needed by LibreNMS check plugins."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2024032701'

import base64
import json
import random

from .globals import STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN

from . import base # pylint: disable=C0413
from . import cache # pylint: disable=C0413
from . import db_sqlite # pylint: disable=C0413
from . import time # pylint: disable=C0413
from . import txt # pylint: disable=C0413
from . import url # pylint: disable=C0413


# tables to cache data from librenms locally
TABLES = [
    {
        'name': 'alerts',
        'lookup_key': 'alerts',
        'definition': """
            id INT NOT NULL,
            device_id INT NOT NULL
        """,
        'idx': 'id',
        'endpoint': '/api/v0/alerts?state=1',
        'expires_after': 60,
    },
    {
        'name': 'devicegroups',
        'lookup_key': 'groups',  # !!!
        'definition': """
            id INT NOT NULL,
            name TEXT DEFAULT NULL
        """,
        'idx': 'id',
        'endpoint': '/api/v0/devicegroups',
        'expires_after': 86400 + random.randint(0, 120),
    },
    {
        'name': 'devices',
        'lookup_key': 'devices',
        'definition': """
            device_id INT NOT NULL,
            hardware TEXT DEFAULT NULL,
            hostname TEXT DEFAULT NULL,
            location TEXT DEFAULT NULL,
            os TEXT DEFAULT NULL,
            sysName TEXT DEFAULT NULL,
            sysDescr TEXT DEFAULT NULL,
            type TEXT DEFAULT NULL
        """,
        'idx': 'device_id',
        'endpoint': '/api/v0/devices?type=active',
        'expires_after': 1800 + random.randint(0, 120),
    },
    {
        'name': 'rules',
        'lookup_key': 'rules',
        'definition': """
            id INT NOT NULL,
            name TEXT DEFAULT NULL
        """,
        'idx': 'id',
        'endpoint': '/api/v0/rules',
        'expires_after': 3600 + random.randint(0, 120),
    },
    {
        'name': 'sensors',
        'lookup_key': 'sensors',
        'definition': """
            sensor_id INT NOT NULL,
            device_id INT DEFAULT NULL,
            lastupdate TEXT DEFAULT NULL,
            sensor_current REAL DEFAULT NULL,
            sensor_descr TEXT DEFAULT NULL,
            sensor_limit INT DEFAULT NULL,
            sensor_limit_low REAL DEFAULT NULL,
            sensor_prev REAL DEFAULT NULL
        """,
        'idx': 'sensor_id',
        'endpoint': '/api/v0/resources/sensors?type=active',
        'expires_after': 300 + random.randint(0, 10),
    },
    {
        'name': 'system',
        'lookup_key': 'system',
        'definition': """
            database_ver TEXT DEFAULT NULL,
            db_schema INT DEFAULT NULL,
            local_branch TEXT DEFAULT NULL,
            local_date TEXT DEFAULT NULL,
            local_sha TEXT DEFAULT NULL,
            local_ver TEXT DEFAULT NULL,
            netsnmp_ver TEXT DEFAULT NULL,
            php_ver TEXT DEFAULT NULL,
            python_ver TEXT DEFAULT NULL,
            rrdtool_ver TEXT DEFAULT NULL
        """,
        'idx': 'local_sha',
        'endpoint': '/api/v0/system',
        'expires_after': 28800 + random.randint(0, 120),
    },
]


def get_state(librestate):
    """Translate LibreNMS' states into Nagios states.
    """
    if librestate == 'ok':
        return STATE_OK
    if librestate == 'warning':
        return STATE_WARN
    if librestate == 'critical':
        return STATE_CRIT
    return STATE_UNKNOWN


def get_filename(args):
    return 'linuxfabrik-lib-librenms-{}.db'.format(
        txt.to_text(base64.urlsafe_b64encode(txt.to_bytes(args.URL))),
    )


def fetch_json(args, endpoint, lookup_key):
    if args.URL.endswith('/'):
        args.URL = args.URL[:-1]
    success, result = url.fetch_json(
        '{}{}'.format(args.URL, endpoint),
        header={'X-Auth-Token': args.TOKEN},
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
    )
    if not success:
        # "No device groups found", for example
        return []
    try:
        result = result[lookup_key]
        return result
    except:
        return []


def update_table(args, endpoint,
               table_name, table_definition, table_idx, table_lookup_key,
               table_expires_after=300,
               path='', filename='linuxfabrik-lib-librenms.db'):
    """Fetch data for one endpoint from SQLite DB or from REST API
    (wplus updating the SQLite DB with the fresh data).
    """
    # init db connection
    print(filename)
    print(table_name)
    success, conn = db_sqlite.connect(path=path, filename=filename)
    print('connect', success)
    if not success:
        return False

    # create the DB structure
    # kind of metadata table "timestamps" holds all tablenames and their
    # last update timestamp
    success, result = db_sqlite.create_table(
        conn,
        '''
        tablename TEXT NOT NULL,
        timestamp INT DEFAULT 1
        ''',
        table='timestamps',
    )
    print('create timestamps', success, result)
    if not success:
        db_sqlite.close(conn)
        return False
    success, result = db_sqlite.create_index(
        conn,
        column_list='tablename',
        table='timestamps',
        unique=True,
    )
    print('create index', success, result)
    if not success:
        db_sqlite.close(conn)
        return False

    # create cache table for data from librenms
    success, result = db_sqlite.create_table(
        conn,
        table_definition,
        table=table_name,
    )
    print('create table', table_definition, success, result)
    if not success:
        db_sqlite.close(conn)
        return False
    success, result = db_sqlite.create_index(
        conn,
        column_list=table_idx,
        table=table_name,
        unique=True,
    )
    print('create index', success, result)
    if not success:
        db_sqlite.close(conn)
        return False

    # populate data
    # Fetch JSON data from LibreNMS' REST-API. Cache the results for various
    # seconds to not overload the server if checking thousands of devices.
    # if table data has expired, fetch the LibreNMS API
    success, result = db_sqlite.select(
        conn,
        '''
        SELECT *
        FROM timestamps
        WHERE tablename = :tablename
        ''',
        {'tablename': table_name},
        fetchone=True,
    )
    print('select from timestamps', success, result, time.now())
    if result \
    and result['timestamp'] > time.now():
        # nothing to do
        success, result = db_sqlite.commit(conn)
        print('commit', success, result)
        db_sqlite.close(conn)
        return True

    # truncate table
    success, result = db_sqlite.delete(
        conn,
        'DELETE FROM {}'.format(table_name),
    )

    # fetch data from the librenms api
    result = fetch_json(args, endpoint, table_lookup_key)
    print('fetch json', len(result), endpoint, table_name)
    if not result:
        # we got nothing, so we cache nothing and try next time again
        success, result = db_sqlite.commit(conn)
        print('commit', success, result)
        db_sqlite.close(conn)
        return True

    # now remove all columns from result that are not in the definition
    # (remember: it is a cache, we just want to store what we really need)
    for r in result:
        row = {key: r[key] for key in r if key in table_definition}
        success, _ = db_sqlite.insert(conn, row, table_name)
        print('.', end='')
        if not success:
            db_sqlite.close(conn)
            return False

    # we got fresh data, so update the timestamp metadata table
    success, result = db_sqlite.replace(
        conn,
        {
            'tablename': table_name,
            'timestamp': time.now() + table_expires_after,
        },
        table='timestamps',
    )
    print('replace timestamp', {
            'tablename': table_name,
            'timestamp': time.now() + table_expires_after,
        }, success, result)
    if not success:
        db_sqlite.close(conn)
        return False

    success, result = db_sqlite.commit(conn)
    print('commit', success, result)
    retc = db_sqlite.close(conn)
    print(retc)
    return True


def update_cache(args, path='', filename='linuxfabrik-lib-librenms.db'):
    # 1. part: ugly, but special due to the API: we have to fetch all
    # devicegroups first to build the correct tablenames (dynamic)
    # https://docs.librenms.org/API/DeviceGroups/#get_devices_by_group
    #devicegroups = fetch_json(args, ...)
    for table in TABLES:
        print('---------------------------')
        if not update_table(
            args,
            table['endpoint'],
            table['name'],
            table['definition'],
            table['idx'],
            table['lookup_key'],
            table_expires_after=table['expires_after'],
            path=path,
            filename=filename,
        ):
            return False
    print('===========================')
    return True
