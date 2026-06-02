#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/lib/blob/main/CONTRIBUTING.md

"""Shared helpers for the `tools/` scripts.

Kept deliberately small. Every tool under `tools/` imports `REPO_ROOT`
and the `err()` / `die()` / `iter_test_modules()` helpers from here so
the top of each tool looks identical; anything specific to a single
tool lives next to its caller.

The shebang-named tools under `tools/` (`run-unit-tests`, ...) import
this module as `_common`. Python's default `sys.path[0]` when running a
script is the directory containing that script, so the relative import
works without any PYTHONPATH gymnastics.
"""

import sys
from pathlib import Path

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026060201'


# Resolve the repository root from this file's location. Any tool that
# sits next to `_common.py` inside `tools/` inherits the same value.
REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / 'tests'
TOOLS_DIR = REPO_ROOT / 'tools'

# The library modules use relative imports (`from . import disk`) and are
# importable only as the `lib` package (pyproject maps `package-dir =
# {"lib" = "."}`, and the repo directory is named `lib`). Tests therefore put
# the repo's PARENT on sys.path and `import lib.<module>` to exercise the local
# source. This constant documents that location for any tool that needs it.
LIB_IMPORT_PATH = REPO_ROOT.parent


def err(msg):
    """Print a message to stderr.

    Used for warnings and errors so the stdout of a tool stays clean for
    piping into other tools or for CI log capture. Callers that want to
    abort after printing should use `die()` instead.
    """
    print(msg, file=sys.stderr, flush=True)


def die(msg, code=1):
    """Print a message to stderr and exit with the given code.

    Convenience wrapper around `err()` + `sys.exit()` so the call-site reads
    as one statement. The default exit code `1` matches the Unix convention
    for a generic failure.
    """
    err(msg)
    sys.exit(code)


def iter_test_modules(skip=frozenset()):
    """Yield every `tests/<module>` directory that holds a `unit-test/run` file.

    Each library module under test gets a `tests/<module>/` directory with a
    `unit-test/run` script and a `lib` symlink to the repo root, mirroring the
    monitoring-plugins `check-plugins/<name>/unit-test/run` layout exactly so
    the test files and the `tools/run-*` discovery stay identical across both
    projects. Directories without a `unit-test/run` file are skipped so
    work-in-progress folders do not break discovery.

    Yields `pathlib.Path` objects (the `tests/<module>` directory) so callers
    can chain the usual `.name`, `.is_dir()`, `/ "sub"` operations.
    """
    if not TESTS_DIR.is_dir():
        return
    for entry in sorted(TESTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in skip:
            continue
        if not (entry / 'unit-test' / 'run').is_file():
            continue
        yield entry
