#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Library for accessing MySQL/MariaDB servers."""

import re
import sys
import warnings

from . import base
from .globals import STATE_UNKNOWN

warnings.filterwarnings('ignore', category=UserWarning, module='pymysql')

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026060201'

try:
    import pymysql.cursors
except ImportError:
    print('Python module "pymysql" is not installed.')
    sys.exit(STATE_UNKNOWN)


def check_privileges(conn, *required):
    """
    Verify the connected MySQL/MariaDB user has the required privileges.

    Without arguments, runs a functional smoke test (`SELECT VERSION()`), which succeeds with
    `GRANT USAGE` alone. This is sufficient for plugins that only call `SHOW GLOBAL VARIABLES`
    or `SHOW GLOBAL STATUS`, which do not need `SELECT` on any table.

    With arguments, parses `SHOW GRANTS FOR CURRENT_USER()` and verifies that every requested
    privilege is granted (case-insensitive, word-boundary match). Each positional argument is
    either:

    - a `str` like `'SELECT'`, `'REPLICATION CLIENT'`, `'PROCESS'`: that exact privilege must
      be present.
    - a `list` or `tuple` of strings: any-of semantics; at least one of the listed privileges
      must be present. Useful for cross-version aliases (e.g. MariaDB 10.5+ split
      `REPLICATION CLIENT` into `BINLOG MONITOR` / `SLAVE MONITOR`, and MariaDB 11+ aliased
      `SLAVE MONITOR` to `REPLICA MONITOR`).

    The pseudo-grants `ALL PRIVILEGES` and `SUPER` short-circuit to success regardless of the
    requested set.

    ### Parameters
    - **conn** (`Connection`):
      An active database connection object.
    - **\\*required** (`str` or `list[str]` or `tuple[str, ...]`):
      Zero or more privilege requirements. Strings are AND-ed together; a list/tuple denotes
      an any-of group within that AND chain.

    ### Returns
    - **tuple** (`bool`, `any`):
      - On success: `(True, <smoke-test row or list of grant rows>)`.
      - On failure: `(False, <error message string>)`.

    Compatible with `lib.base.coe()`.

    ### Example
    Smoke test (login + USAGE):
    >>> success, _ = check_privileges(conn)

    Single privilege:
    >>> success, _ = check_privileges(conn, 'SELECT')

    Multiple privileges (AND):
    >>> success, _ = check_privileges(conn, 'SELECT', 'PROCESS')

    Cross-version aliases (any-of):
    >>> success, _ = check_privileges(
    ...     conn,
    ...     ['REPLICATION CLIENT', 'SLAVE MONITOR', 'REPLICA MONITOR'],
    ... )

    Combined:
    >>> success, _ = check_privileges(
    ...     conn,
    ...     'SELECT',
    ...     ['REPLICATION CLIENT', 'SLAVE MONITOR'],
    ... )
    """
    if not required:
        success, result = select(conn, 'SELECT VERSION() AS version;', fetchone=True)
        if success and result:
            return True, result
        return (
            False,
            'You probably do not have sufficient privileges to connect to the database '
            '(USAGE) or to run SELECT statements.',
        )

    success, rows = select(conn, 'SHOW GRANTS FOR CURRENT_USER();')
    if not success:
        return False, rows
    grants_text = ' '.join(' '.join(str(v) for v in row.values()) for row in rows or [])
    if re.search(r'\bALL PRIVILEGES\b', grants_text, re.IGNORECASE) or re.search(
        r'\bSUPER\b', grants_text, re.IGNORECASE
    ):
        return True, rows

    def _has(privilege):
        return bool(
            re.search(r'\b' + re.escape(privilege) + r'\b', grants_text, re.IGNORECASE)
        )

    missing = []
    for req in required:
        if isinstance(req, (list, tuple)):
            if not any(_has(p) for p in req):
                missing.append(' or '.join(req))
        elif not _has(req):
            missing.append(req)
    if missing:
        return (
            False,
            'The connected user is missing the following privileges: '
            + ', '.join(missing)
            + '.',
        )
    return True, rows


def check_select_privileges(conn):
    """
    Deprecated. Backwards-compatible shim for already-deployed plugins that still call
    `check_select_privileges()` against an upgraded lib. Equivalent to
    `check_privileges(conn)` (the functional `SELECT VERSION()` smoke test). Will be
    removed once a plugin re-deployment cycle has propagated everywhere; new code
    should call `check_privileges()` directly.
    """
    return check_privileges(conn)


