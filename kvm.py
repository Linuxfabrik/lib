#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""This library collects some libvirt related functions that are needed by more
than one consumer.

Every call goes through the `virsh` command line client on a read-only
connection. libvirt grants its read-only action (`org.libvirt.unix.monitor`) to
any local account without authentication, while the read-write action
(`org.libvirt.unix.manage`) is guarded by polkit and fails outright where no
polkit agent can ask for a password, which is the situation on any server. A
read-only connection therefore needs neither root nor sudo nor membership in the
`libvirt` group. Verified against libvirt 12.0.0 on Fedora 44.

Typical use case:
```python
    # One call covers every domain on the host.
    domains = lib.base.coe(lib.kvm.get_domstats(groups=['balloon', 'state']))
    for name, stats in domains.items():
        print(name, lib.kvm.DOMAIN_STATES.get(stats.get('state.state')))
```
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082501'

import re

from . import shell

DEFAULT_TIMEOUT = 8

# Connecting to a hypervisor without saying which one lets libvirt probe, and an
# unprivileged account is probed into its own session daemon (`qemu:///session`),
# which knows none of the host's domains and reports an empty list instead of an
# error. Consumers therefore always name the connection, and this is the one that
# holds the domains of a KVM host.
DEFAULT_URI = 'qemu:///system'

# virDomainState from libvirt's include/libvirt/libvirt-domain.h, spelled the way
# virsh prints it (VIR_ENUM_IMPL(virshDomainState) in tools/virsh-domain-monitor.c).
# The enumeration is complete as of libvirt 12.7; libvirt appends to it over time.
# Three of the eight names contain a space, so a consumer must not split a virsh
# table row on whitespace to recover the state.
DOMAIN_STATES = {
    0: 'no state',
    1: 'running',
    2: 'idle',
    3: 'paused',
    4: 'in shutdown',
    5: 'shut off',
    6: 'crashed',
    7: 'pmsuspended',
}

# The reason libvirt records next to a domain state, one mapping per state. From the
# `virDomain*Reason` enumerations in include/libvirt/libvirt-domain.h, spelled the way
# virsh prints them (VIR_ENUM_IMPL(virshDomain*Reason) in
# tools/virsh-domain-monitor.c) and complete as of libvirt 12.7.
#
# The reason is what separates an ending from how it ended: a domain that was shut
# down, one that was killed off the host and one whose start never succeeded all sit
# in `shut off`, and only the reason tells them apart. libvirt fills it for every
# domain, including the ones it has no history for, where it answers `unknown`.
DOMAIN_STATE_REASONS = {
    0: {0: 'unknown'},
    1: {
        0: 'unknown',
        1: 'booted',
        2: 'migrated',
        3: 'restored',
        4: 'from snapshot',
        5: 'unpaused',
        6: 'migration canceled',
        7: 'save canceled',
        8: 'event wakeup',
        9: 'crashed',
        10: 'post-copy',
        11: 'post-copy failed',
    },
    2: {0: 'unknown'},
    3: {
        0: 'unknown',
        1: 'user',
        2: 'migrating',
        3: 'saving',
        4: 'dumping',
        5: 'I/O error',
        6: 'watchdog',
        7: 'from snapshot',
        8: 'shutting down',
        9: 'creating snapshot',
        10: 'crashed',
        11: 'starting up',
        12: 'post-copy',
        13: 'post-copy failed',
        14: 'api error',
    },
    4: {0: 'unknown', 1: 'user'},
    5: {
        0: 'unknown',
        1: 'shutdown',
        2: 'destroyed',
        3: 'crashed',
        4: 'migrated',
        5: 'saved',
        6: 'failed',
        7: 'from snapshot',
        8: 'daemon',
    },
    6: {0: 'unknown', 1: 'panicked'},
    7: {0: 'unknown'},
}

# The domain filters `virsh list` accepts, from opts_list in
# tools/virsh-domain-monitor.c. Its output-format options (`--name`, `--table`,
# `--uuid`, `--id`, `--title`, `--managed-save`) are deliberately absent, because
# the library always asks for `--name`.
DOMAIN_FILTERS = (
    'autostart',
    'inactive',
    'no-autostart',
    'persistent',
    'state-other',
    'state-paused',
    'state-running',
    'state-shutoff',
    'transient',
    'with-checkpoint',
    'with-managed-save',
    'with-snapshot',
    'without-checkpoint',
    'without-managed-save',
    'without-snapshot',
)

# The statistics groups `virsh domstats` accepts, from opts_domstats in
# tools/virsh-domain-monitor.c. Asking for none of them returns libvirt's own
# default selection.
DOMSTATS_GROUPS = (
    'balloon',
    'block',
    'cpu-total',
    'dirtyrate',
    'interface',
    'iothread',
    'memory',
    'perf',
    'state',
    'vcpu',
    'vm',
)

