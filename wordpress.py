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

The functions here mirror how WordPress itself discovers its own version, locale, plugins
and themes, so no database connection, no HTTP request and no `wp-cli` are needed. All of
them take the path to the installation root, the directory holding `wp-includes/` and
`wp-content/`.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026081101'

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

# The same for the version file, which is smaller still: a licence header and a handful
# of assignments, with `$wp_version` among the first of them.
VERSION_BYTES = 16384

# Stand-in for the version of a plugin or theme that declares none. Nothing can be looked up
# for it, so a consumer has to be able to recognize it rather than pass it on.
UNKNOWN_VERSION = 'unknown'

# Locale of a build that does not name one. Only the localized builds carry
# `$wp_local_package`; the original English release has no such line, and this is the
# spelling wordpress.org uses for it.
DEFAULT_LOCALE = 'en_US'

# Order in which the site URL is taken from the configuration. `WP_HOME` is the address
# visitors use, `WP_SITEURL` the one WordPress itself is reached under. They differ on
# installations that keep the core in a subdirectory, and the visitor-facing one is what
# a consumer wants.
SITE_URL_CONSTANTS = ('WP_HOME', 'WP_SITEURL')

# What closes a comment block on the same line as a header field. WordPress removes this
# from every value it reads (`_cleanup_header_comment()`), so a one-line header does not
# carry its own terminator into the value.
COMMENT_TAIL = re.compile(r'\s*(?:\*/|\?>).*')

# A PHP block comment. Removed before the configuration is searched, so a constant
# commented out with `/* */` cannot win over the one that is actually in effect.
BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)

# How a definition that PHP actually evaluates begins: at the start of a line, with no
# line comment in front of it. PHP ignores a commented-out definition, so this library
# has to as well - switching an installation between a staging and a production address
# by commenting one of the two out is a common hand-edit, and reading the commented one
# would send a consumer to the wrong site. Anchoring is used rather than stripping the
# comments, because `//` also occurs inside every URL this module is looking for.
LINE_START = r'(?m)^[^\S\n]*(?!//|#|\*)'


def _read_header(filename):
    """Return the leading `HEADER_BYTES` of a file as text, or the empty string when it
    cannot be read. Decoded with `strict_or_latin1` because a plugin author is free to
    save the file in any encoding and the values end up in the consumer's output.

    Carriage returns become newlines, the way WordPress normalizes the same read. A file
    saved with carriage returns alone would otherwise hold its whole header on one line,
    where a field would swallow everything behind it instead of ending at its own value.
    """
    success, raw = disk.read_file(filename, binary=True, max_bytes=HEADER_BYTES)
    if not success:
        return ''
    return txt.to_text(raw, errors='strict_or_latin1').replace('\r', '\n')


def _header_value(header, field):
    """Extract a single field from an already-read header block.

    The character class and the trailing cleanup mirror WordPress's own
    `get_file_data()` and `_cleanup_header_comment()`, so a value reads here exactly as
    WordPress reads it. Without the cleanup a header written as a single-line comment,
    `/* Version: 1.2 */`, would yield `1.2 */`.

    The opening PHP tag is allowed in front of the field for the same reason: a file that
    puts its whole header on the first line, `<?php /* Plugin Name: Foo */`, is a plugin
    to WordPress, and a consumer that did not accept the tag would not see it at all.
    """
    match = re.search(
        rf'(?im)^(?:[ \t]*<\?php)?[ \t*#/@]*{re.escape(field)}\s*:\s*(.+)$', header
    )
    if not match:
        return ''
    return COMMENT_TAIL.sub('', match.group(1)).strip()


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


