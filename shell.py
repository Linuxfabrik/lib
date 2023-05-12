#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Communicates with the Shell.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'


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
    """Runs a shell command and returns its output. Optionally, applies a regex and just
    returns the first matching group. If the command is not found, an empty string is returned.

    >>> get_command_output('nano --version')
    GNU nano, version 5.3
     (C) 1999-2011, 2013-2020 Free Software Foundation, Inc.
     (C) 2014-2020 the contributors to nano
     Compiled options: --enable-utf8
    >>> get_command_output('nano --version', regex=r'version (.*)\n')
    5.3
    """
    success, result = shell_exec(cmd)
    if not success:
        return ''
    stdout, stderr, retc = result
    if stdout == '' and stderr != '':
        # https://stackoverflow.com/questions/26028416/why-does-python-print-version-info-to-stderr
        # https://stackoverflow.com/questions/13483443/why-does-java-version-go-to-stderr]
        stdout = stderr
    stdout = stdout.strip()
    if regex:
        # extract something special from output
        try:
            stdout = re.search(regex, stdout)
            return stdout.group(1).strip()
        except:
            return ''
    else:
        return stdout.strip()


def shell_exec(cmd, env=None, shell=False, stdin='', cwd=None, timeout=None):
    """Executes external command and returns the complete output as a
    string (stdout, stderr) and the program exit code (retc).

    Parameters
    ----------
    cmd : str
        Command to spawn the child process.
    env : None or dict
        Environment variables. Example: env={'PATH': '/usr/bin'}.
    shell : bool
        If True, the new process is called via what is set in the SHELL
        environment variable - means using shell=True invokes a program of the
        user's choice and is platform-dependent. It allows you to expand
        environment variables and file globs according to the shell's usual
        mechanism, which can be a security hazard. Generally speaking, avoid
        invocations via the shell. It is very seldom needed to set this
        to True.
    stdin : str
        If set, use this as input into `cmd`.
    cwd : str
        Current Working Directory
    timeout : int
        If the process does not terminate after timeout seconds, False is returned.

    Returns
    -------
    result : tuple
        result[0] = the functions return code (bool)
            False: result[1] contains the error message (str)
            True:  result[1] contains the result of the called `cmd`
                   as a tuple (stdout, stderr, retc)

    https://docs.python.org/2/library/subprocess.html
    """
    if not env:
        env = os.environ.copy()
    # set cmd output to English, no matter what the user has choosen
    env['LC_ALL'] = 'C'

    # subprocess.PIPE: Special value that can be used as the stdin,
    # stdout or stderr argument to Popen and indicates that a pipe to
    # the standard stream should be opened.
    if shell or stdin:
        # New console wanted, or we have some input for our cmd - then we
        # need a new console, too.
        # Pipes '|' are handled by the shell itself.
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, shell=True, cwd=cwd)
        except OSError as e:
            return (False, 'OS Error "{} {}" calling command "{}"'.format(e.errno, e.strerror, cmd))
        except ValueError as e:
            return (False, 'Value Error "{}" calling command "{}"'.format(e, cmd))
        except e:
            return (False, 'Unknown error "{}" while calling command "{}"'.format(e, cmd))

        if stdin:
            # provide stdin as input for the cmd
            stdout, stderr = p.communicate(input=txt.to_bytes(stdin))
        else:
            stdout, stderr = p.communicate()
        retc = p.returncode
        return (True, (txt.to_text(stdout), txt.to_text(stderr), retc))

    # No new console wanted, but then we have to do pipe handling on our own.
    # Examples:
    # * `cat /var/log/messages | grep DENY | grep Rule`
    # * `. /etc/os-release && echo $NAME $VERSION`
    cmds = cmd.split('|')
    p = None
    for cmd in cmds:
        try:
            args = shlex.split(cmd.strip())
            # use the previous output from last cmd call as input for next cmd in pipe chain,
            # if there is any
            stdin = p.stdout if p else subprocess.PIPE
            p = subprocess.Popen(args, stdin=stdin, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, shell=False, cwd=cwd)
        except OSError as e:
            return (False, 'OS Error "{} {}" calling command "{}"'.format(e.errno, e.strerror, cmd))
        except ValueError as e:
            return (False, 'Value Error "{}" calling command "{}"'.format(e, cmd))
        except e:
            return (False, 'Unknown error "{}" while calling command "{}"'.format(e, cmd))

    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        outs, errs = p.communicate()
        return (False, 'Timeout after {} seconds.'.format(timeout))
    retc = p.returncode
    return (True, (txt.to_text(stdout), txt.to_text(stderr), retc))
