#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""This library collects some WordPress related functions, reading a local WordPress
installation directly from the filesystem.

The functions here mirror how WordPress itself discovers its own version, plugins and
themes, so no database connection, no HTTP request and no `wp-cli` are needed. All of
them take the path to the installation root, the directory holding `wp-includes/` and
`wp-content/`.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026080701'

import glob as _glob
import os
import re

from . import disk, txt

# Relative location of the file WordPress keeps its own version in. Present in every
# installation, which makes it the marker for "this path is a WordPress installation".
VERSION_FILE = os.path.join('wp-includes', 'version.php')

# Name of the file holding the installation's configuration, including its database
# credentials. Only the two site URL constants are ever read out of it.
CONFIG_FILE = 'wp-config.php'

# How much of a plugin or theme file is read to find its metadata header. WordPress
# itself reads the same 8 KiB in `get_file_data()`, so a `Plugin Name:` line further
# down the file is not a header field for WordPress either, and must not be treated as
# one here. Keeping the read bounded also means a single oversized file cannot exhaust
# memory.
HEADER_BYTES = 8192

# Upper bound for the configuration read. Every real `wp-config.php` is a few kilobytes;
# the cap only exists so a file that is not what it claims to be cannot be read
# unbounded.
CONFIG_BYTES = 65536

# Order in which the site URL is taken from the configuration. `WP_HOME` is the address
# visitors use, `WP_SITEURL` the one WordPress itself is reached under. They differ on
# installations that keep the core in a subdirectory, and the visitor-facing one is what
# a consumer wants.
SITE_URL_CONSTANTS = ('WP_HOME', 'WP_SITEURL')


def _read_header(filename):
    """Return the leading `HEADER_BYTES` of a file as text, or the empty string when it
    cannot be read. Decoded with `strict_or_latin1` because a plugin author is free to
    save the file in any encoding and the values end up in the consumer's output.
    """
    success, raw = disk.read_file(filename, binary=True, max_bytes=HEADER_BYTES)
    if not success:
        return ''
    return txt.to_text(raw, errors='strict_or_latin1')


def _header_value(header, field):
    """Extract a single field from an already-read header block."""
    match = re.search(rf'(?im)^[ \t*#/]*{re.escape(field)}\s*:\s*(.+)$', header)
    return match.group(1).strip() if match else ''


def get_header_value(filename, field):
    """
    Read a single field from a WordPress file header.

    WordPress describes a plugin through a comment block at the top of its main PHP file
    and a theme through the same kind of block at the top of its `style.css`. Each field
    sits on its own line as `Field: value`, optionally preceded by comment markers.

    ### Parameters
    - **filename** *(str | os.PathLike)*:
      Path to the file to read.
    - **field** *(str)*:
      Name of the header field, for example `'Plugin Name'`, `'Theme Name'` or
      `'Version'`. Matched case-insensitively and taken literally, so a field name
      containing regex metacharacters is safe.

    ### Returns
    - **str**: The value with surrounding whitespace removed, or the empty string when
      the field is absent or the file cannot be read.

    ### Notes
    - Only the leading `HEADER_BYTES` of the file are searched, the same amount
      WordPress reads in `get_file_data()`. A matching line further down is therefore
      not a header field here either, and a large file is never read completely.
    - Only the first occurrence within that block is returned.
    - A field without a colon, such as the `@version` tag of a docblock, is not a header
      field and is deliberately not matched.

    ### Example
    >>> get_header_value('wp-content/plugins/akismet/akismet.php', 'Version')
    '5.7'
    """
    return _header_value(_read_header(filename), field)


def get_plugins(path):
    """
    List the plugins installed in a local WordPress installation.

    Mirrors how WordPress discovers plugins: a plugin is a PHP file lying directly in
    `wp-content/plugins/` or directly in one of its immediate subdirectories and
    carrying a `Plugin Name` header. Files without that header are not plugins, which
    excludes the `index.php` placeholder WordPress ships in every directory as well as
    the remaining source files of a plugin. Nested directories are not searched, matching
    WordPress, which keeps the scan bounded on installations with many plugins.

    ### Parameters
    - **path** *(str | os.PathLike)*: Path to the installation root.

    ### Returns
    - **dict**: `{slug: version}` for every plugin found. The slug is the directory name,
      or the file name without its extension for a single-file plugin such as
      `hello.php`. The version is the value of the `Version` header, or `'unknown'` when
      the plugin declares none. An installation without a readable plugin directory
      yields an empty dict.

    ### Notes
    - Symlinks are followed. The plugin directory is writable by the web server on
      installations that allow updates through the admin interface, so anyone able to
      write there can point an entry at a file outside the installation and have its
      header fields end up in the caller's output. Where that matters, run the consumer
      against a path the web server cannot write to, or verify the tree separately.

    ### Example
    >>> get_plugins('/var/www/html/wordpress')
    {'akismet': '5.7', 'contact-form-7': '5.0', 'hello': '1.7.2'}
    """
    plugins = {}
    plugin_dir = os.path.join(path, 'wp-content', 'plugins')
    # The directory is data, not a pattern: a `[` or `?` in the caller's path would
    # otherwise be read as a glob metacharacter and silently match nothing.
    quoted_dir = _glob.escape(plugin_dir)
    candidates = disk.glob(os.path.join(quoted_dir, '*.php'), recursive=False)
    candidates += disk.glob(os.path.join(quoted_dir, '*', '*.php'), recursive=False)
    for candidate in candidates:
        # One bounded read per file, then both fields out of it.
        header = _read_header(candidate)
        if not _header_value(header, 'Plugin Name'):
            continue
        parent = os.path.dirname(candidate)
        if os.path.normcase(os.path.normpath(parent)) == os.path.normcase(
            os.path.normpath(plugin_dir)
        ):
            slug = os.path.splitext(os.path.basename(candidate))[0]
        else:
            slug = os.path.basename(parent)
        # A plugin directory can hold more than one file with a header; the first one
        # wins, which is the order WordPress uses.
        if slug not in plugins:
            plugins[slug] = get_header_value(candidate, 'Version') or 'unknown'
    return plugins


