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
consumers do not have to assemble (and quote) them by hand. All functions return
the same `(success, result)` shape as `lib.shell.shell_exec()`.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026060601'

from . import shell


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
    Assemble the option string shared by `ssh` and `scp`.

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
    - **str**: The assembled option string (may be empty).

    ### Example
    >>> build_options(identity=['~/.ssh/id_ed25519'], batch_mode=True)
    "-i '~/.ssh/id_ed25519' -o BatchMode=yes"
    """
    parts = []
    if ipv4:
        parts.append('-4')
    if ipv6:
        parts.append('-6')
    if configfile:
        parts.append(f"-F '{configfile}'")
    for item in identity or []:
        parts.append(f"-i '{item}'")
    for item in ssh_option or []:
        parts.append(f"-o '{item}'")
    if quiet:
        parts.append('-q')
    if batch_mode:
        parts.append('-o BatchMode=yes')
    if log_level:
        parts.append(f'-o LogLevel={log_level}')
    if connect_timeout is not None:
        parts.append(f'-o ConnectTimeout={connect_timeout}')
    return ' '.join(parts)


def target(host, username=None):
    """
    Build the `user@host` (or bare `host`) token, both parts single-quoted.

    Leaving `username` empty lets `ssh`/`scp` determine the user from
    `~/.ssh/config` (or fall back to the current local user), so host aliases
    keep working.

    ### Parameters
    - **host** (`str`): Hostname, IP address or `~/.ssh/config` alias.
    - **username** (`str`, optional): Login user. If falsy, omitted.

    ### Returns
    - **str**: e.g. `'root'@'host'` or `'host'`.
    """
    if username:
        return f"'{username}'@'{host}'"
    return f"'{host}'"


def run(
    host,
    command,
    username=None,
    port=None,
    options='',
    disable_pseudo_terminal=False,
    password=None,
    timeout=None,
    use_shell=True,
):
    """
    Run `command` on `host` over SSH.

    The remote command is single-quoted so the local shell does not touch it; the
    remote shell expands `~`, `$VAR`, `&&` etc.

    ### Parameters
    - **host** (`str`): Target host (name, IP or alias).
    - **command** (`str`): Command to run on the remote host.
    - **username** (`str`, optional): Login user (see `target()`).
    - **port** (`int` or `str`, optional): Remote port (`-p`).
    - **options** (`str`, optional): Option string from `build_options()`.
    - **disable_pseudo_terminal** (`bool`, optional): Add `-T`.
    - **password** (`str`, optional): If set, prefix with `sshpass -p` (requires
      `sshpass`; the password is visible in the process list).
    - **timeout** (`int`, optional): Overall timeout in seconds.
    - **use_shell** (`bool`, optional): Execute the local command line through a
      shell. Defaults to `True`, which is required for remote snippets that use
      loops, pipes or `$`-expansions.

    ### Returns
    - **tuple**: `(True, (stdout, stderr, retc))` on success, else
      `(False, error_message)`. Same contract as `lib.shell.shell_exec()`.
    """
    cmd = (
        f'ssh {options}'
        f' {f"-p {port}" if port else ""}'
        f' {"-T" if disable_pseudo_terminal else ""}'
        f" {target(host, username)} '{command}'"
    )
    cmd = ' '.join(cmd.split())
    if password:
        cmd = f'sshpass -p {password} {cmd}'
    return shell.shell_exec(cmd, shell=use_shell, timeout=timeout)


def scp(
    host,
    local,
    remote,
    username=None,
    port=None,
    options='',
    password=None,
    timeout=None,
    use_shell=True,
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
    - **options** (`str`, optional): Option string from `build_options()`.
    - **password** (`str`, optional): If set, prefix with `sshpass -p`.
    - **timeout** (`int`, optional): Overall timeout in seconds.
    - **use_shell** (`bool`, optional): Execute through a shell. Defaults to `True`.
    - **recursive** (`bool`, optional): Copy a directory tree (`-r`), preserving
      modes (`-p`). Useful when the target lacks `tar`. Defaults to `False`.

    ### Returns
    - **tuple**: `(True, (stdout, stderr, retc))` on success, else
      `(False, error_message)`.
    """
    cmd = (
        f'scp {"-r -p" if recursive else ""} {options}'
        f' {f"-P {port}" if port else ""}'
        f" '{local}' {target(host, username)}:{remote}"
    )
    cmd = ' '.join(cmd.split())
    if password:
        cmd = f'sshpass -p {password} {cmd}'
    return shell.shell_exec(cmd, shell=use_shell, timeout=timeout)


def rsync(
    host,
    local,
    remote,
    username=None,
    port=None,
    options='',
    password=None,
    timeout=None,
    use_shell=True,
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
    - **options** (`str`, optional): ssh option string from `build_options()`,
      passed through to rsync via `--rsh`.
    - **password** (`str`, optional): If set, prefix with `sshpass -p`.
    - **timeout** (`int`, optional): Overall timeout in seconds.
    - **use_shell** (`bool`, optional): Execute through a shell. Defaults to
      `True`.
    - **sudo** (`bool`, optional): Run the remote rsync via `sudo`
      (`--rsync-path="sudo rsync"`), so files land root-owned and writes are
      privileged. Requires password-less sudo on the target. Defaults to `False`.

    ### Returns
    - **tuple**: `(True, (stdout, stderr, retc))` on success, else
      `(False, error_message)`.
    """
    rsh = f'ssh {options}' + (f' -p {port}' if port else '')
    rsync_path = "--rsync-path='sudo rsync'" if sudo else ''
    cmd = (
        'rsync --archive'
        f' {rsync_path}'
        f' --rsh="{rsh}"'
        f" '{local}/' {target(host, username)}:{remote}/"
    )
    cmd = ' '.join(cmd.split())
    if password:
        cmd = f'sshpass -p {password} {cmd}'
    return shell.shell_exec(cmd, shell=use_shell, timeout=timeout)
