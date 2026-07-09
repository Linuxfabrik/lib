#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""Provides functions for sending email via SMTP, including multipart
plain-text/HTML messages with inline related images.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026070901'

import smtplib
from email.message import EmailMessage


def send(
    server,
    sender,
    recipient,
    subject='',
    plain='',
    html='',
    images=None,
    port=25,
    username=None,
    password=None,
    timeout=8,
):
    """
    Send an email via SMTP.

    Builds a message from a plain-text body and an optional HTML body, optionally embeds inline
    related images (referenced from the HTML by their Content-ID), and delivers it over SMTP.
    When `password` is set, the connection authenticates before sending.

    ### Parameters
    - **server** (`str`): SMTP server hostname or IP address.
    - **sender** (`str`): Envelope and header `From` address.
    - **recipient** (`str`): Header `To` address.
    - **subject** (`str`, optional): Message subject. Only set as a header when non-empty.
      Defaults to `''`.
    - **plain** (`str`, optional): Plain-text body. Defaults to `''`.
    - **html** (`str`, optional): HTML body. When set, the message becomes a
      `multipart/alternative` with the plain-text part first. Defaults to `''` (plain-text only).
    - **images** (`list` of `dict`, optional): Inline images related to the HTML body. Each dict
      holds `data` (`bytes`), `maintype` (`str`), `subtype` (`str`) and `cid` (`str`, the
      Content-ID the HTML refers to via `cid:`). Ignored when `html` is empty. Defaults to `None`.
    - **port** (`int`, optional): SMTP server port. Defaults to `25`.
    - **username** (`str`, optional): Login user. When omitted while `password` is set, `sender`
      is used as the login user. Defaults to `None`.
    - **password** (`str`, optional): Login password. When set, the connection authenticates.
      Defaults to `None`.
    - **timeout** (`int`, optional): Connection timeout in seconds. Defaults to `8`.

    ### Returns
    - **tuple** (`bool`, `bool` or `str`):
      - On success: `(True, True)`.
      - On failure: `(False, 'Error: <error message>')`.

    ### Example
    >>> send(
    ...     'localhost',
    ...     'icinga@example.com',
    ...     'ops@example.com',
    ...     subject='Hi',
    ...     plain='Body',
    ... )
    (True, True)
    """
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = recipient
    if subject:
        msg['Subject'] = subject

    msg.set_content(plain)
    if html:
        msg.add_alternative(html, subtype='html')
        for image in images or []:
            msg.get_payload()[1].add_related(
                image['data'],
                image['maintype'],
                image['subtype'],
                cid=image['cid'],
            )

    try:
        with smtplib.SMTP(host=server, port=port, timeout=timeout) as smtp:
            if password:
                smtp.login(username or sender, password)
            smtp.send_message(msg)
    except Exception as e:
        return False, f'Error: {e}'

    return True, True
