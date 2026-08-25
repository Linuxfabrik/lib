#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library defines the exit states of a monitoring check, based on the
POSIX spec of returning a positive value and just like in
`monitoring-plugins/plugins-scripts/utils.sh.in`, except that we do not
make use of `STATE_DEPENDENT`.

* STATE_OK = 0:
  The service was checked and appeared to be functioning properly.

* STATE_WARN = 1:
  The service was checked, but it appeared to be above some "warning"
  threshold or did not appear to be working properly.

* STATE_CRIT = 2:
  Either the service was not running, or it was above some "critical"
  threshold.

* STATE_UNKNOWN = 3:
  Invalid command line arguments were supplied, or a low-level failure
  internal to the calling program (such as unable to fork, or open a tcp
  socket) prevented it from performing the specified operation.
  Higher-level errors (such as name resolution errors, socket timeouts,
  etc) are outside of the caller's control and should generally NOT be
  reported as UNKNOWN states.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026082501'


STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3
# STATE_DEPENDENT = 4