def get_locale(path):
    """
    Read the locale a local WordPress installation was built for.

    wordpress.org ships one release per language, not one release plus a language pack, and a
    localized build says which one it is in the same file it keeps its version in. A consumer
    that compares the installation against anything wordpress.org publishes needs to ask for
    the matching build.

    ### Parameters
    - **path** *(str | os.PathLike)*: Path to the installation root.

    ### Returns
    - **tuple[bool, str]**:
      - On success: `(True, locale)`, for example `'de_DE'`. The original English release
        names no locale, and `'en_US'` is returned for it.
      - On failure: `(False, error)` when the version file cannot be opened or read.

    ### Notes
    - Read from `$wp_local_package`, the same variable WordPress and `wp-cli` read it from.
    - A locale reported here is the one the *core* was built for. It says nothing about the
      language the site is displayed in, which an administrator can change at any time
      without replacing the core.

    ### Example
    >>> get_locale('/var/www/html/wordpress')
    (True, 'de_DE')
    """
    success, raw = disk.read_file(
        os.path.join(path, VERSION_FILE), binary=True, max_bytes=VERSION_BYTES
    )
    if not success:
        return (False, raw)
    match = re.search(
        r"wp_local_package\s*=\s*'([^']*)'", txt.to_text(raw, errors='strict_or_latin1')
    )
    return (True, match.group(1) if match and match.group(1) else DEFAULT_LOCALE)


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
    - WordPress lists every header-bearing file separately and has no notion of a main
      file. One entry per directory is more useful to a consumer, so where a directory
      holds several such files the one named after the directory supplies the version,
      that being the convention every plugin follows. Failing that, the first in sorted
      order wins.
    - Symlinks are followed. The plugin directory is writable by the web server on
      installations that allow updates through the admin interface, so anyone able to
      write there can point an entry at a file outside the installation and have its
      header fields end up in the caller's output. Where that matters, run the consumer
      against a path the web server cannot write to, or verify the tree separately.

    ### Example
    >>> get_plugins('/var/www/html/wordpress')
    {'akismet': '5.7', 'contact-form-7': '5.0', 'hello': '1.7.2'}
    """
    return {slug: entry['version'] for slug, entry in _scan_plugins(path).items()}


def get_plugin_slugs(path):
    """
    Map every installed plugin to the slug the wordpress.org plugin directory knows it by.

    A plugin's directory name and its slug in the directory are usually the same, because
    installing from the directory is what creates the directory. They come apart for a
    single-file plugin, whose file name is not its slug - `hello.php`, shipped with every
    WordPress, is `hello-dolly` there - and wherever the directory was renamed by hand.
    Since anything asked about a plugin on wordpress.org is asked by slug, a consumer that
    only has the directory name is asking about the wrong plugin, or about none at all.

    ### Parameters
    - **path** *(str | os.PathLike)*: Path to the installation root.

    ### Returns
    - **dict**: `{directory_slug: wordpress_org_slug}` for every plugin `get_plugins()`
      finds, so the keys of both are the same. The value falls back to the directory slug
      where the plugin names no wordpress.org address.

    ### Notes
    - Taken from the `Plugin URI` header, which is the plugin's own statement of where it
      lives. Only an address below `wordpress.org/plugins/` is read as a slug; a plugin
      hosted on its author's own site keeps its directory name, that being the best guess
      available and the right one whenever it was installed from the directory anyway.
    - Both keys and values are needed. The key is the directory on disk and the value is
      what wordpress.org answers to, and a consumer that conflates them will look in the
      wrong place for one of the two.

    ### Example
    >>> get_plugin_slugs('/var/www/html/wordpress')
    {'akismet': 'akismet', 'hello': 'hello-dolly'}
    """
    return {slug: entry['slug'] for slug, entry in _scan_plugins(path).items()}


def _scan_plugins(path):
    """Read every plugin below `path` once and return what the public functions above
    hand out slices of: `{directory_slug: {'file': ..., 'slug': ..., 'version': ...}}`.

    Mirrors how WordPress discovers plugins: a plugin is a PHP file lying directly in
    `wp-content/plugins/` or directly in one of its immediate subdirectories and carrying
    a `Plugin Name` header. Files without that header are not plugins, which excludes the
    `index.php` placeholder WordPress ships in every directory as well as the remaining
    source files of a plugin. Nested directories are not searched, matching WordPress,
    which keeps the scan bounded on installations with many plugins.
    """
    plugins = {}
    plugin_dir = os.path.join(path, 'wp-content', 'plugins')
    # The directory is data, not a pattern: a `[` or `?` in the caller's path would
    # otherwise be read as a glob metacharacter and silently match nothing.
    quoted_dir = _glob.escape(plugin_dir)
    candidates = disk.glob(os.path.join(quoted_dir, '*.php'), recursive=False)
    candidates += disk.glob(os.path.join(quoted_dir, '*', '*.php'), recursive=False)
    for candidate in candidates:
        # One bounded read per file, then every field out of it.
        header = _read_header(candidate)
        if not _header_value(header, 'Plugin Name'):
            continue
        parent = os.path.dirname(candidate)
        basename = os.path.basename(candidate)
        if os.path.normcase(os.path.normpath(parent)) == os.path.normcase(
            os.path.normpath(plugin_dir)
        ):
            slug = os.path.splitext(basename)[0]
        else:
            slug = os.path.basename(parent)
        # A plugin directory can hold more than one file with a header, an admin page
        # of the plugin among them. WordPress lists each of them separately and has no
        # notion of a main file at all, so there is nothing to mirror here; the file
        # named after its directory is the convention every plugin follows and is
        # therefore preferred. Otherwise the first one in sorted order wins.
        if slug not in plugins or os.path.splitext(basename)[0] == slug:
            plugins[slug] = {
                'file': candidate,
                'slug': _slug_from_uri(_header_value(header, 'Plugin URI')) or slug,
                'version': _header_value(header, 'Version') or UNKNOWN_VERSION,
            }
    return plugins


def _slug_from_uri(uri):
    """Return the plugin slug a `Plugin URI` names, or the empty string when it does not
    point into the wordpress.org plugin directory. Both the `www` and the bare host occur
    in the wild, as do both schemes, and the address may or may not end in a slash.
    """
    match = re.match(
        r'(?i)^https?://(?:[a-z-]+\.)?wordpress\.org/(?:extend/)?plugins/([^/?#]+)',
        uri or '',
    )
    return match.group(1) if match else ''


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

    ### Notes
    - Symlinks are followed, and the theme directory carries the same web server write
      permissions as the plugin directory. See `get_plugins()` for what that means for
      a consumer.

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
        themes[slug] = get_header_value(stylesheet, 'Version') or UNKNOWN_VERSION
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
    - `define()`, `@define()` and `const` are all read, and a definition PHP would skip
      because it sits in a comment is skipped here too.
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
        success, config = disk.read_file(candidate, binary=True, max_bytes=CONFIG_BYTES)
        if not success:
            error = error or config
            continue
        config = BLOCK_COMMENT.sub('', txt.to_text(config, errors='strict_or_latin1'))
        for constant in SITE_URL_CONSTANTS:
            # Matches both PHP quoting styles and tolerates whitespace anywhere the
            # language does. The closing quote must be followed by the end of the
            # argument, so a concatenated expression does not match at all. `@define()`
            # is the same call with its warnings suppressed, and `const` is the other
            # spelling PHP makes visible to `defined()`, so WordPress honours all three.
            match = re.search(
                LINE_START + rf"""@?define\s*\(\s*(['"]){constant}\1\s*,\s*"""
                r"""(['"])(?P<url>https?://[^'"]+)\2\s*[,)]""",
                config,
            ) or re.search(
                LINE_START + rf"""const\s+{constant}\s*=\s*"""
                r"""(['"])(?P<url>https?://[^'"]+)\1\s*;""",
                config,
            )
            if match:
                return (True, match.group('url').rstrip('/'))
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

    ### Notes
    - Read the same bounded, encoding-tolerant way as everything else in this module.
      The file is a few kilobytes of ASCII on every installation, but a consumer must
      not be handed a decoding error dressed up as a missing installation.

    ### Example
    >>> get_version('/var/www/html/wordpress')
    (True, '7.0.2')
    """
    success, raw = disk.read_file(
        os.path.join(path, VERSION_FILE), binary=True, max_bytes=VERSION_BYTES
    )
    if not success:
        return (False, raw)
    match = re.search(
        r"wp_version\s*=\s*'([^']*)'", txt.to_text(raw, errors='strict_or_latin1')
    )
    return (True, match.group(1) if match else '')


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
