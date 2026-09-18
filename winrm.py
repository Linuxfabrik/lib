#!/usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library collects some Microsoft WinRM related functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026091801'

import base64
import re

try:
    import winrm

    HAVE_WINRM = True
except ImportError:
    HAVE_WINRM = False

try:
    from pypsrp.client import Client

    HAVE_JEA = True
except ImportError:
    HAVE_JEA = False

from . import txt

_AUTH_MAP = {
    'kerberos': 'kerberos',
    'negotiate': 'negotiate',
    'ntlm': 'ntlm',
    'credssp': 'credssp',
    'basic': 'basic',
    'plaintext': 'basic',
    'ssl': 'basic',
}


def _build_auth(args):
    """
    Build a `(username, password)` tuple from `args`.

    For Kerberos/negotiate transports with missing credentials,
    returns `(None, None)` so the library falls back to the
    Kerberos credential cache (`kinit`). Otherwise prepends
    `WINRM_DOMAIN` to the username when set.

    Parameters
    ----------
    args
        Object with `WINRM_USERNAME`,
        `WINRM_PASSWORD`, `WINRM_TRANSPORT`, and optionally
        `WINRM_DOMAIN`.

    Returns
    -------
    tuple
        `(username, password)` suitable for
        pypsrp or pywinrm.
    """
    username = getattr(args, 'WINRM_USERNAME', None)
    password = getattr(args, 'WINRM_PASSWORD', None)
    transport = (getattr(args, 'WINRM_TRANSPORT', None) or '').lower()
    if transport in ('kerberos', 'negotiate') and (not username or not password):
        return (None, None)
    if getattr(args, 'WINRM_DOMAIN', None):
        return (f'{username}@{args.WINRM_DOMAIN}', password)
    return (username, password)


def _map_transport(args):
    """
    Derive PSRP auth method, SSL flag, and port from `args`.

    Parameters
    ----------
    args
        Object with `WINRM_TRANSPORT`.

    Returns
    -------
    tuple
        `(psrp_auth, use_ssl, port)`.
    """
    transport = (getattr(args, 'WINRM_TRANSPORT', None) or '').lower()
    psrp_auth = _AUTH_MAP.get(transport, 'negotiate')
    use_ssl = transport == 'ssl'
    port = 5986 if use_ssl else 5985
    return (psrp_auth, use_ssl, port)


def _ps_literal(value):
    """
    Return a PowerShell expression that evaluates to `str(value)`, whatever it holds.

    The value travels base64-encoded and is decoded on the remote host, so it never
    appears in the script text. Quoting cannot give that guarantee: PowerShell closes a
    single-quoted string on the typographic quotes U+2018 to U+201B as well, so a value
    carrying one of them ends the literal and turns the rest into script, however the
    ASCII quote is escaped. Verified against Windows PowerShell 5.1 on Windows Server
    2025 and PowerShell 7.6 on RHEL 9. The base64 alphabet contains no quote and no
    operator, which fixes the boundaries of the value before the value is known.

    Parameters
    ----------
    value
        The value (converted to `str`).

    Returns
    -------
    str
        A parenthesized expression, usable as an argument or parameter value.
    """
    encoded = txt.to_text(base64.b64encode(txt.to_bytes(str(value))))
    return (
        f"([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}')))"
    )


def _native_call(cmd, params):
    """
    Return a command line that runs `cmd` with `params` without `cmd.exe` parsing them.

    WinRS hands a command line to `cmd.exe`, where `&`, `|` and `>` in an argument start
    a second command. The command line returned here holds nothing but base64: it starts
    PowerShell with an encoded script that calls `cmd` with each argument decoded from
    its own literal. A program that cannot be started yields return code 1 and the
    reason on stderr, as it would from `cmd.exe`, instead of `exit $null` reporting
    success.

    Parameters
    ----------
    cmd : str
        The program to run.
    params : list
        Its arguments (each converted to `str`).

    Returns
    -------
    str
        The command line to hand to WinRS.
    """
    call = ' '.join(['&', *(_ps_literal(item) for item in [cmd, *params])])
    script = (
        "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; "
        f'try {{ {call} }} '
        'catch { [Console]::Error.WriteLine($_.ToString()); exit 1 }; '
        'exit $LASTEXITCODE'
    )
    encoded = txt.to_text(base64.b64encode(txt.to_bytes(script, encoding='utf-16-le')))
    return f'powershell.exe -NoProfile -NonInteractive -EncodedCommand {encoded}'