# virStoragePoolState from libvirt's include/libvirt/libvirt-storage.h, in enum
# order, spelled the way virsh prints it. `pool-info` reports the state from this
# list. `pool-list` reports it only when asked for `--details`; without that it
# prints `active` or `inactive` and collapses `running`, `degraded` and
# `inaccessible` into `active` (tools/virsh-pool.c, "only active/inactive state
# strings are used"), hiding exactly the two states worth reacting to.
POOL_STATES = (
    'inactive',
    'building',
    'running',
    'degraded',
    'inaccessible',
)

DOMSTATS_DOMAIN_REGEX = re.compile(r"^Domain:\s+'(.*)'\s*$")
INTEGER_REGEX = re.compile(r'^[0-9]+$')


def get_domains(uri=DEFAULT_URI, filters=None, timeout=DEFAULT_TIMEOUT):
    """
    Return the names of the domains a connection knows, running or not.

    ### Parameters
    - **uri** (`str`, optional): libvirt connection URI. Defaults to `DEFAULT_URI`.
    - **filters** (`list`, optional): Filters to narrow the result down, without the
      leading dashes, for example `['autostart']`. See `DOMAIN_FILTERS` for the
      accepted names. Defaults to None, which returns every domain.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `DEFAULT_TIMEOUT`.

    ### Returns
    - **tuple** (`bool`, `list` or `str`):
      - `success` (`bool`): True if the command succeeded, False otherwise.
      - `result` (`list` or `str`): Domain names, or an error message.

    ### Notes
    - Asks for `--all` and `--name`. `--all` covers inactive domains too, which the
      filters would otherwise silently exclude: asked for `autostart` alone, virsh
      answers with the autostart domains that happen to be running, which is the
      opposite of what a caller looking for a domain that failed to start wants.
    - `--name` prints one name per line. The table virsh prints by default cannot be
      split reliably, because both a domain name and a state may contain a space.
    - `filters=['autostart']` answers "which domains does this host expect to be
      up", so nobody has to maintain a list of expected domains next to the caller.

    ### Example
    >>> success, domains = get_domains(filters=['autostart'])
    """
    args = ['list', '--all', '--name']
    for domain_filter in filters or []:
        if domain_filter not in DOMAIN_FILTERS:
            return False, (
                f'Unknown domain filter "{domain_filter}". '
                f'Known filters: {", ".join(DOMAIN_FILTERS)}.'
            )
        args.append(f'--{domain_filter}')
    success, stdout = virsh(args, uri=uri, timeout=timeout)
    if not success:
        return False, stdout
    return True, [line.strip() for line in stdout.splitlines() if line.strip()]


def get_domstats(
    uri=DEFAULT_URI,
    groups=None,
    running_only=True,
    nowait=False,
    timeout=DEFAULT_TIMEOUT,
):
    """
    Collect statistics for every domain on the connection in a single call.

    ### Parameters
    - **uri** (`str`, optional): libvirt connection URI. Defaults to `DEFAULT_URI`.
    - **groups** (`list`, optional): Statistics groups to ask for, without the
      leading dashes, for example `['balloon', 'cpu-total']`. See `DOMSTATS_GROUPS`
      for the accepted names. Defaults to None, which returns libvirt's own default
      selection.
    - **running_only** (`bool`, optional): Restrict the report to running domains.
      Defaults to True.
    - **nowait** (`bool`, optional): Report only what can be answered without
      querying the hypervisor. Defaults to False.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `DEFAULT_TIMEOUT`.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - `success` (`bool`): True if the command succeeded, False otherwise.
      - `result` (`dict` or `str`): `{domain_name: {field_name: value}}`, or an
        error message.

    ### Notes
    - One call covers the whole host. Asking per domain and per device instead, the
      way `domblkstat` and `domifstat` require, multiplies the round trips without
      returning anything extra.
    - Leave `running_only` at True for anything derived from a counter. A domain
      that is shut off still reports `cpu.time`, `cpu.user` and `cpu.system`, but
      those values are identical across all shut-off domains and keep growing
      between two runs, so they are not that domain's CPU time and a rate computed
      from them is invented. Verified against libvirt 12.0.0.
    - `nowait` trades completeness for a bounded runtime. Left at False, a domain
      whose hypervisor connection hangs holds up the call until `timeout` and the
      caller reports that as the failure it is. Set to True, such a domain silently
      contributes fewer fields while the others are still reported.

    ### Example
    >>> success, domains = get_domstats(groups=['state', 'balloon'])
    """
    args = ['domstats']
    for group in groups or []:
        if group not in DOMSTATS_GROUPS:
            return False, (
                f'Unknown domstats group "{group}". '
                f'Known groups: {", ".join(DOMSTATS_GROUPS)}.'
            )
        args.append(f'--{group}')
    if running_only:
        args.append('--list-running')
    if nowait:
        args.append('--nowait')
    success, stdout = virsh(args, uri=uri, timeout=timeout)
    if not success:
        return False, stdout
    return True, parse_domstats(stdout)


