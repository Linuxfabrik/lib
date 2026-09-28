#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library reads the machine-readable report of a Lynis security audit and
turns its findings into a list an administrator can act on.

Lynis writes one `key=value` pair per line to `/var/log/lynis-report.dat` when it
runs as root. Keys ending in `[]` repeat, one line per item. A finding (`warning[]`)
and a hardening suggestion (`suggestion[]`) carry `TEST-ID|text|details|solution|`,
with `-` for an empty field. Verified against the Lynis source (3.1.8) and against
reports of Lynis 3.0.7 to 3.1.7 on Debian 12/13, Rocky 8/9/10 and Ubuntu
22.04/24.04/26.04.

Lynis rewrites the report while it audits: the file is truncated when an audit
starts and `hardening_index` and `report_datetime_end` are written last, so a
report read during an audit lacks both.

Typical use case:

.. code-block:: python

    report = lib.lynis.parse_report(text)
    findings = lib.lynis.parse_findings(report['warnings'])
    suggestions = lib.lynis.parse_findings(report['suggestions'])
    print(lib.lynis.get_findings_msg(findings, suggestions))
"""

from . import base
from .globals import STATE_OK, STATE_WARN

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026092801'

# Where Lynis keeps its files when it runs as root.
CUSTOM_PROFILE = '/etc/lynis/custom.prf'
LOG = '/var/log/lynis.log'
PID = '/var/run/lynis.pid'
REPORT = '/var/log/lynis-report.dat'


def parse_report(text):
    """
    Parse a Lynis `lynis-report.dat` into a dictionary.

    Parameters
    ----------
    text : str
        The content of the report.

    Returns
    -------
    dict
        `hardening_index` (int, or None while the audit that writes the report is
        still running), `hostname`, `ipv4_addresses` and `ipv6_addresses` (lists),
        `lynis_version`, `os_name`, `report_datetime_end` (`YYYY-MM-DD HH:MM:SS` in
        the audited host's local time, empty while the audit is still running),
        `suggestions` and `warnings` (lists of the raw `TEST-ID|text|details|...`
        values).

    Examples
    --------
    >>> parse_report('hardening_index=65\\nwarning[]=SSH-7408|Weak option|-|-|\\n')
    {'hardening_index': 65, 'hostname': '', 'ipv4_addresses': [], ...}
    """
    data = {
        'hardening_index': None,
        'hostname': '',
        'ipv4_addresses': [],
        'ipv6_addresses': [],
        'lynis_version': '',
        'os_name': '',
        'report_datetime_end': '',
        'suggestions': [],
        'warnings': [],
    }
    for line in text.splitlines():
        key, sep, value = line.partition('=')
        if not sep:
            continue
        if key == 'hardening_index':
            try:
                data['hardening_index'] = int(value)
            except ValueError:
                pass
        elif key == 'warning[]':
            data['warnings'].append(value)
        elif key == 'suggestion[]':
            data['suggestions'].append(value)
        elif key == 'network_ipv4_address[]':
            data['ipv4_addresses'].append(value)
        elif key == 'network_ipv6_address[]':
            data['ipv6_addresses'].append(value)
        elif key in ('hostname', 'lynis_version', 'os_name', 'report_datetime_end'):
            data[key] = value
    return data


def parse_findings(entries):
    """
    Split Lynis `warning[]` or `suggestion[]` values into rows.

    Parameters
    ----------
    entries : list of str
        Values of the form `TEST-ID|text|details|solution|`. Lynis writes `-` for an
        empty field.

    Returns
    -------
    list of dict
        One row per entry, with `test`, `finding` and `details` (empty instead of
        `-`).

    Examples
    --------
    >>> parse_findings(['KRNL-5820|Disable core dumps|-|-|'])
    [{'test': 'KRNL-5820', 'finding': 'Disable core dumps', 'details': ''}]
    """
    rows = []
    for entry in entries:
        fields = entry.split('|')
        details = fields[2] if len(fields) > 2 else ''
        rows.append(
            {
                'test': fields[0],
                'finding': fields[1] if len(fields) > 1 else '',
                'details': '' if details == '-' else details,
            }
        )
    return rows


def get_findings_msg(findings, suggestions):
    """
    List the findings and suggestions of one or more reports for the plugin output.

    A finding is marked `[WARNING]`, a suggestion is hardening advice and carries no
    state. Both lists are sorted by test ID, so a category stays together and the
    same item on several hosts ends up side by side. A closing line tells how to
    look up an item and how to accept it.

    Parameters
    ----------
    findings : list of dict
        Rows from `parse_findings()` of the `warning[]` entries. A row with a `host`
        key is prefixed with that host.
    suggestions : list of dict
        Rows from `parse_findings()` of the `suggestion[]` entries, likewise.

    Returns
    -------
    str
        The lists, each preceded by an empty line, or an empty string if there is
        nothing to list.

    Examples
    --------
    >>> get_findings_msg(
    ...     [], [{'test': 'KRNL-5820', 'finding': 'Disable core dumps', 'details': ''}]
    ... )
    '\\n\\nSuggestions:\\n* KRNL-5820: Disable core dumps.\\n\\nTo look up an item, ...'
    """
    msg = ''
    for rows, label, item_state in (
        (findings, 'Findings', STATE_WARN),
        (suggestions, 'Suggestions', STATE_OK),
    ):
        if not rows:
            continue
        msg += f'\n\n{label}:'
        for row in sorted(
            rows, key=lambda r: (r['test'], r.get('host', ''), r['finding'])
        ):
            host = f'{row["host"]}: ' if row.get('host') else ''
            text = f'{row["finding"].rstrip(".")}.'
            if row['details']:
                text += f' {row["details"].rstrip(".")}.'
            msg += (
                f'\n* {host}{row["test"]}: {text}'
                f'{base.state2str(item_state, prefix=" ")}'
            )
    if findings or suggestions:
        example = min(row['test'] for row in findings or suggestions)
        msg += (
            f'\n\nTo look up an item, run `lynis show details {example}` on the host. '
            f'To accept it, add `skip-test={example}` to `{CUSTOM_PROFILE}`.'
        )
    return msg
