#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://nagios-plugins.org/doc/guidelines.html

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020010802'


def execute_command(command, env=None, shell=False, stdin_input=False):
    import subprocess
    if shell:
        sp = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=True)
        stdout, stderr = sp.communicate()
        retc = sp.returncode
        return stdout, stderr, retc

    if stdin_input:
        sp = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=True)
        stdout, stderr = sp.communicate(input=stdin_input)
        retc = sp.returncode
        return stdout, stderr, retc

    import shlex
    command_list = command.split('|')

    p_last = None
    first = True
    for command in command_list:
        if first:
            first = False
            args = shlex.split(command.strip())
            p_last = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=False)
            continue

        args = shlex.split(command.strip())
        p_last = subprocess.Popen(args, stdin=p_last.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=False)

    stdout, stderr = p_last.communicate()
    retc = p_last.returncode
    return stdout, stderr, retc


def disk_partitions(ignore=[]):
    import psutil
    # remove all empty items from the ignore list, because `'' in 'any_string' == true`
    ignore = list(filter(None, ignore))
    return list(filter(lambda part: not any(ignore_item in part.mountpoint for ignore_item in ignore), psutil.disk_partitions(all=False)))