def close(conn):
    """
    Close a database connection safely.

    This function attempts to close an open database connection.
    If an exception occurs during closing, it is silently ignored to avoid affecting the main flow.

    ### Parameters
    - **conn** (`Connection`):
      An active database connection object to close.

    ### Returns
    - **bool**:
      Always returns `True` after attempting to close the connection.

    ### Notes
    - Any exceptions raised during connection closure are silently ignored.
    - This function is designed to be safe to call even if the connection is already closed or
      invalid.

    ### Example
    >>> close(conn)
    True
    """
    try:
        conn.close()
    except Exception:
        pass
    return True


def commit(conn):
    """
    Commit any pending changes to the database.

    This function saves (commits) all changes made during the current database session.
    If the commit fails, it returns an error message.

    ### Parameters
    - **conn** (`Connection`):
      An active database connection object.

    ### Returns
    - **tuple** (`bool`, `str or None`):
      - First element (`bool`): `True` if the commit succeeded, `False` if it failed.
      - Second element (`str` or `None`):
        - `None` on success.
        - Error message (`str`) on failure.

    ### Notes
    - Any exceptions raised during commit are caught and returned as a formatted error message.
    - This function allows the caller to handle commit errors gracefully.

    ### Example
    >>> success, error = commit(conn)
    >>> if not success:
    >>>     print(error)
    >>> else:
    >>>     print("Changes committed successfully.")
    """
    try:
        conn.commit()
        return True, None
    except Exception as e:
        return False, f'Commit failed: {e}'


def connect(mysql_connection, **kwargs):
    """
    Connect to a MySQL or MariaDB server using a dictionary of connection parameters.

    This function establishes a database connection using parameters from the given dictionary,
    such as configuration file, group, timeout, and cursor class. Additional connection options
    can be passed via `**kwargs`.

    ### Parameters
    - **mysql_connection** (`dict`):
      A dictionary containing connection settings.
      - `defaults_file` (`str`, optional): Path to a MySQL options file.
      - `defaults_group` (`str`, optional): Group to read from the options file.
        Defaults to `'client'`.
      - `timeout` (`int`, optional): Connection timeout in seconds. Defaults to `3`.
      - `cursorclass` (optional): Cursor class to use. Defaults to `DictCursor`.
    - **kwargs** (`any`, optional):
      Additional keyword arguments passed directly to `pymysql.connect()`.

    ### Returns
    - **tuple** (`bool`, `Connection or str`):
      - First element (`bool`): `True` if connection succeeded, `False` if it failed.
      - Second element (`Connection` or `str`):
        - Database connection object on success.
        - Error message string on failure.

    ### Notes
    - If connection fails, the error message contains the reason for failure.
    - `pymysql`'s `read_default_file` and `read_default_group` allow connection settings from a
      `.cnf` file.
    - After the connection is up, the function aligns the session's character set and collation
      with the `mysql` system schema (`SET NAMES ... COLLATE ...`). This stops queries against
      system tables like `mysql.user` and `mysql.global_priv` from aborting with ER 1267
      ("Illegal mix of collations") when the server's connection-collation default differs from
      the column collations. On MariaDB 10.4+, `mysql.user` is a view over `mysql.global_priv`
      whose JSON-derived columns return COERCIBLE results, so a plain `col = 'literal'` compare
      breaks the moment `collation_connection` and the column collation differ. The alignment
      is best-effort: on any error the connection stays usable with the server's defaults.

    ### Example
    >>> mysql_connection = {
    >>>     'defaults_file': '/etc/mysql/my.cnf',
    >>>     'defaults_group': 'client',
    >>>     'timeout': 5,
    >>> }
    >>> success, conn = connect(mysql_connection)
    >>> if success:
    >>> # Use conn
    >>>     pass
    >>> else:
    >>>     print(conn)
    """
    try:
        conn = pymysql.connect(
            read_default_file=mysql_connection.get('defaults_file'),
            read_default_group=mysql_connection.get('defaults_group', 'client'),
            cursorclass=mysql_connection.get('cursorclass', pymysql.cursors.DictCursor),
            connect_timeout=mysql_connection.get('timeout', 3),
            **kwargs,
        )
    except Exception as e:
        return False, f'Connecting to DB failed: {e}'

    _align_session_collation(conn)
    return True, conn


