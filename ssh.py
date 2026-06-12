#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst


"""Run commands and copy files over SSH.

Builds and executes `ssh` and `scp` command lines from individual options, so
consumers do not have to assemble them by hand. Commands are built as argument
lists (argv) and run without a local shell, so option and target values are never
subject to local shell interpretation. All functions return the same
`(success, result)` shape as `lib.shell.shell_exec()`.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026061201'

from . import shell


def _check_target(host, username):
    """Reject a host or username that ssh could read as an option (leading `-`),
    for example `-oProxyCommand=...`. Returns `(True, None)` when both are safe,
    else `(False, error_message)`."""
    for label, value in (('host', host), ('username', username)):
        ok, msg = shell.safe_cli_value(value, f'ssh {label}')
        if not ok:
            return False, msg
    return True, None


def build_options(
    configfile=None,
    identity=None,
    ssh_option=None,
    ipv4=False,
    ipv6=False,
    quiet=False,
    batch_mode=False,
    connect_timeout=None,
    log_level=None,
):
    """
    Assemble the option tokens shared by `ssh` and `scp`.

    The result intentionally omits the port, because `ssh` uses `-p` while `scp`
    uses `-P`; `run()` and `scp()` add the port themselves.

    ### Parameters
    - **configfile** (`str`, optional): Path passed as `-F`.
    - **identity** (`list`, optional): Identity files, each passed as `-i`.
    - **ssh_option** (`list`, optional): Raw options, each passed as `-o`.
    - **ipv4** (`bool`, optional): Force IPv4 (`-4`).
    - **ipv6** (`bool`, optional): Force IPv6 (`-6`).
    - **quiet** (`bool`, optional): Quiet mode (`-q`).
    - **batch_mode** (`bool`, optional): Add `-o BatchMode=yes` to never prompt
      for a password or passphrase (non-interactive runs).
    - **connect_timeout** (`int`, optional): Seconds for `-o ConnectTimeout`.
    - **log_level** (`str`, optional): Value for `-o LogLevel` (e.g. `ERROR` to
      suppress the "Permanently added to known_hosts" warning).

    ### Returns
    - **list**: The assembled option tokens (may be empty).

    ### Example
    >>> build_options(identity=['~/.ssh/id_ed25519'], batch_mode=True)
    ['-i', '~/.ssh/id_ed25519', '-o', 'BatchMode=yes']
    """
    parts = []
    if ipv4:
        parts.append('-4')
    if ipv6:
        parts.append('-6')
    if configfile:
        parts += ['-F', configfile]
    for item in identity or []:
        parts += ['-i', item]
    for item in ssh_option or []:
        parts += ['-o', item]
    if quiet:
        parts.append('-q')
    if batch_mode:
        parts += ['-o', 'BatchMode=yes']
    if log_level:
        parts += ['-o', f'LogLevel={log_level}']
    if connect_timeout is not None:
        parts += ['-o', f'ConnectTimeout={connect_timeout}']
    return parts


def target(host, username=None):
    """
    Build the `user@host` (or bare `host`) token.

    Leaving `username` empty lets `ssh`/`scp` determine the user from
    `~/.ssh/config` (or fall back to the current local user), so host aliases
    keep working.

    ### Parameters
    - **host** (`str`): Hostname, IP address or `~/.ssh/config` alias.
    - **username** (`str`, optional): Login user. If falsy, omitted.

    ### Returns
    - **str**: e.g. `root@host` or `host`.
    """
    if username:
        return f'{username}@{host}'
    return host


def run(
    host,
    command,
    username=None,
    port=None,
    options=None,
    disable_pseudo_terminal=False,
    password=None,
    timeout=None,
):
    """
    Run `command` on `host` over SSH.

    The local command line is built as an argv list and run without a local
    shell, so `host`, `username`, `port` and `options` are passed verbatim. The
    remote `command` is sent to the host as a single argument; the remote shell
    expands `~`, `$VAR`, `&&`, pipes etc.

    ### Parameters
    - **host** (`str`): Target host (name, IP or alias).
    - **command** (`str`): Command to run on the remote host.
    - **username** (`str`, optional): Login user (see `target()`).
    - **port** (`int` or `str`, optional): Remote port (`-p`).
    - **options** (`list`, optional): Option tokens from `build_options()`.
    - **disable_pseudo_terminal** (`bool`, optional): Add `-T`.
    - **password** (`str`, optional): If set, prefix with `sshpass -p` (requires
      `sshpass`; the password is visible in the process list).
    - **timeout** (`int`, optional): Overall timeout in seconds.

    ### Returns
    - **tuple**: `(True, (stdout, stderr, retc))` on success, else
      `(False, error_message)`. Same contract as `lib.shell.shell_exec()`.
    """
    ok, msg = _check_target(host, username)
    if not ok:
        return False, msg
    cmd = ['ssh', *(options or [])]
    if port:
        cmd += ['-p', str(port)]
    if disable_pseudo_terminal:
        cmd.append('-T')
    cmd += [target(host, username), command]
    if password:
        cmd = ['sshpass', '-p', password, *cmd]
    return shell.shell_exec(cmd, timeout=timeout)


def scp(
    host,
    local,
    remote,
    username=None,
    port=None,
    options=None,
    password=None,
    timeout=None,
    recursive=False,
):
    """
    Copy the local path `local` to `remote` on `host` via scp.

    scp shares ssh's options except that the port flag is `-P`, not `-p`.

    ### Parameters
    - **host** (`str`): Target host (name, IP or alias).
    - **local** (`str`): Local source path (a directory if `recursive=True`).
    - **remote** (`str`): Remote destination path (relative paths are resolved
      against the login home).
    - **username** (`str`, optional): Login user (see `target()`).
    - **port** (`int` or `str`, optional): Remote port (`-P`).
    - **options** (`list`, optional): Option tokens from `build_options()`.
    - **password** (`str`, optional): If set, prefix with `sshpass -p`.
    - **timeout** (`int`, optional): Overall timeout in seconds.
    - **recursive** (`bool`, optional): Copy a directory tree (`-r`), preserving
      modes (`-p`). Useful when the target lacks `tar`. Defaults to `False`.

    ### Returns
    - **tuple**: `(True, (stdout, stderr, retc))` on success, else
      `(False, error_message)`.
    """
    ok, msg = _check_target(host, username)
    if not ok:
        return False, msg
    cmd = ['scp']
    if recursive:
        cmd += ['-r', '-p']
    cmd += options or []
    if port:
        cmd += ['-P', str(port)]
    cmd += [local, f'{target(host, username)}:{remote}']
    if password:
        cmd = ['sshpass', '-p', password, *cmd]
    return shell.shell_exec(cmd, timeout=timeout)


def rsync(
    host,
    local,
    remote,
    username=None,
    port=None,
    options=None,
    password=None,
    timeout=None,
    sudo=False,
):
    """
    Copy a directory tree to `remote` on `host` with rsync over SSH.

    rsync is faster than `scp -r` for trees with many files, but requires rsync
    to be installed on both ends. The contents of `local` are mirrored into
    `remote` (both are treated as directories). Callers that cannot guarantee
    rsync on the target should fall back to `scp(..., recursive=True)`.

    ### Parameters
    - **host** (`str`): Target host (name, IP or alias).
    - **local** (`str`): Local source directory.
    - **remote** (`str`): Remote destination directory.
    - **username** (`str`, optional): Login user (see `target()`).
    - **port** (`int` or `str`, optional): Remote port.
    - **options** (`list`, optional): ssh option tokens from `build_options()`,
      passed through to rsync via `--rsh`.
    - **password** (`str`, optional): If set, prefix with `sshpass -p`.
    - **timeout** (`int`, optional): Overall timeout in seconds.
    - **sudo** (`bool`, optional): Run the remote rsync via `sudo`
      (`--rsync-path="sudo rsync"`), so files land root-owned and writes are
      privileged. Requires password-less sudo on the target. Defaults to `False`.

    ### Returns
    - **tuple**: `(True, (stdout, stderr, retc))` on success, else
      `(False, error_message)`.
    """
    ok, msg = _check_target(host, username)
    if not ok:
        return False, msg
    # rsync's --rsh takes the remote-shell command as a single string.
    rsh = ' '.join(['ssh', *(options or [])]) + (f' -p {port}' if port else '')
    cmd = ['rsync', '--archive']
    if sudo:
        cmd += ['--rsync-path', 'sudo rsync']
    cmd += ['--rsh', rsh, f'{local}/', f'{target(host, username)}:{remote}/']
    if password:
        cmd = ['sshpass', '-p', password, *cmd]
    return shell.shell_exec(cmd, timeout=timeout)
