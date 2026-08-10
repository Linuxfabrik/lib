#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""Parse Atom and RSS feeds in Python.

Time zone handling is not implemented.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026081001'

import sys

from .globals import STATE_UNKNOWN

try:
    from bs4 import BeautifulSoup
except ImportError:
    print('Python module "BeautifulSoup4" is not installed.')
    sys.exit(STATE_UNKNOWN)

from . import time, url


def fetch_soup(
    feed_url,
    insecure=False,
    no_proxy=False,
    timeout=5,
    encoding='urlencode',
    retries=0,
):
    """
    Fetch an Atom or RSS feed from a URL and return it as a parsed XML document.

    Use this instead of `parse()` to work on the feed's own markup, for example to read an
    element `parse()` does not map or to keep the time zone of a timestamp, which `parse()`
    drops.

    The response is validated by `parse_soup()`, so a server that answers with HTTP 200 and
    a feed content type but sends something other than a feed is a failure here rather than
    a feed without any entries.

    ### Parameters
    - **feed_url** (`str`):
      The URL of the feed to fetch.
    - **insecure** (`bool`, optional):
      If `True`, disable SSL verification during download. Default is `False`.
    - **no_proxy** (`bool`, optional):
      If `True`, ignore any system proxy settings. Default is `False`.
    - **timeout** (`int`, optional):
      Timeout in seconds for the download request, per attempt. Default is `5`.
    - **encoding** (`str`, optional):
      Encoding to use for the URL fetch operation. Default is `'urlencode'`.
    - **retries** (`int`, optional):
      How many extra attempts to make if the request fails or the body is not a feed.
      `0` (default) means a single attempt. Useful against flaky endpoints (e.g. a status
      page behind a load balancer) that occasionally answer with something else.

    ### Returns
    - **tuple**:
      - `(True, BeautifulSoup)`: On success, the parsed feed document.
      - `(False, str or Exception)`: On failure (after all retries), an error message or
        exception.

    ### Example
    >>> success, soup = fetch_soup('https://linuxfabrik.ch/feed.xml', retries=3)
    """
    attempt = 0
    while True:
        success, xml = url.fetch(
            feed_url,
            encoding=encoding,
            insecure=insecure,
            no_proxy=no_proxy,
            timeout=timeout,
        )
        result = parse_soup(xml, feed_url) if success else (False, xml)

        if result[0] or attempt >= retries:
            return result
        attempt += 1


def parse(
    feed_url,
    insecure=False,
    no_proxy=False,
    timeout=5,
    encoding='urlencode',
    retries=0,
):
    """
    Parse an Atom or RSS feed from a URL, file, stream, or string.

    This function fetches a feed resource, parses it as XML using BeautifulSoup, and attempts to
    automatically detect and parse Atom or RSS formats into structured dictionaries.

    ### Parameters
    - **feed_url** (`str`):
      The URL or file path of the feed to fetch and parse.
    - **insecure** (`bool`, optional):
      If `True`, disable SSL verification during download. Default is `False`.
    - **no_proxy** (`bool`, optional):
      If `True`, ignore any system proxy settings. Default is `False`.
    - **timeout** (`int`, optional):
      Timeout in seconds for the download request. Default is `5`.
    - **encoding** (`str`, optional):
      Encoding to use for the URL fetch operation. Default is `'urlencode'`.
    - **retries** (`int`, optional):
      How many extra attempts to make if the request fails or the body is not a feed.
      `0` (default) means a single attempt. See `fetch_soup()`.

    ### Returns
    - **tuple**:
      - `(True, dict)`: On success, returns parsed feed data.
      - `(False, str or Exception)`: On failure, returns an error message or exception.

    ### Notes
    - Atom feeds must have a `<feed>` root element.
    - RSS feeds must have a `<rss>` root element.
    - Automatically detects the feed format (Atom or RSS).

    ### Example
    >>> success, result = parse('https://linuxfabrik.ch/feed.xml')
    >>> if success:
    >>>     print(result)
    {
        'title': 'Linuxfabrik Posts',
        'updated': '2025-04-17T11:29:00.000Z',
        'updated_parsed': datetime.datetime(2025, 4, 17, 11, 29),
        'entries': [
            {
                'title': 'Lorem ipsum',
                'id': 'https://linuxfabrik.ch',
                'updated': '2017-04-17T11:29:00.000Z',
                ...
            },
            ...
        ]
    }
    """
    success, soup = fetch_soup(
        feed_url,
        encoding=encoding,
        insecure=insecure,
        no_proxy=no_proxy,
        retries=retries,
        timeout=timeout,
    )
    if not success:
        return False, soup

    if soup.feed:
        return True, parse_atom(soup)

    return True, parse_rss(soup)


