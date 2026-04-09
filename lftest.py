#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""Provides test functions for unit tests.
"""

import os

from . import base
from . import disk
from . import shell


__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026040901'


def run(test_instance, plugin, testcase):
    """Run a single testcase against a plugin and assert the results.

    Designed to be used with unittest.TestCase.subTest() for declarative,
    data-driven test definitions. Each testcase is a dict describing what
    to run and what to expect.

    ### Parameters
    - **test_instance** (`unittest.TestCase`): The test instance (self)
      for assertions.
    - **plugin** (`str`): Path to the plugin executable.
    - **testcase** (`dict`): Test definition with keys:
      - `test` (`str`): --test parameter value,
        e.g. `'stdout/ok-healthy,,0'`.
      - `params` (`str`, optional): Additional plugin parameters.
        Default: `''`.
      - `assert-retc` (`int`): Expected return code (STATE_OK, etc.).
      - `assert-in` (`list` of `str`, optional): Strings that must
        appear in stdout.
      - `assert-not-in` (`list` of `str`, optional): Strings that must
        not appear in stdout.
      - `assert-regex` (`str`, optional): Regex pattern that must match
        stdout.
      - `assert-stderr` (`str`, optional): Expected stderr content.
        Default: `''`.

    ### Example
    >>> TESTS = [
    ...     {
    ...         'id': 'ok-all-healthy',
    ...         'test': 'stdout/ok-all-healthy,,0',
    ...         'assert-retc': STATE_OK,
    ...         'assert-in': ['Everything is ok.'],
    ...     },
    ...     {
    ...         'id': 'crit-threshold-exceeded',
    ...         'test': 'stdout/crit-threshold-exceeded,,0',
    ...         'params': '--critical 50',
    ...         'assert-retc': STATE_CRIT,
    ...         'assert-regex': r'90.0%.*\\[CRITICAL\\]',
    ...     },
    ... ]
    ...
    ... class TestCheck(unittest.TestCase):
    ...     check = '../my-plugin'
    ...
    ...     def test(self):
    ...         for t in TESTS:
    ...             with self.subTest(id=t['id']):
    ...                 lib.lftest.run(self, self.check, t)
    """
    params = testcase.get('params', '')
    cmd = f'{plugin} {params} --test={testcase["test"]}'.strip()
    stdout, stderr, retc = base.coe(shell.shell_exec(cmd))

    test_instance.assertEqual(
        retc,
        testcase['assert-retc'],
        f'Expected retc {testcase["assert-retc"]}, got {retc}',
    )

    expected_stderr = testcase.get('assert-stderr', '')
    test_instance.assertEqual(stderr, expected_stderr)

    for text in testcase.get('assert-in', []):
        test_instance.assertIn(text, stdout)

    for text in testcase.get('assert-not-in', []):
        test_instance.assertNotIn(text, stdout)

    if 'assert-regex' in testcase:
        test_instance.assertRegex(stdout, testcase['assert-regex'])


def test(args):
    """
    Returns the content of two files and the provided return code. The first file represents STDOUT,
    and the second represents STDERR. This function is useful for enabling unit tests.

    ### Parameters
    - **args** (`list`): A list containing:
      - The path to the file representing STDOUT or the string to be used as STDOUT.
      - The path to the file representing STDERR or the string to be used as STDERR.
      - The return code (integer or string). Defaults to 0 if not provided.

    ### Returns
    - **tuple**:
      - **stdout** (`str`): The content of the first file or the provided STDOUT string.
      - **stderr** (`str`): The content of the second file or the provided STDERR string.
      - **retc** (`int`): The return code, either from the provided value or defaulted to 0.

    ### Example
    >>> test('path/to/stdout.txt', 'path/to/stderr.txt', 128)
    ('This is stdout content', 'This is stderr content', 128)
    """
    stdout = args[0]
    stderr = args[1]
    retc = int(args[2]) if len(args) > 2 and args[2] != '' else 0

    if stdout and os.path.isfile(stdout):
        success, stdout = disk.read_file(stdout)
    if stderr and os.path.isfile(stderr):
        success, stderr = disk.read_file(stderr)

    return stdout, stderr, retc
