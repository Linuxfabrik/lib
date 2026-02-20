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
__version__ = '2025111402'

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
    # Determine authentication credentials
    # For Kerberos, allow using existing credentials from kinit
    username = getattr(args, 'WINRM_USERNAME', None)
    password = getattr(args, 'WINRM_PASSWORD', None)

    # Check if we should use Kerberos with existing credentials
    _transport = (getattr(args, 'WINRM_TRANSPORT', None) or '').lower()
    use_kerberos_cache = (_transport in ['kerberos', 'negotiate']) and (not username or not password)

    if use_kerberos_cache:
        # Use None for username/password to let Kerberos use credential cache
        auth = (None, None)
    else:
        # Use provided credentials
        auth = (username, password)
        if getattr(args, 'WINRM_DOMAIN', None):
            auth = (f'{username}@{args.WINRM_DOMAIN}', password)

    if params is None:
        params = []

    if HAVE_JEA:
        try:
            # translate pywinrm transport -> pypsrp auth/ssl/port
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

            stdout, stderr, rc = session.execute_cmd(cmd, args=params)
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


def run_ps(args, cmd, params=None):
    """
    Run a PowerShell cmdlet on a remote Windows host via WinRM/PSRP and
    return a normalized result dictionary.

    Prefers **pypsrp (PSRP)** if available (best for JEA/PowerShell Remoting);
    otherwise falls back to **pywinrm**. Authentication, transport, and SSL/port
    are derived from the provided `args`.

    ### Parameters
    - **args**: An object (e.g., `argparse.Namespace`) that provides at least:
        - `WINRM_HOSTNAME` (`str`): Target host or IP.
        - `WINRM_USERNAME` (`str`, optional): Username. If `None` or empty when using
          Kerberos transport, will use existing Kerberos credentials from credential cache
          (e.g., obtained via `kinit`).
        - `WINRM_PASSWORD` (`str`, optional): Password. If `None` or empty when using
          Kerberos transport, will use existing Kerberos credentials from credential cache.
        - `WINRM_TRANSPORT` (`str`, optional): Transport (`'negotiate'`, `'kerberos'`,
          `'ntlm'`, `'credssp'`, `'basic'`, `'ssl'`, etc.). Defaults to `'negotiate'`
          if unset.
        - `WINRM_DOMAIN` (`str`, optional): If set, username is sent as `user@domain`.
        - `WINRM_CONFIGURATION_NAME` (`str`, optional): PowerShell session configuration
          name (JEA endpoint). Defaults to `'Microsoft.PowerShell'` if unset.
          Only supported with **pypsrp**.
      (Additional attributes may be honored by the underlying libraries if present.)
    - **cmd** (`str`): PowerShell cmdlet name to execute remotely (e.g. `'Get-Service'`).
      When using pypsrp, this is passed directly as a cmdlet to the pipeline so JEA
      can properly allow/deny it. When falling back to pywinrm, it is passed as a
      scriptblock string.
    - **params** (`list[str]`, optional): Positional arguments passed to the cmdlet.
      Only used with pypsrp. Defaults to `[]`.

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
      then executes via a direct PSRP pipeline (RunspacePool + PowerShell) to avoid
      Invoke-Expression wrapping, ensuring JEA can enforce allow/deny on the cmdlet name.
    - Falls back to **pywinrm** and executes via `Session.run_ps()` if pypsrp is not available.
    - For Kerberos authentication: if `WINRM_USERNAME` and `WINRM_PASSWORD` are not provided
      (or are empty/None), the function will attempt to use existing Kerberos credentials
      from the credential cache (obtained via `kinit`).
    - On any exception, returns `{'retc': 1, 'stdout': '', 'stderr': <exception text>}`.
    - If neither backend is installed, returns an error indicating that no compatible
      remoting library is available.

    ### Example
    >>> # With explicit credentials:
    >>> run_ps(args, "Get-Process | Select-Object -First 1 | Format-Table Name,Id -AutoSize")
    {'retc': 0, 'stdout': 'Name    Id\\r\\n----    --\\r\\n...\\r\\n', 'stderr': ''}
    >>> # With Kerberos using kinit credentials (username/password can be None):
    >>> run_ps(args, "Get-Process | Select-Object -First 1 | Format-Table Name,Id -AutoSize")
    {'retc': 0, 'stdout': 'Name    Id\\r\\n----    --\\r\\n...\\r\\n', 'stderr': ''}
    >>> # With custom configuration name (JEA endpoint):
    >>> args.WINRM_CONFIGURATION_NAME = 'MyJEAEndpoint'
    >>> run_ps(args, "Get-Service", ["servicename"])
    {'retc': 0, 'stdout': '...','stderr': ''}
    """
    # Determine authentication credentials
    # For Kerberos, allow using existing credentials from kinit
    username = getattr(args, 'WINRM_USERNAME', None)
    password = getattr(args, 'WINRM_PASSWORD', None)

    # Check if we should use Kerberos with existing credentials
    _transport = (getattr(args, 'WINRM_TRANSPORT', None) or '').lower()
    use_kerberos_cache = (_transport in ['kerberos', 'negotiate']) and (not username or not password)

    if use_kerberos_cache:
        # Use None for username/password to let Kerberos use credential cache
        auth = (None, None)
    else:
        # Use provided credentials
        auth = (username, password)
        if getattr(args, 'WINRM_DOMAIN', None):
            auth = (f'{username}@{args.WINRM_DOMAIN}', password)

    if params is None:
        params = []

    configuration_name = getattr(args, 'WINRM_CONFIGURATION_NAME', None)
    if configuration_name and not HAVE_JEA:
        return {
            'retc': 1,
            'stdout': '',
            'stderr': 'WINRM_CONFIGURATION_NAME requires pypsrp (JEA). Install pypsrp or unset --winrm-configuration-name.',
        }

    if HAVE_JEA:
        try:
            from pypsrp.powershell import PowerShell, RunspacePool
            from pypsrp.wsman import WSMan

            # translate pywinrm transport -> pypsrp auth/ssl/port
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

            wsman = WSMan(
                server=args.WINRM_HOSTNAME,
                username=auth[0],
                password=auth[1],
                auth=_psrp_auth,
                ssl=_use_ssl,
                port=_port,
                cert_validation=True,
            )

            if not params:  
                parts = cmd.split()
                cmd = parts[0]
                params = parts[1:]

            # Use RunspacePool + PowerShell directly to avoid Invoke-Expression wrapping, so JEA can properly allow/deny
            # the cmdlet by name rather than seeing a raw string blob.
            with RunspacePool(wsman, configuration_name=configuration_name or 'Microsoft.PowerShell') as pool:
                ps = PowerShell(pool)
                ps.add_cmdlet(cmd)
                for param in params:
                    ps.add_argument(param)
                output = ps.invoke()

            stdout = '\n'.join([str(o) for o in output])

            # stderr from PSRP error stream(s)
            stderr_lines = []
            for err in ps.streams.error:
                # err.to_string() gives a readable message with category/position if available
                try:
                    stderr_lines.append(err.to_string())
                except Exception:
                    # fallback to message text
                    msg = getattr(err, 'message', None) or str(err)
                    stderr_lines.append(str(msg))
            stderr = '\n'.join(stderr_lines)

            result = {
                'retc': 0 if not ps.had_errors else 1,
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