#! /usr/bin/env python3
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
__version__ = '2021082601'

import json
import re
import ssl
import urllib
import urllib.parse
import urllib.request


def fetch(url, insecure=False, no_proxy=False, timeout=8,
          header={}, data={}, encoding='urlencode',
          digest_auth_user=None, digest_auth_password=None):
    """Fetch any URL.

    Basic authentication:
    >>> auth = args.USERNAME + ':' + args.PASSWORD
    >>> encoded_auth = base64.b64encode(auth.encode()).decode()
    >>> result = lib.base3.coe(lib.url3.fetch(url, timeout=args.TIMEOUT,
            header={'Authorization': 'Basic {}'.format(encoded_auth)}))

    POST: the HTTP request will be a POST instead of a GET when the data parameter is provided
    >>> result = fetch(URL, header=header, data={...})
    """
    try:
        if digest_auth_user is not None and digest_auth_password is not None:
            # HTTP Digest Authentication
            passmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            passmgr.add_password(None, url, digest_auth_user, digest_auth_password)
            auth_handler = urllib.request.HTTPDigestAuthHandler(passmgr)
            opener = urllib.request.build_opener(auth_handler)
            urllib.request.install_opener(opener)
        if data:
            # serializing dictionary
            if encoding == 'urlencode':
                data = urllib.parse.urlencode(data)
            if encoding == 'serialized-json':
                data = json.dumps(data)
            data = data.encode('utf-8')
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib.request.Request(url, data=data)
        else:
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib.request.Request(url)

        for key, value in header.items():
            request.add_header(key, value)
        # close http connections by myself
        request.add_header('Connection', 'close')
        # identify as Linuxfabrik Monitoring-Plugin
        request.add_header('User-Agent', 'Linuxfabrik Monitoring Plugin')

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
        elif digest_auth_user is not None:
            response = urllib.request.urlopen(request, timeout=timeout)
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
        try:
            result = response.read().decode('utf-8', errors='replace')
        except:
            return (False, 'Unknown error while fetching {}, maybe timeout or '
                       'error on webserver'.format(url))
        return (True, result)


def fetch_ext(url, insecure=False, no_proxy=False, timeout=8,
          header={}, data={}, encoding='urlencode',
          digest_auth_user=None, digest_auth_password=None):
    """Fetch any URL, extended version of fetch(). Returns the response body plus response header.
    """
    try:
        if digest_auth_user is not None and digest_auth_password is not None:
            # HTTP Digest Authentication
            passmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            passmgr.add_password(None, url, digest_auth_user, digest_auth_password)
            auth_handler = urllib.request.HTTPDigestAuthHandler(passmgr)
            opener = urllib.request.build_opener(auth_handler)
            urllib.request.install_opener(opener)
        if data:
            # serializing dictionary
            if encoding == 'urlencode':
                data = urllib.parse.urlencode(data)
            if encoding == 'serialized-json':
                data = json.dumps(data)
            data = data.encode('utf-8')
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib.request.Request(url, data=data)
        else:
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib.request.Request(url)

        for key, value in header.items():
            request.add_header(key, value)
        # close http connections by myself
        request.add_header('Connection', 'close')
        # identify as Linuxfabrik Monitoring-Plugin
        request.add_header('User-Agent', 'Linuxfabrik Monitoring Plugin')

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
        elif digest_auth_user is not None:
            response = urllib.request.urlopen(request, timeout=timeout)
        else:
            response = urllib.request.urlopen(request, context=ctx, timeout=timeout)
    except urllib.request.HTTPError as e:
        # hide passwords
        url = re.sub(r'(token|password)=([^&]+)', r'\1********', url)
        return (False, 'HTTP error "{} {}" while fetching {}'.format(e.code, e.reason, url), False)
    except urllib.request.URLError as e:
        # hide passwords
        url = re.sub(r'(token|password)=([^&]+)', r'\1********', url)
        return (False, 'URL error "{}" for {}'.format(e.reason, url), False)
    except TypeError as e:
        return (False, 'Type error "{}", data="{}"'.format(e, data), False)
    except:
        # hide passwords
        url = re.sub(r'(token|password)=([^&]+)', r'\1********', url)
        return (False, 'Unknown error while fetching {}, maybe timeout or '
                       'error on webserver'.format(url), False)
    try:
        result = response.read()
        response_header = response.info()
    except:
        return (False, 'Unknown error while fetching {}, maybe timeout or '
                   'error on webserver'.format(url), False)
    return (True, result, response_header)


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


def fetch_json_ext(url, insecure=False, no_proxy=False, timeout=8,
               header={}, data={}, encoding='urlencode',
               digest_auth_user=None, digest_auth_password=None):
    """Fetch JSON from an URL, extended version of fetch_json(). 
    Returns the response body plus response header.

    >>> success, result, response_header = url2.fetch_json_ext(
        args.URL, header=header, data=data, timeout=timeout, insecure=True)
    >>> print(response_header['X-RestSvcSessionId'])
    NGY5NzI2MDgtMjU3My00MmEzLThiNDEtOWYxZmJkNzI2ZDZl
    """
    success, jsonst, response_header = fetch_ext(
        url, insecure=insecure, no_proxy=no_proxy, timeout=timeout,
        header=header, data=data, encoding=encoding,
        digest_auth_user=digest_auth_user, digest_auth_password=digest_auth_password)
    if not success:
        return (False, jsonst, False)
    try:
        result = json.loads(jsonst)
    except:
        return (False, 'ValueError: No JSON object could be decoded', False)
    return (True, result, response_header)


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
