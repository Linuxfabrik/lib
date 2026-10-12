#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""This library collects some Nextcloud related functions."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026101201'

import json
import os
import shlex
import shutil
import stat

from . import disk, shell


def _as_owner(cmd, uid):
    """Prefix `cmd` with `sudo --user '#<uid>'` unless this process runs as `uid`
    already, so no sudoers entry is needed then and the call also works in containers
    that ship without `sudo`. The `#` selects the account by UID; it only needs escaping
    for a shell, which is not used. geteuid() is POSIX-only, so it is probed for instead
    of testing the platform."""
    if not hasattr(os, 'geteuid') or os.geteuid() != uid:
        return ['sudo', '--user', f'#{uid}', *cmd]
    return cmd


# Reads the configuration the way `OC\Config::readData()` does, `config.php` first and
# then every `*.config.php` in natural order, merged with `array_replace_recursive()`,
# and prints the app directories (`OC::initPaths()` takes an `apps_paths` entry only
# with both `path` and `url`) and the data directory. `OC::$SERVERROOT` is provided
# because a configuration may build paths from it. Output of the included files is
# discarded, since Nextcloud refuses a configuration that prints anything. Verified
# against lib/private/Config.php and lib/OC.php of nextcloud/server f9bc042df03
# (36.0.0 dev).
_READ_CONFIG_PHP = """
ini_set('display_errors', 'stderr');
class OC { public static $SERVERROOT = ''; }
OC::$SERVERROOT = $argv[1];
$lf_files = [$argv[2] . 'config.php'];
$lf_extra = glob($argv[2] . '*.config.php');
if (is_array($lf_extra)) {
    natsort($lf_extra);
    $lf_files = array_merge($lf_files, $lf_extra);
}
$lf_all = [];
ob_start();
foreach ($lf_files as $lf_file) {
    unset($CONFIG);
    if (is_file($lf_file)) {
        include $lf_file;
    }
    if (isset($CONFIG) && is_array($CONFIG)) {
        $lf_all = array_replace_recursive($lf_all, $CONFIG);
    }
}
ob_end_clean();
$lf_apps = [];
foreach ((array) ($lf_all['apps_paths'] ?? []) as $lf_entry) {
    if (is_array($lf_entry) && isset($lf_entry['path'], $lf_entry['url'])) {
        $lf_apps[] = rtrim((string) $lf_entry['path'], '/');
    }
}
echo json_encode([
    'apps' => $lf_apps,
    'data' => (string) ($lf_all['datadirectory'] ?? $argv[1] . '/data'),
]);
"""


def _read_config(php, root, uid, timeout):
    """Return `(True, (app_dirs, data_dir))` as the configuration below `root` names
    them, or `(False, message)`. Runs PHP as `uid`, the account `occ` runs as, on the
    configuration files `occ` itself would include; the caller has checked them."""
    config_dir = os.path.join(root, 'config') + os.sep
    success, result = shell.shell_exec(
        _as_owner([php, '-r', _READ_CONFIG_PHP, '--', root, config_dir], uid),
        cwd=root,
        timeout=timeout,
    )
    if not success:
        return False, result
    stdout, _stderr, rc = result
    try:
        if rc != 0:
            raise ValueError
        config = json.loads(stdout)
        apps = [p for p in config['apps'] if isinstance(p, str) and p]
        data = config['data']
    except (KeyError, TypeError, ValueError):
        # PHP's message is left out: a parse error quotes the configuration, a
        # password included, and the caller may not be allowed to read it
        return False, (
            f'Could not read the configuration below `{root}`: PHP ended with rc={rc}. '
            f'Run `php occ status` in `{root}` as the owner of `config/config.php` to '
            'see why.'
        )
    return True, (apps, data)