def get_themes(path):
    """
    List the themes installed in a local WordPress installation.

    A theme is a directory below `wp-content/themes/` holding a `style.css`, whose
    header block carries the theme metadata.

    ### Parameters
    - **path** *(str | os.PathLike)*: Path to the installation root.

    ### Returns
    - **dict**: `{slug: version}` for every theme found, the slug being the directory
      name. The version is the value of the `Version` header, or `'unknown'` when the
      theme declares none. An installation without a readable theme directory yields an
      empty dict.

    ### Example
    >>> get_themes('/var/www/html/wordpress')
    {'twentytwentyfive': '1.5', 'twentytwentyfour': '1.5'}
    """
    themes = {}
    theme_dir = os.path.join(path, 'wp-content', 'themes')
    # See get_plugins(): the directory is data, not a pattern.
    for stylesheet in disk.glob(
        os.path.join(_glob.escape(theme_dir), '*', 'style.css'), recursive=False
    ):
        slug = os.path.basename(os.path.dirname(stylesheet))
        themes[slug] = get_header_value(stylesheet, 'Version') or 'unknown'
    return themes


def get_site_url(path):
    """
    Read the site URL a local WordPress installation is served under.

    WordPress keeps the site URL in its database, but an installation may pin it in
    `wp-config.php` through the `WP_HOME` and `WP_SITEURL` constants. Where they are
    set, a consumer can address the site without being told the URL. Where they are not,
    the URL is simply not knowable from the filesystem and the caller has to ask for it.

    ### Parameters
    - **path** *(str | os.PathLike)*: Path to the installation root.

    ### Returns
    - **tuple[bool, str]**:
      - On success: `(True, url)`, where `url` is the empty string when the
        configuration is readable but pins neither constant.
      - On failure: `(False, error)` when no configuration file can be read.

    ### Notes
    - `WP_HOME` wins over `WP_SITEURL`. The first is the address visitors use, the
      second the one the core itself is reached under; they differ on installations
      keeping the core in a subdirectory.
    - Looked up in `<path>/wp-config.php` first, then one directory above, which is the
      only other place WordPress itself accepts the file in.
    - A value assembled at runtime, such as `'https://' . $_SERVER['HTTP_HOST']`, is not
      a fixed URL and is skipped rather than returned half-read.
    - `wp-config.php` holds the database credentials. Only the two constants above are
      ever extracted; no other part of the file is returned to the caller. On a typical
      installation the file is not world-readable, so an unprivileged consumer will
      usually get the failure branch, which is a permission problem and not an error in
      the installation.

    ### Example
    >>> get_site_url('/var/www/html/wordpress')
    (True, 'https://www.example.com')
    """
    error = ''
    for candidate in (
        os.path.join(path, CONFIG_FILE),
        os.path.join(path, os.pardir, CONFIG_FILE),
    ):
        success, config = disk.read_file(
            candidate, binary=True, max_bytes=CONFIG_BYTES
        )
        if not success:
            error = error or config
            continue
        config = txt.to_text(config, errors='strict_or_latin1')
        for constant in SITE_URL_CONSTANTS:
            # Matches both PHP quoting styles and tolerates whitespace anywhere the
            # language does. The closing quote must be followed by the end of the
            # argument, so a concatenated expression does not match at all.
            match = re.search(
                rf"""define\s*\(\s*(['"]){constant}\1\s*,\s*"""
                r"""(['"])(https?://[^'"]+)\2\s*[,)]""",
                config,
            )
            if match:
                return (True, match.group(3).rstrip('/'))
        return (True, '')
    return (False, error or f'No "{CONFIG_FILE}" found below "{path}".')


def get_version(path):
    """
    Read the WordPress core version from a local installation.

    Reads the same file WordPress reads to know its own version, so the result is the
    installed version, not one inferred from a fingerprint.

    ### Parameters
    - **path** *(str | os.PathLike)*: Path to the installation root.

    ### Returns
    - **tuple[bool, str]**:
      - On success: `(True, version)`, where `version` is the empty string when the file
        is present but carries no recognizable version assignment.
      - On failure: `(False, error)` when the file cannot be opened or read.

    ### Example
    >>> get_version('/var/www/html/wordpress')
    (True, '7.0.2')
    """
    return disk.grep_file(
        os.path.join(path, VERSION_FILE),
        r"wp_version\s*=\s*'([^']*)'",
    )


def is_installation(path):
    """
    Report whether a path holds a WordPress installation.

    Useful to tell "the caller pointed at the wrong directory" apart from "the
    installation is there but empty", which the inventory functions above cannot express
    on their own: both would simply yield nothing.

    ### Parameters
    - **path** *(str | os.PathLike)*: Path to the installation root.

    ### Returns
    - **bool**: True if the WordPress version file is present and readable below `path`.

    ### Example
    >>> is_installation('/var/www/html/wordpress')
    True
    """
    return disk.file_exists(os.path.join(path, VERSION_FILE))