def _align_session_collation(conn):
    """Match `collation_connection` to the `mysql` system schema's default collation.

    Without this, queries that compare a JSON-derived column from the `mysql.user`
    view (e.g. `IS_ROLE = 'N'`, `plugin = 'mysql_native_password'`) abort with
    ER 1267 ("Illegal mix of collations") when the server's connection collation
    default doesn't match the schema's column collation. Looking up the schema's
    own defaults from `information_schema.schemata` keeps this working across
    MySQL/MariaDB versions and locale-specific installs (utf8mb3 on older
    servers, utf8mb4_general_ci on most current ones, utf8mb4_uca1400_ai_ci on
    MariaDB 10.10+). Best-effort: on any error the connection stays usable.
    """
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                'select default_character_set_name as cs, '
                'default_collation_name as coll '
                'from information_schema.schemata '
                "where schema_name = 'mysql'"
            )
            row = cursor.fetchone()
        if not row:
            return
        cs = (row.get('cs') or '').strip()
        coll = (row.get('coll') or '').strip()
        # Whitelist identifiers to keep the formatted `SET NAMES` safe from
        # any caller-controlled value (the row comes from a system view, but
        # defence in depth doesn't cost anything).
        if not (re.match(r'^[A-Za-z0-9_]+$', cs) and re.match(r'^[A-Za-z0-9_]+$', coll)):
            return
        with conn.cursor() as cursor:
            cursor.execute(f'set names {cs} collate {coll}')
    except Exception:
        pass


def get_all_status(conn):
    """
    Fetch the complete output of `SHOW GLOBAL STATUS` as a dictionary.

    The result is what `lod2dict()` produces against the rows of
    `SHOW GLOBAL STATUS`. Keys are MySQL/MariaDB status variable names, values
    are the raw string values returned by the server. One round trip; cheaper
    than issuing many `SHOW GLOBAL STATUS LIKE '...'` queries when a plugin
    needs more than a handful of values.

    ### Parameters
    - **conn** (`Connection`): An active database connection.

    ### Returns
    - **dict** (`str: str`): All status variables. On error returns the same
      `(False, errormessage)` tuple as `select()` via `lib.base.coe()` in the
      caller.

    ### Example
    >>> mystat = get_all_status(conn)
    >>> int(mystat['Uptime'])
    3600
    """
    return lod2dict(base.coe(select(conn, 'SHOW GLOBAL STATUS')))


def get_all_variables(conn):
    """
    Fetch the complete output of `SHOW GLOBAL VARIABLES` as a dictionary.

    Same shape as `get_all_status()`, but for server variables instead of
    status counters. Use when a plugin needs more than a handful of variables
    and wants to avoid the per-`LIKE` query overhead.

    ### Parameters
    - **conn** (`Connection`): An active database connection.

    ### Returns
    - **dict** (`str: str`): All system variables.

    ### Example
    >>> myvar = get_all_variables(conn)
    >>> int(myvar['max_connections'])
    151
    """
    return lod2dict(base.coe(select(conn, 'SHOW GLOBAL VARIABLES')))


def get_engines(conn):
    """
    Retrieve the available storage engines from the database.

    This function runs `SHOW ENGINES` against the connected database, normalizes the output,
    and returns a dictionary mapping engine names to their support status.
    It emulates the old `have_*` status variables for compatibility with older codebases.
    Also works around MySQL bug #59393 related to `skip-innodb`.

    ### Parameters
    - **conn** (`Connection`):
      An active database connection object.

    ### Returns
    - **dict** (`str: str`):
      A dictionary where keys are `have_<engine>` and values are:
      - `'YES'` if the engine is available by default.
      - The actual support status reported otherwise (`DISABLED`, etc.).

    ### Notes
    - `have_*` variables are deprecated since MySQL 5.6 and removed afterward.
    - Special mappings:
      - `federated` → `have_federated_engine`
      - `blackhole` → `have_blackhole_engine`
      - `berkeleydb` → `have_bdb`
    - This function helps maintain compatibility with monitoring scripts expecting old-style
      `have_*` variables.

    ### Example
    >>> get_engines(conn)
    {
        'have_innodb': 'YES',
        'have_myisam': 'YES',
        'have_blackhole_engine': 'DISABLED',
        ...
    }
    """
    engines = {}
    success, result = select(conn, 'SHOW ENGINES')

    if not success or not result:
        return engines

    for line in result:
        engine = line['Engine'].lower()
        if engine in ('federated', 'blackhole'):
            engine += '_engine'
        elif engine == 'berkeleydb':
            engine = 'bdb'

        engines[f'have_{engine}'] = (
            'YES' if line['Support'] == 'DEFAULT' else line['Support']
        )

    return engines


def get_flavor():
    """
    Return the installed MySQL/MariaDB flavor.

    Thin wrapper around `get_server_info()` for callers that only care
    about the flavor.

    ### Returns
    - **str | None**: `'mariadb'`, `'mysql'`, or `None` when no binary
      responds.

    ### Example
    >>> get_flavor()
    'mariadb'
    """
    info = get_server_info()
    return info['flavor'] if info else None


