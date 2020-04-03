#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://nagios-plugins.org/doc/guidelines.html

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020010801'


STATE_OK        = 0
STATE_WARN      = 1
STATE_CRIT      = 2
STATE_UNKNOWN   = 3
STATE_DEPENDENT = 4

def get_greater_state(first_state, second_state):
    # order from most to least important:
    # CRIT
    # WARN
    # UNK
    # OK

    if second_state == STATE_CRIT:
        return second_state

    if second_state == STATE_WARN and first_state != STATE_CRIT:
        return second_state

    if second_state == STATE_UNKNOWN and first_state not in [STATE_WARN, STATE_CRIT]:
        return second_state

    return first_state


def get_worst(state1, state2):
    """Get the more worst of two states, in this particular order:
        # CRIT    (2)
        # WARN    (1)
        # UNKNOWN (3)
        # OK      (0)
    """
    if state1 == STATE_CRIT or state2 == STATE_CRIT:
        return STATE_CRIT
    if state1 == STATE_WARN or state2 == STATE_WARN:
        return STATE_WARN
    if state1 == STATE_UNKNOWN or state2 == STATE_UNKNOWN:
        return STATE_UNKNOWN
    return STATE_OK
