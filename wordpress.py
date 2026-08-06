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
__version__ = '2026080601'

import os
import re

from . import disk

# Relative location of the file WordPress keeps its own version in. Present in every
# installation, which makes it the marker for "this path is a WordPress installation".
VERSION_FILE = os.path.join('wp-includes', 'version.php')


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
    - Only the first occurrence is returned, which is the header block, because the
      block sits at the top of the file.
    - A field without a colon, such as the `@version` tag of a docblock, is not a header
      field and is deliberately not matched.

    ### Example
    >>> get_header_value('wp-content/plugins/akismet/akismet.php', 'Version')
    '5.7'
    """
    success, value = disk.grep_file(
        filename,
        rf'(?im)^[ \t*#/]*{re.escape(field)}\s*:\s*(.+)$',
    )
    if not success:
        return ''
    return value.strip()


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

    ### Example
    >>> get_plugins('/var/www/html/wordpress')
    {'akismet': '5.7', 'contact-form-7': '5.0', 'hello': '1.7.2'}
    """
    plugins = {}
    plugin_dir = os.path.join(path, 'wp-content', 'plugins')
    candidates = disk.glob(os.path.join(plugin_dir, '*.php'), recursive=False)
    candidates += disk.glob(os.path.join(plugin_dir, '*', '*.php'), recursive=False)
    for candidate in candidates:
        if not get_header_value(candidate, 'Plugin Name'):
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
    for stylesheet in disk.glob(
        os.path.join(theme_dir, '*', 'style.css'), recursive=False
    ):
        slug = os.path.basename(os.path.dirname(stylesheet))
        themes[slug] = get_header_value(stylesheet, 'Version') or 'unknown'
    return themes


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
        r"wp_version\s*=\s*'(.*)'",
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