def _locate(path, php, timeout=None):
    """Resolve an installation and the account `occ` has to run as.

    The account is the owner of `config/config.php`, so whoever can place that file
    decides who runs `occ`. The file therefore has to be a real file, not a symlink to
    one that belongs to somebody else, and the installation must be out of reach of
    anybody but root and that account: otherwise an account without access to the
    installation could have `occ` code of its choosing run as root or as the owner.

    That covers every file `occ` loads, not only `occ` and `config.php`:
    `console.php`, `lib/` with its autoloader, `3rdparty/`, `core/`,
    `config/*.config.php`, and the app directories, which `apps_paths` may place
    outside the installation (Fedora: /var/lib/nextcloud/apps). So the configuration
    directory is checked first, then read for the app and data directories, then the
    installation is checked except its data directory, which holds no code, and every
    app directory on its own. The data directory is left out only as the entry its
    configured path names below a parent nobody else can change, never by where it
    resolves to. A `config.php` that belongs to root, as
    `config_is_read_only` allows, passes only if nobody but root can change any of it.
    Verified against `occ`, `console.php`, `lib/OC.php` and `lib/private/Config.php`
    of nextcloud/server f9bc042df03 (36.0.0 dev), and the Fedora package
    nextcloud-34.0.4-1.fc44.

    Objects below the installation are not named in a refusal: the caller chose the
    path, but may not be allowed to see what is below it.

    Returns `(True, (root, occ, uid))` with resolved paths, or `(False, message)`.
    """
    try:
        path = os.fspath(path)
    except TypeError:
        return False, f'Refusing `{path}`: not a path.'
    config = os.path.join(path, 'config', 'config.php')
    try:
        config_stat = os.lstat(config)
    except (OSError, TypeError, ValueError):
        return False, (
            f'Could not determine the owner of `{config}`. Make sure the path points to '
            'a Nextcloud installation and that the file is readable.'
        )
    if not stat.S_ISREG(config_stat.st_mode):
        return False, f'Refusing `{config}`: not a regular file.'
    uid = config_stat.st_uid
    resolved = []
    for candidate in (path, config, os.path.join(path, 'occ')):
        success, result = disk.resolve_trusted_path(candidate, owners=[uid])
        if not success:
            return False, result
        resolved.append(result)
    root, _config, occ = resolved

    # the configuration is code; check all of it before it runs
    success, result = disk.resolve_trusted_tree(
        os.path.join(root, 'config'), owners=[uid], name_objects=False
    )
    if not success:
        return False, result
    success, result = _read_config(php, root, uid, timeout)
    if not success:
        return False, result
    app_dirs, data_dir = result

    # Leave out the data directory, but only as the entry its configured path names
    # below a parent nobody else can change. Its resolved location must not decide:
    # whoever controls a component of that path could otherwise point it at `apps/`
    # and have the code there skipped.
    data_entry = None
    data_parent, data_name = os.path.split(os.path.normpath(data_dir))
    success, real_parent = disk.resolve_trusted_path(data_parent, owners=[uid])
    if success and data_name:
        data_entry = os.path.join(real_parent, data_name)
    success, result = disk.resolve_trusted_tree(
        root,
        owners=[uid],
        prune=lambda entry: entry == data_entry,
        name_objects=False,
    )
    if not success:
        return False, result
    # every app directory on its own, also one inside the installation: the check
    # above may have left it out with the data directory
    for app_dir in app_dirs:
        if not os.path.isdir(app_dir):
            return False, (
                f'Refusing `{root}`: an app directory its configuration names does not '
                'exist.'
            )
        success, result = disk.resolve_trusted_tree(
            app_dir, owners=[uid], name_objects=False
        )
        if not success:
            return False, (
                f'Refusing `{root}`: an app directory its configuration names can be '
                f'changed by an account other than root and uid {uid}, or cannot be '
                'examined.'
            )
    return True, (root, occ, uid)


