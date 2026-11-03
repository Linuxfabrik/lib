#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This module tries to make accessing the Icinga2 API and the configuration of the
Icinga Director easier."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026110301'

import base64
import html
import json
import re
import time
import urllib.parse
from string import Template

from . import shell, txt, url

# Take care of Icinga and throttle the amount of requests, don't overload it
# with too fast subsequent api-calls.
DEFAULT_SLEEP = 1.0


def api_post(
    uri,
    username,
    password,
    data=None,
    method_override='',
    insecure=False,
    no_proxy=False,
    proxy=None,
    timeout=3,
):
    """
    Send a low-level POST request to the Icinga API.

    This function manually crafts a POST request to the Icinga REST API, adding basic authentication
    headers and optionally overriding the HTTP method via `X-HTTP-Method-Override`.

    Parameters
    ----------
    uri : str
        Full API endpoint URL (e.g., `https://icinga.example.com:5665/v1/objects/services`).
    username : str
        API username.
    password : str
        API password.
    data : dict, optional
        Payload to send with the request. Defaults to `None`.
    method_override : str, optional
        If set, override HTTP method (e.g., `'GET'`). Defaults to `''`.
    insecure : bool, optional
        Disable SSL certificate verification. Defaults to `False`.
    no_proxy : bool, optional
        Bypass proxy. Defaults to `False`.
    proxy : str, optional
        Proxy to reach the target through, overriding the one the environment names.
        Defaults to `None`, which leaves the choice to the environment.
    timeout : int, optional
        Timeout for the request in seconds. Defaults to `3`.

    Returns
    -------
    tuple (bool, object)
        The result from the `url.fetch_json` call.

    Notes
    -----
    - Collapses repeated slashes in the path of the URI (`//v1`, from a base URL with a
      trailing slash). The host is left alone, `v1.icinga.example.com` included.
    - Pauses execution for a short duration after sending the request (`DEFAULT_SLEEP`).

    Examples
    --------
    >>> uri = 'https://icinga.example.com:5665/v1/objects/services'
    >>> data = {
    ...     'filter': 'match("special-service", service.name)',
    ...     'attrs': ['name', 'state', 'acknowledgement'],
    ... }
    >>> result = lib.base.coe(
    ...     lib.icinga.api_post(
    ...         uri,
    ...         args.USERNAME,
    ...         args.PASSWORD,
    ...         data=data,
    ...         method_override='GET',
    ...         timeout=3,
    ...     )
    ... )
    """
    # Only the path: replacing `//v1` in the whole URI also hit the `//` after the
    # scheme of a host such as `v1.icinga.example.com`.
    try:
        parts = urllib.parse.urlsplit(uri)
    except ValueError as e:
        # a bracketed host that is no IP address, refused by urlsplit() since gh-103848
        # (CPython 3.9.21, 3.10.16, 3.11.4, 3.12.0, and backports)
        return False, f'Cannot read the URL "{txt.sanitize_sensitive_data(uri)}": {e}'
    uri = urllib.parse.urlunsplit(
        parts._replace(path=re.sub(r'/{2,}', '/', parts.path))
    )
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Basic {txt.to_text(base64.b64encode(txt.to_bytes(f"{username}:{password}")))}',
    }
    if method_override:
        headers['X-HTTP-Method-Override'] = method_override

    result = url.fetch_json(
        uri,
        data=data or {},
        encoding='serialized-json',
        header=headers,
        insecure=insecure,
        no_proxy=no_proxy,
        proxy=proxy,
        timeout=timeout,
    )
    time.sleep(DEFAULT_SLEEP)
    return result