def get_replica_status(conn):
    """
    Return the first row of `SHOW REPLICA STATUS` (or the legacy
    `SHOW SLAVE STATUS`), or `None` if the server is not configured as a
    replica.

    `SHOW REPLICA STATUS` is the MariaDB 10.5+ / MySQL 8.0.22+ wording;
    older servers only know `SHOW SLAVE STATUS`. This helper tries the newer
    form first and silently falls back, so plugins do not have to know which
    server flavour they are talking to.

    ### Parameters
    - **conn** (`Connection`): An active database connection.

    ### Returns
    - **dict** or **None**: First row of the result, or `None` when neither
      command returns rows (server is not a replica).
    """
    success, rows = select(conn, 'SHOW REPLICA STATUS')
    if not success:
        success, rows = select(conn, 'SHOW SLAVE STATUS')
    if not success or not rows:
        return None
    return rows[0]


# Output formats handled by the regex parser:
#
#   mysqld  Ver 8.0.45 for Linux on x86_64 (Source distribution)
#   mysqld  Ver 10.11.15-MariaDB for Linux on x86_64 (MariaDB Server)
#   mysql  Ver 14.14 Distrib 5.7.44, for Linux (x86_64) using EditLine wrapper
#   mariadb  Ver 15.1 Distrib 10.5.x-MariaDB, for Linux on x86_64
#   mariadb from 11.4.10-MariaDB, client 15.2 for debian-linux-gnu (x86_64) using EditLine wrapper
#
# MariaDB 11.4 dropped the `mysqld` symlink and renamed the client
# version banner from "Distrib X.Y.Z" to "from X.Y.Z", so the parser
# probes both server and client binaries and accepts both prefixes.
_VERSION_REGEXES = (
    # `mysqld  Ver X.Y.Z[-MariaDB] for ...` (any distro suffix like
    # `-1~trusty` is stripped further down)
    r'Ver (\d+\.\d+\.\d+(?:-MariaDB)?)',
    # `mysql  Ver 14.14 Distrib X.Y.Z[-MariaDB], for ...`
    # `mariadb  Ver 15.1 Distrib 10.5.x-MariaDB, for ...`
    r'Distrib (\S+?),',
    # `mariadb from X.Y.Z[-MariaDB], client ...`  (MariaDB 11.4+)
    r'from (\d+\.\d+\.\d+(?:-MariaDB)?),',
)


def _parse_version_banner(banner):
    """Extract `(flavor, version)` from a `mysqld`/`mariadbd`/`mariadb`/
    `mysql` --version banner. Returns `(None, None)` if no regex matches.
    """
    for regex in _VERSION_REGEXES:
        m = re.search(regex, banner)
        if not m:
            continue
        raw = m.group(1).strip()
        flavor = 'mariadb' if '-MariaDB' in raw else 'mysql'
        version = raw.replace('-MariaDB', '')
        return flavor, version
    return None, None


def get_server_info(banner=None):
    """
    Determine the installed MySQL/MariaDB flavor and version. Does not
    require a database connection.

    Returns a dict like `{'flavor': 'mariadb', 'version': '10.11.16'}`,
    or `None` when nothing matches.

    If `banner` is `None`, probe `mysqld`, `mariadbd`, `mariadb`, `mysql`
    in order and parse the first responding --version banner. Server
    binaries are tried first; the client fallback exists because MariaDB
    11.4 dropped the `mysqld` symlink and renamed the client.

    Pass a banner string directly (for example a unit-test fixture) to
    skip the shell probe entirely.

    Useful where the systemd-based distinction is unreliable: on Fedora
    and RHEL `mysql.service` is aliased to `mariadb.service`, so
    `systemctl is-enabled mysql.service` reports `alias` rather than the
    underlying flavor.

    ### Parameters
    - **banner** (`str | None`): Optional pre-collected --version banner
      to parse instead of probing.

    ### Returns
    - **dict | None**: `{'flavor': 'mariadb'|'mysql', 'version': str}`
      or `None`.

    ### Example
    >>> get_server_info()
    {'flavor': 'mariadb', 'version': '10.11.16'}
    """
    if banner is not None:
        flavor, version = _parse_version_banner(banner)
        if version:
            return {'flavor': flavor, 'version': version}
        return None

    # local import to keep db_mysql usable without shell at module load
    from . import shell

    for command in (
        'mysqld --version',
        'mariadbd --version',
        'mariadb --version',
        'mysql --version',
    ):
        success, result = shell.shell_exec(command)
        if not success:
            continue
        stdout, _, _ = result
        if not stdout:
            continue
        flavor, version = _parse_version_banner(stdout.strip())
        if version:
            return {'flavor': flavor, 'version': version}
    return None