def run_occ(path, cmd, _format='json', timeout=None):
    """
    Run a Nextcloud `occ` command as the owner of `config/config.php`.

    The function locates the PHP interpreter on the system and invokes `occ` explicitly as
    `php <occ> --no-warnings <cmd>`. Calling PHP directly avoids relying on `occ` being
    marked executable or on its shebang resolving to a working interpreter, which is not
    always the case on hardened or SCL-based installations.

    Nextcloud's `console.php` aborts unless the calling process runs under the UID that
    owns `config/config.php`. If the current process is not that owner, the command is
    prefixed with `sudo --user '#<uid>'`; if it already is, `sudo` is skipped, so no sudoers
    entry is needed and the call also works in containers that ship without `sudo`.

    Parameters
    ----------
    path : str | os.PathLike
        Absolute path to the root of the Nextcloud installation (directory that contains `occ` and
        `config/`).
    cmd : str
        The `occ` subcommand and arguments to execute (e.g., `"status"`, `"user:list --output=json"`).
    _format : str, optional
        Use `"json"` to parse `stdout` as JSON and return a Python object, or any other value
        (e.g., `"text"`) to return the raw string output. Defaults to `"json"`.
    timeout : int | float | None, optional
        Seconds to wait for `occ` before killing it. `None` (the default) waits indefinitely,
        which is what long-running commands such as `app:update` need.

    Returns
    -------
    tuple[bool, Any]
        - On success: `(True, result)` where `result` is a Python object if `_format == "json"`,
          otherwise a trimmed `str` of `stdout`.
        - On failure: `(False, error)` where `error` is a message describing the failed
          precondition, the failure reported by `shell.shell_exec()` (interpreter not found,
          timeout), the captured output of a non-zero exit, or the JSON decode error.

    Notes
    -----
    - The installation is refused unless nobody but root and the owner of
      `config/config.php` can change it, from `/` down to `occ`, everything below the
      installation except its data directory, and every app directory the
      configuration names (see `disk.resolve_trusted_path()` and
      `disk.resolve_trusted_tree()`), and `config/config.php` has to be a real file. Who
      owns that file decides who `occ` runs as, so a symlink or a copy placed by someone
      else would otherwise choose the account for them, and any file `occ` loads that
      somebody else can change would run their code as that account. A refusal does
      not name the object below the installation, since the caller may not be allowed
      to see it.
    - To find the app and data directories, the configuration is evaluated by PHP as
      the owner of `config/config.php`, after it has been checked; `occ` includes the
      same files as the same account.
    - `_format` only selects how the output is parsed. It does not add `--output=json` to the
      command; the caller has to do that. Not every `occ` command accepts that option, and the
      only valid values are `plain`, `json` and `json_pretty`. Some commands, `config:list`
      among them, already emit JSON without the option.
    - PHP is resolved via `shutil.which('php')`. If no `php` binary is found in `PATH`, the
      call fails with a descriptive error.
    - `--no-warnings` keeps Nextcloud's startup banners (missing PCNTL extension, environment
      complaints, upgrade and maintenance notices) out of the output. `console.php` writes
      several of them to stdout, where they would otherwise break JSON parsing. The option is
      global and does not silence the command's own output.
    - `occ` is run with the Nextcloud root as its working directory, which is where
      `console.php` chdirs to anyway. Doing it up front avoids the complaint it emits when the
      inherited working directory is unreadable.
    - A few failure paths inside Nextcloud print an error and exit with code 0. In JSON mode
      those are caught by the failing parse. In text mode they are indistinguishable from
      regular output, and one of them is translated, so no attempt is made to detect them.

    Examples
    --------
    >>> ok, result = run_occ('/var/www/nextcloud', 'status --output=json')
    >>> ok
    True
    >>> isinstance(result, dict)
    True

    >>> ok, err = run_occ(
    ...     '/var/www/nextcloud', 'user:list --output=json', _format='json'
    ... )
    >>> ok in (True, False)
    True
    """
    php = shutil.which('php')
    if not php:
        return False, (
            'Could not find a `php` interpreter in PATH. Install PHP or make sure it is '
            'reachable for the user running this process.'
        )

    success, result = _locate(path, php, timeout=timeout)
    if not success:
        return False, result
    path, occ, user = result

    # `--no-warnings` goes in front of the subcommand so it cannot be swallowed as the value
    # of a preceding optional-value option. Symfony parses global options anywhere.
    occ_cmd = [php, occ, '--no-warnings', *shlex.split(cmd)]

    occ_cmd = _as_owner(occ_cmd, user)

    success, result = shell.shell_exec(occ_cmd, cwd=path, timeout=timeout)
    # shell_exec() reports its own failures (spawn error, timeout) as (False, <message>),
    # so the result is only a triple once success is confirmed.
    if not success:
        return False, result

    stdout, stderr, rc = result

    # Prefer the return code to decide success/failure, not stderr presence
    if rc != 0:
        cmd_display = ' '.join(occ_cmd)
        return False, f'Error running `{cmd_display}`: rc={rc}\n{stderr or stdout}'

    # If we expect JSON, try to parse it; otherwise return text
    if str(_format).lower() == 'json':
        try:
            return True, json.loads(stdout)
        except json.JSONDecodeError as e:
            # Fall back to text with a clear error
            return False, f'JSON decode error: {e}\nRaw stdout:\n{stdout}'

    return True, stdout.strip()
