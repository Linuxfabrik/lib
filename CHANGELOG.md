# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

* args.py: `--no-perfdata` help text, so plugins can offer a switch to suppress performance data output.
* base.py: `oao()` gained a `no_perfdata` parameter to suppress the performance data section while keeping the message and exit code.
* db_mysql.py: `get_replica_hosts()` lists the replicas registered with a server, using `SHOW REPLICAS` on MySQL 8.0.22+ and falling back to `SHOW SLAVE HOSTS` on MariaDB and older MySQL.
* db_mysql.py: `get_server_info()` also returns `version_tuple`, the comparable form of the version it already reported as a string.
* db_mysql.py: `get_version()` returns the connected server's flavor and version as a comparable tuple, so callers no longer parse the version string themselves.
* disk.py: `get_fingerprint()` hashes a file's head, tail or whole content, so callers can recognize a file by what it holds rather than by metadata, which reports nothing when a file is rewritten in place.
* disk.py: `glob()` returns a sorted list of paths matching a shell glob pattern (recursive by default).
* disk.py: `read_file()` can return raw `bytes` via a new `binary` parameter.
* disk.py: `stat()` returns a filesystem entry's `os.stat()` result (or `None`), so callers get every field (size, mtime, mode, owner, ...) in one syscall.
* disk.py: `is_within()` reports whether a path resolves inside a set of allowed directories (symlinks and `..` are resolved so they cannot escape), for callers that must confine filesystem access.
* icinga.py: `build_icingaweb2_url()` builds an Icinga Web 2 host or service detail URL from a base URL and the object name(s), URL-encoding the untrusted names and pinning the scheme to http/https.
* icinga.py: `get_logo()` returns the bundled Icinga logo as PNG bytes.
* icinga.py: `render_notification_mail()` renders the plain-text and HTML body of an Icinga notification mail from label/value rows, HTML-escaping the untrusted cell values.
* mail.py: new library for sending plain-text and HTML email via SMTP, with optional login and inline related images.
* openmetrics.py: new library reading the OpenMetrics and Prometheus text formats served by a `/metrics` endpoint, so consumers select a metric by name and labels instead of parsing the payload themselves.
* redfish.py: a cache-aware Redfish fetch layer. `fetch_collection()` reads a collection in a single request via the `$expand` query where the controller supports it (falling back to one request per member), `fetch_members()` resolves bare member references, and `fetch_resource()` reads a single resource such as the service root; `get_expand_suffix()` returns the deepest `$expand` the controller advertises and `get_auth_header()` obtains a session token. Each caches its result by URL under the shared `CACHE_FILENAME` when the caller passes a non-zero `cache_expire`, so the several Redfish checks on a host share fetched data and one session instead of each hitting the controller; with the default they fetch straight through. `is_member_expanded()` tells an inlined member from a bare reference.
* rocket.py: `send_message()` posts a JSON payload to a complete Rocket.Chat incoming-webhook URL (with custom headers and the parsed response returned), complementing `send2webhook()` which builds the URL from a base plus a webhook id.

### Changed

* db_mysql.py: both version parsers share one flavor rule and delegate to `version.version()`, so a lowercase `-mariadb` tag is no longer read as MySQL.
* version.py: importing the module no longer drags in the cache, SQLite and HTTP machinery; only `check_eol()` loads those, on call.

### Fixed

* db_sqlite.py: `get_db_path()` rejects a database filename that is not a plain basename, so a caller cannot traverse out of the secured per-user directory.
* lftest.py: the shared `--test` unit-test mechanism could be used to read arbitrary files as root on hosts where plugins run via a sudoers allowlist; fixture reads are now confined to the calling plugin's own `unit-test/` directory ([GHSA-rh9c-rqvg-f7pr](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-rh9c-rqvg-f7pr)).


## [v6.0.0] - 2026-07-07

### Added