def build_icingaweb2_url(base_url, hostname, servicename=None):
    """
    Build an Icinga Web 2 detail URL for a host or a service.

    Composes the Icinga DB module's host or service detail URL from a base Icinga Web 2 URL and the
    object name(s). A service URL is built when `servicename` is a non-empty string, otherwise a
    host URL.

    The object names are treated as untrusted: they are URL-encoded (including `/`, `&`, `?`, `#`,
    quotes and spaces), so a name cannot inject extra query parameters or break out of the URL. The
    returned link is meant to be embedded verbatim in notifications (mail, chat), so the function
    also pins the scheme to `http`/`https` and never emits a `javascript:`, `data:` or `file:` URL
    from a malformed base URL.

    Parameters
    ----------
    base_url : str
        Base Icinga Web 2 URL, e.g. `https://example.com/icingaweb2`.
    hostname : str
        Host object name.
    servicename : str, optional
        Service object name. When a non-empty string, a service
        detail URL is built; otherwise a host detail URL. Defaults to `None`.

    Returns
    -------
    str or None
        The composed URL, or `None` when `base_url`/`hostname` is missing, not a
        string, or when `base_url` does not use the `http`/`https` scheme.

    Notes
    -----
    - Callers that embed the URL in HTML must still HTML-escape it; encoding a URL is not the same
      as escaping it for an HTML attribute.

    Examples
    --------
    >>> build_icingaweb2_url('https://example.com/icingaweb2', 'web01')
    'https://example.com/icingaweb2/icingadb/host?name=web01'
    >>> build_icingaweb2_url('https://example.com/icingaweb2', 'web01', 'http')
    'https://example.com/icingaweb2/icingadb/service?name=http&host.name=web01'
    """
    if not isinstance(base_url, str) or not isinstance(hostname, str):
        return None
    if not base_url or not hostname:
        return None
    try:
        scheme = urllib.parse.urlsplit(base_url).scheme.lower()
    except ValueError:
        return None
    if scheme not in ('http', 'https'):
        return None
    if isinstance(servicename, str) and servicename:
        query = urllib.parse.urlencode(
            {'name': servicename, 'host.name': hostname},
            quote_via=urllib.parse.quote,
        )
        path = f'icingadb/service?{query}'
    else:
        query = urllib.parse.urlencode(
            {'name': hostname},
            quote_via=urllib.parse.quote,
        )
        path = f'icingadb/host?{query}'
    return urllib.parse.urljoin(f'{base_url}/', path)


# Director keeps keys starting with this prefix in the vars of services generated by
# "apply for" rules (`CustomVariables::RESERVED_OVERRIDE_HANDOFF_KEY`, Director 1.12.1).
# They are bookkeeping, not variables anybody sets.
DIRECTOR_RESERVED_PREFIX = '__director'


def director_cli(argv, timeout=8):
    """
    Run `icingacli director <argv>` and return its parsed JSON output.

    `icingacli` reads the Icinga Director configuration as the account running it, so
    no credentials are needed, but that account has to be able to read the Icinga Web 2
    configuration (on most installations: be a member of the group `icingaweb2`).

    Parameters
    ----------
    argv : list of str
        The arguments after `icingacli director`, for example
        `['hosts', 'fetch', '--json', '--no-pretty']`. Every element is passed as one
        argument, no shell is involved. A value in a positional slot (an object name)
        has to be guarded by the caller, see `shell.safe_cli_value()`, or use
        `director_host_services()`, which does it.
    timeout : int or float, optional
        Seconds the call may take. Defaults to `8`.

    Returns
    -------
    tuple (bool, any)
        `(True, data)` with the parsed JSON, or `(False, message)`.

    Notes
    -----
    - The output carries the variables of the configuration, credentials included,
      so no part of stdout ever goes into a message. Of stderr, only the first line
      is passed on, redacted with `txt.sanitize_sensitive_data()` and cut to 200
      characters.
    - An account that cannot read the configuration gets `ERROR: Cannot read enabled
      modules. Config directory "/etc/icingaweb2" is not readable` with exit code 1
      (Icinga Web 2.14 on Rocky 10). The message then says how to fix it.

    Examples
    --------
    >>> success, hosts = director_cli(['hosts', 'fetch', '--json', '--no-pretty'])
    """
    if not isinstance(argv, (list, tuple)) or not argv:
        return (False, 'director_cli() needs a non-empty list of arguments.')
    if not all(isinstance(arg, str) and '\0' not in arg for arg in argv):
        return (False, 'director_cli() only takes strings without NUL bytes.')
    what = f'`icingacli director {" ".join(argv[:2])}`'
    success, result = shell.shell_exec(
        ['icingacli', 'director', *argv], timeout=timeout
    )
    if not success:
        return (False, f'{what} failed: {result}')
    stdout, stderr, retc = result
    if retc != 0:
        first_line = next((line for line in stderr.splitlines() if line.strip()), '')
        msg = f'{what} failed with exit code {retc}'
        if first_line:
            msg += f': {txt.sanitize_sensitive_data(first_line.strip())[:200]}'
        msg += '.'
        if 'not readable' in first_line or 'permission denied' in first_line.lower():
            msg += (
                ' The account running this has to be able to read the Icinga Web 2'
                ' configuration, for example as a member of the group `icingaweb2`.'
            )
        return (False, msg)
    try:
        return (True, json.loads(stdout))
    except ValueError:
        return (False, f'{what} did not return valid JSON.')


