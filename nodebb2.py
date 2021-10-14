#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""This library collects some NodeBB related functions that are
needed by more than one NodeBB plugin."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021090701'

import base2
import url2


def get_data(args, url=''):
    """Fetch json from the NodeBB API using an user token. For details have a look at
    https://docs.nodebb.org/api/
    """
    return base2.coe(url2.fetch_json(
        args.URL + url,
        insecure=args.INSECURE,
        timeout=args.TIMEOUT,
        header={
            'Accept': 'application/json',
            'Authorization': 'Bearer {}'.format(args.TOKEN),
        },
    ))
