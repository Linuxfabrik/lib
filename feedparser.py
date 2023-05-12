#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Parse Atom and RSS feeds in Python.

Time zone handling is not implemented.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023051201'

import sys

from .globals import STATE_UNKNOWN
try:
    from bs4 import BeautifulSoup
except ImportError as e:
    print('Python module "BeautifulSoup4" is not installed.')
    sys.exit(STATE_UNKNOWN)

from . import time
from . import url


def parse_atom(soup):
    result = {}
    result['title'] = soup.title.string
    result['updated'] = soup.updated.string
    # cut the timezone part
    result['updated_parsed'] = time.timestr2datetime(result['updated'][0:19], pattern='%Y-%m-%dT%H:%M:%S')

    result['entries'] = []
    for entry in soup.find_all('entry'):
        tmp = {}
        tmp['title'] = entry.title.string
        tmp['id'] = entry.id.string
        tmp['updated'] = entry.updated.string
        # cut the timezone part
        tmp['updated_parsed'] = time.timestr2datetime(tmp['updated'][0:19], pattern='%Y-%m-%dT%H:%M:%S')
        try:
            soup = BeautifulSoup(entry.summary.string, 'lxml')
            tmp['summary'] = soup.get_text()
        except:
            try:
                soup = BeautifulSoup(entry.content.string, 'lxml')
                tmp['summary'] = soup.get_text()
            except:
                pass
        result['entries'].append(tmp)
    return result


def parse_rss(soup):
    result = {}
    result['title'] = soup.rss.channel.title.string
    result['updated'] = soup.rss.channel.pubDate.string
    # cut the timezone part
    result['updated_parsed'] = time.timestr2datetime(result['updated'][0:25], pattern='%a, %d %b %Y %H:%M:%S')

    result['entries'] = []
    for entry in soup.find_all('item'):
        tmp = {}
        tmp['title'] = entry.title.string
        tmp['id'] = entry.guid.string
        tmp['updated'] = entry.pubDate.string
        # cut the timezone part
        tmp['updated_parsed'] = time.timestr2datetime(tmp['updated'][0:25], pattern='%a, %d %b %Y %H:%M:%S')
        try:
            soup = BeautifulSoup(entry.description.string, 'lxml')
            tmp['summary'] = soup.get_text()
        except:
            pass
        result['entries'].append(tmp)
    return result


def parse(feed_url, insecure=False, no_proxy=False, timeout=5, encoding='urlencode'):
    """Parse a feed from a URL, file, stream, or string.
    """

    success, xml = url.fetch(feed_url, insecure=insecure, no_proxy=no_proxy, timeout=timeout,
        encoding=encoding)
    if not success:
        return (False, xml)

    try:
        soup = BeautifulSoup(xml, 'xml')
    except Exception as e:
        return (False, e)

    is_atom = soup.feed
    if is_atom is not None:
        return (True, parse_atom(soup))

    is_rss = soup.rss
    if is_rss is not None:
        return (True, parse_rss(soup))

    return (False, '{} does not seem to be an Atom or RSS feed I understand.'.format(feed_url))