# A runtime macro such as `$cpu_usage_warning$` or `$service.vars.cpu_usage_warning$`.
# `$$` is an escaped dollar sign and does not match.
_MACRO = re.compile(r'\$([A-Za-z0-9_.\-]+)\$')
# Macros starting with one of these name an object attribute, not a service variable.
_MACRO_OBJECTS = ('command', 'host', 'icinga', 'notification', 'service', 'user')


def _macro_vars(value):
    """Return the names of the service variables that the runtime macros in `value`
    refer to. `value` may be any JSON-serializable structure.
    """
    names = set()
    for macro in _MACRO.findall(json.dumps(value, ensure_ascii=False)):
        if macro.startswith('service.vars.'):
            macro = macro[len('service.vars.') :]
        elif macro.split('.')[0] in _MACRO_OBJECTS:
            continue
        # a dictionary member such as `$disks.root$` belongs to the variable `disks`
        names.add(macro.split('.')[0])
    return names


def director_command_vars(commands, name, _seen=()):
    """
    Return the names of the variables a check command uses.

    Collects the variables that the macros in the command line, the arguments, the
    environment and the variables of the command refer to, including those of the
    commands it imports.

    Parameters
    ----------
    commands : dict
        The commands as `icingacli director commands fetch --json` returns them,
        keyed by name. Fetch them without `--resolved`: the resolved export does not
        contain the arguments of imported commands (Director 1.12.1), which is what
        the `-sudo` variants of a command consist of.
    name : str
        The name of the check command.

    Returns
    -------
    set or None
        The variable names, or `None` if the command is unknown, so that a caller can
        tell "uses nothing" from "cannot tell".

    Examples
    --------
    >>> director_command_vars(
    ...     {'cmd-check-load': {'arguments': {'--warning': '$load_warning$'}}},
    ...     'cmd-check-load',
    ... )
    {'load_warning'}
    """
    if not isinstance(commands, dict):
        return None
    obj = commands.get(name)
    if not isinstance(obj, dict) or name in _seen:
        return None
    seen = (*_seen, name)
    names = _macro_vars(
        {key: obj.get(key) for key in ('arguments', 'command', 'env', 'vars')}
    )
    for parent in obj.get('imports') or []:
        names |= director_command_vars(commands, parent, seen) or set()
    return names


def director_host_services(host, timeout=8):
    """
    Return the services of a host with their resolved variables, as the Icinga
    Director computes them.

    Covers the services of Service Sets (also those assigned by filter), of apply
    rules, of host templates and of the host itself, with their templates resolved,
    but without the overrides stored on the host. This is the default every service
    on the host has before "Modify".

    Parameters
    ----------
    host : str
        The name of the host object.
    timeout : int or float, optional
        Seconds the call may take. Defaults to `8`.

    Returns
    -------
    tuple (bool, list or str)
        `(True, services)`, a list of service dicts with `object_name`,
        `check_command`, `service_set` and `vars` among others, or
        `(False, message)`.

    Notes
    -----
    - Uses `icingacli director host show --resolved --with-services --all-services`.
      The REST API of the Director does not offer `--all-services`: its
      `withServices` returns the services of the host object only.
    - Takes 0.5 to 1.2 seconds per host (Director 1.12.1, about 130 services).
    """
    success, host = shell.safe_cli_value(host, 'host name')
    if not success:
        return (False, host)
    if not isinstance(host, str) or not host:
        return (False, 'director_host_services() needs a host name.')
    success, result = director_cli(
        [
            'host',
            'show',
            host,
            '--json',
            '--resolved',
            '--with-services',
            '--all-services',
            '--no-defaults',
            '--no-pretty',
        ],
        timeout=timeout,
    )
    if not success:
        return (False, result)
    services = result.get('services') if isinstance(result, dict) else None
    if not isinstance(services, list):
        return (False, f'The Icinga Director returned no services for host "{host}".')
    return (True, services)


