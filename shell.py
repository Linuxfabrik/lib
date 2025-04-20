#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Communicates with the Shell on Linux and Windows.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025042001'


import os
import re
import shlex
import subprocess

from . import txt


RETC_SSHPASS = {
    1: 'Invalid command line argument',
    2: 'Conflicting arguments given',
    3: 'General runtime error',
    4: 'Unrecognized response from ssh (parse error)',
    5: 'Invalid/incorrect password',
    6: 'Host public key is unknown. sshpass exits without confirming the new key.',
    7: 'IP public key changed. sshpass exits without confirming the new key.',
}


def get_command_output(cmd, regex=None):
    """
    Execute a shell command and return its output, optionally filtered by a regular expression.

    This function runs the given command using the `shell_exec()` function and processes the output
    as follows:
      - If `shell_exec()` indicates an execution failure, an empty string is returned.
      - Retrieves standard output (stdout), standard error (stderr), and exit code.
      - If stdout is empty but stderr contains output, stderr is used instead.
      - The output is stripped of any leading or trailing whitespace.
      - If a regex is provided, attempts to extract and return the text captured by
        the first capturing group. If no match is found or an error occurs, returns an empty string.
      - If no regex is provided, the complete stripped output is returned.

    ### Parameters
    - **cmd** (`str`): The command to execute.
    - **regex** (`str`, optional): A regular expression pattern with at least one capturing group to
      extract specific output. Defaults to None.

    ### Returns
    - **str**: The processed command output, or the extracted substring if regex is provided; 
      returns an empty string if execution fails or no match is found.

    ### Example
    >>> get_command_output('nano --version')
    GNU nano, version 5.3
    (C) 1999-2011, 2013-2020 Free Software Foundation, Inc.
    (C) 2014-2020 the contributors to nano
    Compiled options: --enable-utf8

    >>> get_command_output('nano --version', regex=r'version (.*)\\n')
    5.3
    """
    success, result = shell_exec(cmd)
    if not success:
        return ''

    stdout, stderr, _ = result
    output = stdout.strip() or stderr.strip()

    if regex:
        try:
            match = re.search(regex, output)
            return match.group(1).strip() if match else ''
        except Exception:
            return ''

    return output


def shell_exec(cmd, env=None, shell=False, stdin='', cwd=None, timeout=None):
    """
    Execute a command in a subprocess with flexible options for shell execution, environment
    variables, piping, standard input, working directory, and a timeout.

    On Windows, the function changes the codepage to 65001 (UTF-8) so that command output is
    handled in UTF-8.

    ### Parameters
    - **cmd** (`str`):  
      The command string to execute. Use `|` to separate piped commands.
    - **env** (`dict`, optional):  
      A dictionary of environment variables to merge with the current OS environment.
      Defaults to the current environment.
    - **shell** (`bool`, optional):  
      If True, execute using the shell. Required when using shell features or stdin.
      Defaults to False.
    - **stdin** (`str`, optional):  
      A string to pass as standard input to the command. Defaults to ''.
    - **cwd** (`str`, optional):  
      Working directory in which to execute the command. Defaults to None (current directory).
    - **timeout** (`int` or `float`, optional):  
      Maximum time (in seconds) to allow the command to run. If exceeded, the process is terminated.
      Defaults to None.

    ### Returns
    - **tuple**:  
      On success:  
      `(True, (stdout, stderr, return_code))`  
      - **stdout** (`str`): Standard output of the command.  
      - **stderr** (`str`): Standard error of the command.  
      - **return_code** (`int`): Exit status of the command.  

      On failure:  
      `(False, error_message)` — a string describing the error.

    ### Notes
    - Output is always forced to English by setting `LC_ALL=C`.
    - On Windows, the command is prepended with `chcp 65001 &&` to ensure UTF-8 output.
    - If `shell=False` and the command contains pipes (`|`), it creates a manual pipeline.
    - Exceptions such as `OSError`, `ValueError`, or general execution errors are caught and
      reported.
    """
    env = {**os.environ.copy(), **(env or {})}
    env['LC_ALL'] = 'C'

    if os.name == 'nt':
        cmd = f'chcp 65001 && {cmd}'
        shell = True

    if shell or stdin:
        try:
            p = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=True,
                cwd=cwd,
            )
        except (OSError, ValueError, Exception) as e:
            return False, f'Error "{e}" while calling command "{cmd}"'

        stdout, stderr = p.communicate(input=txt.to_bytes(stdin) if stdin else None)
        retc = p.returncode
        stdout = txt.to_text(stdout).replace('Active code page: 65001\r\n', '')
        stderr = txt.to_text(stderr)
        return True, (stdout, stderr, retc)

    cmds = cmd.split('|')
    p = None
    for part in cmds:
        try:
            args = shlex.split(part.strip())
            p = subprocess.Popen(
                args,
                stdin=p.stdout if p else subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=False,
                cwd=cwd,
            )
        except (OSError, ValueError, Exception) as e:
            return False, f'Error "{e}" while calling command "{part}"'

    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        return False, f'Timeout after {timeout} seconds.'

    return True, (txt.to_text(stdout), txt.to_text(stderr), p.returncode)