def run_cmd(args, cmd, params=None):
    """
    Run a native command on a remote Windows host via WinRM/PSRP and return a
    normalized result dictionary.

    Prefers **pypsrp (PSRP)** if available (for JEA/PowerShell Remoting
    compatibility); otherwise falls back to **pywinrm**. Authentication,
    transport and SSL/port selection are derived from the provided `args`.

    Parameters
    ----------
    args
        An object (e.g., `argparse.Namespace`) that provides at least:

          - `WINRM_HOSTNAME` (`str`): Target host or IP.
          - `WINRM_USERNAME` (`str`, optional): Username. If `None` or empty when using
            Kerberos transport, will use existing Kerberos credentials from credential cache
            (e.g., obtained via `kinit`).
          - `WINRM_PASSWORD` (`str`, optional): Password. If `None` or empty when using
            Kerberos transport, will use existing Kerberos credentials from credential cache.
          - `WINRM_TRANSPORT` (`str`, optional): Transport (e.g., `'negotiate'`, `'kerberos'`,
            `'ntlm'`, `'credssp'`, `'basic'`, `'ssl'`). Defaults to `'negotiate'` if unset.
          - `WINRM_DOMAIN` (`str`, optional): If set, username is sent as `user@domain`.
        (Additional fields may be honored by the underlying libraries if present.)
    cmd : str
        The executable/command to run remotely (native command, not a PowerShell
         script block). Without `params` it is handed to `cmd.exe` as it stands, so it
         must not contain untrusted data.
    params : list[str], optional
        Positional arguments passed to the command. Each
         one reaches the program as a single argument, whatever it contains: `cmd.exe`
         never parses them. Defaults to `[]`.

    Returns
    -------
    dict
        A normalized result with:

          - `retc` (`int`): Process return code (`0` on success).
          - `stdout` (`str`): Captured standard output (text).
          - `stderr` (`str`): Captured standard error (text).

    Notes
    -----
    - If **pypsrp** is available, maps `WINRM_TRANSPORT` to an appropriate PSRP auth
      and chooses SSL/port (5986 for SSL, 5985 otherwise), then executes the command
      via `Client.execute_cmd()`.
    - If pypsrp is unavailable but **pywinrm** is installed, executes via
      `Session.run_cmd()`.
    - With `params`, the command runs through an encoded PowerShell call rather than
      through `cmd.exe`, which would read `&`, `|` or `>` in an argument as the start
      of another command. Return code, stdout and stderr are those of the program. A
      `.bat` or `.cmd` file is still interpreted by `cmd.exe`, arguments included.
    - For Kerberos authentication: if `WINRM_USERNAME` and `WINRM_PASSWORD` are not provided
      (or are empty/None), the function will attempt to use existing Kerberos credentials
      from the credential cache (obtained via `kinit`).
    - On any exception, returns `{'retc': 1, 'stdout': '', 'stderr': <exception text>}`.
    - If neither backend is present, returns an error indicating that no compatible
      remoting library is available.

    Examples
    --------
    >>> # With explicit credentials:
    >>> run_cmd(args, 'ipconfig', ['/all'])
    {'retc': 0, 'stdout': 'Windows IP Configuration\\r\\n...','stderr': ''}
    >>> # With Kerberos using kinit credentials (username/password can be None):
    >>> run_cmd(args, 'ipconfig', ['/all'])
    {'retc': 0, 'stdout': 'Windows IP Configuration\\r\\n...','stderr': ''}
    """
    auth = _build_auth(args)
    command = _native_call(cmd, params) if params else cmd

    if HAVE_JEA:
        try:
            _psrp_auth, _use_ssl, _port = _map_transport(args)
            session = Client(
                server=args.WINRM_HOSTNAME,
                username=auth[0],
                password=auth[1],
                auth=_psrp_auth,
                ssl=_use_ssl,
                port=_port,
                cert_validation=True,
            )

            stdout, stderr, rc = session.execute_cmd(command)
            return {
                'retc': rc,
                'stdout': txt.to_text(stdout, errors='strict_or_latin1'),
                'stderr': txt.to_text(stderr, errors='strict_or_latin1'),
            }
        except Exception as e:
            return {
                'retc': 1,
                'stdout': '',
                'stderr': txt.exception2text(e),
            }

    if HAVE_WINRM:
        try:
            session = winrm.Session(
                args.WINRM_HOSTNAME,
                auth=auth,
                transport=args.WINRM_TRANSPORT,
            )

            result = session.run_cmd(command)
            return {
                'retc': result.status_code,
                'stdout': txt.to_text(result.std_out, errors='strict_or_latin1'),
                'stderr': txt.to_text(result.std_err, errors='strict_or_latin1'),
            }
        except Exception as e:
            return {
                'retc': 1,
                'stdout': '',
                'stderr': txt.exception2text(e),
            }

    return {
        'retc': 1,
        'stdout': '',
        'stderr': 'No compatible remoting library available (pypsrp or pywinrm).',
    }