def director_inherited_overrides(hosts, name, varname, _seen=()):
    """
    Return the overrides of service variables a host inherits from its host templates.

    Icinga Director renders the override variable with `+=`, so Icinga 2 adds the
    entries of every imported host template in import order, and those of the host
    itself last. An entry for a service name replaces the one inherited for the same
    name as a whole, it is not merged with it.

    Parameters
    ----------
    hosts : dict
        Hosts and host templates as `icingacli director hosts fetch --json` returns
        them, keyed by name.
    name : str
        The host (or host template). Its own overrides are left out.
    varname : str
        The name of the override variable, `_override_servicevars` unless the
        Director setting `override_services_varname` was changed.

    Returns
    -------
    dict
        `{service name: {variable: value}}`.
    """
    if not isinstance(hosts, dict):
        return {}
    obj = hosts.get(name)
    if not isinstance(obj, dict) or name in _seen:
        return {}
    seen = (*_seen, name)
    overrides = {}
    for parent in obj.get('imports') or []:
        overrides.update(director_inherited_overrides(hosts, parent, varname, seen))
        overrides.update(director_own_overrides(hosts.get(parent), varname))
    return overrides


# Variable names whose values are treated as secrets even if the Director does not
# mark them as hidden or sensitive.
_SENSITIVE_NAME = re.compile(
    r'(api.?key|community|credential|pass|private.?key|secret|token)', re.IGNORECASE
)


def director_is_sensitive(name, sensitive_vars=None):
    """
    Return True if the value of the variable `name` must not be shown.

    Parameters
    ----------
    name : str
        The variable name.
    sensitive_vars : set, optional
        The names `director_sensitive_vars()` returned.

    Returns
    -------
    bool
        True if `name` is in `sensitive_vars`, or if it contains `api-key`,
        `community`, `credential`, `pass`, `private-key`, `secret` or `token`.
    """
    if not isinstance(name, str):
        return False
    return name in (sensitive_vars or set()) or bool(_SENSITIVE_NAME.search(name))


def director_own_overrides(obj, varname):
    """
    Return the overrides of service variables stored on a host or host template.

    Parameters
    ----------
    obj : dict
        The host or host template as `icingacli director hosts fetch --json` returns
        it.
    varname : str
        The name of the override variable, `_override_servicevars` unless the
        Director setting `override_services_varname` was changed.

    Returns
    -------
    dict
        `{service name: {variable: value}}`. Entries that are not a dictionary are
        left out.
    """
    own_vars = (obj.get('vars') or {}) if isinstance(obj, dict) else {}
    own = own_vars.get(varname) if isinstance(own_vars, dict) else None
    if not isinstance(own, dict):
        return {}
    return {
        service: service_vars
        for service, service_vars in own.items()
        if isinstance(service_vars, dict)
    }


def _is_nullish(value):
    """An unset and an empty value have the same effect on a check command."""
    return value is None or value in ('', [], {})


def director_same_value(a, b):
    """
    Compare two variable values the way they reach a check plugin.

    The Icinga Director stores the same number once as a number and once as a string
    (`25` vs `"25"`), so scalars are compared by their text and as numbers. Booleans
    never equal numbers. Unset and empty values are the same. Lists are compared by
    their members, so a reordered list is not a change. Dictionaries are compared key
    by key.

    Parameters
    ----------
    a, b : any
        The two values, as decoded from the JSON of the Director.

    Returns
    -------
    bool

    Examples
    --------
    >>> director_same_value(25, '25')
    True
    >>> director_same_value(['/tmp', '/boot'], ['/boot', '/tmp'])
    True
    >>> director_same_value(True, 1)
    False
    """
    if _is_nullish(a) and _is_nullish(b):
        return True
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float, str)) and isinstance(b, (int, float, str)):
        if str(a) == str(b):
            return True
        try:
            return float(a) == float(b)
        except ValueError:
            return False
    if isinstance(a, list) and isinstance(b, list):
        return (
            len(a) == len(b)
            and all(any(director_same_value(x, y) for y in b) for x in a)
            and all(any(director_same_value(x, y) for x in a) for y in b)
        )
    if isinstance(a, dict) and isinstance(b, dict):
        keys = {k for k, v in a.items() if not _is_nullish(v)}
        keys |= {k for k, v in b.items() if not _is_nullish(v)}
        return all(director_same_value(a.get(k), b.get(k)) for k in keys)
    return False