* args.py: added a central help text for the `--no-match-severity` parameter, used by filter-based plugins to make the state configurable when no item matches the filters.
* args.py: added a central help text for the `--unreachable-severity` parameter, used by end-of-life checks to make the state configurable when the online source is unreachable.
* bexio.py: new library
* huawei_pacific.py: new library for Huawei OceanStor Pacific storage systems, which use the `/api/v2/` REST API with `X-Auth-Token` authentication (a different protocol from the Dorado line).
* redfish.py: `build_url()` builds a follow-up Redfish URL from a base URL and an `@odata.id` link, rejecting non-relative links so a response cannot redirect the request to another host ([GHSA-96fx-pqc3-28xv](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-96fx-pqc3-28xv)).
* shell.py: `shell_exec()` gained a `run_as` parameter to run a command as another local user with that user's session runtime directory (`XDG_RUNTIME_DIR`), as rootless Podman and other per-user session services require.
* url.py: added new optional flag `response_on_error` for `fetch()`/`fetch_json()` to return the response body instead of an error message on failure. Primarily for use with APIs that provide machine-readable error responses such as the Bexio API.
* version.py: `check_eol()` gained an `unreachable_severity` parameter to report a configurable state (default OK) when the online end-of-life source is unreachable and the bundled offline data is used. The offline fallback is no longer cached, so the next call retries the online source instead of masking a persistent outage.

### Changed