def parse_atom(soup):
    """
    Parse an Atom XML feed into a structured dictionary.

    This function processes an Atom feed using BeautifulSoup, extracting metadata such as the feed
    title, last updated timestamp, and a list of entries with their respective information.

    ### Parameters
    - **soup** (`BeautifulSoup`):
      A BeautifulSoup object parsed from an Atom XML feed.

    ### Returns
    - **dict**:
      A dictionary containing feed metadata and a list of parsed entries.

    ### Notes
    - The `updated` fields are also parsed into Python `datetime` objects (`updated_parsed`).
    - Summaries are extracted from either `<summary>` or `<content>`, cleaned of HTML tags.

    ### Example
    >>> parse_atom(soup)
    {
        'title': 'My Feed',
        'updated': '2024-04-17T15:04:00+00:00',
        'updated_parsed': datetime.datetime(2024, 4, 17, 15, 4, 0),
        'entries': [...],
    }
    """
    result = {
        'title': soup.title.string if soup.title else 'n/a',
        'updated': soup.updated.string if soup.updated else '1970-01-01T00:00:00',
    }
    result['updated_parsed'] = time.timestr2datetime(
        result['updated'][:19],
        pattern='%Y-%m-%dT%H:%M:%S',
    )

    result['entries'] = []
    for entry in soup.find_all('entry'):
        tmp = {
            'title': entry.title.string if entry.title else 'n/a',
            'id': entry.id.string if entry.id else 'n/a',
            'updated': entry.updated.string if entry.updated else '1970-01-01T00:00:00',
        }
        tmp['updated_parsed'] = time.timestr2datetime(
            tmp['updated'][:19],
            pattern='%Y-%m-%dT%H:%M:%S',
        )
        # summary
        try:
            parsed_summary = BeautifulSoup(entry.summary.string, 'lxml')
            tmp['summary'] = parsed_summary.get_text()
        except Exception:
            try:
                parsed_summary = BeautifulSoup(entry.content.string, 'lxml')
                tmp['summary'] = parsed_summary.get_text()
            except Exception:
                tmp['summary'] = ''
        result['entries'].append(tmp)
    return result


def parse_rss(soup):
    """
    Parse an RSS XML feed into a structured dictionary.

    This function processes an RSS feed using BeautifulSoup, extracting metadata such as the feed
    title, last update timestamp, and a list of items with their respective information.

    ### Parameters
    - **soup** (`BeautifulSoup`):
      A BeautifulSoup object parsed from an RSS XML feed.

    ### Returns
    - **dict**:
      A dictionary containing feed metadata and a list of parsed items.

    ### Notes
    - If `pubDate` is missing, `lastBuildDate` is used instead.
    - The `updated` fields are parsed into Python `datetime` objects (`updated_parsed`).
    - Summaries are extracted from the `<description>` tag, cleaned of HTML tags.

    ### Example
    >>> parse_rss(soup)
    {
        'title': 'My RSS Feed',
        'updated': 'Wed, 10 Apr 2024 06:12:00 Z',
        'updated_parsed': datetime.datetime(2024, 4, 10, 6, 12, 0),
        'entries': [...],
    }
    """
    result = {}
    result['title'] = (
        soup.rss.channel.title.string
        if soup.rss and soup.rss.channel and soup.rss.channel.title
        else 'n/a'
    )

    updated = None
    try:
        updated = soup.rss.channel.pubDate.string
    except Exception:
        try:
            updated = soup.rss.channel.lastBuildDate.string
        except Exception:
            pass

    if updated:
        result['updated'] = updated
        result['updated_parsed'] = time.timestr2datetime(
            updated[:25],
            pattern='%a, %d %b %Y %H:%M:%S',
        )

    result['entries'] = []
    for entry in soup.find_all('item'):
        tmp = {
            'title': entry.title.string if entry.title else 'n/a',
            'id': entry.guid.string if entry.guid else 'n/a',
            'updated': entry.pubDate.string
            if entry.pubDate
            else 'Wed, 01 Jan 1970 00:00:00',
        }
        tmp['updated_parsed'] = time.timestr2datetime(
            tmp['updated'][:25],
            pattern='%a, %d %b %Y %H:%M:%S',
        )
        try:
            description_soup = BeautifulSoup(entry.description.string, 'lxml')
            tmp['summary'] = description_soup.get_text()
        except Exception:
            tmp['summary'] = ''
        result['entries'].append(tmp)

    return result


def parse_soup(xml, feed_url=''):
    """
    Parse an Atom or RSS document that has already been read into memory.

    Use this for a feed that did not come from `fetch_soup()`, for example one read from a
    file or from a test fixture, so that both paths apply the same validation.

    ### Parameters
    - **xml** (`str` | `bytes`):
      The feed document.
    - **feed_url** (`str`, optional):
      Where the document came from. Only used to name the source in the error message.

    ### Returns
    - **tuple**:
      - `(True, BeautifulSoup)`: On success, the parsed feed document.
      - `(False, str or Exception)`: If the document has neither an `<rss>` nor a `<feed>`
        root, or if it could not be parsed at all.

    ### Example
    >>> success, soup = parse_soup(open('feed.xml').read())
    """
    try:
        soup = BeautifulSoup(xml, 'xml')
    except Exception as e:
        return False, e

    # A feed document has an <rss> or a <feed> root. Anything else means the source
    # answered with something that is not a feed at all, for example a near-empty body or
    # an HTML error page. Both parse without raising and would otherwise be mistaken for a
    # feed that happens to carry no entries.
    if soup.feed or soup.rss:
        return True, soup

    return False, f'{feed_url} does not seem to be an Atom or RSS feed I understand.'