def director_sensitive_vars(datafields, customproperties):
    """
    Return the names of the variables the Icinga Director marks as secret.

    Parameters
    ----------
    datafields : list
        As `icingacli director export datafields` returns them. A data field with the
        visibility "hidden" counts.
    customproperties : list
        As `icingacli director export customproperties` returns them (Director 1.12
        and later). A custom variable of the type "sensitive", or with a member of that
        type at any depth, counts.

    Returns
    -------
    set
        The variable names.
    """
    names = set()
    for field in datafields if isinstance(datafields, list) else []:
        if not isinstance(field, dict):
            continue
        settings = field.get('settings') or {}
        if isinstance(settings, dict) and settings.get('visibility') == 'hidden':
            names.add(field.get('varname'))

    def is_sensitive(prop):
        if not isinstance(prop, dict):
            return False
        if prop.get('value_type') == 'sensitive':
            return True
        items = prop.get('items') or {}
        return isinstance(items, dict) and any(map(is_sensitive, items.values()))

    for prop in customproperties if isinstance(customproperties, list) else []:
        if is_sensitive(prop):
            names.add(prop.get('key_name'))
    names.discard(None)
    return names


def director_used_vars(command_vars, service_vars):
    """
    Return the variables that reach a check command, directly or indirectly.

    Extends the variables the check command uses by those that the values of used
    variables refer to, for example a variable whose value is `$other_variable$`.

    Parameters
    ----------
    command_vars : set
        As `director_command_vars()` returns them.
    service_vars : dict
        The variables of the service, as they apply on the host.

    Returns
    -------
    set
    """
    used = set(command_vars or ())
    service_vars = service_vars if isinstance(service_vars, dict) else {}
    todo = list(used)
    while todo:
        name = todo.pop()
        for ref in _macro_vars(service_vars.get(name)) - used:
            used.add(ref)
            todo.append(ref)
    return used


