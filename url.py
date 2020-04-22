#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020042201'

import json
import re
import ssl
import urllib
import urllib2


def fetch(url, insecure=False, no_proxy=False, timeout=5, header={}, data={}):
    try:
        if data:
            data = urllib.urlencode(data)
            request = urllib2.Request(url, data=data)
        else:
            request = urllib2.Request(url)

        for key, value in header.items():
            request.add_header(key, value)

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
    except TypeError as e:
        return (False, 'Type error "{}", data="{}"'.format(e, data))
    except:
        return (False, 'Unknown error while fetching {}, maybe timeout or error on webserver'.format(url))
    else:
        result = response.read()
        return (True, result)


def fetch_json(url, insecure=False, no_proxy=False, timeout=5, header={}, data={}):
    """Fetch JSON from an URL.

    >>> lib.url.fetch_json('https://1.2.3.4/api/v2/monitor/system/resource/usage?resource=cpu&interval=1-min&access_token=abc123')
    """

    success, jsonst = fetch(url, insecure=insecure, no_proxy=no_proxy, timeout=timeout, header=header, data=data)
    if not success:
        return (False, jsonst)
    try:
        result = json.loads(jsonst)
    except:
        return (False, 'ValueError: No JSON object could be decoded')
    return (True, result)


def get_latest_version_from_github(user, repo, key='tag_name'):
    github_url = 'https://api.github.com/repos/{}/{}/releases/latest'.format(user, repo)
    success, result = fetch(github_url)
    if not success:
        return (success, result)
    if not result:
        return (True, False)
    try:
        result = json.loads(result)
    except:
        return (True, False)
    #print(json.dumps(result, indent=4, sort_keys=True))

    # on GitHub, here is the version (format of the version string depends on the maintainer)
    return (True, result[key])


def strip_tags(html):
    # tries to return a string with all HTML tags stripped from a given string
    return re.sub(r'<[^<]+?>', '', html)