# What PowerShell accepts as a parameter name. A name is spliced into the script text as
# it stands, so anything else could carry script of its own.
_PS_PARAMETER_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def run_ps(args, cmd, params=None):
    """
    Run PowerShell on a remote Windows host via WinRM/PSRP
    and return a normalized result dictionary.

    Prefers **pypsrp (PSRP)** if available (best for
    JEA/PowerShell Remoting); otherwise falls back to
    **pywinrm**.

    Parameters
    ----------
    args
        Object (e.g. `argparse.Namespace`) with:

          - `WINRM_HOSTNAME` (`str`): Target host or IP.
          - `WINRM_USERNAME` (`str`, optional): Username.
            If empty with Kerberos transport, the credential
            cache (`kinit`) is used.
          - `WINRM_PASSWORD` (`str`, optional): Password.
            Same Kerberos fallback as username.
          - `WINRM_TRANSPORT` (`str`, optional): Transport
            (e.g. `'negotiate'`, `'kerberos'`, `'ntlm'`,
            `'credssp'`, `'basic'`, `'ssl'`).
            Defaults to `'negotiate'`.
          - `WINRM_DOMAIN` (`str`, optional): If set,
            username is sent as `user@domain`.
          - `WINRM_CONFIGURATION_NAME` (`str`, optional):
            JEA endpoint name. Defaults to
            `'Microsoft.PowerShell'`. Only with **pypsrp**.
    cmd : str
        What to execute remotely. Meaning
        depends on `params`:

          - `params is None` — `cmd` is an arbitrary
            PowerShell script (pipelines, expressions, etc.)
            executed via `add_script()`.
          - `params` given (`list` or `dict`) — `cmd` is a
            single cmdlet name executed via `add_cmdlet()`
            (optimal for JEA allow/deny).
    params : list[str], dict, or None
          - `None` (default) — no params; `cmd` is run as a
            script.
          - `list[str]` — positional arguments added via
            `add_argument()`.
          - `dict` — named parameters added via
            `add_parameter(name, value)`.
          Values may be untrusted: each one reaches the cmdlet
          as a single value, whatever it contains. With
          **pywinrm** every value is converted to `str`, and a
          parameter name that PowerShell would not accept is
          refused with `retc` 1.

    Returns
    -------
    dict
        Normalized result with:

          - `retc` (`int`): `0` if no errors.
          - `stdout` (`str`): Captured output.
          - `stderr` (`str`): Error/diagnostic output.
            For **pywinrm**: CLIXML progress noise is
            suppressed when `retc == 0`.

    Examples
    --------
    Pipeline (params=None, uses add_script):
    >>> run_ps(args, 'Get-Process | Select -First 1')

    Positional params (uses add_cmdlet + add_argument):
    >>> run_ps(args, 'Get-Service', ['WinRM'])

    Named params (uses add_cmdlet + add_parameter):
    >>> run_ps(
    ...     args,
    ...     'Get-WmiObject',
    ...     {'Class': 'Win32_OperatingSystem'},
    ... )
    """
    auth = _build_auth(args)

    configuration_name = getattr(
        args,
        'WINRM_CONFIGURATION_NAME',
        None,
    )
    if configuration_name and not HAVE_JEA:
        return {
            'retc': 1,
            'stdout': '',
            'stderr': 'WINRM_CONFIGURATION_NAME requires '
            'pypsrp (JEA). Install pypsrp or '
            'unset '
            '--winrm-configuration-name.',
        }

    if HAVE_JEA:
        try:
            from pypsrp.powershell import (
                PowerShell,
                RunspacePool,
            )
            from pypsrp.wsman import WSMan

            _psrp_auth, _use_ssl, _port = _map_transport(args)

            wsman = WSMan(
                server=args.WINRM_HOSTNAME,
                username=auth[0],
                password=auth[1],
                auth=_psrp_auth,
                ssl=_use_ssl,
                port=_port,
                cert_validation=True,
            )

            with RunspacePool(
                wsman,
                configuration_name=(configuration_name or 'Microsoft.PowerShell'),
            ) as pool:
                ps = PowerShell(pool)
                if params is not None:
                    ps.add_cmdlet(cmd)
                    if isinstance(params, dict):
                        for name, value in params.items():
                            ps.add_parameter(name, value)
                    else:
                        for param in params:
                            ps.add_argument(param)
                else:
                    ps.add_script(cmd)
                output = ps.invoke()

            stdout = '\n'.join(str(o) for o in output)

            stderr_lines = []
            for err in ps.streams.error:
                try:
                    stderr_lines.append(
                        err.to_string(),
                    )
                except Exception:
                    msg = getattr(err, 'message', None) or str(err)
                    stderr_lines.append(str(msg))
            stderr = '\n'.join(stderr_lines)

            return {
                'retc': 0 if not ps.had_errors else 1,
                'stdout': txt.to_text(stdout, errors='strict_or_latin1'),
                'stderr': txt.to_text(stderr, errors='strict_or_latin1'),
            }
        except Exception as e:
            return {
                'retc': 1,
                'stdout': '',
                'stderr': txt.exception2text(e),
            }

    if HAVE_WINRM:
        try:
            session = winrm.Session(
                args.WINRM_HOSTNAME,
                auth=auth,
                transport=args.WINRM_TRANSPORT,
            )

            # pywinrm only runs script text, so the structured call pypsrp makes is
            # rebuilt here: the command and every value are decoded from literals of
            # their own, and a parameter name has to be one before it is spliced in.
            if params is not None:
                if isinstance(params, dict):
                    for name in params:
                        if not _PS_PARAMETER_NAME.match(str(name)):
                            return {
                                'retc': 1,
                                'stdout': '',
                                'stderr': f'Invalid PowerShell parameter name: {name}',
                            }
                    arguments = [
                        f'-{name} {_ps_literal(value)}'
                        for name, value in params.items()
                    ]
                else:
                    arguments = [_ps_literal(param) for param in params]
                ps_cmd = ' '.join(['&', _ps_literal(cmd), *arguments])
            else:
                ps_cmd = cmd

            result = session.run_ps(ps_cmd)

            result = {
                'retc': result.status_code,
                'stdout': txt.to_text(result.std_out, errors='strict_or_latin1'),
                'stderr': txt.to_text(result.std_err, errors='strict_or_latin1'),
            }
            if result['retc'] == 0 and result['stderr'].startswith(
                '#< CLIXML',
            ):
                result['stderr'] = ''
            return result
        except Exception as e:
            return {
                'retc': 1,
                'stdout': '',
                'stderr': txt.exception2text(e),
            }

    return {
        'retc': 1,
        'stdout': '',
        'stderr': 'No compatible remoting library available (pypsrp or pywinrm).',
    }
