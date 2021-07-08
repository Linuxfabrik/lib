#! /usr/bin/env python2
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

"""Get for example HTML or JSON from an URL.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2021050602'

import json
import re
import ssl
import urllib
import urllib2



def fetch(url, insecure=False, no_proxy=False, timeout=8,
          header={}, data={}, encoding='urlencode',
          digest_auth_user=None, digest_auth_password=None):
    """Fetch any URL.

    Basic authentication:
    >>> header = {
            'Authorization': "Basic {}".format(
                base64.b64encode(username + ':' + password)
                )
        }
    >>> result = fetch(URL)

    POST: the HTTP request will be a POST instead of a GET when the data parameter is provided
    >>> result = fetch(URL, header=header, data={...})
    """

    try:
        if digest_auth_user is not None and digest_auth_password is not None:
            # HTTP Digest Authentication
            passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passmgr.add_password(None, url, digest_auth_user, digest_auth_password)
            auth_handler = urllib2.HTTPDigestAuthHandler(passmgr)
            opener = urllib2.build_opener(auth_handler)
            urllib2.install_opener(opener)
        if data:
            # serializing dictionary
            if encoding == 'urlencode':
                data = urllib.urlencode(data)
            if encoding == 'serialized-json':
                data = json.dumps(data)
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib2.Request(url, data=data)
        else:
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib2.Request(url)

        for key, value in header.items():
            request.add_header(key, value)
        # close http connections by myself
        request.add_header('Connection', 'close')

        # SSL/TLS certificate validation
        # see: https://stackoverflow.com/questions/19268548/python-ignore-certificate-validation-urllib2
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        # Proxy handler
        if no_proxy:
            proxy_handler = urllib2.ProxyHandler({})
            ctx_handler = urllib2.HTTPSHandler(context=ctx)
            opener = urllib2.build_opener(proxy_handler, ctx_handler)
            response = opener.open(request)
        elif digest_auth_user is not None:
            response = urllib2.urlopen(request, timeout=timeout)
        else:
            response = urllib2.urlopen(request, context=ctx, timeout=timeout)
    except urllib2.HTTPError as e:
        # hide passwords
        url = re.sub(r'(token|password)=([^&]+)', r'\1********', url)
        return (False, 'HTTP error "{} {}" while fetching {}'.format(e.code, e.reason, url))
    except urllib2.URLError as e:
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
        try:
            result = response.read()
        except SSLError as e:
            return (False, 'SSL error "{}" while fetching {}'.format(e, url))
        except:
            return (False, 'Unknown error while fetching {}, maybe timeout or '
                       'error on webserver'.format(url))
        return (True, result)


def fetch_json(url, insecure=False, no_proxy=False, timeout=8,
               header={}, data={}, encoding='urlencode',
               digest_auth_user=None, digest_auth_password=None):
    """Fetch JSON from an URL.

    >>> fetch_json('https://1.2.3.4/api/v2/?resource=cpu')
    """

    success, jsonst = fetch(url, insecure=insecure, no_proxy=no_proxy, timeout=timeout,
                            header=header, data=data, encoding=encoding,
                            digest_auth_user=digest_auth_user, digest_auth_password=digest_auth_password)
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
