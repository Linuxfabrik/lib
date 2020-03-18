#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020031801'

import ssl
import urllib2


def fetch_url(url, insecure=False, no_proxy=False, timeout=5):
    try:
        request = urllib2.Request(url)

        # SSL/TLS certificate validation (see: https://stackoverflow.com/questions/19268548/python-ignore-certificate-validation-urllib2)
        ctx = ssl.create_default_context()
        if (insecure):
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        # Proxy handler
        if (no_proxy):
            proxy_handler = urllib2.ProxyHandler({})
            ctx_handler = urllib2.HTTPSHandler(context=ctx)
            opener = urllib2.build_opener(proxy_handler, ctx_handler)
            response = opener.open(request)
        else:
            response = urllib2.urlopen(request, context=ctx, timeout=timeout)
    except urllib2.HTTPError as e:
        return (False, 'HTTP error "{} {}" while fetching {}'.format(e.code, e.reason, url))
    except urllib2.URLError as e:
        return (False, 'URL error "{}" for {}'.format(e.reason, url))
    except:
        return (False, 'Unknown error while fetching {}'.format(url))
    else:
        result = response.read()
        return (True, result)