# Base64-encoded Icinga logo (PNG, 100x35 px).
_LOGO_PNG_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAAGQAAAAjCAQAAADItmcLAAAAAmJLR0QA/4ePzL8AAAAJcEhZcwAA
CxMAAAsTAQCanBgAAAAHdElNRQfhChAQLB+jeuiSAAAFCklEQVRYw9WYf0yVVRjHP5d7uYAo6JKf
Ggm4NtY0S1PyF6FLW239wRICLfmnQEv+snJmtbExwVzRD2eWs5xDpQbD5la2tlolRKHJQmqZrulF
B1oKBMiFe5/+uIeX9733fbkX18a95/3jfc/zPOc553vOeX69MHGzU0MPLrYT4W0Xop5NkQ3krAak
IbwXGhWE/4/JV0S2fG4jCH3khPdCbUElDjKTTg7xV2SfSBYNREfCQn02kk4dW035m6hnJHL2/UsE
YV0AfS5NxEYGBN+J9ABeHjQ5jwZum47L5DFmhJ+xR1POJZ7gGjW4iWMj84nnHAUUMmAyqoB6HHSx
lKvheDpOdnKAzXRpQbCXFaaSrYq/I3yv2mt4NBiCMOwHZTrL2cIVxS0L3zhykSw/SjMrgAQWsohF
pNNBOwPsYT4nKLawoCkHspB2E5lqUkimg3bO8QceRY1hOJyuksPQW2AqM0oNF/D6UYdNPKAd8ARI
ms16D9Pp4obl9kZhwxuCJou2zmAfY89aE8lCPiDbsAVNuJX8D6zRcZbxIXm6fgy7+VtJ/sTKAM2z
qeWG4p+l2AJoFXUkWgNJZSgARj8xAXJJjCLUa/1nGDaM8fKqxvsT4ZLWu48Og6SHaoPmB3Q+0/cc
87s1ACUIwpGJzmRvAJAaE6l7EYQ21VvNCILgpplmBtS4ZxX3FoKowBvL74p7mZ81yS2a3hSuKlon
LfSq79qA+X9UHjXVGkiCSlfGnlPYgwJpVxdqrroajQhCt1q8Hohvm1zkAxDHOwjCv5qn3I8gXCEX
gHjF95BpmH2ptro3JjqT9bTRgeDlIictClw9kFS17ESdKXciCNP8gDjpQ/CySqfpMwShSjkLH/8h
Hb8BQXjSMPsRDcg168w8mSaygVk4gFROkBQEyP0IwnsG/jJ+4ZBy7eNAFqhLE+hevlK3QX/OY2lr
M98YzDqFYYQRLiAIJVZAanna0C81PT49kFwE4WXLEx4H8ohJ7T9Pp+kuBKExiGd9HUE4TimC0GJe
sxdh0/kigKPkU2tqJ8YmIQdfj4Hm1XFsIWiKphyAtznGdSCXJeMBcQbrmcdNfqOE5/0Uuckmj4N0
TEGwXsIGHMAA++hWtKdIA1poBQ6wC6jw+UcHGZxW/sZDpTZgvG0jh/NTkjx9wWz1PYtt2mp8BuDz
ca8QTRHb6YEo3lIwwM6LJr+Hmtgd0sX5v5vofkAlq/diHlbnUkcdb9IHOH05uMNQ4CaRwK2wyQNX
s5Y57NFRKtR7g0GunGpGovyMb/J7P6LqFH2L5QVDvhVa8/hp6uYopwAYUttcZDounQJw0ESpRrpM
/6Sn912Axw1uej+leIifZKI/iGBjOYn0arRHAXABUEYM8DXvGqK8z+DrIYlftcJ2ZYhT6uOIXeWq
42niRgRhFKdfHMlHED41aMpAEM6o3ncqRkRr9dFNBGEN4MCFIIZMGpx0I4jvx4mdLBaTQ1zIe2fM
tSrURnzLVspoxIsgfBQQEIMDyVNjz/MSm9nHIILQig0oRBCTwq8SQfjkzswwE0H4XnOUxwNy5jMk
KO51hCFswCoE4bBBU5pKOMfajgBNLjIAOIwgPGdiIW7EskQL6uNP4tblOVHspF9XjXysM9lKPOwF
YBptDAY4gUZGdFYKxVoqLwifk6ZlZW5Om/4urMLD+7Y7do52P38Xw93MxE4/LvosJf1HmdHszCEJ
BwO4DMHAidvyR5b7P+7cOe8ELUP1AAAAAElFTkSuQmCC"""


def get_logo():
    """
    Return the Icinga logo as PNG image bytes.

    Provides the bundled Icinga logo as a 100x35 px PNG.

    Returns
    -------
    bytes
        The decoded PNG image data.

    Examples
    --------
    >>> get_logo()[:8]
    b'\\x89PNG\\r\\n\\x1a\\n'
    """
    return base64.b64decode(_LOGO_PNG_BASE64)


def get_service(
    uri,
    username,
    password,
    servicename,
    attrs='state',
    insecure=False,
    no_proxy=False,
    proxy=None,
    timeout=3,
):
    """
    Query a service object from the Icinga API.

    This function sends a high-level request to the Icinga `/v1/objects/services` endpoint
    to retrieve attributes for a specific service, identified by its `__name`.

    Parameters
    ----------
    uri : str
        Base API URL (e.g., `https://icinga.example.com:5665`).
    username : str
        API username.
    password : str
        API password.
    servicename : str
        Unique service name, typically in the format `hostname!service`.
    attrs : str, optional
        Comma-separated list of attributes to retrieve. Defaults to `'state'`.
    insecure : bool, optional
        Disable SSL certificate verification. Defaults to `False`.
    no_proxy : bool, optional
        Ignore proxy settings. Defaults to `False`.
    proxy : str, optional
        Proxy to reach the target through, overriding the one the environment names.
        Defaults to `None`, which leaves the choice to the environment.
    timeout : int, optional
        Request timeout in seconds. Defaults to `3`.

    Returns
    -------
    tuple (bool, object)
        The result from the Icinga API request.

    Notes
    -----
    - The `servicename` must match the `__name` attribute exactly. It is passed as a
      filter variable, so quotes, backslashes and glob characters in it are taken
      literally.
    - Uses a `GET` override on a `POST` request (`X-HTTP-Method-Override` header).

    Examples
    --------
    >>> uri = 'https://icinga.example.com:5665'
    >>> result = lib.base.coe(
    ...     lib.icinga.get_service(
    ...         uri,
    ...         args.USERNAME,
    ...         args.PASSWORD,
    ...         servicename='hostname!special-service',
    ...         attrs='state,acknowledgement',
    ...     )
    ... )
    >>> print(result['result'][0]['attrs'])
    """
    uri = f'{uri.rstrip("/")}/v1/objects/services'
    # The name travels in `filter_vars`, so it is a value and never part of the
    # filter expression: a `"` in it could otherwise add a filter of its own, and a
    # trailing `\\` (a Windows path) broke the parse. `==` rather than `match()`,
    # which compares globs and would let a `*` in the name select other services.
    # Verified against lib/remote/filterutility.cpp of Icinga 2 v2.16.0-206-g703e7d4d3.
    data = {
        'filter': 'service.__name == lf_service',
        'filter_vars': {'lf_service': servicename},
        'attrs': ['name', *attrs.split(',')],
    }
    return api_post(
        uri=uri,
        username=username,
        password=password,
        data=data,
        method_override='GET',
        insecure=insecure,
        no_proxy=no_proxy,
        proxy=proxy,
        timeout=timeout,
    )


def render_notification_mail(rows, logo_cid, hostname):
    """
    Render the plain-text and HTML body of an Icinga notification mail.

    Turns a list of label/value rows into a two-column notification: a plain-text version and an
    HTML version whose header references the bundled logo by Content-ID. Cell values are treated as
    untrusted and HTML-escaped; a newline becomes `<br>` and a value that is a URL becomes a link.

    Parameters
    ----------
    rows : list of dict
        One row per line. Each dict has:

        - `left_column` (`str`): The label.
        - `right_column` (`str` or falsy): The value. Escaped before it reaches the HTML.
        - `right_column_attributes` (`str`, optional): Extra attributes inserted verbatim into the
          value cell's `<td>` (e.g. a fixed `style="..."`). The caller must keep this trusted; it is
          not escaped.
    logo_cid : str
        Content-ID of the inline logo image as produced by
        `email.utils.make_msgid()` (with angle brackets); the brackets are stripped for the `cid:`
        reference.
    hostname : str
        Name of the host generating the notification, shown in the footer.

    Returns
    -------
    tuple (str, str)
        `(plain_text, html)`.

    Notes
    -----
    - `right_column_attributes` is the only field inserted without escaping, so callers must build
      it from trusted data only (a state-keyed color lookup, not raw external input).
    """
    row_template = Template("""
                <tr>
                    <th width="180px" class="$row_class">$left_column</th><td class="$row_class" $right_column_attributes>$right_column</td>
                </tr>