* args.py: the developer-only `--test` parameter is now hidden from plugin `--help` output. It is still accepted on the command line, so the unit-test suite keeps working.
* huawei.py: renamed to `huawei_dorado.py`, freeing the generic name now that a second Huawei storage line is supported. **Breaking:** consumers must change their import from `lib.huawei` to `lib.huawei_dorado`.
* redfish.py: a cached Redfish session token is now kept only as long as the controller itself keeps the session alive, read from the controller's own session timeout. This avoids sporadic "401 Unauthorized" errors on controllers with short session timeouts (such as Supermicro's 300 seconds) without having to tune the cache expiration by hand ([#246](https://github.com/Linuxfabrik/lib/issues/246)).
* time.py: clarified the `timestr2epoch(..., pattern='iso8601')` docstring - the mode is backed by `datetime.fromisoformat()`, not a full ISO 8601 parser, and which layouts it accepts beyond RFC 3339 depends on the Python version.

### Fixed

* huawei_dorado.py: Huawei OceanStor Dorado checks no longer raise a false warning for a backup battery unit that is charging, and more component states are now shown with a readable label instead of `Unknown` (for example spun-down disks, link up/down, and replication states). The running-status translation was completed against the full documented status list.
* huawei_dorado.py: Huawei OceanStor Dorado checks now recover on their own when the cached API session is no longer accepted by the appliance (after a controller reboot, a manual session reset, or the server-side session timeout). The check logs in again and retries instead of failing, and it no longer keeps retrying a doomed request long enough to risk hitting the monitoring server's check timeout.
* powershell.py, shell.py, winrm.py: command output that contains non-UTF-8 bytes (such as a Windows username with an umlaut, or a locale-dependent tool message) no longer crashes the plugin later when it prints its result. Such output is now read as Latin-1 instead of producing text that fails to print ([#256](https://github.com/Linuxfabrik/lib/issues/256)).
* url.py: fetching a page or JSON no longer fails with a decode error when the remote host sends non-UTF-8 content without declaring a charset (such as sensor firmware that serves the degree sign as a raw Latin-1 byte). The response is read as Latin-1 in that case instead of aborting the check.

### Security

* url.py: `fetch()` no longer forwards credential headers to another host when a server redirects there (SSRF / token leak) ([GHSA-4jc5-g844-4x33](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-4jc5-g844-4x33)).


## [v5.1.0] - 2026-06-24

### Added

* endoflifedate.py: bundled offline End-of-Life data for Apache Tomcat.
* txt.py: `compile_regex()` accepts a `flags` argument, so callers can compile case-insensitive patterns (`re.IGNORECASE`) without a separate helper.

### Fixed

* db_sqlite.py: cached databases now self-heal after a schema change between releases. A constraint or data error (such as a `NOT NULL` column that a newer or older release no longer writes) deletes and rebuilds the cache on the next run, instead of failing on every run until the stale file is removed by hand.
* lftest.py: no longer breaks at import with a `SyntaxError` on Python interpreters older than 3.10 (such as the system Python 3.6 on RHEL 8 / Rocky 8, and our supported Python 3.9 floor). A parenthesized context manager was rewritten as nested `with` statements, so every plugin that imports this module stays runnable on those interpreters.
* time.py: no longer fails to import on Python interpreters older than 3.9 (such as the system Python 3.6 on RHEL 8 / Rocky 8) where the `zoneinfo` module does not exist. Consumers that do not need named time zones keep working and fall back to UTC.

### Security

* Python 3.9 lockfile bumps the cryptography library to a release that ships a patched OpenSSL, closing a known vulnerability for downstreams that vendor the pinned dependencies on RHEL 8 / Debian 11.


## [v5.0.0] - 2026-06-12

### Changed

* distro.py, version.py: read the OS name and version directly from `/etc/os-release` instead of sourcing it through a shell
* shell.py: `shell_exec()` requires the command as a list of arguments (argv) and always runs with `shell=False`. It no longer accepts a command string, a `shell=` parameter, or `|` pipelines. This is a breaking change: pass `['df', '-h', path]` instead of `'df -h ' + path`
* shell.py: new `safe_cli_value()` rejects a value that a called program could misread as an option (leading `-`), to guard positional or target arguments (such as an ssh destination or a `ping` target) against option injection
* ssh.py: `build_options()` and `target()` return argument lists/tokens instead of pre-quoted strings; `run()`, `scp()` and `rsync()` build argument lists, drop the `use_shell` parameter, and reject an option-like host or username

### Removed

* shell.py: removed `get_command_output()` (it had no consumers; use `shell_exec()` directly)

### Fixed

* base.py: `oao()` normalizes CRLF and stray CR in the plugin message to LF, so Windows command output is no longer rendered with doubled line breaks in web UIs that use `white-space: pre-wrap`
* endoflifedate.py: the Apache httpd and Rocket.Chat offline data is keyed under their current endoflife.date URLs (`apache-http-server`, `rocket-chat`), so version checks still work when the endoflife.date API is unreachable
* lftest.py: use the classic `with a, b:` form instead of parenthesized context managers (Python 3.10+ syntax), so the module parses under RHEL 8's default Python 3.6
* shell.py: on Windows, a subprocess's piped output is decoded with the console / OEM code page instead of UTF-8, so non-ASCII characters such as umlauts in usernames are no longer mangled ([monitoring-plugins#681](https://github.com/Linuxfabrik/monitoring-plugins/issues/681))
* url.py: use the classic `with a, b:` form instead of parenthesized context managers (Python 3.10+ syntax), so `import lib.url` no longer raises a SyntaxError under RHEL 8's default Python 3.6


## [v4.4.0] - 2026-06-09

### Added

* disk.py: `shorten_path()` abbreviates a path for display by reducing every parent component to its first character (zsh-style), keeping the basename in full
* redfish.py: `get_auth_header()` builds the request authentication header, reusing a cached session token to avoid creating a new controller session on every request, and falling back to HTTP Basic auth
* redfish.py: `get_chassis_power_powercontrol()` parses a power control (overall power consumption) entry for health monitoring and reporting
* redfish.py: `get_manager()` parses a manager (BMC) resource for health monitoring and identification
* redfish.py: `get_systems_ethernetinterfaces()` parses an Ethernet interface resource for health monitoring and identification
* redfish.py: `get_systems_memory()` parses a memory module (DIMM) resource for health monitoring and identification, applying vendor quirks (Dell module size, HPE/Fujitsu OEM module status)
* redfish.py: `get_systems_processors()` parses a processor (CPU) resource for health monitoring and identification
* redfish.py: `get_systems_storage_volumes()` parses a volume (logical drive) resource for health monitoring and identification
* redfish.py: `get_updateservice_firmwareinventory()` parses a firmware inventory resource for version reporting and health monitoring

### Changed

* net.py: `get_netinfo()` and `get_subnet_hosts()` read interface addresses via psutil instead of the deprecated `netifaces`, and the default gateway is read from the Linux routing table. This drops the `netifaces` dependency, so the library installs from pure wheels on Python 3.10+ without a build toolchain
* redfish.py: `get_chassis_thermal_fans()` normalizes fan speed reported in RPM or percent onto a single shape
* redfish.py: `get_manager_logservices_sel_entries()` can filter log entries by regular expression and age out entries older than a cutoff
* redfish.py: `get_systems_storage_drives()` also extracts `PowerOnHours` and the drive temperature, so consumers can report drive age and temperature
* time.py: `timestr2epoch()` accepts `pattern='iso8601'` to parse ISO 8601 timestamps (trailing `Z`, embedded offset or date-only) without specifying the exact layout
* url.py: `fetch_json()` accepts a `retries` argument to re-attempt a failed request or an unparseable body, for flaky endpoints


## [v4.3.0] - 2026-06-06

### Added

* disk.py: `copy_dir()` and `copy_file()` copy a directory tree / single file and report success or an error message, matching the other disk helpers
* disk.py: `get_block_devices()` lists all local block devices, including ones without a mounted filesystem, so callers can also work with raw or unmounted devices such as multipath SAN volumes
* disk.py: `make_temp_dir()` creates a unique temporary directory (companion to `get_tmpdir()`), reporting the path or an error message
* disk.py: `mkdir()` creates a directory (including missing parents) and reports success or an error message, matching the other disk helpers
* disk.py: `rm_dir()` recursively deletes a directory tree (companion to `rm_file()`), reporting success or an error message
* lftest.py: `network()` plus `network` / `network_alias` arguments on `run_container()` let a test wire an application container to a backing service (e.g. a database) on a shared network, for multi-container integration tests
* net.py: `cidr_to_hosts()` returns the usable IPv4 or IPv6 host addresses of a network given in CIDR notation, with a configurable size limit, for callers that need to enumerate an explicit subnet
* net.py: `get_subnet_hosts()` returns the usable IPv4 or IPv6 host addresses of an interface's subnet, for callers that need to enumerate a local network
* shell.py: `which()` locates an executable in PATH (wrapper around `shutil.which()`), so callers detect installed tools consistently
* ssh.py: new module to run commands (`run()`) and copy files (`scp()`, `rsync()`) over SSH, assembling and quoting the command lines from individual options (`build_options()`, `target()`), so callers no longer hand-roll ssh/scp invocations
* url.py: `fetch()` / `fetch_json()` accept a `method` argument to force the HTTP method, enabling a bodyless POST

### Fixed

* huawei.py: the session cookie is read regardless of how the storage system cases the response header, preventing authentication from failing on a case-sensitive header lookup
* redfish.py: Sensors that report an empty min/max range (identical min and max, used by some firmware as a "no limit" placeholder) no longer raise false warnings ([#1211](https://github.com/Linuxfabrik/monitoring-plugins/issues/1211))
* url.py: a caller-supplied `Content-Length` is ignored and recomputed from the request body
* url.py: response header names are exposed in lower case, so callers read them reliably no matter how the server cased them
* veeam.py: authentication against the Veeam Enterprise Manager API no longer fails with a `415 Unsupported Media Type` error or a false "unauthorized" result
* Installing the library from source (for example `pip install --editable .`) no longer hangs, which also unblocks the API documentation build
* Resolve the remaining ruff lint violations across the library, including a few robustness fixes: a bare `except` in disk.py now catches only `OSError`, mutable default arguments in url.py and rocket.py are no longer shared between calls, and uptimerobot.py uses `isinstance()` instead of a `type()` comparison ([#118](https://github.com/Linuxfabrik/lib/issues/118))


## [v4.2.0] - 2026-06-02

### Added

* db_sqlite.py: `get_db_path()` resolves and returns the absolute path of a database without opening it, so callers that need to seed, migrate or remove a database file rely on a single source of truth instead of rebuilding the path themselves

### Security

* db_sqlite.py: SQLite databases are now created in a private, per-user `0700` directory under the system temporary directory instead of directly in the shared, world-writable `/tmp`. This closes a local symlink attack on the predictable database paths where an unprivileged user could redirect writes from a process running as root to arbitrary files ([GHSA-r35r-fpx2-jgr4](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-r35r-fpx2-jgr4), thanks to [OoYo0uto](https://github.com/OoYo0uto))


## [v4.1.0] - 2026-05-29

### Added

* db_mysql.py: `get_server_info()` returns `{flavor, version}` for the installed MySQL/MariaDB server, probing `mysqld`, `mariadbd`, `mariadb`, `mysql` and parsing the --version banner with regexes that cover all known output formats (legacy `Distrib` banner, modern `from` banner, server-binary banner, MariaDB-suffixed and plain). Accepts a pre-collected banner string to support unit-test fixtures without shelling out. Works without a database connection
* db_mysql.py: `get_flavor()` returns whether the installed binary is MariaDB or MySQL (thin wrapper around `get_server_info()`). Useful where systemd-based detection is unreliable (e.g. Fedora aliases `mysql.service` to `mariadb.service`)

### Fixed

* db_sqlite.py: consumers that cache trend data in `/tmp` no longer fail with "attempt to write a readonly database" when first run as one user (e.g. root) and later scheduled under another. Each user now gets its own cache file ([#181](https://github.com/Linuxfabrik/lib/issues/181))

### Security

* Bump `idna` to 3.16 in the Python 3.9 lockfile, closing a moderate vulnerability where crafted input to `idna.encode()` could bypass the CVE-2024-3651 fix


## [v4.0.2] - 2026-05-18

### Fixed

* url.py: `import lib.url` no longer aborts with `AttributeError: module 'ssl' has no attribute 'TLSVersion'` on Python interpreters below 3.7 (e.g. RHEL 8's default `python3` = 3.6). The TLS version mapping is now built only when `ssl.TLSVersion` is available; any consumer that doesn't use TLS version pinning keeps importing. Callers that pass `tls_min` / `tls_max` get a clear `RuntimeError` naming the missing requirement instead of the cryptic `AttributeError`. Note: the lib's supported minimum is still Python 3.9; this only makes one specific import path resilient


## [v4.0.1] - 2026-05-18

### Fixed

* db_mysql.py: `connect()` aligns the session's character set and collation with the `mysql` system schema right after the connection is up. Stops queries against `mysql.user` and `mysql.global_priv` from aborting with ER 1267 ("Illegal mix of collations") when the server's connection-collation default differs from the system tables' column collations. MariaDB 10.4+ exposes `mysql.user` as a view over `mysql.global_priv` with JSON-derived columns whose results carry COERCIBLE coercibility, which makes plain `col = 'literal'` compares trip whenever `collation_connection` and the column collation don't match. Lookup uses `information_schema.schemata` so the right collation is picked across MySQL/MariaDB versions and locale-specific installs. Best-effort: on any error the connection stays usable. Fixes all `mysql-*` plugins ([linuxfabrik/monitoring-plugins#1139](https://github.com/Linuxfabrik/monitoring-plugins/issues/1139))


## [v4.0.0] - 2026-05-15

### Breaking Changes

* base.py: rename module-level constant `X86_64` to `IS_64BIT`. The old name was misleading because it suggested Intel/AMD 64-bit only, while the underlying check (`sys.maxsize > 2**32`) is True on any 64-bit Python build (aarch64, ppc64le, s390x, riscv64, …). Logic unchanged. Downstream consumers must update imports

### Added

* db_mysql.py: `check_privileges(conn, *required)` replaces the old `check_select_privileges()`. Without arguments it keeps the previous functional smoke test (`SELECT VERSION()`, works with `GRANT USAGE` alone). With arguments it parses `SHOW GRANTS FOR CURRENT_USER()` and reports any privilege that is missing for the current user, with `ALL PRIVILEGES` and `SUPER` short-circuiting to success. Each positional argument can be a string (single privilege required) or a list/tuple of strings (any-of group, useful for cross-version aliases like `REPLICATION CLIENT` / `SLAVE MONITOR` / `REPLICA MONITOR` introduced by MariaDB 10.5+). Enables consumers to declare their actual privilege requirements precisely
* db_mysql.py: four new helpers consolidate patterns that several consumers implement by hand. `get_all_status(conn)` and `get_all_variables(conn)` return the complete `SHOW GLOBAL STATUS` / `SHOW GLOBAL VARIABLES` as a dict in one round trip (cheaper than many `LIKE '...'` queries when a consumer needs more than a handful of values). `get_replica_status(conn)` issues `SHOW REPLICA STATUS` and silently falls back to the legacy `SHOW SLAVE STATUS`, returning the first row or `None` when the server is not configured as a replica. `has_is_role_column(conn)` reports whether `mysql.user.IS_ROLE` exists (MariaDB 10.0.5+ roles) so consumers can gate `IS_ROLE = 'N'` clauses without each implementing the same probe
* db_sqlite.py: `per_second_deltas(filename, name, counters)` consolidates the cross-run "delta of cumulative counters between runs" pattern that several consumers implement by hand. Persists the counters in a local SQLite cache (schema derived from the counters dict so callers no longer have to spell out the table definition per consumer) and returns the per-second rates vs. the previous run. Useful for any cumulative counter that needs to be reported as a per-second rate: /proc and /sys byte counters (disk I/O, network traffic, file descriptors), database status counters, application metrics. Returns `None` on the first run, on counter resets and on schema changes (auto-rebuilds the cache table in that case). Lets consumers emit per-second rates as perfdata instead of `uom='c'` continuous counters, so Grafana panels do not need their own `non_negative_difference()` workaround
* lftest.py: `run_mariadb_from_containerfile(containerfile_path, ...)` builds a per-consumer Containerfile via testcontainers' DockerImage and yields `(container, defaults_file)` like `run_mariadb()`. Consumers move their test-image matrix into `unit-test/containerfiles/<name>` so each consumer owns its supported MariaDB / MySQL LTS coverage instead of relying on a hardcoded image list in the lib. The `MARIADB_LTS_IMAGES` constant has been removed (no in-tree caller after the migration)
* lftest.py: `run_mariadb` / `run_mariadb_from_containerfile` renamed to `run_mysql_compatible` / `run_mysql_compatible_from_containerfile` to reflect that both upstream MySQL and MariaDB images are supported (`docker.io/library/mysql:*`, `docker.io/library/mariadb:*`, `quay.io/sclorg/mariadb-*`, `quay.io/sclorg/mysql-*`). Family detection picks `mariadbd` vs `mysqld` when `extra_args` is set. Old names are kept as aliases for one release
* net.py: `fetch()` and `fetch_socket()` gain an optional `dialog` parameter for multi-step request/response conversations (regex-driven, no half-close). Enables clean implementations for protocols like NUT, SMTP, POP3, IMAP and FTP without re-implementing socket handling per consumer
* net.py: `fetch()` gains a `tls=True` switch that wraps the socket in a TLS 1.2+ context with SNI, equivalent to calling `fetch_ssl()`. The legacy `fetch_ssl()` helper stays for backward compatibility but is now marked deprecated in its docstring
* time.py: `now()` gains `as_type='utc'` returning the current UTC time as a naive `datetime.datetime`. Useful for fields defined as UTC by spec (x509 `notBefore` / `notAfter`, HTTP `Date`, RFC 3339 timestamps), so consumers can stay on the lib helper instead of falling back to `datetime.datetime.now(datetime.timezone.utc)`
* url.py: `fetch()` and `fetch_json()` now speak HTTP/1.0, HTTP/1.1 and HTTP/2 via `httpx`, with new `http_version`, `tls_min` and `tls_max` parameters for protocol pinning. `extended=True` now also returns the negotiated TLS version, ALPN protocol, the server certificate in DER form, and a per-phase `timings` dict with `dns`, `connect`, `tls`, `ttfb`, `transfer` and `total` (all seconds), ready for downstream certificate inspection and HTTPS-availability monitoring. `http_version='3'` is reserved and currently returns a clear error until QUIC support lands. Existing callers and parameters are unchanged

### Changed

* pyproject.toml: declare `pypsrp` and `pywinrm` as direct dependencies. `lib.winrm` imports both at module load time (wrapped in `try/except ImportError` only so a non-WinRM consumer still loads); previously they had to be pinned in every downstream project that consumed `lib.winrm` (e.g. monitoring-plugins for `dhcp-scope-usage` on Windows). Same convention as `psutil`, `smbprotocol` etc., which `lib.psutil` / `lib.smb` import conditionally but which are declared as hard deps because they are part of lib's published surface
* requirements: one hash-pinned lockfile per supported Python LTS, each in its own `lockfiles/pyXX/` subdirectory (`py39` to `py314`). Replaces the single `requirements.txt`. Dependabot watches each subdirectory separately, except `lockfiles/py39/` which is excluded from both version bumps and security PRs: most upstream packages dropped Python 3.9 over 2025/2026, so automated bumps would break `pip install --require-hashes` on RHEL 8 / Debian 11. The py39 lockfile is regenerated manually as needed
* url.py: `fetch()` switched its underlying engine from stdlib `urllib` to `httpx`. Behaviour for existing callers is preserved (parameters, return-tuple shape, redirect-following, default `Connection: close` and `User-Agent` headers, automatic `application/x-www-form-urlencoded` for POST without explicit Content-Type). `response_header` in the extended dict is now a plain dict instead of `http.client.HTTPMessage`; existing consumers only relied on `.get()` access

### Deprecated

* db_mysql.py: `check_select_privileges()` is deprecated and now a thin backwards-compatible shim that delegates to `check_privileges(conn)`. New code should call `check_privileges()` directly. The shim exists to keep already-deployed consumers working when the lib is upgraded ahead of the consumer set; it will be removed in a future major release

### Fixed

* base.py: `oao()` now properly HTML-escapes `&`, `<` and `>` into `&amp;`, `&lt;` and `&gt;` instead of replacing `<` and `>` with apostrophes. The previous implementation destroyed legitimate threshold descriptions like `<= 10` and shell snippets like `echo 1 > /proc/sys/...`, turning them into `'= 10` and `echo 1 ' /proc/sys/...` in consumer output. HTML-based web UIs (Icinga Web, Naemon-Adagios) render the entities back to the original characters; terminal viewers see the literal entities, which preserves the information. The XSS-protection goal of the original change is still met
* db_sqlite.py: `per_second_deltas()` no longer crashes with `sqlite3.ProgrammingError: Cannot operate on a closed database` when the cache table schema mismatches an earlier consumer version. The internal `insert()` call now uses `delete_db_on_operational_error=False` so the connection survives the schema-mismatch error; the explicit drop/recreate path below operates on a live connection as intended
* url.py: `fetch()` with HTTP digest authentication and `insecure=True` now actually disables certificate verification. Previously the digest auth path silently lost the SSL context
* url.py: `fetch()` with `no_proxy=True` now applies the `timeout` parameter. Previously the no-proxy path called `opener.open(request)` without a timeout, so hangs were only caught by the outer consumer wrapper
* url.py: `import lib.url` no longer fails on hosts where `httpx` is not installed; the import is now lazy and `fetch()` returns a clear "httpx not installed" error message instead of crashing on import. Consumers that pull `lib.url` only transitively (for example via `lib.net`) keep working without `httpx`. Hosts that actually use `fetch()` still need `httpx[http2]` installed via `pip` or `dnf install python3-httpx python3-h2`


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

* args.py: add a generic `--check-security` help text so version-style consumers can offer an upstream security-update check with a uniform parameter description


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
* lftest.py: add `attach_tests()` helper that attaches one `test_*` method per entry in a consumer's `TESTS` list, so that test discovery and reporting show the actual number of fixtures instead of a single aggregate test
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
* base.py: `get_worst()` now accepts any number of state arguments (`*states`). Existing two-argument callers keep working unchanged, but consumers that need to combine three or more states in one call no longer have to nest the call - e.g. `get_worst(state, used_state, committed_state)` instead of `get_worst(state, get_worst(used_state, committed_state))`
* base.py: deduplicate `get_state()` operator logic using `operator` module
* base.py: deduplicate `sum_dict()` by delegating to `sum_lod()`
* base.py: improve `get_table()` performance for large tables
* base.py: move `parse_range()` and state name mapping to module level
* base.py: remove unused `collections` import
* db_sqlite.py: reduce unnecessary dictionary object creation
* human.py: deduplicate `bits2human()`/`bps2human()`/`bytes2human()` via shared `_to_human()` helper
* human.py: deduplicate `humanrange2bytes()`/`humanrange2seconds()` via shared `_convert_range()` helper
* human.py: pre-compute mappings as module constants
* lftest.py: `test()` now accepts `args` with fewer than three elements. Consumers can be invoked as `--test=path/to/fixture` without the trailing `,,0`; stderr defaults to the empty string and the return code to `0`
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


[Unreleased]: https://github.com/Linuxfabrik/lib/compare/v6.0.0...HEAD
[v6.0.0]: https://github.com/Linuxfabrik/lib/compare/v5.1.0...v6.0.0
[v5.1.0]: https://github.com/Linuxfabrik/lib/compare/v5.0.0...v5.1.0
[v5.0.0]: https://github.com/Linuxfabrik/lib/compare/v4.4.0...v5.0.0
[v4.4.0]: https://github.com/Linuxfabrik/lib/compare/v4.3.0...v4.4.0
[v4.3.0]: https://github.com/Linuxfabrik/lib/compare/v4.2.0...v4.3.0
[v4.2.0]: https://github.com/Linuxfabrik/lib/compare/v4.1.0...v4.2.0
[v4.1.0]: https://github.com/Linuxfabrik/lib/compare/v4.0.2...v4.1.0
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
