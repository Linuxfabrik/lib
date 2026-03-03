#!/usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library collects some Microsoft WinRM related functions.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026030301'

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

    ### Parameters
    - **args**: Object with `WINRM_USERNAME`,
      `WINRM_PASSWORD`, `WINRM_TRANSPORT`, and optionally
      `WINRM_DOMAIN`.

    ### Returns
    - **tuple**: `(username, password)` suitable for
      pypsrp or pywinrm.
    """
    username = getattr(args, 'WINRM_USERNAME', None)
    password = getattr(args, 'WINRM_PASSWORD', None)
    transport = (
        getattr(args, 'WINRM_TRANSPORT', None) or ''
    ).lower()
    if transport in ('kerberos', 'negotiate') and (
        not username or not password
    ):
        return (None, None)
    if getattr(args, 'WINRM_DOMAIN', None):
        return (f'{username}@{args.WINRM_DOMAIN}', password)
    return (username, password)


def _map_transport(args):
    """
    Derive PSRP auth method, SSL flag, and port from `args`.

    ### Parameters
    - **args**: Object with `WINRM_TRANSPORT`.

    ### Returns
    - **tuple**: `(psrp_auth, use_ssl, port)`.
    """
    transport = (
        getattr(args, 'WINRM_TRANSPORT', None) or ''
    ).lower()
    psrp_auth = _AUTH_MAP.get(transport, 'negotiate')
    use_ssl = (transport == 'ssl')
    port = 5986 if use_ssl else 5985
    return (psrp_auth, use_ssl, port)


def run_cmd(args, cmd, params=None):
    """
    Run a native command on a remote Windows host via WinRM/PSRP and return a
    normalized result dictionary.

    Prefers **pypsrp (PSRP)** if available (for JEA/PowerShell Remoting
    compatibility); otherwise falls back to **pywinrm**. Authentication,
    transport and SSL/port selection are derived from the provided `args`.

    ### Parameters
    - **args**: An object (e.g., `argparse.Namespace`) that provides at least:
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
    - **cmd** (`str`): The executable/command to run remotely (native command, not a PowerShell
       script block).
    - **params** (`list[str]`, optional): Positional arguments passed to the command. Defaults
       to `[]`.

    ### Returns
    - **dict**: A normalized result with:
        - `retc` (`int`): Process return code (`0` on success).
        - `stdout` (`str`): Captured standard output (text).
        - `stderr` (`str`): Captured standard error (text).

    ### Behavior
    - If **pypsrp** is available, maps `WINRM_TRANSPORT` to an appropriate PSRP auth
      and chooses SSL/port (5986 for SSL, 5985 otherwise), then executes the command
      via `Client.execute_cmd()`.
    - If pypsrp is unavailable but **pywinrm** is installed, executes via
      `Session.run_cmd()`.
    - For Kerberos authentication: if `WINRM_USERNAME` and `WINRM_PASSWORD` are not provided
      (or are empty/None), the function will attempt to use existing Kerberos credentials
      from the credential cache (obtained via `kinit`).
    - On any exception, returns `{'retc': 1, 'stdout': '', 'stderr': <exception text>}`.
    - If neither backend is present, returns an error indicating that no compatible
      remoting library is available.

    ### Example
    >>> # With explicit credentials:
    >>> run_cmd(args, "ipconfig", ["/all"])
    {'retc': 0, 'stdout': 'Windows IP Configuration\\r\\n...','stderr': ''}
    >>> # With Kerberos using kinit credentials (username/password can be None):
    >>> run_cmd(args, "ipconfig", ["/all"])
    {'retc': 0, 'stdout': 'Windows IP Configuration\\r\\n...','stderr': ''}
    """
    auth = _build_auth(args)
    if params is None:
        params = []

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

            stdout, stderr, rc = session.execute_cmd(
                cmd,
                args=params,
            )
            return {
                'retc': rc,
                'stdout': txt.to_text(stdout),
                'stderr': txt.to_text(stderr),
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

            result = session.run_cmd(cmd, params)
            return {
                'retc': result.status_code,
                'stdout': txt.to_text(result.std_out),
                'stderr': txt.to_text(result.std_err),
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
        'stderr': 'No compatible remoting library available '
                 '(pypsrp or pywinrm).',
    }


def _quote_ps_value(value):
    """Escape a value for use in a PowerShell command string.

    Single-quotes the value, doubling any embedded single
    quotes (`'` becomes `''`).

    ### Parameters
    - **value**: The value to quote (converted to `str`).

    ### Returns
    - **str**: A safely quoted PowerShell string literal.
    """
    return "'{}'".format(str(value).replace("'", "''"))


def run_ps(args, cmd, params=None):
    """
    Run PowerShell on a remote Windows host via WinRM/PSRP
    and return a normalized result dictionary.

    Prefers **pypsrp (PSRP)** if available (best for
    JEA/PowerShell Remoting); otherwise falls back to
    **pywinrm**.

    ### Parameters
    - **args**: Object (e.g. `argparse.Namespace`) with:
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
    - **cmd** (`str`): What to execute remotely. Meaning
      depends on `params`:
        - `params is None` — `cmd` is an arbitrary
          PowerShell script (pipelines, expressions, etc.)
          executed via `add_script()`.
        - `params` given (`list` or `dict`) — `cmd` is a
          single cmdlet name executed via `add_cmdlet()`
          (optimal for JEA allow/deny).
    - **params** (`list[str]`, `dict`, or `None`):
        - `None` (default) — no params; `cmd` is run as a
          script.
        - `list[str]` — positional arguments added via
          `add_argument()`.
        - `dict` — named parameters added via
          `add_parameter(name, value)`.

    ### Returns
    - **dict**: Normalized result with:
        - `retc` (`int`): `0` if no errors.
        - `stdout` (`str`): Captured output.
        - `stderr` (`str`): Error/diagnostic output.
          For **pywinrm**: CLIXML progress noise is
          suppressed when `retc == 0`.

    ### Example
    Pipeline (params=None, uses add_script):
    >>> run_ps(args, "Get-Process | Select -First 1")

    Positional params (uses add_cmdlet + add_argument):
    >>> run_ps(args, "Get-Service", ["WinRM"])

    Named params (uses add_cmdlet + add_parameter):
    >>> run_ps(
    ...     args,
    ...     "Get-WmiObject",
    ...     {"Class": "Win32_OperatingSystem"},
    ... )
    """
    auth = _build_auth(args)

    configuration_name = getattr(
        args, 'WINRM_CONFIGURATION_NAME', None,
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

            _psrp_auth, _use_ssl, _port = (
                _map_transport(args)
            )

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
                configuration_name=(
                    configuration_name
                    or 'Microsoft.PowerShell'
                ),
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

            stdout = '\n'.join(
                str(o) for o in output
            )

            stderr_lines = []
            for err in ps.streams.error:
                try:
                    stderr_lines.append(
                        err.to_string(),
                    )
                except Exception:
                    msg = (
                        getattr(err, 'message', None)
                        or str(err)
                    )
                    stderr_lines.append(str(msg))
            stderr = '\n'.join(stderr_lines)

            return {
                'retc': 0 if not ps.had_errors else 1,
                'stdout': txt.to_text(stdout),
                'stderr': txt.to_text(stderr),
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

            if params is not None:
                if isinstance(params, dict):
                    param_str = ' '.join(
                        '-{} {}'.format(
                            k, _quote_ps_value(v),
                        )
                        for k, v in params.items()
                    )
                    ps_cmd = '{} {}'.format(
                        cmd, param_str,
                    )
                else:
                    ps_cmd = '{} {}'.format(
                        cmd,
                        ' '.join(str(p) for p in params),
                    ) if params else cmd
            else:
                ps_cmd = cmd

            result = session.run_ps(ps_cmd)

            result = {
                'retc': result.status_code,
                'stdout': txt.to_text(result.std_out),
                'stderr': txt.to_text(result.std_err),
            }
            if (
                result['retc'] == 0
                and result['stderr'].startswith(
                    '#< CLIXML',
                )
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
        'stderr': 'No compatible remoting library '
                 'available (pypsrp or pywinrm).',
    }