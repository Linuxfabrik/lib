#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://nagios-plugins.org/doc/guidelines.html

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020010601'


from .globals import *

def evaluate_greater(value, warn, crit):
    # make sure to use float comparison
    # todo check logic

    if crit or crit == 0:
        crit = float(crit)
        value = float(value)
        if value >= crit:
            return STATE_CRIT

    if warn or warn == 0:
        warn = float(warn)
        value = float(value)
        if value >= warn:
            return STATE_WARN 

    return STATE_OK


def evaluate_smaller(value, warn, crit):
    # make sure to use float comparison
    # todo check logic

    if crit or crit == 0:
        crit = float(crit)
        value = float(value)
        if value <= crit:
            return STATE_CRIT

    if warn or warn == 0:
        warn = float(warn)
        value = float(value)
        if value <= warn:
            return STATE_WARN 

    return STATE_OK


def filter_input(input, ignore):
    filtered_input = ''
    for line in input.splitlines():
        if not any(i_line in line for i_line in ignore):
            filtered_input += line + '\n'

    return filtered_input


def evaluate_greater_date_to_today(date_in, warn, crit):
    import datetime
    # only compares the date, not the time
    # thresholds in days
    # eg: date_in = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z') # Oct 29 08:41:00 2028 GMT

    time_delta = (date_in.date() - datetime.datetime.now().date()).total_seconds() / 3600 / 24

    if crit or crit == 0:
        if diff > crit:
            return STATE_CRIT

    if warn or warn == 0:
        if diff > warn:
            return STATE_WARN 

    return STATE_OK


def evaluate_smaller_date_to_today(date_in, warn, crit):
    import datetime
    # only compares the date, not the time
    # thresholds in days
    # eg: date_in = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z') # Oct 29 08:41:00 2028 GMT

    time_delta = (date_in.date() - datetime.datetime.now().date()).total_seconds() / 3600 / 24

    if crit or crit == 0:
        if diff < crit:
            return STATE_CRIT

    if warn or warn == 0:
        if diff < warn:
            return STATE_WARN 

    return STATE_OK


def evaluate_greater_date_now(date_in, warn, crit):
    import datetime
    # thresholds in hours
    # eg: date_in = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z') # Oct 29 08:41:00 2028 GMT

    time_delta = (date_in - datetime.datetime.now()).total_seconds() / 3600

    if crit or crit == 0:
        if diff > crit:
            return STATE_CRIT

    if warn or warn == 0:
        if diff > warn:
            return STATE_WARN 

    return STATE_OK


def mltext2array(input, skip_header=False, sort_key=-1):
    from operator import itemgetter
    input = input.strip(' \t\n\r').split('\n')
    lines = []
    if skip_header:
        del input[0]
    for row in input:
        lines.append(row.split())
    if sort_key != -1:
        lines = sorted(lines, key=itemgetter(sort_key))        
    return lines


def str2bytes(strbytes):
    bytes = 0
    strbytes = strbytes.lower().strip()
    # make GiB to GB etc.
    strbytes = strbytes.replace('i', '')

    if strbytes.find('tb') > -1:
        strbytes = strbytes.replace('tb', '')
        bytes = float(strbytes) * 1024 * 1024 * 1024 * 1024
    if strbytes.find('gb') > -1:
        bytes = float(strbytes.replace('gb', '')) * 1024 * 1024 * 1024
    elif strbytes.find('mb') > -1:
        bytes = float(strbytes.replace('mb', '')) * 1024 * 1024
    elif strbytes.find('kb') > -1:
        bytes = float(strbytes.replace('kb', '')) * 1024
    elif strbytes.find('b') > -1:
        bytes = float(strbytes.replace('b', ''))
    else:
        bytes = float(strbytes)

    return long(bytes)
