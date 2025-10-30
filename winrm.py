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
__version__ = '2025103002'

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
        - `WINRM_USERNAME` (`str`): Username.
        - `WINRM_PASSWORD` (`str`): Password.
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
    - On any exception, returns `{'retc': 1, 'stdout': '', 'stderr': <exception text>}`.
    - If neither backend is present, returns an error indicating that no compatible
      remoting library is available.

    ### Example
    >>> # args provides WINRM_* settings (hostname, creds, transport, etc.)
    >>> run_cmd(args, "ipconfig", ["/all"])
    {'retc': 0, 'stdout': 'Windows IP Configuration\\r\\n...','stderr': ''}
    """
    auth = (args.WINRM_USERNAME, args.WINRM_PASSWORD)
    if getattr(args, 'WINRM_DOMAIN', None):
        auth = (f'{args.WINRM_USERNAME}@{args.WINRM_DOMAIN}', args.WINRM_PASSWORD)

    if params is None:
        params = []

    if HAVE_JEA:
        try:
            # translate pywinrm transport -> pypsrp auth/ssl/port
            _transport = (args.WINRM_TRANSPORT or '').lower()
            _auth_map = {
                'kerberos': 'kerberos',
                'negotiate': 'negotiate',
                'ntlm': 'negotiate',   # NTLM is negotiated under "negotiate"
                'credssp': 'credssp',
                'basic': 'basic',
                'plaintext': 'basic',  # basic over HTTP
                'ssl': 'basic',        # basic over HTTPS
            }
            _psrp_auth = _auth_map.get(_transport, 'negotiate')
            _use_ssl = (_transport == 'ssl')
            _port = 5986 if _use_ssl else 5985

            # create PSRP client
            session = Client(
                server=args.WINRM_HOSTNAME,
                username=auth[0],
                password=auth[1],
                auth=_psrp_auth,
                ssl=_use_ssl,
                port=_port,
                cert_validation=True,
            )

            # run native command (not PowerShell script)
            stdout, stderr, rc = session.execute_cmd(cmd, params)

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

    # Neither pypsrp nor pywinrm is available
    return {
        'retc': 1,
        'stdout': '',
        'stderr': 'No compatible remoting library available (pypsrp or pywinrm).',
    }


def run_ps(args, cmd):
    """
    Run a PowerShell script/string on a remote Windows host via WinRM/PSRP and
    return a normalized result dictionary.

    Prefers **pypsrp (PSRP)** if available (best for JEA/PowerShell Remoting);
    otherwise falls back to **pywinrm**. Authentication, transport, and SSL/port
    are derived from the provided `args`.

    ### Parameters
    - **args**: An object (e.g., `argparse.Namespace`) that provides at least:
        - `WINRM_HOSTNAME` (`str`): Target host or IP.
        - `WINRM_USERNAME` (`str`): Username.
        - `WINRM_PASSWORD` (`str`): Password.
        - `WINRM_TRANSPORT` (`str`, optional): Transport (`'negotiate'`, `'kerberos'`,
          `'ntlm'`, `'credssp'`, `'basic'`, `'ssl'`, etc.). Defaults to `'negotiate'`
          if unset.
        - `WINRM_DOMAIN` (`str`, optional): If set, username is sent as `user@domain`.
      (Additional attributes may be honored by the underlying libraries if present.)
    - **cmd** (`str`): PowerShell scriptblock/string to execute remotely.

    ### Returns
    - **dict**: A normalized result with:
        - `retc` (`int`): Return code (`0` if no PowerShell errors were reported).
        - `stdout` (`str`): Captured standard output/text from the script.
        - `stderr` (`str`): Aggregated error/diagnostic output.
          - For **PSRP**: collects entries from the PowerShell *Error* stream
            (human-readable via `to_string()` when available).
          - For **pywinrm**: uses `std_err`; if `retc == 0` and stderr begins with
            `#< CLIXML`, it is suppressed as benign progress noise.

    ### Behavior
    - Maps `WINRM_TRANSPORT` to PSRP auth (`kerberos`, `negotiate`, `credssp`, `basic`)
      and decides SSL/port (5986 for SSL, 5985 otherwise) when using **pypsrp**,
      then executes via `Client.execute_ps()`.
    - Falls back to **pywinrm** and executes via `Session.run_ps()` if pypsrp is not available.
    - On any exception, returns `{'retc': 1, 'stdout': '', 'stderr': <exception text>}`.
    - If neither backend is installed, returns an error indicating that no compatible
      remoting library is available.

    ### Example
    >>> # args must provide WINRM_* settings (hostname, creds, transport, etc.)
    >>> run_ps(args, "Get-Process | Select-Object -First 1 | Format-Table Name,Id -AutoSize")
    {'retc': 0, 'stdout': 'Name    Id\\r\\n----    --\\r\\n...\\r\\n', 'stderr': ''}
    """
    auth = (args.WINRM_USERNAME, args.WINRM_PASSWORD)
    if getattr(args, 'WINRM_DOMAIN', None):
        auth = (f'{args.WINRM_USERNAME}@{args.WINRM_DOMAIN}', args.WINRM_PASSWORD)

    if HAVE_JEA:
        try:
            # translate pywinrm transport -> pypsrp auth/ssl/port
            _transport = (args.WINRM_TRANSPORT or '').lower()
            _auth_map = {
                'kerberos': 'kerberos',
                'negotiate': 'negotiate',
                'ntlm': 'negotiate',   # NTLM is negotiated under "negotiate"
                'credssp': 'credssp',
                'basic': 'basic',
                'plaintext': 'basic',  # basic over HTTP
                'ssl': 'basic',        # basic over HTTPS
            }
            _psrp_auth = _auth_map.get(_transport, 'negotiate')
            _use_ssl = (_transport == 'ssl')
            _port = 5986 if _use_ssl else 5985

            # create PSRP client (like in winrm.Session)
            session = Client(
                server=args.WINRM_HOSTNAME,
                username=auth[0],
                password=auth[1],
                auth=_psrp_auth,
                ssl=_use_ssl,
                port=_port,
                cert_validation=True,
            )

            # run PowerShell
            stdout, streams, had_errors = session.execute_ps(cmd)

            # stdout is already a string; stderr from PSRP error stream(s)
            stderr_lines = []
            for err in getattr(streams, 'error', []):
                # err.to_string() gives a readable message with category/position if available
                try:
                    stderr_lines.append(err.to_string())
                except Exception:
                    # fallback to message text
                    msg = getattr(err, 'message', None) or str(err)
                    stderr_lines.append(str(msg))
            stderr = '\n'.join(stderr_lines)

            result = {
                'retc': 0 if not had_errors else 1,
                'stdout': txt.to_text(stdout),
                'stderr': txt.to_text(stderr),
            }
            return result
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

            # run PowerShell
            result = session.run_ps(cmd)

            result = {
                'retc': result.status_code,
                'stdout': txt.to_text(result.std_out),
                'stderr': txt.to_text(result.std_err),
            }
            # if `result.status_code == 0`, ignore stderr that starts with `#< CLIXML`
            # (it's just progress noise)
            if result['retc'] == 0 and result['stderr'].startswith('#< CLIXML'):
                result['stderr'] = ''
            return result
        except Exception as e:
            return {
                'retc': 1,
                'stdout': '',
                'stderr': txt.exception2text(e),
            }

    # Neither pypsrp nor pywinrm is available
    return {
        'retc': 1,
        'stdout': '',
        'stderr': 'No compatible remoting library available (pypsrp or pywinrm).',
    }
