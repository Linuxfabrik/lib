#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""Provides test functions for unit tests."""

import contextlib
import os
import re
import shlex
import tempfile

from . import base, disk, shell

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026061201'


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
    ...
    ... class TestCheck(unittest.TestCase):
    ...     check = '../my-plugin'
    ...
    ...     def test(self):
    ...         for t in TESTS:
    ...             with self.subTest(id=t['id']):
    ...                 lib.lftest.run(self, self.check, t)
    """
    # params come from the trusted testcase definition; tokenize them the way a
    # shell would so quoted multi-word values stay intact, then build the argv.
    params = testcase.get('params', '')
    cmd = [plugin, *shlex.split(params), f'--test={testcase["test"]}']
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


def attach_tests(test_class, tests, plugin_attr='check'):
    """Dynamically attach one ``test_<id>`` method per testcase to a
    ``unittest.TestCase`` subclass, so that every entry in the TESTS
    list shows up as an individual test in the unittest discovery
    output instead of being collapsed into a single ``test`` method
    with sub-tests.

    ### Why
    The naive approach is::

        class TestCheck(unittest.TestCase):
            def test(self):
                for t in TESTS:
                    with self.subTest(id=t['id']):
                        lib.lftest.run(self, self.check, t)

    That works, but unittest counts the whole loop as **one** test, so
    the user sees ``Ran 1 test`` regardless of how many fixtures the
    file actually exercises. Failures still surface (sub-tests print
    their `id`), but the test count is misleading and `./run -v` does
    not list each scenario. ``attach_tests()`` materialises one real
    test method per testcase so the count is accurate and verbose
    output names every scenario.

    ### Parameters
    - **test_class** (`type`): a ``unittest.TestCase`` subclass with a
      ``check`` (or other ``plugin_attr``-named) attribute pointing at
      the plugin executable.
    - **tests** (`list[dict]`): a TESTS list of testcase dicts, each
      shaped as ``run()`` expects, with a unique ``id`` field.
    - **plugin_attr** (`str`, optional): the attribute name on
      ``test_class`` that holds the plugin path. Defaults to
      ``'check'``.

    ### Example
    >>> class TestCheck(unittest.TestCase):
    ...     check = '../my-plugin'
    >>> attach_tests(TestCheck, TESTS)
    >>>
    >>> if __name__ == '__main__':
    ...     unittest.main()

    The resulting class has a ``test_<sanitised id>`` method per
    entry in ``TESTS``. Running ``./run -v`` then lists every test
    by name and ``./run`` reports the real test count.
    """
    seen = set()
    for testcase in tests:
        raw_id = testcase['id']
        method_name = 'test_' + re.sub(r'\W+', '_', raw_id).strip('_')
        if method_name in seen:
            raise ValueError(
                f'attach_tests: duplicate test id "{raw_id}" '
                f'maps to method name "{method_name}"'
            )
        seen.add(method_name)

        def _make(captured_testcase):
            def _method(self):
                run(self, getattr(self, plugin_attr), captured_testcase)

            return _method

        setattr(test_class, method_name, _make(testcase))


def attach_each(test_class, items, action, id_func=str):
    """Attach one ``test_<id>`` method per item to a ``unittest.TestCase``
    subclass.

    Sister of :func:`attach_tests`. Where ``attach_tests`` works on a
    TESTS list of dicts that ``run()`` knows how to execute,
    ``attach_each`` accepts an arbitrary iterable plus a callable that
    decides what to do with each item. Useful for container-image
    matrices, file-based fixtures with stateful per-item setup, and
    any other pattern that doesn't fit the TESTS-dict shape.

    Like ``attach_tests``, this materialises one real test method per
    item so unittest counts and names them individually instead of
    collapsing the whole loop into a single ``test`` method.

    ### Parameters
    - **test_class** (`type`): a ``unittest.TestCase`` subclass.
    - **items** (`iterable`): the things to iterate over (image
      tuples, fixture paths, scenario dicts, ...).
    - **action** (`callable`): a function ``action(self, item)``
      that the generated test method calls with the captured item.
      ``self`` is the ``unittest.TestCase`` instance and may be
      used to issue assertions.
    - **id_func** (`callable`, optional): a function that turns one
      item into a short, human-readable string used as the test
      method name. Defaults to ``str``, which is fine for plain
      strings; pass ``lambda it: it[1]`` (or similar) for tuples
      and dicts.

    ### Example
    >>> IMAGES = [
    ...     ('quay.io/keycloak/keycloak:25.0.6', 'v25'),
    ...     ('quay.io/keycloak/keycloak:26.6', 'v26'),
    ... ]
    >>>
    >>> def _check(test, image_pair):
    ...     image, version_tag = image_pair
    ...     with lib.lftest.run_container(image, ...) as container:
    ...         # ... run plugin, assert ...
    ...         pass
    >>>
    >>> class TestCheck(unittest.TestCase):
    ...     pass
    >>>
    >>> attach_each(TestCheck, IMAGES, _check, id_func=lambda it: it[1])
    """
    seen = set()
    for item in items:
        raw_id = id_func(item)
        method_name = 'test_' + re.sub(r'\W+', '_', str(raw_id)).strip('_')
        if method_name in seen:
            raise ValueError(
                f'attach_each: duplicate id "{raw_id}" '
                f'maps to method name "{method_name}"'
            )
        seen.add(method_name)

        def _make(captured_item):
            def _method(self):
                action(self, captured_item)

            return _method

        setattr(test_class, method_name, _make(item))


@contextlib.contextmanager
def network():
    """Yield a testcontainers `Network`, removed on exit.

    Used to wire a multi-container test together: start a backend (e.g. a
    database) and the application container on the same network, passing the
    network to :func:`run_container` via its `network` / `network_alias`
    arguments so the application can reach the backend by alias.

    ### Yields
    - **Network**: a created docker/podman network.

    ### Example
    >>> with lib.lftest.network() as net:
    ...     with lib.lftest.run_container(
    ...         'docker.io/library/mariadb:11',
    ...         env={'MARIADB_ROOT_PASSWORD': 'linuxfabrik'},
    ...         network=net,
    ...         network_alias='db',
    ...         wait_log='ready for connections',
    ...     ):
    ...         pass
    """
    try:
        from testcontainers.core.network import Network
    except ImportError as e:
        raise RuntimeError(
            'testcontainers is not installed; run `pip install testcontainers`'
        ) from e

    net = Network()
    net.create()
    try:
        yield net
    finally:
        net.remove()


@contextlib.contextmanager
def run_container(
    image,
    *,
    env=None,
    ports=None,
    command=None,
    wait_log=None,
    wait_log_timeout=120,
    network=None,
    network_alias=None,
):
    """Start a testcontainers-python managed container and yield it.

    A thin wrapper around `testcontainers.core.container.DockerContainer`
    that handles the boilerplate most Linuxfabrik container-based unit
    tests need: set env vars, expose a port, wait for a log marker,
    tear down on exit.

    Compatible with both Docker and rootless Podman. For Podman, the
    caller must export `DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock`
    and disable the Ryuk cleanup container via
    `TESTCONTAINERS_RYUK_DISABLED=true` (Ryuk hangs on Podman).
    The helper itself is daemon-agnostic.

    ### Parameters
    - **image** (`str`): The image reference to pull and run, e.g.
      `'quay.io/keycloak/keycloak:25.0.4'`.
    - **env** (`dict`, optional): Environment variables to pass into
      the container (e.g. `{'KEYCLOAK_ADMIN': 'admin'}`).
    - **ports** (`list` of `int`, optional): Container ports to
      expose to the host. Use `container.get_exposed_port(port)` to
      get the ephemeral host port after start.
    - **command** (`str`, optional): Command to run instead of the
      image's default ENTRYPOINT/CMD (e.g. `'start-dev'`).
    - **wait_log** (`str`, optional): Substring to wait for in the
      container's logs before yielding control. Most services write
      a "ready" marker line like "Listening on:" or "ready for
      connections". If `None`, the helper yields as soon as the
      container is running.
    - **wait_log_timeout** (`int`, optional): Maximum time to wait
      for the log marker, in seconds. Defaults to `120`.
    - **network** (`Network`, optional): A network from :func:`network`
      to attach the container to, so it can reach sibling containers by
      alias (multi-container tests).
    - **network_alias** (`str`, optional): Hostname this container is
      reachable under on `network` (e.g. `'db'`).

    ### Yields
    - **DockerContainer**: The running container, with
      `get_container_host_ip()` / `get_exposed_port(port)` usable for
      building a host-side URL.

    ### Example
    >>> with lib.lftest.run_container(
    ...     'quay.io/keycloak/keycloak:25.0.4',
    ...     env={'KEYCLOAK_ADMIN': 'admin', 'KEYCLOAK_ADMIN_PASSWORD': 'admin'},
    ...     ports=[8080],
    ...     command='start-dev',
    ...     wait_log='Listening on:',
    ... ) as container:
    ...     url = 'http://{}:{}'.format(
    ...         container.get_container_host_ip(),
    ...         container.get_exposed_port(8080),
    ...     )
    ...     # point the plugin at this url
    """
    try:
        from datetime import timedelta

        from testcontainers.core.container import DockerContainer
        from testcontainers.core.wait_strategies import LogMessageWaitStrategy
    except ImportError as e:
        raise RuntimeError(
            'testcontainers is not installed; run `pip install testcontainers`'
        ) from e

    c = DockerContainer(image)
    if env:
        for key, value in env.items():
            c.with_env(key, value)
    if ports:
        for port in ports:
            c.with_exposed_ports(port)
    if command:
        c.with_command(command)
    if network is not None:
        c.with_network(network)
        if network_alias:
            c.with_network_aliases(network_alias)
    if wait_log:
        c.waiting_for(
            LogMessageWaitStrategy(wait_log).with_startup_timeout(
                timedelta(seconds=wait_log_timeout)
            )
        )
    c.start()
    try:
        yield c
    finally:
        c.stop()


def _is_mariadb_image(image_ref):
    """Return True if the image reference looks like a MariaDB image
    (`mariadb`-named upstream or sclorg variant), False if it looks
    like an upstream MySQL image. Used to pick the right server
    binary (`mariadbd` vs `mysqld`) when the caller passes
    `extra_args`.
    """
    return 'mariadb' in image_ref.lower()


def _mysql_compatible_startup_command(image_ref, extra_args):
    """Pick the right startup command for a MySQL- or MariaDB-compatible
    image.

    - **Red Hat family via sclorg** (`quay.io/sclorg/mariadb-*` /
      `quay.io/sclorg/mysql-*`): sclorg's entrypoint binds only the
      unix socket by default, so the helper forces
      `run-mysqld --port=3306`. The same `run-mysqld` wrapper exists
      on both sclorg flavours.
    - **Upstream** (`docker.io/library/mariadb:*` /
      `docker.io/library/mysql:*`): the default `docker-entrypoint.sh`
      already enables TCP on 3306; the helper only overrides the
      command when `extra_args` are given, in which case it appends
      them to `mariadbd` (MariaDB) or `mysqld` (MySQL).
    """
    if 'sclorg/' in image_ref:
        cmd = 'run-mysqld --port=3306'
        if extra_args:
            cmd = f'{cmd} {extra_args}'
        return cmd
    if not extra_args:
        return None
    server_bin = 'mariadbd' if _is_mariadb_image(image_ref) else 'mysqld'
    return f'{server_bin} {extra_args}'


def _dockerfile_from_image(containerfile_path):
    """Return the image reference from the first `FROM` line of a
    Containerfile/Dockerfile, e.g. `quay.io/sclorg/mariadb-1108-c10s`
    or `docker.io/library/mysql:8.4`. Strips any `AS <alias>` suffix.
    """
    with open(containerfile_path, encoding='utf-8') as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if stripped.upper().startswith('FROM '):
                # `FROM image[:tag][@digest] [AS alias]`
                ref = stripped.split(None, 1)[1].split(None, 1)[0]
                return ref
    raise RuntimeError(f'No FROM line found in {containerfile_path}')


@contextlib.contextmanager
def _run_mysql_compatible_resolved(image_ref, command, seed):
    """Run an already-resolved MySQL- or MariaDB-compatible image and
    yield `(container, defaults_file)` with the usual MYSQL_* env vars,
    TCP port 3306, a `port: 3306` log-wait and an optional seed SQL
    statement.

    The `defaults_file` is a temporary `[client]` `.cnf` deleted on
    context exit so callers can invoke plugins with `--defaults-file=...`
    without manual tempfile bookkeeping.

    The `MYSQL_*` env var names work for both flavours: MariaDB
    upstream accepts them as aliases for `MARIADB_*`, and MySQL
    upstream uses them natively. The log marker `port: 3306` appears
    in both startup banners once the TCP listener is bound.
    """
    with run_container(
        image_ref,
        env={
            'MYSQL_ROOT_PASSWORD': 'test',
            'MYSQL_USER': 'test',
            'MYSQL_PASSWORD': 'test',
            'MYSQL_DATABASE': 'test',
        },
        ports=[3306],
        command=command,
        wait_log='port: 3306',
        wait_log_timeout=180,
    ) as container:
        if seed:
            # MariaDB 11.x upstream dropped the `mysql` client symlink
            # in favour of `mariadb`; sclorg c10s ships both; MySQL
            # ships `mysql` only. Prefer `mariadb`, fall back to
            # `mysql` so all flavours work.
            container.exec(
                [
                    'sh',
                    '-c',
                    'if command -v mariadb >/dev/null 2>&1; then CLIENT=mariadb; '
                    'else CLIENT=mysql; fi; '
                    f'"$CLIENT" -utest -ptest test -e "{seed}"',
                ]
            )

        host = container.get_container_host_ip()
        port = container.get_exposed_port(3306)

        fd, defaults_file = tempfile.mkstemp(suffix='.cnf')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(
                    f'[client]\n'
                    f'host={host}\n'
                    f'port={port}\n'
                    f'user=test\n'
                    f'password=test\n'
                    f'database=test\n'
                )
            yield container, defaults_file
        finally:
            try:
                os.unlink(defaults_file)
            except OSError:
                pass


@contextlib.contextmanager
def run_mysql_compatible(image, *, extra_args=None, seed=None):
    """Start a MySQL- or MariaDB-compatible container and yield
    `(container, defaults_file)`.

    Thin convenience wrapper around :func:`run_container` for the
    Linuxfabrik mysql-* check plugins. Hides the image-family
    boilerplate (env vars, TCP port exposure, start command, log
    marker to wait on) and writes a temporary `[client]` `.cnf` file
    pointing at the exposed host port so the caller can run a plugin
    with `--defaults-file=...` without manual tempfile management.

    For the canonical convention (per-plugin Containerfile under
    `unit-test/containerfiles/`), prefer
    :func:`run_mysql_compatible_from_containerfile`. This entry point
    is kept for the legacy path that hard-codes an image reference.

    Supports four image families:

    - **Red Hat family via sclorg** MariaDB (`quay.io/sclorg/mariadb-*`)
    - **Red Hat family via sclorg** MySQL (`quay.io/sclorg/mysql-*`)
    - **Upstream MariaDB** (`docker.io/library/mariadb:*`)
    - **Upstream MySQL** (`docker.io/library/mysql:*`)

    See :func:`_mysql_compatible_startup_command` for the
    family-specific differences.

    ### Parameters
    - **image** (`str`): image reference.
    - **extra_args** (`str`, optional): Extra server flags appended to
      the startup command (`mariadbd` on MariaDB, `mysqld` on MySQL,
      and to the sclorg `run-mysqld` wrapper otherwise).
    - **seed** (`str`, optional): SQL statement executed once via
      `container.exec` right after the container is ready. Used to
      seed happy-path state (e.g. creating an empty InnoDB table so
      storage-engine checks see the engine "in use").

    ### Yields
    - **tuple** (`DockerContainer`, `str`):
      - The running container.
      - Absolute path to a temporary `[client]` `.cnf` file deleted
        when the context manager exits.
    """
    command = _mysql_compatible_startup_command(image, extra_args)
    with _run_mysql_compatible_resolved(image, command, seed) as result:
        yield result


@contextlib.contextmanager
def run_mysql_compatible_from_containerfile(
    containerfile_path,
    *,
    extra_args=None,
    seed=None,
):
    """Build a MySQL- or MariaDB-compatible image from a per-plugin
    Containerfile, start it and yield `(container, defaults_file)`
    exactly like :func:`run_mysql_compatible`.

    The canonical layout for a Linuxfabrik mysql-* plugin places one
    Containerfile per LTS release under
    `<plugin>/unit-test/containerfiles/` (e.g. `mariadb-v118`,
    `mariadb-v1011`, `mysql-v80`, `mysql-v84`). Each file is typically
    a one-liner (`FROM <upstream-or-sclorg-image>`) but can be extended
    with plugin-specific layers if a test needs custom server config
    or pre-seeded state.

    The DBMS family (MariaDB vs MySQL; sclorg vs upstream) is detected
    from the Containerfile's `FROM` line so the right startup command
    is used. The built image is tagged `lfmp-mysql-<filename>` and
    kept around (`clean_up=False`) so subsequent runs reuse the cached
    layers.

    ### Parameters
    - **containerfile_path** (`str`): Path to the Containerfile, e.g.
      `os.path.join(HERE, 'containerfiles', 'mariadb-v118')`.
    - **extra_args** (`str`, optional): same as :func:`run_mysql_compatible`.
    - **seed** (`str`, optional): same as :func:`run_mysql_compatible`.

    ### Yields
    - **tuple** (`DockerContainer`, `str`): same as
      :func:`run_mysql_compatible`.

    ### Example
    >>> with lib.lftest.run_mysql_compatible_from_containerfile(
    ...     os.path.join(HERE, 'containerfiles', 'mysql-v84'),
    ... ) as (container, defaults_file):
    ...     result = subprocess.run(
    ...         ['python3', '../mysql-traffic', f'--defaults-file={defaults_file}'],
    ...         capture_output=True,
    ...         text=True,
    ...     )
    """
    try:
        from testcontainers.core.image import DockerImage
    except ImportError as e:
        raise RuntimeError(
            'testcontainers is not installed; run `pip install testcontainers`'
        ) from e

    abspath = os.path.abspath(containerfile_path)
    from_image = _dockerfile_from_image(abspath)
    command = _mysql_compatible_startup_command(from_image, extra_args)

    build_dir = os.path.dirname(abspath)
    dockerfile_name = os.path.basename(abspath)
    tag = f'lfmp-mysql-{dockerfile_name}'.lower().replace('_', '-')

    # No parenthesized context managers: they are Python 3.10+ syntax and break
    # parsing on RHEL 8's default Python 3.6.
    with (
        DockerImage(
            path=build_dir,
            dockerfile_path=dockerfile_name,
            tag=tag,
            clean_up=False,
        ) as image,
        _run_mysql_compatible_resolved(
            str(image.tag),
            command,
            seed,
        ) as result,
    ):
        yield result


# Back-compat aliases for one release. Out-of-tree callers can
# migrate to the new names at their own pace; in-tree callers are
# being migrated in the same release that introduces the rename.
run_mariadb = run_mysql_compatible
run_mariadb_from_containerfile = run_mysql_compatible_from_containerfile


def test(args):
    """
    Returns the content of two files and the provided return code. The first file represents STDOUT,
    and the second represents STDERR. This function is useful for enabling unit tests.

    Only the STDOUT entry is required. STDERR and the return code default to
    the empty string and 0, so callers can pass `--test=path/to/stdout`
    without trailing commas.

    ### Parameters
    - **args** (`list`): A list containing:
      - The path to the file representing STDOUT or the string to be used as STDOUT.
      - Optional: the path to the file representing STDERR or the string to be used
        as STDERR. Defaults to the empty string if not provided.
      - Optional: the return code (integer or string). Defaults to 0 if not provided.

    ### Returns
    - **tuple**:
      - **stdout** (`str`): The content of the first file or the provided STDOUT string.
      - **stderr** (`str`): The content of the second file or the provided STDERR string.
      - **retc** (`int`): The return code, either from the provided value or defaulted to 0.

    ### Example
    >>> test(['path/to/stdout.txt', 'path/to/stderr.txt', 128])
    ('This is stdout content', 'This is stderr content', 128)
    >>> test(['path/to/stdout.txt'])
    ('This is stdout content', '', 0)
    """
    stdout = args[0] if len(args) > 0 else ''
    stderr = args[1] if len(args) > 1 else ''
    retc = int(args[2]) if len(args) > 2 and args[2] != '' else 0

    if stdout and os.path.isfile(stdout):
        _, stdout = disk.read_file(stdout)
    if stderr and os.path.isfile(stderr):
        _, stderr = disk.read_file(stderr)

    return stdout, stderr, retc