def parse_pool_info(stdout):
    """
    Turn the output of `virsh pool-info` into a mapping.

    ### Parameters
    - **stdout** (`str`): Raw `virsh pool-info` output.

    ### Returns
    - **dict**: `{lowercased_key: value}`. A value made up of digits only is
      returned as `int`, every other value as `str`.

    ### Notes
    - Public for the same reason `parse_domstats()` is: a consumer that replays
      recorded output rather than talking to a hypervisor needs the same parser the
      live path uses, and reimplementing it would let the two drift apart.
    - A line without a colon is skipped, so a heading or a blank line in the output
      costs nothing.
    """
    info = {}
    for line in stdout.splitlines():
        key, separator, value = line.partition(':')
        if not separator:
            continue
        key = key.strip().lower()
        value = value.strip()
        info[key] = int(value) if INTEGER_REGEX.match(value) else value
    return info


def get_pool_info(pool, uri=DEFAULT_URI, timeout=DEFAULT_TIMEOUT):
    """
    Return name, state, autostart and sizes of one storage pool.

    ### Parameters
    - **pool** (`str`): Name of the storage pool.
    - **uri** (`str`, optional): libvirt connection URI. Defaults to `DEFAULT_URI`.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `DEFAULT_TIMEOUT`.

    ### Returns
    - **tuple** (`bool`, `dict` or `str`):
      - `success` (`bool`): True if the command succeeded, False otherwise.
      - `result` (`dict` or `str`): Keys `allocation`, `autostart`, `available`,
        `capacity`, `name`, `persistent`, `state` and `uuid`, or an error message.
        The three sizes are byte counts.

    ### Notes
    - Asks for `--bytes`, so the sizes arrive as exact integers. Without it libvirt
      prints them rounded to two decimals with a unit (`1.82 TiB`), which a consumer
      would have to convert back and would lose precision doing so.
    - `state` carries the real pool state out of `POOL_STATES`, which is the reason
      to ask per pool rather than to read the `pool-list` table.
    - The pool name reaches virsh as a positional argument, so a value that looks
      like an option is refused rather than handed to virsh as one.

    ### Example
    >>> success, info = get_pool_info('default')
    """
    success, pool = shell.safe_cli_value(pool, 'pool name')
    if not success:
        return False, pool
    success, stdout = virsh(
        ['pool-info', '--bytes', pool],
        uri=uri,
        timeout=timeout,
    )
    if not success:
        return False, stdout
    return True, parse_pool_info(stdout)


def get_pool_xml(pool, uri=DEFAULT_URI, timeout=DEFAULT_TIMEOUT):
    """
    Return the XML definition of one storage pool.

    ### Parameters
    - **pool** (`str`): Name of the storage pool.
    - **uri** (`str`, optional): libvirt connection URI. Defaults to `DEFAULT_URI`.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `DEFAULT_TIMEOUT`.

    ### Returns
    - **tuple** (`bool`, `str`):
      - `success` (`bool`): True if the command succeeded, False otherwise.
      - `result` (`str`): The pool's XML, or an error message.

    ### Notes
    - Everything about a pool that is not a name, a state or a size lives here and
      nowhere else: what kind of pool it is, where it points, and what it is built on.
      `pool-info` reports none of it.
    - Returned as text rather than parsed, because what a consumer needs out of it
      differs per pool type and parsing all of it would serve none of them.
    - The pool name reaches virsh as a positional argument, so a value that looks like
      an option is refused rather than handed to virsh as one.

    ### Example
    >>> success, xml = get_pool_xml('default')
    """
    success, pool = shell.safe_cli_value(pool, 'pool name')
    if not success:
        return False, pool
    return virsh(['pool-dumpxml', pool], uri=uri, timeout=timeout)


def get_pools(uri=DEFAULT_URI, timeout=DEFAULT_TIMEOUT):
    """
    Return every storage pool known to the connection, running or not.

    ### Parameters
    - **uri** (`str`, optional): libvirt connection URI. Defaults to `DEFAULT_URI`.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `DEFAULT_TIMEOUT`.

    ### Returns
    - **tuple** (`bool`, `list` or `str`):
      - `success` (`bool`): True if the command succeeded, False otherwise.
      - `result` (`list` or `str`): Pool names, or an error message.

    ### Notes
    - Reports names only. Pair it with `get_pool_info()` for state and sizes.

    ### Example
    >>> success, pools = get_pools()
    """
    success, stdout = virsh(
        ['pool-list', '--all', '--name'],
        uri=uri,
        timeout=timeout,
    )
    if not success:
        return False, stdout
    return True, [line.strip() for line in stdout.splitlines() if line.strip()]


