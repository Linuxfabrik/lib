# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

* db_mysql.py: `get_flavor()` returns whether the installed MySQL/MariaDB binary is MariaDB or MySQL. Works without a database connection - probes `mysqld --version`, `mariadbd --version`, `mariadb --version`, `mysql --version` in order and checks for the `-MariaDB` suffix. Useful where systemd-based detection is unreliable (e.g. Fedora aliases `mysql.service` to `mariadb.service`)


## [v4.0.2] - 2026-05-18

### Fixed

* url.py: `import lib.url` no longer aborts with `AttributeError: module 'ssl' has no attribute 'TLSVersion'` on Python interpreters below 3.7 (e.g. RHEL 8's default `python3` = 3.6). The TLS version mapping is now built only when `ssl.TLSVersion` is available; any plugin that doesn't use TLS version pinning keeps importing. Callers that pass `tls_min` / `tls_max` get a clear `RuntimeError` naming the missing requirement instead of the cryptic `AttributeError`. Note: the lib's supported minimum is still Python 3.9; this only makes one specific import path resilient


## [v4.0.1] - 2026-05-18

### Fixed

* db_mysql.py: `connect()` aligns the session's character set and collation with the `mysql` system schema right after the connection is up. Stops queries against `mysql.user` and `mysql.global_priv` from aborting with ER 1267 ("Illegal mix of collations") when the server's connection-collation default differs from the system tables' column collations. MariaDB 10.4+ exposes `mysql.user` as a view over `mysql.global_priv` with JSON-derived columns whose results carry COERCIBLE coercibility, which makes plain `col = 'literal'` compares trip whenever `collation_connection` and the column collation don't match. Lookup uses `information_schema.schemata` so the right collation is picked across MySQL/MariaDB versions and locale-specific installs. Best-effort: on any error the connection stays usable. Fixes all `mysql-*` plugins ([linuxfabrik/monitoring-plugins#1139](https://github.com/Linuxfabrik/monitoring-plugins/issues/1139))


## [v4.0.0] - 2026-05-15

### Breaking Changes

* base.py: rename module-level constant `X86_64` to `IS_64BIT`. The old name was misleading because it suggested Intel/AMD 64-bit only, while the underlying check (`sys.maxsize > 2**32`) is True on any 64-bit Python build (aarch64, ppc64le, s390x, riscv64, …). Logic unchanged. Downstream consumers must update imports

### Added

* db_mysql.py: `check_privileges(conn, *required)` replaces the old `check_select_privileges()`. Without arguments it keeps the previous functional smoke test (`SELECT VERSION()`, works with `GRANT USAGE` alone). With arguments it parses `SHOW GRANTS FOR CURRENT_USER()` and reports any privilege that is missing for the current user, with `ALL PRIVILEGES` and `SUPER` short-circuiting to success. Each positional argument can be a string (single privilege required) or a list/tuple of strings (any-of group, useful for cross-version aliases like `REPLICATION CLIENT` / `SLAVE MONITOR` / `REPLICA MONITOR` introduced by MariaDB 10.5+). Enables plugins to declare their actual privilege requirements precisely
* db_mysql.py: four new helpers consolidate patterns that several check plugins implement by hand. `get_all_status(conn)` and `get_all_variables(conn)` return the complete `SHOW GLOBAL STATUS` / `SHOW GLOBAL VARIABLES` as a dict in one round trip (cheaper than many `LIKE '...'` queries when a plugin needs more than a handful of values). `get_replica_status(conn)` issues `SHOW REPLICA STATUS` and silently falls back to the legacy `SHOW SLAVE STATUS`, returning the first row or `None` when the server is not configured as a replica. `has_is_role_column(conn)` reports whether `mysql.user.IS_ROLE` exists (MariaDB 10.0.5+ roles) so plugins can gate `IS_ROLE = 'N'` clauses without each implementing the same probe
* db_sqlite.py: `per_second_deltas(filename, name, counters)` consolidates the cross-run "delta of cumulative counters between runs" pattern that several check plugins implement by hand. Persists the counters in a local SQLite cache (schema derived from the counters dict so callers no longer have to spell out the table definition per plugin) and returns the per-second rates vs. the previous run. Useful for any cumulative counter that needs to be reported as a per-second rate: /proc and /sys byte counters (disk I/O, network traffic, file descriptors), database status counters, application metrics. Returns `None` on the first run, on counter resets and on schema changes (auto-rebuilds the cache table in that case). Lets plugins emit per-second rates as perfdata instead of `uom='c'` continuous counters, so Grafana panels do not need their own `non_negative_difference()` workaround
* lftest.py: `run_mariadb_from_containerfile(containerfile_path, ...)` builds a per-plugin Containerfile via testcontainers' DockerImage and yields `(container, defaults_file)` like `run_mariadb()`. Plugins move their test-image matrix into `unit-test/containerfiles/<name>` so each plugin owns its supported MariaDB / MySQL LTS coverage instead of relying on a hardcoded image list in the lib. The `MARIADB_LTS_IMAGES` constant has been removed (no in-tree caller after the migration)
* lftest.py: `run_mariadb` / `run_mariadb_from_containerfile` renamed to `run_mysql_compatible` / `run_mysql_compatible_from_containerfile` to reflect that both upstream MySQL and MariaDB images are supported (`docker.io/library/mysql:*`, `docker.io/library/mariadb:*`, `quay.io/sclorg/mariadb-*`, `quay.io/sclorg/mysql-*`). Family detection picks `mariadbd` vs `mysqld` when `extra_args` is set. Old names are kept as aliases for one release
* net.py: `fetch()` and `fetch_socket()` gain an optional `dialog` parameter for multi-step request/response conversations (regex-driven, no half-close). Enables clean implementations of plugins for protocols like NUT, SMTP, POP3, IMAP and FTP without re-implementing socket handling per plugin
* net.py: `fetch()` gains a `tls=True` switch that wraps the socket in a TLS 1.2+ context with SNI, equivalent to calling `fetch_ssl()`. The legacy `fetch_ssl()` helper stays for backward compatibility but is now marked deprecated in its docstring
* time.py: `now()` gains `as_type='utc'` returning the current UTC time as a naive `datetime.datetime`. Useful for fields defined as UTC by spec (x509 `notBefore` / `notAfter`, HTTP `Date`, RFC 3339 timestamps), so consumers can stay on the lib helper instead of falling back to `datetime.datetime.now(datetime.timezone.utc)`
* url.py: `fetch()` and `fetch_json()` now speak HTTP/1.0, HTTP/1.1 and HTTP/2 via `httpx`, with new `http_version`, `tls_min` and `tls_max` parameters for protocol pinning. `extended=True` now also returns the negotiated TLS version, ALPN protocol, the server certificate in DER form, and a per-phase `timings` dict with `dns`, `connect`, `tls`, `ttfb`, `transfer` and `total` (all seconds), ready for downstream certificate inspection and HTTPS-availability monitoring. `http_version='3'` is reserved and currently returns a clear error until QUIC support lands. Existing callers and parameters are unchanged

### Changed

* pyproject.toml: declare `pypsrp` and `pywinrm` as direct dependencies. `lib.winrm` imports both at module load time (wrapped in `try/except ImportError` only so a non-WinRM consumer still loads); previously they had to be pinned in every downstream project that consumed `lib.winrm` (e.g. monitoring-plugins for `dhcp-scope-usage` on Windows). Same convention as `psutil`, `smbprotocol` etc., which `lib.psutil` / `lib.smb` import conditionally but which are declared as hard deps because they are part of lib's published surface
* requirements: one hash-pinned lockfile per supported Python LTS, each in its own `lockfiles/pyXX/` subdirectory (`py39` to `py314`). Replaces the single `requirements.txt`. Dependabot watches each subdirectory separately, except `lockfiles/py39/` which is excluded from both version bumps and security PRs: most upstream packages dropped Python 3.9 over 2025/2026, so automated bumps would break `pip install --require-hashes` on RHEL 8 / Debian 11. The py39 lockfile is regenerated manually as needed
* url.py: `fetch()` switched its underlying engine from stdlib `urllib` to `httpx`. Behaviour for existing callers is preserved (parameters, return-tuple shape, redirect-following, default `Connection: close` and `User-Agent` headers, automatic `application/x-www-form-urlencoded` for POST without explicit Content-Type). `response_header` in the extended dict is now a plain dict instead of `http.client.HTTPMessage`; existing consumers only relied on `.get()` access

### Deprecated

* db_mysql.py: `check_select_privileges()` is deprecated and now a thin backwards-compatible shim that delegates to `check_privileges(conn)`. New code should call `check_privileges()` directly. The shim exists to keep already-deployed plugins working when the lib is upgraded ahead of the plugin set; it will be removed in a future major release

### Fixed

* base.py: `oao()` now properly HTML-escapes `&`, `<` and `>` into `&amp;`, `&lt;` and `&gt;` instead of replacing `<` and `>` with apostrophes. The previous implementation destroyed legitimate threshold descriptions like `<= 10` and shell snippets like `echo 1 > /proc/sys/...`, turning them into `'= 10` and `echo 1 ' /proc/sys/...` in plugin output. HTML-based web UIs (Icinga Web, Naemon-Adagios) render the entities back to the original characters; terminal viewers see the literal entities, which preserves the information. The XSS-protection goal of the original change is still met
* db_sqlite.py: `per_second_deltas()` no longer crashes with `sqlite3.ProgrammingError: Cannot operate on a closed database` when the cache table schema mismatches an earlier plugin version. The internal `insert()` call now uses `delete_db_on_operational_error=False` so the connection survives the schema-mismatch error; the explicit drop/recreate path below operates on a live connection as intended
* url.py: `fetch()` with HTTP digest authentication and `insecure=True` now actually disables certificate verification. Previously the digest auth path silently lost the SSL context
* url.py: `fetch()` with `no_proxy=True` now applies the `timeout` parameter. Previously the no-proxy path called `opener.open(request)` without a timeout, so hangs were only caught by the outer plugin wrapper
* url.py: `import lib.url` no longer fails on hosts where `httpx` is not installed; the import is now lazy and `fetch()` returns a clear "httpx not installed" error message instead of crashing on import. Plugins that pull `lib.url` only transitively (for example via `lib.net`) keep working without `httpx`. Hosts that actually use `fetch()` still need `httpx[http2]` installed via `pip` or `dnf install python3-httpx python3-h2`


## [v3.4.1] - 2026-05-07

### Fixed

* librenms.py: `get_state()` now also maps the LibreNMS alert states `WORSE` (3), `BETTER` (4) and `CHANGED` (5) to WARN/CRIT. Previously only `ACTIVE` (1) was treated as an alerting state, so open alerts in any of those three states were silently reported as OK. `WORSE` and `BETTER` exist in LibreNMS since 1.54 (July 2019); `CHANGED` was added in LibreNMS 25.2.0 (February 2025) and is now triggered whenever the alert `diff` detects a change

### Security

* **ci**: Scope `GITHUB_TOKEN` permissions in the dependabot-auto-merge workflow to the job level, with top-level now `read-all`. Matches the pattern used by the other Linuxfabrik workflows and addresses the OpenSSF Scorecard `Token-Permissions` finding.


## [v3.4.0] - 2026-04-22

### Added

* time.py: add `macro2timestr(s, format='')` to expand time macros in a string. Supports `{today}`, `{yesterday}` (rendered with the given format, default ISO 8601) and single strftime components (`{%Y}`, `{%y}`, `{%m}`, `{%d}`, `{%H}`, `{%M}`, `{%S}`). Unknown `{...}` tokens pass through unchanged


## [v3.3.0] - 2026-04-19

### Added

* args.py: add a generic `--check-security` help text so version-style plugins can offer an upstream security-update check with a uniform parameter description


## [v3.2.0] - 2026-04-14

### Added

* url.py: add `split_basic_auth(url)` helper that extracts userinfo from a URL like `https://user:secret@host/path`, returns the URL with the userinfo stripped from the netloc, plus a headers dict carrying the matching `Authorization: Basic ...` entry. Pass both into `lib.url.fetch()` / `lib.url.fetch_json()`. This lets apps accept HTTP basic auth via the URL itself instead of exposing separate `--username` / `--password` arguments, which keeps the credentials out of `ps` listings, out of the request line, and out of any proxy access log


## [v3.1.1] - 2026-04-14

### Changed

* human.py: `human2seconds()` and `humanduration2seconds()` now accept the Unix-style lowercase day/week markers `d` and `w` in addition to the canonical Linuxfabrik uppercase `D` and `W`. This lets callers parse duration strings from third-party tools that follow the Unix convention (exim `mailq` age literals, `sleep 3d`, systemd timers, etc.) without having to normalize the input first. Uppercase `D`/`W` continue to work exactly as before, so no existing caller breaks
* nextcloud.py: `run_occ()` no longer relies on the Nextcloud `occ` script being marked executable. It now locates `php` via `shutil.which('php')` and invokes `sudo -u \#<uid> php <occ> <cmd>`, which also works on installations where `occ` lacks the execute bit or its shebang does not resolve to a working PHP interpreter. If no `php` is found in `PATH`, the call returns a descriptive error instead of silently failing


### Security

* Harden the CI supply chain: the `pre-commit` install in the pre-commit-autoupdate workflow is now hash-pinned via `.github/pre-commit/requirements.txt` (generated with `pip-compile --generate-hashes --strip-extras`), and `dependabot/fetch-metadata` is pinned to a commit SHA so all GitHub Actions used in `.github/workflows/` are now pinned by hash. The policy is documented in CONTRIBUTING.md under "CI Supply Chain"


## [v3.1.0] - 2026-04-13

### Added

* disk.py: add `dir_exists()` as the directory-only counterpart to `file_exists()`. The existing `file_exists()` wraps `os.path.isfile()` and therefore returns `False` for directories, which is easy to miss; callers that want to check for a directory should now use `dir_exists()`
* lftest.py: add `attach_each()` helper for iterating over arbitrary lists (e.g. container image matrices, file-based fixtures) with a caller-supplied action, complementing `attach_tests()` which only works on the `TESTS` dict shape
* lftest.py: add `attach_tests()` helper that attaches one `test_*` method per entry in a plugin's `TESTS` list, so that test discovery and reporting show the actual number of fixtures instead of a single aggregate test
* lftest.py: add `run_mariadb()` context manager and `MARIADB_LTS_IMAGES` constant for container-based MariaDB integration tests. Starts a sclorg or upstream MariaDB container, waits for the TCP listener, yields a temporary client option file, and cleans up on exit. `MARIADB_LTS_IMAGES` lists the currently supported MariaDB LTS releases (10.6, 10.11, 11.4, 11.8) so the mysql-* monitoring plugins can iterate over a single canonical matrix


## [v3.0.0] - 2026-04-13

### Added

* Add GitHub Actions workflow to automatically build and deploy API documentation to GitHub Pages
* Add bandit and vulture to `.pre-commit-config.yaml` for security and dead-code checks on every commit
* Add pre-commit hooks
* Add ruff linter and formatter to pre-commit hooks ([#117](https://github.com/Linuxfabrik/lib/issues/117))
* args.py: expand `HELP_TEXTS` with standard help texts for all common parameters (always-ok, critical, warning, insecure, no-proxy, timeout, url, ignore-regex, match, lengthy, count, test, etc.)
* disk.py: add `get_owner()`
* lftest.py: add `run()` function for declarative, data-driven unit tests using `subTest()`
* nextcloud.py: new library
* txt.py: add `exception2text()`
* winrm.py: add `WINRM_CONFIGURATION_NAME` option to `run_ps()`
* winrm.py: execute ps in `run_ps()` directly without Invoke-Expression wrapping

### Changed

* base.py: `get_perfdata()` now sanitizes labels by stripping single quotes and replacing `=` with `_`
* base.py: `get_perfdata()` output no longer has trailing semicolons
* base.py: `get_table()`: document why pure ASCII delimiters are used instead of Unicode box-drawing characters
* base.py: `get_worst()` now accepts any number of state arguments (`*states`). Existing two-argument callers keep working unchanged, but plugins that need to combine three or more states in one call no longer have to nest the call - e.g. `get_worst(state, used_state, committed_state)` instead of `get_worst(state, get_worst(used_state, committed_state))`
* base.py: deduplicate `get_state()` operator logic using `operator` module
* base.py: deduplicate `sum_dict()` by delegating to `sum_lod()`
* base.py: improve `get_table()` performance for large tables
* base.py: move `parse_range()` and state name mapping to module level
* base.py: remove unused `collections` import
* db_sqlite.py: reduce unnecessary dictionary object creation
* human.py: deduplicate `bits2human()`/`bps2human()`/`bytes2human()` via shared `_to_human()` helper
* human.py: deduplicate `humanrange2bytes()`/`humanrange2seconds()` via shared `_convert_range()` helper
* human.py: pre-compute mappings as module constants
* lftest.py: `test()` now accepts `args` with fewer than three elements. Plugins can be invoked as `--test=path/to/fixture` without the trailing `,,0`; stderr defaults to the empty string and the return code to `0`
* powershell.py: `run_ps()` now always returns a dict
* Remove pre-built documentation from the repository (now auto-deployed via GitHub Actions)
* txt.py: improve `filter_mltext()` performance (avoid O(n²) string concatenation)
* txt.py: improve readability of `extract_str()` fallback logic
* txt.py: remove unused Python 2 type aliases and outdated comments
* txt.py: simplify `to_text()` and `to_bytes()` for Python 3 only (remove dead Python 2 codepaths)
* winrm.py: make `run_cmd()` and `run_ps()` JEA-aware
* winrm.py: make `run_cmd()` and `run_ps()` Kerberos-aware

### Removed

* Drop support for Python older than 3.9. The lib now requires Python 3.9 or newer; this matches the oldest still-supported enterprise Linux (RHEL 8) and lets the codebase use modern syntax and standard-library features

### Fixed

* base.py: `cu()` now also escapes HTML characters in the error message, not just in the traceback
* base.py: `cu()` now detects active exceptions via `sys.exc_info()` instead of string-matching the traceback
* base.py: `get_state()` no longer calls `sys.exit()` on malformed range specs, returns UNKNOWN instead
* base.py: `get_table()` no longer uses the wrong separator for the second data row when called without a header
* base.py: `oao()` now escapes HTML characters in the output message to prevent injection in web UIs
* base.py: fix invalid `-10` range example in `_parse_range()` docstring (correct syntax is `-10:0`)
* cache.py: treat a cache entry as valid up to and including its `expire` timestamp instead of expiring it one second early (`<` instead of `<=`). A key set with `expire=now+5` is now still served at `now+5` and first becomes unavailable at `now+6`, matching HTTP Cache-Control max-age and Redis EXPIRE semantics. Callers that relied on the old one-second-early expiry see their cached value live one second longer ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* db_sqlite.py: pass `usedforsecurity=False` to `hashlib.sha1()` so bandit no longer flags a non-security SHA1 use as a weak hash (the hash is only used to derive sanitized SQL identifiers)
* db_sqlite.py: rename unused loop variable in `rm_db()` to silence ruff B007
* Fix `--require-hashes` pip installs in CI workflows by using pinned versions instead
* grassfish.py: remove unused `match()` helper that referenced undefined names (`re` and `compiled_custom_id_regex`); the function was never called and would have raised `NameError` at runtime
* human.py: `bits2human()`, `bytes2human()` and `bps2human()` now scale negative values to a unit that matches their magnitude. Before, `bytes2human(-1048576)` returned `-1048576.0B`, now it returns `-1.0MiB`. This matters for counter deltas that can legitimately be negative (counter resets, reclaimed memory, bandwidth drops) ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* human.py: fix incorrect `seconds2human()` docstring example for sub-second values
* net.py: fix `get_netinfo()` which called a non-existent `get_ip_public()` and swallowed the resulting `NameError` by returning `[]`; the function now leaves `public_address` as `None` and callers that need the public IP must use `get_public_ip()` directly
* powershell.py: fix outdated shebang line
* rocket.py: `get_groups_history()` no longer mutates a shared default `params={}` dict (B006) and properly defaults `params` to `None`
* shell.py: `shell_exec()` now applies timeout to the `shell=True` path (was previously ignored)
* shell.py: close the upstream process's `stdout` after connecting it to the next pipeline stage. Without this, the upstream process never received EOF/SIGPIPE when the downstream stage exited early, and each pipeline stage leaked a file descriptor until garbage collection caught up ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* txt.py: `sanitize_sensitive_data()` now also redacts JSON-style fields and HTTP Authorization headers
* txt.py: fix `exception2text()` missing `traceback` import (fallback path was dead code)
* txt.py: fix `pluralize()` not stripping whitespace from comma-separated suffix parts
* txt.py: fix `sanitize_sensitive_data()` replacing the key name instead of the secret value
* url.py: `fetch()` and `fetch_json()` no longer use mutable default arguments for `header` and `data` (B006); defaults are now `None` with initialization inside the function
* url.py: drop the dead `timeout=timeout if digest_auth_user else timeout` ternary in `fetch()`; both branches evaluated to `timeout`, so behavior is unchanged ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* winrm.py: pass parameters correctly in `run_cmd()` when using pypsrp

### Security

* Annotate all remaining bandit low/medium findings with `# nosec BXXX` comments and a short justification (subprocess helpers with `shell=True` by design, admin-controlled URLs passed to `urlopen`, SQL built from sanitized identifiers in `db_sqlite`). Bandit now runs clean at `--severity-level=low --confidence-level=low` over the whole lib


## [v2.4.0] - 2025-09-17

### Added

* rocket.py: add `get_groups_history()`, `get_rooms_info()`, `send2webhook()`
* time.py: add `get_weekday()`

### Changed

* args.py: add `--stratum` parameter
* args.py: add `--verbose` parameter
* dmidecode.py: collapse near-duplicate data in an admin-friendly way

### Fixed

* base.py: `get_table()` no longer modifies the input `data`
* redfish.py: check sensor state against user thresholds first


## [v2.3.0] - 2025-06-20

### Added

* endoflifedate.py: add Icinga

### Changed

* shell.py: add optional parameter `lc_all='C'` to `shell_exec()`

### Fixed

* distro.py: incorrect `os_family` for Devuan in `get_distribution_facts()` ([#87](https://github.com/Linuxfabrik/lib/issues/87))


## [v2.2.1] - 2025-05-30

### Fixed

* net.py: use `ssl.PROTOCOL_TLS_CLIENT` as best practice in `fetch_ssl()`


## [v2.2.0] - 2025-05-30

### Added

* time.py: add `get_timezone()`
* tools/update-endoflifedate: add Valkey

### Changed

* net.py: force `fetch_ssl()` to use TLS 1.2+
* txt.py: enhance sanitize regex


## [v2.1.1.15] - 2025-05-07

### Changed

* net.py: add `fetch_socket()` and `fetch_ssl()`, improve `fetch()`


## [v2.1.1.7] - 2025-04-21

### Changed

* distro.py: move `get_os_info()` from version.py to distro.py
* human.py: simplify `bits2human()` parameters (no more %-syntax)
* Improve code style across all libraries


## [v2.1.1.5] - 2025-04-19

### Added

* txt.py: add `sanitize_sensitive_data()`

### Changed

* base.py, url.py: use `txt.sanitize_sensitive_data()`
* disk.py: `get_real_disks()` now ignores loop devices
* docs: improve and convert docstrings to Markdown, create `docs` folder using `pdoc`
* shell.py: remove optional output from Windows `chcp` command

### Fixed

* shell.py: fix special character decoding in Windows output by switching to codepage 65001


## [v2.1.0.7] - 2025-04-08

### Fixed

* disk.py: fix static path to `udevadm` ([#85](https://github.com/Linuxfabrik/lib/issues/85))


## [v2.1.0.4] - 2025-03-29

### Changed

* uptimerobot.py: add handling of PSPs, restructure code


## [v2.1.0.0] - 2025-03-23

### Added

* uptimerobot.py: new library for the UptimeRobot API


## [v2.0.0.7] - 2025-03-10

### Added

* tools/update-endoflifedate: add OpenVPN

### Fixed

* txt.py: fix `extract_str()`


## [v2.0.0.0] - 2025-02-15

### Breaking Changes

* Rename test.py to lftest.py due to `nuitka` compilation error on Windows.
* Switch from [calendar versioning](https://calver.org/) to [semantic versioning](https://semver.org/) due to [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) and Windows MSI requirements.

### Added

* keycloak.py: new library for Keycloak API interactions

### Changed

* db_sqlite.py: `create_index()`, `cut()`, `delete()`, `insert()`, `replace()`, and `select()` now delete the underlying SQLite db file by default on `OperationalError` (e.g., when new SQL references columns missing in an older db file). Disable with `delete_db_on_operational_error=False`.
* librenms.py: `get_state()` returns `STATE_OK` instead of `STATE_UNKNOWN`
* url.py: improve error messages and comments

### Fixed

* disk.py: fix `ValueError` if value contains `=`


## [2024060401] - 2024-06-04

Minor improvements, barely any changes.


## [2024052901] - 2024-05-29

### Breaking Changes

* librenms.py: `get_state()` now expects numeric status codes

### Added

* args.py: add `help()`
* base.py: add `str2bool()`
* disk.py: add `get_real_disks()`, `udevadm()`
* human.py: add `human2seconds()`
* txt.py: add `get_dm_name()`, `match_regex()`

### Changed

* base.py: `oao()` replaces `|` character in output with `! ` (reserved for performance data separator)
* db_sqlite.py: increase connect timeout to 5 seconds in `connect()`, return `False` on failure in `close()`
* grassfish.py: add `insecure=False, no_proxy=False, timeout=8` to `fetch_json()`
* huawei.py: remove hardcoded `insecure` parameter in `get_creds()` and `get_data()`
* icinga.py: remove hardcoded `insecure` parameter; add `insecure=False, no_proxy=False, timeout=3` to all functions
* infomaniak.py: add `insecure=False, no_proxy=False, timeout=8` to all functions
* jitsi.py: remove hardcoded `insecure` and evaluate `no_proxy` in `get_data()`
* librenms.py: improve `get_data()` parameter handling
* net.py: add `insecure=False, no_proxy=False, timeout=3` to `get_public_ip()`
* nodebb.py: evaluate `no_proxy` in `get_data()`
* rocket.py: add `insecure=False, no_proxy=False, timeout=3` to all functions
* veeam.py: remove hardcoded `insecure` and evaluate `no_proxy` in `get_token()`
* version.py: add `insecure=False, no_proxy=False, timeout=8` to `check_eol()`
* wildfly.py: evaluate `insecure` and `no_proxy` in `get_data()`

### Fixed

* base.py: `lookup_lod()` never uses the default parameter ([#82](https://github.com/Linuxfabrik/lib/issues/82))
* db_mysql.py: fix `select()` and providing data
* feed.py: incompatible with Azure status RSS ([#756](https://github.com/Linuxfabrik/monitoring-plugins/issues/756))


## [2023112901] - 2023-11-29

### Added

* endoflifedate.py: new auto-built library for end-of-life date tracking
* [Published on PyPI](https://pypi.org/project/linuxfabrik-lib/), installable via `pip install linuxfabrik-lib`
* qts.py: new library for the QNAP QTS API
* tools/update-endoflifedate: tool to update endoflifedate.py

### Changed

* base.py: `cu()` appends an optional message, making it a true error message function
* base.py: `oao()` prints/suffixes ' (always ok)' if `always_ok=True`
* shell.py: `shell_exec()` merges OS environment variables with those set by the `env` parameter
* version.py: `check_eol()` also fetches and caches info from https://endoflife.date/api


## [2023051201] - 2023-05-12

### Breaking Changes

* db_mysql.py: change from username/password to option file authentication in `connect()`
* Remove all Python 2 based plugins and libraries, and remove the "3" suffix from all Python 3 based libraries ([#589](https://github.com/Linuxfabrik/monitoring-plugins/issues/589))

### Added

* args.py: add `number_unit_method` type (used in `disk-usage` monitoring plugin)
* disk.py: add `read_env()`
* version.py: new library

### Changed

* base.py: improve `str2state()`

### Fixed

* smb.py: `TypeError`: object `SMBDirEntry` has no attribute `from_filename`


## [2023030801] - 2023-03-08

### Breaking Changes

* db_mysql3: change from username/password to option file authentication in `connect()`
* net3: rename `get_ip_public()` to `get_public_ip()`
* net3: rename `ip_to_cdir()` to `netmask_to_cdir()`

### Added

* dmidecode3.py: new library
* grassfish3.py: new library

### Changed

* base3.py: make `get_worst()` more robust
* human3.py: `human2bytes()` now handles values like "3.0M"
* infomaniak3.py: apply new API version
* shell3.py: `shell_exec()` also handles timeouts
* wildfly3.py: update library


## [2022072001] - 2022-07-20

### Added

* distro3.py: new library

### Changed

* cache3.py: use more unique default names for SQLite databases
* db_mysql3.py: enhance for new mysql checks
* db_mysql3.py: switch from `mysql.connector` to `PyMySQL` ([#570](https://github.com/Linuxfabrik/monitoring-plugins/issues/570))
* db_sqlite3.py: use more unique default names for SQLite databases
* disk3.py: add `file_exists()` function
* Revert Python 3.6+ f-strings to `.format()` for broader compatibility


## [2022022801] - 2022-02-28

### Added

* human3.py: new library for converting raw numbers and times to human-readable representations
* shell3.py: new library for shell communication
* time3.py: new library for date/time functions
* txt3.py: new library for text handling, encoding, and decoding
* redfish.py: add `get_systems*()` functions for Systems collection
* winrm.py: add function to run shell commands ([#41](https://github.com/Linuxfabrik/lib/issues/41))
* powershell.py: add PowerShell support ([#40](https://github.com/Linuxfabrik/lib/issues/40))

### Changed

* base3: move `filter_str()` to db_sqlite3.py ([#52](https://github.com/Linuxfabrik/lib/issues/52))
* base3: move `get_owner()` to nextcloud-version3 ([#53](https://github.com/Linuxfabrik/lib/issues/53))
* base3: move `sha1sum()` to db_sqlite3.py ([#50](https://github.com/Linuxfabrik/lib/issues/50))
* base3: move `x2human` and `human2x` functions to new human.py library ([#49](https://github.com/Linuxfabrik/lib/issues/49))
* base3: move date/time functions to new time3.py library ([#55](https://github.com/Linuxfabrik/lib/issues/55))
* base3: move shell functions to new shell3.py library ([#56](https://github.com/Linuxfabrik/lib/issues/56))
* base3: move text functions to new txt3.py library ([#51](https://github.com/Linuxfabrik/lib/issues/51))
* Lint all libraries ([#57](https://github.com/Linuxfabrik/lib/issues/57))
* Standardize try-except import statements ([#60](https://github.com/Linuxfabrik/lib/issues/60))
* txt3: handle all encoding and decoding ([#59](https://github.com/Linuxfabrik/lib/issues/59))
* url3.py: extend `fetch_json()` to make `fetch_json_ext()` obsolete
* veeam: use new `fetch_json()` instead of `fetch_json_ext()` ([#42](https://github.com/Linuxfabrik/lib/issues/42))

### Removed

* base3: remove `yesterday()` function ([#54](https://github.com/Linuxfabrik/lib/issues/54))

### Fixed

* base: fix `hashlib.md5()` on FIPS-compliant systems ([#30](https://github.com/Linuxfabrik/lib/issues/30))
* base: fix tuple item assignment error ([#43](https://github.com/Linuxfabrik/lib/issues/43))
* librenms-alerts2: `--lengthy` causes error ([#61](https://github.com/Linuxfabrik/lib/issues/61))
* nginx-status: `TypeError`: a bytes-like object is required, not 'str' ([#47](https://github.com/Linuxfabrik/lib/issues/47))
* url3.py: `AttributeError`: 'str' object has no attribute 'to_bytes' ([#62](https://github.com/Linuxfabrik/lib/issues/62))
* url3: `TypeError`: a bytes-like object is required, not str ([#44](https://github.com/Linuxfabrik/lib/issues/44))
* Various fixes after linting
* veeam.py: `ValueError`: need more than 2 values to unpack ([#45](https://github.com/Linuxfabrik/lib/issues/45))
* veeam3.py, huawei3.py: `getheader()` should be `get()` in Python 3 ([#46](https://github.com/Linuxfabrik/lib/issues/46))


## [2021101401] - 2021-10-14

### Added

* base: add `utc_offset()` function ([#35](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/35))
* db_sqlite: add REGEXP function ([#36](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/36))
* jitsi.py: new library
* nodebb.py: new library
* test.py: new library for unit testing
* veeam.py: new library

### Changed

* base2: improve Unicode, UTF-8, and ASCII handling
* base: `get_state()` can now evaluate against a range ([#34](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/34))
* base: `version2float()` now strips everything except numbers and decimal points ([#26](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/26))
* base: improve line drawing in `get_table()` ([#7](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/7))
* base: make `version()` more robust ([#28](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/28))
* cache: make filename for cache configurable ([#21](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/21))
* db_sqlite: support `LIKE` statements using a regexp
* get_table(): use ASCII characters only for broadest terminal compatibility ([#33](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/33))
* url: `fetch()` and `fetch_json()` can now also return HTTP status code and response headers ([#32](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/32))
* url: identify as Linuxfabrik Monitoring Plugin ([#24](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/24))

### Fixed

* base2: `AttributeError`: 'exceptions.ValueError' object has no attribute 'encode' ([#37](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/37))
* base2: `UnicodeDecodeError`: 'ascii' codec can't decode byte 0xc2 ([#38](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/38))
* base: `get_table()` does not handle length of UTF-8 correctly ([#8](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/8))
* cache3: `NameError`: name 'base' is not defined ([#29](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/29))
* db_sqlite: 8-bit bytestrings error with text_factory ([#20](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/20))
* disk: problems with `read_csv()` ([#25](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/25))
* librenms3.py: fix error ([#27](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/27))
* net: `fetch()` port and timeout must be integers ([#22](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/22))
* net: socket `recv()` timeout ([#23](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/23))


## [2020052801] - 2020-05-28

### Added

* db_mysql.py: new library
* feedparser.py: new library
* icinga.py: new library


## 2020042001 - 2020-04-20

### Changed

* base.py: add `shell_exec()`
* net.py: improvements
* url.py: improvements


## [2020041501] - 2020-04-15

### Added

* args.py: new library
* base.py: new library
* cache.py: new library
* db_sqlite.py: new library
* disk.py: new library
* net.py: new library
* rocket.py: new library
* url.py: new library


## [2020022801] - 2020-02-28

Initial release.


[Unreleased]: https://github.com/Linuxfabrik/lib/compare/v4.0.2...HEAD
[v4.0.2]: https://github.com/Linuxfabrik/lib/compare/v4.0.1...v4.0.2
[v4.0.1]: https://github.com/Linuxfabrik/lib/compare/v4.0.0...v4.0.1
[v4.0.0]: https://github.com/Linuxfabrik/lib/compare/v3.4.1...v4.0.0
[v3.4.1]: https://github.com/Linuxfabrik/lib/compare/v3.4.0...v3.4.1
[v3.4.0]: https://github.com/Linuxfabrik/lib/compare/v3.3.0...v3.4.0
[v3.3.0]: https://github.com/Linuxfabrik/lib/compare/v3.2.0...v3.3.0
[v3.2.0]: https://github.com/Linuxfabrik/lib/compare/v3.1.1...v3.2.0
[v3.1.1]: https://github.com/Linuxfabrik/lib/compare/v3.1.0...v3.1.1
[v3.1.0]: https://github.com/Linuxfabrik/lib/compare/v3.0.0...v3.1.0
[v3.0.0]: https://github.com/Linuxfabrik/lib/compare/v2.4.0...v3.0.0
[v2.4.0]: https://github.com/Linuxfabrik/lib/compare/v2.3.0...v2.4.0
[v2.3.0]: https://github.com/Linuxfabrik/lib/compare/v2.2.1...v2.3.0
[v2.2.1]: https://github.com/Linuxfabrik/lib/compare/v2.2.0...v2.2.1
[v2.2.0]: https://github.com/Linuxfabrik/lib/compare/v2.1.1.15...v2.2.0
[v2.1.1.15]: https://github.com/Linuxfabrik/lib/compare/v2.1.1.7...v2.1.1.15
[v2.1.1.7]: https://github.com/Linuxfabrik/lib/compare/v2.1.1.5...v2.1.1.7
[v2.1.1.5]: https://github.com/Linuxfabrik/lib/compare/v2.1.0.7...v2.1.1.5
[v2.1.0.7]: https://github.com/Linuxfabrik/lib/compare/v2.1.0.4...v2.1.0.7
[v2.1.0.4]: https://github.com/Linuxfabrik/lib/compare/v2.1.0.0...v2.1.0.4
[v2.1.0.0]: https://github.com/Linuxfabrik/lib/compare/v2.0.0.7...v2.1.0.0
[v2.0.0.7]: https://github.com/Linuxfabrik/lib/compare/v2.0.0.0...v2.0.0.7
[v2.0.0.0]: https://github.com/Linuxfabrik/lib/compare/2024060401...v2.0.0.0
[2024060401]: https://github.com/Linuxfabrik/lib/compare/2024052901...2024060401
[2024052901]: https://github.com/Linuxfabrik/lib/compare/2023112901...2024052901
[2023112901]: https://github.com/Linuxfabrik/lib/compare/2023051201...2023112901
[2023051201]: https://github.com/Linuxfabrik/lib/compare/2023030801...2023051201
[2023030801]: https://github.com/Linuxfabrik/lib/compare/2022072001...2023030801
[2022072001]: https://github.com/Linuxfabrik/lib/compare/2022022801...2022072001
[2022022801]: https://github.com/Linuxfabrik/lib/compare/2021101401...2022022801
[2021101401]: https://github.com/Linuxfabrik/lib/compare/2020052801...2021101401
[2020052801]: https://github.com/Linuxfabrik/lib/compare/2020042001...2020052801
[2020042001]: https://github.com/Linuxfabrik/lib/compare/2020041501...2020042001
[2020041501]: https://github.com/Linuxfabrik/lib/compare/2020022801...2020041501
[2020022801]: https://github.com/Linuxfabrik/lib/releases/tag/2020022801
