#! /usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Get for example HTML or JSON from an URL.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020092401'

import json
import re
import ssl
import urllib


def fetch(url, insecure=False, no_proxy=False, timeout=5,
          header={}, data={}, encoding='urlencode'):
    """Fetch any URL.

    Basic authentication:
    >>> header = {
            'Authorization': "Basic {}".format(
                base64.b64encode(username + ':' + password)
                )
        }
    >>> jsonst = lib.base.coe(lib.url.fetch(URL, header=header))
    """

    try:
        if data:
            # serializing dictionary
            if encoding == 'urlencode':
                data = urllib.urlencode(data)
            if encoding == 'serialized-json':
                data = json.dumps(data)
            request = urllib.request.Request(url, data=data)
        else:
            request = urllib.request.Request(url)

        for key, value in header.items():
            request.add_header(key, value)

        # SSL/TLS certificate validation
        # see: https://stackoverflow.com/questions/19268548/python-ignore-certificate-validation-urllib2
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        # Proxy handler
        if no_proxy:
            proxy_handler = urllib.request.ProxyHandler({})
            ctx_handler = urllib.request.HTTPSHandler(context=ctx)
            opener = urllib.request.build_opener(proxy_handler, ctx_handler)
            response = opener.open(request)
        else:
            response = urllib.request.urlopen(request, context=ctx, timeout=timeout)
    except urllib.request.HTTPError as e:
        # hide passwords
        url = re.sub(r'(token|password)=([^&]+)', r'\1********', url)
        return (False, 'HTTP error "{} {}" while fetching {}'.format(e.code, e.reason, url))
    except urllib.request.URLError as e:
        # hide passwords
        url = re.sub(r'(token|password)=([^&]+)', r'\1********', url)
        return (False, 'URL error "{}" for {}'.format(e.reason, url))
    except TypeError as e:
        return (False, 'Type error "{}", data="{}"'.format(e, data))
    except:
        # hide passwords
        url = re.sub(r'(token|password)=([^&]+)', r'\1********', url)
        return (False, 'Unknown error while fetching {}, maybe timeout or '
                       'error on webserver'.format(url))
    else:
        result = response.read()
        return (True, result)


def fetch_json(url, insecure=False, no_proxy=False, timeout=5,
               header={}, data={}, encoding='urlencode'):
    """Fetch JSON from an URL.

    >>> fetch_json('https://1.2.3.4/api/v2/?resource=cpu')
    """

    success, jsonst = fetch(url, insecure=insecure, no_proxy=no_proxy, timeout=timeout,
                            header=header, data=data, encoding=encoding)
    if not success:
        return (False, jsonst)
    try:
        result = json.loads(jsonst)
    except:
        return (False, 'ValueError: No JSON object could be decoded')
    return (True, result)


def get_latest_version_from_github(user, repo, key='tag_name'):
    """Get the newest release tag from a GitHub repo.

    >>> get_latest_version_from_github('matomo-org', 'matomo')
    """

    github_url = 'https://api.github.com/repos/{}/{}/releases/latest'.format(user, repo)
    success, result = fetch_json(github_url)
    if not success:
        return (success, result)
    if not result:
        return (True, False)

    # on GitHub, here is the version (format of the version string depends on the maintainer)
    return (True, result[key])


def strip_tags(html):
    """Tries to return a string with all HTML tags stripped from a given string.
    """

    return re.sub(r'<[^<]+?>', '', html)