def parse_domstats(stdout):
    """
    Turn the output of `virsh domstats` into a mapping per domain.

    ### Parameters
    - **stdout** (`str`): Raw `virsh domstats` output.

    ### Returns
    - **dict**: `{domain_name: {field_name: value}}`. A value made up of digits only
      is returned as `int`, every other value as `str`.

    ### Notes
    - The domain name is read from the quoted `Domain: '<name>'` header, so a name
      containing a space survives.
    - libvirt omits a field it cannot fill instead of reporting a placeholder, so a
      consumer looks fields up defensively. A domain that is not running reports few
      fields, and the ones it does report are not all meaningful; see `get_domstats`.
    """
    domains = {}
    name = None
    for line in stdout.splitlines():
        match = DOMSTATS_DOMAIN_REGEX.match(line)
        if match:
            name = match.group(1)
            domains[name] = {}
            continue
        if name is None:
            continue
        key, separator, value = line.strip().partition('=')
        if not separator:
            continue
        domains[name][key] = int(value) if INTEGER_REGEX.match(value) else value
    return domains


def _explain_virsh_error(stderr, uri):
    """
    Turn a virsh error into a sentence that names the next step.

    ### Parameters
    - **stderr** (`str`): What virsh wrote to standard error.
    - **uri** (`str`): The connection URI that was used.

    ### Returns
    - **str**: The advice, followed by what virsh reported.

    ### Notes
    - Only the failures an administrator can act on are translated. Everything else
      is passed on as libvirt worded it, because libvirt says it better than a guess
      would. Error strings verified against libvirt 12.0.0.
    """
    stderr = stderr.strip()
    advice = ''
    if 'failed to connect to the hypervisor' in stderr:
        advice = (
            f'Cannot reach the libvirt daemon at "{uri}". Check that the daemon is '
            f'running ("systemctl status virtqemud.socket", or "libvirtd" on hosts '
            f'that still run the monolithic daemon) and that the URI names the '
            f'hypervisor this host actually runs. '
        )
    elif 'virConnectGetAllDomainStats' in stderr:
        advice = (
            f'The hypervisor at "{uri}" does not report domain statistics. Only '
            f'QEMU/KVM and Virtuozzo do; Xen ("xen:///") and libvirt-LXC '
            f'("lxc:///") implement neither the statistics call nor any substitute '
            f'for it, so the data this needs cannot be had from them. Point the '
            f'connection at a QEMU/KVM host. '
        )
    elif 'no polkit agent available' in stderr:
        advice = (
            'libvirt asked for a read-write connection, which polkit guards and '
            'which cannot be granted without someone to type a password. '
        )
    return f'{advice}{stderr}' if advice else stderr


def virsh(args, uri=DEFAULT_URI, timeout=DEFAULT_TIMEOUT):
    """
    Run a `virsh` sub-command on a read-only connection and return its output.

    ### Parameters
    - **args** (`list`): The sub-command and its options, for example
      `['domstats', '--balloon']`.
    - **uri** (`str`, optional): libvirt connection URI. Defaults to `DEFAULT_URI`.
      Takes any URI libvirt understands, including `qemu+ssh://user@host/system` to
      reach a hypervisor that runs no local agent.
    - **timeout** (`int`, optional): Timeout in seconds. Defaults to `DEFAULT_TIMEOUT`.

    ### Returns
    - **tuple** (`bool`, `str`):
      - `success` (`bool`): True if virsh succeeded, False otherwise.
      - `result` (`str`): Standard output, or an error message that says what to do
        about it.

    ### Notes
    - Always connects read-only. Everything in this library reads, and a read-only
      connection is the only one that works unattended.
    - The URI is bound to its option as `--connect=<uri>`, so a value that starts
      with a dash cannot turn into an option of its own.

    ### Example
    >>> success, stdout = virsh(['list', '--all', '--name'])
    """
    if not shell.which('virsh'):
        return False, (
            'The "virsh" command was not found. It ships with the libvirt client '
            'package ("libvirt-client" on RHEL and SUSE, "libvirt-clients" on '
            'Debian and Ubuntu), which has to be present wherever this runs, not '
            'only on the hypervisor.'
        )

    success, result = shell.shell_exec(
        ['virsh', '--readonly', f'--connect={uri}', *args],
        timeout=timeout,
    )
    if not success:
        return False, result
    stdout, stderr, retc = result
    if retc != 0:
        return False, _explain_virsh_error(stderr, uri)
    return True, stdout
