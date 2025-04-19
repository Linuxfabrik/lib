#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library defines the global plugin states, based on the POSIX
spec of returning a positive value and just like in
`monitoring-plugins/plugins-scripts/utils.sh.in`, except that we do not
make use of `STATE_DEPENDENT`.

* STATE_OK = 0:  
  The plugin was able to check the service and it appeared
  to be functioning properly.

* STATE_WARN = 1:  
  The plugin was able to check the service, but it
  appeared to be above some "warning" threshold or did not appear to be
  working properly.

* STATE_CRIT = 2:  
  The plugin detected that either the service was not
  running or it was above some "critical" threshold.

* STATE_UNKNOWN = 3:  
  Invalid command line arguments were supplied to the
  plugin or low-level failures internal to the plugin (such as unable to
  fork, or open a tcp socket) that prevent it from performing the
  specified operation. Higher-level errors (such as name resolution
  errors, socket timeouts, etc) are outside of the control of plugins and
  should generally NOT be reported as UNKNOWN states.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025041901'


STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3
#STATE_DEPENDENT = 4
