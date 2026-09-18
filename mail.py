#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Provides functions for sending email via SMTP, including multipart
plain-text/HTML messages with inline related images, over a connection that is
optionally encrypted with STARTTLS or implicit TLS.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026091401'

import smtplib
import ssl
from email.message import EmailMessage

from . import txt, url

ENCRYPTIONS = ('none', 'starttls', 'tls')


def _error_message(exc, server, port):
    """Return the error message for a failed delivery, in words an operator can act on.

    `smtplib` hands over the answer of the server as `bytes`, and TLS failures arrive in
    the wording of OpenSSL, which says what broke but not what to do about it.
    """
    # Worded and explained like a certificate `url.fetch()` cannot verify. Not
    # delegated to `url._tls_verify_message()`, which names
    # `ssl.SSLCertVerificationError`: Python 3.6 does not have that class, and
    # `verify_code` identifies the exception without it.
    verify_code = getattr(exc, 'verify_code', None)
    if verify_code is not None:
        reason = (getattr(exc, 'verify_message', '') or '').strip().rstrip('.')
        message = f'Error: TLS certificate verification failed for {server}:{port}'
        if reason:
            message += f': {reason}'
        hint = url.TLS_VERIFY_HINTS.get(verify_code, '')
        return message + '.' + (f' {hint}' if hint else '')
    if (
        isinstance(exc, ssl.SSLError)
        and getattr(exc, 'reason', None) == 'WRONG_VERSION_NUMBER'
    ):
        return (
            f'Error: {server}:{port} does not speak TLS from the start. '
            'It expects a plaintext connection, possibly upgraded with STARTTLS.'
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        refused = ', '.join(
            f'{recipient} ({code} {txt.to_text(answer, errors="strict_or_latin1")})'
            for recipient, (code, answer) in exc.recipients.items()
        )
        return f'Error: recipient refused: {refused}'
    if isinstance(exc, smtplib.SMTPResponseException):
        answer = txt.to_text(exc.smtp_error, errors='strict_or_latin1')
        return f'Error: {exc.smtp_code} {answer}'
    return f'Error: {exc}'


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
    encryption='none',
    insecure=False,
):
    """
    Send an email via SMTP.

    Builds a message from a plain-text body and an optional HTML body, optionally
    embeds inline related images (referenced from the HTML by their Content-ID), and
    delivers it over SMTP, encrypted with STARTTLS or implicit TLS on request. When
    `password` is set, the connection authenticates before sending, and only after it
    has been encrypted.

    Parameters
    ----------
    server : str
        SMTP server hostname or IP address. With `encryption`, the
        server certificate has to be valid for exactly this name.
    sender : str
        Envelope and header `From` address.
    recipient : str
        Header `To` address.
    subject : str, optional
        Message subject. Only set as a header when
        non-empty. Defaults to `''`.
    plain : str, optional
        Plain-text body. Defaults to `''`.
    html : str, optional
        HTML body. When set, the message becomes a
        `multipart/alternative` with the plain-text part first. Defaults to `''`
        (plain-text only).
    images : list of dict, optional
        Inline images related to the HTML body.
        Each dict holds `data` (`bytes`), `maintype` (`str`), `subtype` (`str`) and `cid`
        (`str`, the Content-ID the HTML refers to via `cid:`). Ignored when `html` is
        empty. Defaults to `None`.
    port : int, optional
        SMTP server port. Defaults to `25`.
    username : str, optional
        Login user. When omitted while `password` is set,
        `sender` is used as the login user. Defaults to `None`.
    password : str, optional
        Login password. When set, the connection
        authenticates. Defaults to `None`.
    timeout : int, optional
        Connection timeout in seconds. Defaults to `8`.
    encryption : str, optional
        One of `ENCRYPTIONS`. `'none'` sends the message
        and the login in plaintext. `'starttls'` upgrades the connection with STARTTLS
        before anything else is sent, and fails if the server does not offer it.
        `'tls'` encrypts the connection from the first byte (SMTPS, implicit TLS). The
        server certificate is verified against the trust store of the host. Defaults to
        `'none'`.
    insecure : bool, optional
        Skip the verification of the server certificate
        and its name. Has no effect without `encryption`. Defaults to `False`.

    Returns
    -------
    tuple (bool, bool or str)
        - On success: `(True, True)`.
        - On failure: `(False, 'Error: <error message>')`, also for an unknown
          `encryption`, in which case no connection is opened. The answer of the server
          is decoded to text, and a certificate that does not verify or a port that does
          not speak TLS is explained.

    Examples
    --------
    >>> send(
    ...     'smtp.example.com',
    ...     'icinga@example.com',
    ...     'ops@example.com',
    ...     subject='Hi',
    ...     plain='Body',
    ...     port=465,
    ...     username='icinga@example.com',
    ...     password='linuxfabrik',
    ...     encryption='tls',
    ... )
    (True, True)
    """
    if encryption not in ENCRYPTIONS:
        return (
            False,
            f'Error: unknown encryption "{encryption}", expected one of '
            f'{", ".join(ENCRYPTIONS)}',
        )

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

    # smtplib verifies nothing unless it is handed a context: without one, both
    # SMTP.starttls() and SMTP_SSL fall back to ssl._create_stdlib_context, which is
    # ssl._create_unverified_context. Verified against CPython 3.14 `smtplib.py`, and
    # against Postfix with Python 3.9 on Rocky 9 and Python 3.13 on Debian 13 (a
    # certificate for another name is refused).
    context = None
    if encryption != 'none':
        context = ssl.create_default_context()
        if insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

    try:
        if encryption == 'tls':
            smtp = smtplib.SMTP_SSL(
                host=server,
                port=port,
                timeout=timeout,
                context=context,
            )
        else:
            smtp = smtplib.SMTP(host=server, port=port, timeout=timeout)
        with smtp:
            if encryption == 'starttls':
                # raises SMTPNotSupportedError if the server does not offer STARTTLS,
                # so the mail is never sent in plaintext by accident
                smtp.starttls(context=context)
            if password:
                smtp.login(username or sender, password)
            smtp.send_message(msg)
    except Exception as e:
        return False, _error_message(e, server, port)

    return True, True
