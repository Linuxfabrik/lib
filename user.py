#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library answers what a Unix host says about one of its local accounts: which
name a numeric id belongs to, where the boundary between system and regular accounts
runs, whether an account can be logged into, and whether it carries a password at all.

Everything here reads the local databases and nothing else. An account served by a
directory service is therefore reported as absent rather than as broken, which are
two different facts and are told apart in the return value: a consumer that judges an
account has to be able to say "this host does not manage that account" instead of
guessing.

On a system without the Unix account databases every lookup degrades to the plain
number or an empty answer, so a caller does not have to branch on the platform.

Typical use case:
```python
    state, password = lib.user.get_shadow_password('www-data')
    if state == 'found' and lib.user.password_state(password) == 'usable':
        print('The account carries a password somebody can log in with.')
```
"""

import os

from . import disk, txt

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082901'

try:
    import grp
    import pwd

    HAVE_ACCOUNT_DB = True
except ImportError:
    # Windows has neither module. Every lookup below falls back to the number or to
    # an empty answer there, which is what a consumer would have to do itself.
    HAVE_ACCOUNT_DB = False

# Where the boundary between system and regular accounts sits when the host does not
# say. 1000 is what the whole Red Hat and Debian family ships; the older 500 belongs
# to RHEL 6 and earlier, which no supported release reaches back to.
DEFAULT_UID_MIN = 1000

# The file the boundary is configured in, and the two databases read below. Named
# here so a caller reading them under a different root can relocate them with
# `lib.disk.under_root()`.
LOGIN_DEFS = '/etc/login.defs'
SHADOW = '/etc/shadow'
SHELLS = '/etc/shells'


def _read_lines(path):
    """
    Return the lines of a local account database, or None where it cannot be read.

    Read as bytes and decoded afterwards, because these files carry whatever a
    comment or a GECOS field was written in, and a single byte that is not UTF-8
    must not take the reading of the whole file down.
    """
    success, raw = disk.read_file(path, binary=True)
    if not success:
        return None
    return txt.to_text(raw, errors='strict_or_latin1').splitlines()


def get_gid_name(gid):
    """
    Resolve a numeric group id to its name.

    ### Parameters
    - **gid** (`int`): The group id to resolve.

    ### Returns
    - **str**: The group name, or the number as a string where the host does not
      know it or has no group database at all.

    ### Example
    >>> get_gid_name(0)
    'root'
    """
    if HAVE_ACCOUNT_DB:
        try:
            return grp.getgrgid(gid).gr_name
        except (KeyError, OverflowError, TypeError, ValueError):
            pass
    return str(gid)


def get_interactive_shells(path=SHELLS):
    """
    Return the shells the host itself lists as usable for logging in.

    ### Parameters
    - **path** (`str`, optional): The file to read. Defaults to `/etc/shells`.

    ### Returns
    - **set**: The shells listed there. Empty where the file does not exist, which
      is a host that makes no such statement rather than one that allows nothing.

    ### Example
    >>> '/bin/bash' in get_interactive_shells()
    True
    """
    shells = set()
    lines = _read_lines(path)
    if lines is None:
        return shells
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            shells.add(stripped)
    return shells


def get_shadow_password(user, path=SHADOW):
    """
    Return `(state, password)` for the shadow entry of a local account.

    Read from the shadow database directly rather than through `passwd -S`, whose
    output format differs between distributions.

    ### Parameters
    - **user** (`str`): The account name to look up.
    - **path** (`str`, optional): The file to read. Defaults to `/etc/shadow`.

    ### Returns
    - **tuple**: `(state, password)`. `state` is `'found'` with the password field
      as the second element, `'unreadable'` where the database could not be read,
      and `'missing'` where it was read and holds no such account. The two absent
      cases mean different things and are told apart on purpose: `unreadable` is a
      missing privilege on this run, `missing` is an account served by a directory
      service rather than by local files.

    ### Example
    >>> get_shadow_password('root')
    ('found', '!!')
    """
    lines = _read_lines(path)
    if lines is None:
        return ('unreadable', None)
    for line in lines:
        fields = line.split(':')
        if len(fields) > 1 and fields[0] == user:
            return ('found', fields[1])
    return ('missing', None)


def get_uid_min(path=LOGIN_DEFS):
    """
    Return `UID_MIN`, the boundary between system and regular accounts.

    ### Parameters
    - **path** (`str`, optional): The file to read. Defaults to `/etc/login.defs`.

    ### Returns
    - **int**: The configured boundary, or `DEFAULT_UID_MIN` where the host does not
      state one or states something that is not a number.

    ### Example
    >>> get_uid_min()
    1000
    """
    lines = _read_lines(path)
    if lines is None:
        return DEFAULT_UID_MIN
    for line in lines:
        if not line.startswith('UID_MIN'):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            return int(fields[1])
        except ValueError:
            # A line that names the setting but not a number says nothing, and the
            # file may well hold a second one that does.
            continue
    return DEFAULT_UID_MIN


def get_uid_name(uid):
    """
    Resolve a numeric user id to its name.

    ### Parameters
    - **uid** (`int`): The user id to resolve.

    ### Returns
    - **str**: The account name, or the number as a string where the host does not
      know it or has no account database at all.

    ### Example
    >>> get_uid_name(0)
    'root'
    """
    if HAVE_ACCOUNT_DB:
        try:
            return pwd.getpwuid(uid).pw_name
        except (KeyError, OverflowError, TypeError, ValueError):
            pass
    return str(uid)


def own_mount_namespace():
    """
    Return the mount namespace of this process.

    Two processes in the same mount namespace see the same filesystem, which is what
    a consumer needs to know before it reads a path on behalf of another process:
    the same path means a different file inside a container.

    ### Returns
    - **str**: The namespace as the kernel names it, or `None` where the kernel does
      not publish one, which is every system that is not Linux.

    ### Example
    >>> own_mount_namespace()
    'mnt:[4026531841]'
    """
    try:
        return os.readlink('/proc/self/ns/mnt')
    except OSError:
        return None


def password_state(shadow):
    """
    Say what the password field of a shadow entry means.

    ### Parameters
    - **shadow** (`str`): The second field of a shadow entry, as
      `get_shadow_password()` returns it.

    ### Returns
    - **str**: One of

        - `'locked'`: the field is prefixed with `!`, which is what `passwd --lock`
          writes in front of whatever was there. `!!` is the same thing on an account
          that never had a password.
        - `'no-login'`: the field is `*` or starts with it, the distribution default
          for an account that is not meant to be logged into with a password.
        - `'none'`: the field is empty. This is the dangerous one and is not a locked
          account: it is a password of no characters, which anybody can use.
        - `'usable'`: the field holds a hash somebody can authenticate against.

    ### Example
    >>> password_state('!!')
    'locked'
    >>> password_state('')
    'none'
    """
    shadow = '' if shadow is None else str(shadow)
    if shadow.startswith('!'):
        return 'locked'
    if shadow.startswith('*'):
        return 'no-login'
    if not shadow:
        return 'none'
    return 'usable'