def has_is_role_column(conn):
    """
    Return `True` if `mysql.user.IS_ROLE` exists (MariaDB 10.0.5+ roles).

    When the column exists, role rows in `mysql.user` carry `IS_ROLE = 'Y'`
    and should typically be excluded from anonymous-user / empty-password /
    username-as-password checks (a role legitimately has no password and an
    empty `host` column). Plugins use the return value to gate `IS_ROLE = 'N'`
    fragments in their `WHERE` clauses.

    ### Parameters
    - **conn** (`Connection`): An active database connection.

    ### Returns
    - **bool**: `True` if the column exists, `False` otherwise.
    """
    sql = """
        SELECT COUNT(*) AS cnt
        FROM information_schema.columns
        WHERE TABLE_SCHEMA = 'mysql'
            AND TABLE_NAME = 'user'
            AND COLUMN_NAME = 'IS_ROLE'
        ;
    """
    row = base.coe(select(conn, sql, fetchone=True))
    return int(row['cnt']) > 0


def lod2dict(lod):
    """
    Convert a list of simple key-value dictionaries into a single dictionary.

    This function processes a list of dictionaries and merges them into one dictionary.
    It handles special cases where the input uses `Variable_name` and `Value` fields, as returned
    by SQL queries like `SHOW VARIABLES;`.

    ### Parameters
    - **lod** (`list` of `dict`):
      A list where each element is a dictionary with either:
      - A simple `{key: value}` structure.
      - A special `{Variable_name: ..., Value: ...}` structure (from MySQL system queries).

    ### Returns
    - **dict** (`str: str`):
      A dictionary with keys and values extracted from the input list.

    ### Notes
    - If a dictionary contains `Variable_name` and `Value`, they are used as key and value.
    - Otherwise, the first key-value pair from the dictionary is used directly.
    - Later keys will overwrite earlier ones if duplicate keys exist.

    ### Example
    >>> lod2dict(
    ...     [{'Variable_name': 'a', 'Value': 'b'}, {'Variable_name': 'c', 'Value': 'd'}]
    ... )
    {'a': 'b', 'c': 'd'}

    >>> lod2dict([{'key1': 'value1'}, {'key2': 'value2'}])
    {'key1': 'value1', 'key2': 'value2'}
    """
    result = {}
    for row in lod:
        if 'Variable_name' in row and 'Value' in row:
            result[row['Variable_name']] = row['Value']
        else:
            result.update(row)
    return result


def select(conn, sql, data=None, fetchone=False):
    """
    Execute a SQL SELECT query on the database connection.

    This function executes a SELECT statement against the connected database,
    optionally using provided parameters, and returns either one row or all rows.
    SELECT operations do not modify the database.

    ### Parameters
    - **conn** (`Connection`):
      An active database connection object.
    - **sql** (`str`):
      The SQL SELECT query to execute.
      Use placeholders (`%s`) for any parameters.
    - **data** (`list`, optional):
      A list of values to bind to the placeholders in the SQL query.
      Defaults to an empty list (no parameters).
    - **fetchone** (`bool`, optional):
      If `True`, fetch only the first matching row.
      If `False` (default), fetch all matching rows.

    ### Returns
    - **tuple** (`bool`, `any`):
      - First element (`bool`): `True` if the query succeeded, `False` if it failed.
      - Second element (`list`, `dict`, or `str`):
        - The query result (one row as a dict if `fetchone=True`, or a list of dicts).
        - Error message string on failure.

    ### Notes
    - On success, results are returned as dictionaries (one per row) if the connection uses
      `DictCursor`.
    - On failure, an error message is returned with the failed SQL, the exception, and any
      input data.

    ### Example
    Query using a LIKE pattern:
    >>> data = ['val1%']
    >>> sql = 'SELECT * FROM t WHERE c LIKE %s'
    >>> success, result = select(conn, sql, data)

    Query using an IN clause:
    >>> data = ['val1', 'val2']
    >>> sql = 'SELECT * FROM t WHERE c IN (f{", ".join("%s" for _ in data)})'
    >>> success, result = select(conn, sql, data)
    """
    data = data or []
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, tuple(data)) if data else cursor.execute(sql)
            return (True, cursor.fetchone()) if fetchone else (True, cursor.fetchall())
    except Exception as e:
        return False, f'Query failed: {sql}, Error: {e}, Data: {data}'
