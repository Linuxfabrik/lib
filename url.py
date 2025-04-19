#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Get for example HTML or JSON from an URL.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025041902'

import json
import re
import ssl
import urllib
import urllib.parse
import urllib.request

from . import txt


def fetch(url, insecure=False, no_proxy=False, timeout=8,
          header={}, data={}, encoding='urlencode',
          digest_auth_user=None, digest_auth_password=None,
          extended=False, to_text=True):
    """
    Fetch any URL with optional POST, basic authentication, and SSL/TLS handling.

    This function supports:
    - GET and POST requests (using the `data` parameter).
    - Basic authentication (using the `header` and `digest_auth_*` parameters).
    - SSL/TLS certificate validation (with the `insecure` parameter to disable it).
    - Handling of response headers (with `extended=True`).

    ### Parameters
    - **url** (`str`):
        The URL to fetch.
    - **insecure** (`bool`, optional):
        If True, disables SSL certificate validation. Defaults to False.
    - **no_proxy** (`bool`, optional):
        If True, disables the use of proxies. Defaults to False.
    - **timeout** (`int`, optional):
        Timeout in seconds for the request. Defaults to 8 seconds.
    - **header** (`dict`, optional):
        Headers to include in the request.
    - **data** (`dict`, optional):
        Data to send in the request body (used for POST requests).
    - **encoding** (`str`, optional):
        The encoding type for the request body. Defaults to `'urlencode'`.
    - **digest_auth_user** (`str`, optional):
        The username for HTTP Digest Authentication.
    - **digest_auth_password** (`str`, optional):
        The password for HTTP Digest Authentication.
    - **extended** (`bool`, optional):
        If True, includes the response header and status code in the result. Defaults to False.
    - **to_text** (`bool`, optional):
        If True, converts the response to text. Defaults to True.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the request was successful, False otherwise.
      - **result** (`dict` or `str`): 
        - If successful, the response body (as a string or raw data).
        - If `extended=True`, the result includes the response, status code, and response headers.
        - An error message string if the request failed.

    ### Example
    >>> result = fetch('https://api.example.com', timeout=10, header={'Authorization': 'Bearer token'})

    >>> result = fetch('https://api.example.com', data={'key': 'value'}, extended=True)
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
            data = txt.to_bytes(data)
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib.request.Request(url, data=data)
        else:
            # the HTTP request will be a POST instead of a GET when the data parameter is provided
            request = urllib.request.Request(url)

        for key, value in header.items():
            request.add_header(key, value)
        # close http connections by myself
        request.add_header('Connection', 'close')
        # identify as Linuxfabrik Monitoring Plugins
        request.add_header('User-Agent', 'Linuxfabrik Monitoring Plugins')

        # SSL/TLS certificate validation
        # see:
        # https://stackoverflow.com/questions/19268548/python-ignore-certificate-validation-urllib2
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
        url = txt.sanitize_sensitive_data(url)
        return (False, 'HTTP error "{} {}" while fetching {}'.format(e.code, e.reason, url))
    except urllib.request.URLError as e:
        # hide passwords
        url = txt.sanitize_sensitive_data(url)
        return (False, 'URL error "{}" for {}'.format(e.reason, url))
    except TypeError as e:
        return (False, 'Type error "{}", data="{}"'.format(e, data))
    except Exception as e:
        # hide passwords
        url = txt.sanitize_sensitive_data(url)
        return (False, '{} while fetching {}'.format(e, url))
    else:
        try:
            charset = response.headers.get_content_charset()
            if charset is None:
                # if the server doesn't send charset info
                charset = 'UTF-8'
            if not extended:
                if to_text:
                    result = txt.to_text(response.read(), encoding=charset)
                else:
                    result = response.read()
            else:
                result = {}
                if to_text:
                    result['response'] = txt.to_text(response.read(), encoding=charset)
                else:
                    result['response'] = response.read()
                result['status_code'] = response.getcode()
                result['response_header'] = response.info()
        except Exception as e:
            return (False, '{} while fetching {}'.format(e, url))
        return (True, result)


def fetch_json(url, insecure=False, no_proxy=False, timeout=8,
               header={}, data={}, encoding='urlencode',
               digest_auth_user=None, digest_auth_password=None,
               extended=False):
    """
    Fetch JSON from a URL with optional POST, authentication, and SSL/TLS handling.

    This function uses the `fetch()` function to retrieve the content from the URL and then
    attempts to parse the response as JSON.

    ### Parameters
    - **url** (`str`): The URL to fetch the JSON from.
    - **insecure** (`bool`, optional):
        If True, disables SSL certificate validation. Defaults to False.
    - **no_proxy** (`bool`, optional):
        If True, disables the use of proxies. Defaults to False.
    - **timeout** (`int`, optional):
        Timeout in seconds for the request. Defaults to 8 seconds.
    - **header** (`dict`, optional):
        Headers to include in the request.
    - **data** (`dict`, optional):
        Data to send in the request body (used for POST requests).
    - **encoding** (`str`, optional):
        The encoding type for the request body. Defaults to `'urlencode'`.
    - **digest_auth_user** (`str`, optional):
        The username for HTTP Digest Authentication.
    - **digest_auth_password** (`str`, optional):
        The password for HTTP Digest Authentication.
    - **extended** (`bool`, optional):
        If True, includes the response header and status code in the result. Defaults to False.

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the JSON was successfully fetched and parsed, False otherwise.
      - **result** (`dict` or `str`): 
        - The parsed JSON object if successful.
        - An error message string if the request failed or JSON decoding failed.

    ### Example
    >>> fetch_json('https://192.0.2.74/api/v2/?resource=cpu')
    (True, {'cpu': {'usage': '45%', 'temperature': '50C'}})
    """
    success, jsonst = fetch(
        url,
        data=data,
        digest_auth_password=digest_auth_password,
        digest_auth_user=digest_auth_user,
        encoding=encoding,
        extended=extended,
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )
    if not success:
        return (False, jsonst)
    try:
        if not extended:
            result = json.loads(jsonst)
        else:
            result = jsonst
            result['response_json'] = json.loads(jsonst['response'])
    except Exception as e:
        return (False, '{}. No JSON object could be decoded.'.format(e))
    return (True, result)


def get_latest_version_from_github(user, repo, key='tag_name'):
    """
    Get the newest release tag from a GitHub repository.

    This function fetches the latest release information from the GitHub API and retrieves the release tag.

    ### Parameters
    - **user** (`str`): The GitHub username or organization name.
    - **repo** (`str`): The GitHub repository name.
    - **key** (`str`, optional): The key to retrieve from the JSON response (default is `'tag_name'`).

    ### Returns
    - **tuple**:
      - **success** (`bool`): True if the latest version was successfully fetched, False otherwise.
      - **result** (`str` or `bool`): 
        - The value of the specified key (e.g., the latest release tag) if successful.
        - `False` if no result was found or the GitHub API did not return any data.

    ### Example
    >>> get_latest_version_from_github('Linuxfabrik', 'monitoring-plugins')
    (True, 'v1.2.3')
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
    """
    Strips all HTML tags from a given string.

    This function removes any HTML tags from the input string, leaving only the raw text content.

    ### Parameters
    - **html** (`str`): The string containing HTML tags to be stripped.

    ### Returns
    - **str**: The input string with all HTML tags removed.

    ### Example
    >>> strip_tags('<div>Hello, <b>world</b>!</div>')
    'Hello, world!'
    """
    return re.sub(r'<[^<]+?>', '', html)