""")

    html_template = Template("""
<html><head><style type="text/css">
body {text-align: center; font-family: Verdana, sans-serif; font-size: 10pt;}
img.logo {float: left; margin: 10px 10px 10px; vertical-align: middle}
img.link {float: right;  margin: 0px 1px; vertical-align: middle}
span {font-family: Verdana, sans-serif; font-size: 12pt;}
table {text-align:center; margin-left: auto; margin-right: auto; border: 1px solid black;}
th {white-space: nowrap;}
th.even {background-color: #D9D9D9;}
td.even {background-color: #F2F2F2;}
th.odd {background-color: #F2F2F2;}
td.odd {background-color: #FFFFFF;}
th,td {font-family: Verdana, sans-serif; font-size: 10pt; text-align:left;}
th.customer {width: 600px; background-color: #004488; color: #ffffff;}
p.foot {width: 1002px; background-color: #004488; color: #ffffff; margin-left: auto; margin-right: auto;};
    </style></head>
        <body>
            <table width="1000px">
                <tr>
                    <td><img class="logo" src="cid:$logo_cid"></td><td><span>Icinga Monitoring System Notification</span></td>
                </tr>
                $table
            </table>

            <p class="foot">Generated by Icinga2 on $icinga_host, the OpenSource monitoring solution.</p>
        </body>
</html>
""")

    table = ''
    plain = ''
    for index, row in enumerate(rows):
        value = row.get('right_column')
        plain += f'{row["left_column"]} {value if value else ""}\n'

        if value:
            if value.startswith('http'):
                safe = html.escape(value, quote=True)
                cell = f'<a href="{safe}">{safe}</a>'
            else:
                cell = html.escape(value).replace('\n', '<br>')
        else:
            cell = ''

        table += row_template.substitute(
            row_class='even' if index % 2 == 0 else 'odd',
            left_column=html.escape(row['left_column']),
            right_column_attributes=row.get('right_column_attributes', ''),
            right_column=cell,
        )

    # the logo_cid arrives wrapped in <> from make_msgid(); the HTML cid: needs it without
    html_body = html_template.substitute(
        table=table,
        icinga_host=html.escape(hostname),
        logo_cid=logo_cid[1:-1],
    )
    return plain, html_body
