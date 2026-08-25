# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

* base.py: `range2txt()` renders a threshold range in words (`age=3D not in (0s..2D)`), so a check does not have to repeat the range syntax at the reader
* db_sqlite.py: `cut_per_sensor()` trims a history table per sensor instead of by total row count, so the instance written most often no longer evicts the others
* keycloak.py: `get_server_info_section()` returns one section of the server info document, and names the role Keycloak requires for it
* kvm.py: new module for libvirt hosts, covering domain statistics and listings, storage pools, and the names of domain states and their reasons. Runs over a read-only connection, so it needs neither root nor sudo
* redfish.py: `start_trace()` logs every request, its duration and the authentication path taken to a file, written as the run progresses

### Changed

* db_sqlite.py: `compute_load()` reports the sensors that already have enough samples, and leaves out one whose counter started over instead of reporting a negative rate
* url.py: `fetch()` says what is wrong with a certificate that does not verify and what to do about it, and points out a plaintext request sent to a port that speaks TLS

### Fixed

* base.py: `match_range()` and `get_state()` report a value that is not a number instead of raising, and refuse `nan`, which used to pass as inside every range
* human.py: `seconds2human()` answers `0s` for a duration of zero and signs a negative duration
* redfish.py: `get_auth_header()` keeps a session token for as long as the controller keeps the session, closes the previous session before opening a new one, retries a failed login instead of falling back to HTTP Basic, and re-authenticates once on a "401 Unauthorized"
* url.py: `fetch(extended=True)` tries every address a hostname resolves to, not only the first


## [v7.1.1] - 2026-08-18

### Fixed

* base.py: `match_range()` accepts a threshold with a percent sign (`90%:`) or an exponent (`1e3`), compares a very large threshold correctly, and reports a mistyped threshold instead of raising
* human.py: `human2bytes()` reads a size without a qualifier (`1048576`) as a byte count instead of zero, which alerted on everything
* human.py: `humanrange2bytes()` and `humanrange2seconds()` keep an open lower bound (`~:1M`), a bare `@` and the catch-all `:`, and report an unreadable bound instead of turning it into the threshold zero


## [v7.1.0] - 2026-08-14

### Added

* base.py: `cu()` takes a `traceback`, so a consumer reporting an expected situation prints its sentence without a stack trace below it

### Fixed

* base.py: `get_table()` keeps its rows aligned when a cell reads like an HTML tag (`<unknown>`)


## [v7.0.0] - 2026-08-14

**Highlights:** The SQLite cache layer stops discarding a database over transient problems such as a lock held by a parallel check, so checks sharing a cache file no longer wipe each other's data. Huawei Dorado and Pacific sessions are closed on the appliance instead of piling up until its session pool is full and it refuses every login, including an administrator's login to the management GUI. Distribution detection is corrected for Alpine, Amazon Linux and the whole SUSE family, which were all reported as Debian. Several function renames and one removed function need consumer changes, see Breaking Changes.

### Breaking Changes

* distro.py: `distribution_release` holds the release name (`Plow`, `noble`, `bookworm`), the same as the Ansible fact of the same name, instead of the running kernel release
* huawei_dorado.py: `get_data()` no longer takes URL parameters in a separate argument; append them to the endpoint instead
* huawei_dorado.py: `get_logic_type()` is now `get_enclosure_logic_type()` and `get_role()` is now `get_controller_role()`. A HyperMetro domain and a DR Star trio have their own `get_hypermetro_domain_running_status()` and `get_dr_star_running_status()`, because the appliance numbers those fields differently
* version.py: `get_os_info()` is gone, it duplicated `distro.get_distribution_facts()`. Read its `os_info` key instead

### Added

* args.py: shared help texts for `--brief`, `--fail-severity`, `--no-checksum-data-severity`, `--no-vuln-data-severity`, `--password-file`, `--unscored-severity`, `--warning-temperature` / `--critical-temperature` and `--warning-voltage` / `--critical-voltage`. `MATCH_IGNORE_PRECEDENCE` carries the one sentence on how `--match` and `--ignore` combine
* args.py: `load_secret()` reads a secret out of a file, so it does not have to be passed on the command line where every user on the host sees it
* base.py: `get_table()` takes a `hide_empty` to drop columns no row filled in, a `max_rows` to cap the printed rows and state how many were left out, and a `missing` placeholder for a cell an API did not send. All off by default, and they shape the text alone
* base.py: `verbose()` prints a progress message only when verbose output is switched on
* cache.py: `get(allow_stale=True)` serves an expired entry instead of deleting it, so a consumer whose source is unreachable can fall back on the last answer. `prune()` deletes the entries a version-keyed cache leaves behind
* db_sqlite.py: `connect()` takes a `timeout`, so checks sharing a database file can wait longer for a lock
* disk.py: `get_fingerprint()` takes an `algorithm`, so a digest can be taken in whatever a foreign checksum list published it in. `read_file()` takes a `max_bytes`
* disk.py: `get_package()` names the package a path belongs to, which tells software the distribution installed apart from software put there by hand
* distro.py: Clear Linux, CoreOS, Flatcar, Mandriva, OpenWrt, Slackware, SUSE, UnionTech and the Debian derivatives Cumulus Linux, Deepin, Devuan, Kali, Linux Mint, Parrot, SteamOS and Uos are recognised. Anything else is identified from `/etc/os-release` instead of being reported as plain "Linux"
* feedparser.py: `fetch_soup()` and `parse_soup()` hand back the feed's own markup, and `retries` repeats a download that came back as something other than a feed
* huawei_dorado.py, huawei_pacific.py: `as_code()`, `assert_ok()`, `get_all_data()` for paged list endpoints, the envelope readers `get_error_code()` / `get_result_code()` / `get_status_envelope()`, and a full set of status translators including their `_state()` counterparts. Consumers used to carry a copy of each
* huawei_dorado.py: `get_performance()` and `get_performance_perfdata()` read the current counters of a managed object and turn them into performance data under the vendor's own indicator names. `as_temperature()`, `field()`, `get_account_state()` and `sectors2bytes()` cover placeholder readings, alternate field spellings, the login password status and the sector-counted capacity fields
* huawei_pacific.py: `get_data(base_path=...)` reaches the older endpoint generation below `/dsware/service/` and `/dfv/service/`, which alone serves the disk inventory
* huawei_pacific.py: `get_cluster_nodes()`, `get_node_names_by_ip()`, `get_performance()`, `get_quota_bytes()` and `get_warranty_status()`, plus readable translations for base boards, disks, pools, replication pairs and the login password status
* lftest.py: `test_json()` and `test_text()` read one of several test fixtures of a run
* nextcloud.py: `run_occ()` takes a `timeout`, so a hanging `occ` no longer keeps a check running forever
* shell.py: `shell_exec()` takes a `run_as_session` to run as another user without exporting that user's session runtime directory, which a sudo rule spelling out exact arguments requires. An `env` entry set to None removes that variable from the environment
* txt.py: `shorten()` cuts a long value down out of the middle, `strip_ansi()` removes the escape sequences a CLI tool colorizes with, and `unescape()` resolves HTML character references in plain text
* url.py: `compare_github_refs()` counts how far a branch is ahead of a tag, `get_latest_tag_from_github()` covers projects that tag but never release, and `get_latest_version_from_github()` takes `insecure`, `no_proxy`, `timeout` and `header`. `github_token_header()` builds that header and raises the limit from 60 to 5000 requests per hour
* wordpress.py: new module reading a local WordPress installation from the filesystem - core version and locale, plugins with their wordpress.org slugs, themes, site URL - without a database connection, an HTTP request or `wp-cli`

### Changed

* args.py: the shared `--unreachable-severity` help text describes any unreachable online source rather than only an end-of-life one
* base.py: `oao()` only escapes a `<` that would open an HTML tag, so `< 5.3.2`, `<= 10` and `echo 1 > /proc/sys/...` reach the terminal exactly as written
* disk.py: `walk_directory()` relativizes its paths instead of stripping the root off the front as a plain substring
* huawei_dorado.py, huawei_pacific.py: `--cache-expire 0` switches session caching off, session tokens live in the library's own cache file instead of the one every plugin shares, `get_data()` returns the response as it is instead of adding a `counter` field, and takes a `max_attempts`
* huawei_dorado.py: the appliance device ID is optional. Without one the login goes to the placeholder path the vendor documents and the appliance answers with its own ID
* huawei_dorado.py: a dead power feed, a component that is not running, a disk parked for overheating and a replication relationship that is not mirroring are reported as CRITICAL instead of WARNING
* lftest.py: `assert-retc` is optional in a testcase, like every other assertion already was
* nextcloud.py: `occ` is called without `sudo` when the check already runs as the owner of `config/config.php`, so no sudoers entry is needed and the checks work inside the official container
* url.py: a GitHub repository that has published no release is reported as having none instead of as a failed request, and a rejected token and an exhausted rate limit are named as such

### Fixed

* base.py: `get_perfdata()` reports no metric at all for a reading a source did not deliver, instead of emitting a literal `None` that made consumers drop the whole line
* db_sqlite.py: a cached database is only rebuilt on a schema mismatch or an unreadable file, no longer over a lock held by a parallel check, a full or read-only disk, a bad query, a duplicate record, a missing table or an oversized value. Checks sharing the default database file no longer discard each other's data
* db_sqlite.py: table, index and column names carrying SQL keywords, punctuation, commas or doubled quotes are used as written, unique indexes and indexes on generated columns are created, and a rowid alias no longer looks like a broken database
* db_sqlite.py: a single unusable row no longer aborts a CSV import and deletes the database. The offending line number is reported and the imported rows are kept
* db_sqlite.py: several checks share one rate cache file, each keeping its own history, and a rate counter whose name contains punctuation is recorded
* db_sqlite.py: RHEL 8 and other systems on old SQLite work again - databases open on Python 3.6, a corrupt file is actually removed below SQLite 3.39, and a misspelled column is caught below SQLite 3.26
* db_sqlite.py: journal and write-ahead log files of a discarded database are removed with it, an unusable argument (fewer than two samples, a negative or non-numeric record count) is refused with a clear message, and a regular expression match works against empty and numeric values
* distro.py: the OS family of Alpine, Amazon Linux and the whole SUSE family is correct. All three were reported as Debian, so checks branching on the OS family ran the Debian code path
* distro.py: a distribution without `/etc/os-release` (RHEL 6, CentOS 6, SLES 11) is named and versioned, CentOS reports its two-part version, CentOS Stream is reported as Stream, Oracle Linux as Oracle Linux, and the release name is reported on AlmaLinux, Alpine, Amazon Linux, Kali, Kylin, openEuler, Parrot and TencentOS
* huawei_dorado.py, huawei_pacific.py: sessions are closed on the appliance instead of being left open until they time out. A check used to leave one behind per run, or up to three with caching off, and could fill a session pool that on a Dorado holds 32
* huawei_dorado.py, huawei_pacific.py: an HTTP error, a load balancer answering for the appliance or a failed connection is retried and reported with the appliance's own error text instead of ending the check on the spot
* huawei_dorado.py, huawei_pacific.py: a rejected login says so instead of raising a type error further down, a wrong password is no longer retried towards the lockout threshold, an expired or still-initial monitoring password is named, a missing status field no longer aborts the check, and checks running under different accounts no longer share one session
* huawei_dorado.py: V700 controller boards, enclosures, interface modules, models and states are named instead of shown as "Unknown", including RDMA/NoF interface modes, 100 Gbit/s RoCE link speeds, a faulty HyperMetro pair and a failed rollback
* huawei_pacific.py: a cluster node without a management IP address, and a cluster with more nodes than one response returns, are flagged instead of being skipped while the check still reported OK
* huawei_pacific.py: events and minor alarms are listed with a readable status instead of "Unknown"
* nextcloud.py: a missing or unreadable `config/config.php` is reported with its path, an `occ` that cannot be started at all is reported as an error, and Nextcloud's own startup warnings are kept out of the evaluated result
* time.py: an ISO 8601 timestamp with nanosecond precision, the form every Go-based tool writes, is parsed on RHEL 8 and RHEL 9 instead of being rejected
* wordpress.py: a plugin header is found the way WordPress finds it, including a header behind the opening PHP tag, a multi-file plugin and carriage-return line breaks. A site URL pinned with `const` is read and one sitting in a comment is ignored, as PHP ignores it

### Security

* Lockfiles pin the build-time packages as well, so vendoring them with `pip install --require-hashes` no longer depends on what a build host happens to have installed ([#156](https://github.com/Linuxfabrik/lib/issues/156))
* Python 3.9 lockfile bumps the cryptography library past a padding oracle in its PKCS#7 decryption, for downstreams that vendor the pinned dependencies on RHEL 8 / Debian 11
* db_sqlite.py: table, index and column names are quoted when a statement is built, so a name carrying SQL syntax cannot alter the statement
* shell.py: a command that could not be started at all is reported with its arguments redacted
* ssh.py: an SSH password is handed to `sshpass` through the environment instead of its command line, so it is no longer readable in the host's process list
* txt.py: HTTP basic credentials, a credential carried inside a URL, a Python mapping and a stringified argument list are redacted too
* url.py: a failed request no longer echoes the request body, so login credentials cannot reach the plugin output


## [v6.1.0] - 2026-08-04

**Highlights:** Two security fixes: a malicious or compromised Keycloak can no longer collect the admin credentials, and the shared `--test` mechanism can no longer be used to read arbitrary files as root on hosts where plugins run via a sudoers allowlist. A cache-aware Redfish layer lets the several Redfish checks on a host share one session and the fetched data instead of each hitting the controller. New libraries for sending mail, reading OpenMetrics endpoints and rendering Icinga notification mails.

### Added

* args.py: shared help texts for `--no-insecure` and `--no-perfdata`, `epilog()` builds the pointer to a script's online documentation, and `HelpFormatter` wraps `--help` output without breaking long words such as URLs
* base.py: `oao()` takes a `no_perfdata` to suppress the performance data section
* db_mysql.py: `get_replica_hosts()` lists the replicas registered with a server, `get_version()` returns flavor and version as a comparable tuple, and `get_server_info()` also returns that tuple as `version_tuple`
* disk.py: `get_fingerprint()` hashes a file's head, tail or whole content, so a file is recognized by what it holds rather than by metadata
* disk.py: `get_inode_usage()`, `glob()`, `stat()`, `is_within()` for confining filesystem access, and a `binary` parameter on `read_file()`
* icinga.py: `build_icingaweb2_url()`, `get_logo()` and `render_notification_mail()` build an Icinga Web 2 detail URL and the plain-text and HTML body of a notification mail, escaping the untrusted parts
* mail.py: new library for sending plain-text and HTML email via SMTP, with optional login and inline related images
* openmetrics.py: new library reading the OpenMetrics and Prometheus text formats, so a consumer selects a metric by name and labels instead of parsing the payload
* redfish.py: a cache-aware fetch layer. `fetch_collection()` reads a collection in one request via `$expand` where the controller supports it, `fetch_members()` and `fetch_resource()` cover bare references and single resources, `get_expand_suffix()` and `get_auth_header()` negotiate the deepest `$expand` and a session token. With a non-zero `cache_expire` the several Redfish checks on a host share one session and the fetched data
* rocket.py: `send_message()` posts to a complete incoming-webhook URL, complementing `send2webhook()` which builds the URL from a base plus a webhook id

### Changed

* db_mysql.py: both version parsers share one flavor rule, so a lowercase `-mariadb` tag is no longer read as MySQL
* disk.py: `shorten_path()` takes a `max_len`, leaving short paths untouched and middle-truncating an over-long result
* version.py: importing the module no longer drags in the cache, SQLite and HTTP machinery; only `check_eol()` loads those, on call

### Fixed

* db_sqlite.py: `get_db_path()` rejects a database filename that is not a plain basename, so a caller cannot traverse out of the secured per-user directory
* keycloak.py: the admin token is requested from the monitored Keycloak itself instead of from the URL its discovery document announces, so a compromised host can no longer collect the admin credentials ([GHSA-88fj-95f7-w68m](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-88fj-95f7-w68m))
* lftest.py: the shared `--test` mechanism could be used to read arbitrary files as root where plugins run via a sudoers allowlist; fixture reads are confined to the calling plugin's own `unit-test/` directory ([GHSA-rh9c-rqvg-f7pr](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-rh9c-rqvg-f7pr))


## [v6.0.0] - 2026-07-07

**Highlights:** `huawei.py` is renamed to `huawei_dorado.py`, so consumers have to change their import. A redirect can no longer make `fetch()` forward credential headers to another host. Dorado checks recover on their own when the cached API session is no longer accepted, and command output containing non-UTF-8 bytes no longer crashes a plugin when it prints its result.

### Breaking Changes

* huawei.py: renamed to `huawei_dorado.py`, freeing the generic name now that a second Huawei storage line is supported. Change the import from `lib.huawei` to `lib.huawei_dorado`

### Added

* args.py: shared help texts for `--no-match-severity` and `--unreachable-severity`
* bexio.py: new library
* huawei_pacific.py: new library for Huawei OceanStor Pacific, which speaks the `/api/v2/` REST API with `X-Auth-Token` authentication, a different protocol from the Dorado line
* redfish.py: `build_url()` builds a follow-up URL from a base and an `@odata.id` link, rejecting a non-relative link so a response cannot redirect the request to another host ([GHSA-96fx-pqc3-28xv](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-96fx-pqc3-28xv))
* shell.py: `shell_exec()` takes a `run_as` to run a command as another local user with that user's `XDG_RUNTIME_DIR`, as rootless Podman requires
* url.py: `fetch()` / `fetch_json()` take a `response_on_error` to return the response body instead of an error message, for APIs with machine-readable error responses
* version.py: `check_eol()` takes an `unreachable_severity` for when the online end-of-life source is unreachable and the bundled offline data is used. The offline fallback is no longer cached, so the next call retries the online source

### Changed

* args.py: the developer-only `--test` parameter is hidden from `--help`, but still accepted
* redfish.py: a cached session token is kept only as long as the controller's own session timeout, which avoids sporadic "401 Unauthorized" errors on controllers with short timeouts such as Supermicro's 300 seconds ([#246](https://github.com/Linuxfabrik/lib/issues/246))
* time.py: the `timestr2epoch(..., pattern='iso8601')` docstring states that the mode is backed by `datetime.fromisoformat()`, not a full ISO 8601 parser

### Fixed

* bexio.py: requests carrying data send an explicit JSON content-type header, as the API now requires
* huawei_dorado.py: a check recovers on its own when the cached API session is no longer accepted, and no longer retries a doomed request long enough to risk the monitoring server's check timeout
* huawei_dorado.py: the running-status translation was completed against the full documented status list, so spun-down disks, link states and replication states are readable and a charging backup battery no longer raises a false warning
* powershell.py, shell.py, winrm.py: command output containing non-UTF-8 bytes is read as Latin-1 instead of producing text that fails to print later ([#256](https://github.com/Linuxfabrik/lib/issues/256))
* url.py: a response without a declared charset is read as Latin-1 instead of aborting the check with a decode error

### Security

* url.py: `fetch()` no longer forwards credential headers to another host when a server redirects there (SSRF / token leak) ([GHSA-4jc5-g844-4x33](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-4jc5-g844-4x33))


## [v5.1.0] - 2026-06-24

### Added

* endoflifedate.py: bundled offline End-of-Life data for Apache Tomcat
* txt.py: `compile_regex()` takes a `flags` argument, so a caller compiles a case-insensitive pattern without a separate helper

### Fixed

* db_sqlite.py: a cached database self-heals after a schema change between releases, instead of failing on every run until the stale file is removed by hand
* lftest.py, time.py: both import again on Python older than 3.10 and 3.9 respectively, so every plugin importing them stays runnable on RHEL 8's system Python

### Security

* Python 3.9 lockfile bumps the cryptography library to a release shipping a patched OpenSSL, for downstreams that vendor the pinned dependencies on RHEL 8 / Debian 11


## [v5.0.0] - 2026-06-12

### Breaking Changes

* shell.py: `shell_exec()` requires the command as an argument list and always runs with `shell=False`. It no longer accepts a command string, a `shell=` parameter or `|` pipelines: pass `['df', '-h', path]` instead of `'df -h ' + path`
* ssh.py: `build_options()` and `target()` return argument lists instead of pre-quoted strings, `run()`, `scp()` and `rsync()` build argument lists and drop the `use_shell` parameter

### Added

* shell.py: `safe_cli_value()` rejects a value a called program could misread as an option (leading `-`), guarding a positional or target argument such as an ssh destination against option injection

### Changed

* distro.py, version.py: the OS name and version are read directly from `/etc/os-release` instead of being sourced through a shell

### Removed

* shell.py: `get_command_output()` is gone, it had no consumers. Use `shell_exec()` directly

### Fixed

* base.py: `oao()` normalizes CRLF and stray CR to LF, so Windows command output is no longer rendered with doubled line breaks in web UIs
* endoflifedate.py: the Apache httpd and Rocket.Chat offline data is keyed under their current endoflife.date URLs, so version checks still work when the API is unreachable
* lftest.py, url.py: both parse under RHEL 8's default Python 3.6 again
* shell.py: on Windows, piped output is decoded with the console code page instead of UTF-8, so umlauts in usernames are no longer mangled ([monitoring-plugins#681](https://github.com/Linuxfabrik/monitoring-plugins/issues/681))


## [v4.4.0] - 2026-06-09

### Added

* disk.py: `shorten_path()` abbreviates a path for display by reducing every parent component to its first character, keeping the basename in full
* redfish.py: `get_auth_header()` builds the request authentication header, reusing a cached session token instead of creating a controller session per request, and falling back to HTTP Basic
* redfish.py: parsers for managers, processors, memory modules, Ethernet interfaces, storage volumes, power control entries and the firmware inventory, applying the vendor quirks of Dell, HPE and Fujitsu

### Changed

* net.py: `get_netinfo()` and `get_subnet_hosts()` read interface addresses via psutil instead of the deprecated `netifaces`, and the default gateway from the routing table. This drops the `netifaces` dependency, so the library installs from pure wheels on Python 3.10+ without a build toolchain
* redfish.py: `get_chassis_thermal_fans()` normalizes fan speed reported in RPM or percent onto a single shape, `get_manager_logservices_sel_entries()` filters by regular expression and age, and `get_systems_storage_drives()` also reports `PowerOnHours` and the drive temperature
* time.py: `timestr2epoch()` takes `pattern='iso8601'` to parse an ISO 8601 timestamp without spelling out the layout
* url.py: `fetch_json()` takes a `retries` argument for flaky endpoints


## [v4.3.0] - 2026-06-06

### Added

* disk.py: `copy_dir()`, `copy_file()`, `make_temp_dir()`, `mkdir()` and `rm_dir()` round out the filesystem helpers, each reporting success or an error message
* disk.py: `get_block_devices()` lists all local block devices, including ones without a mounted filesystem, such as raw or unmounted multipath SAN volumes
* lftest.py: `network()` plus `network` / `network_alias` arguments on `run_container()` wire an application container to a backing service for multi-container integration tests
* net.py: `cidr_to_hosts()` and `get_subnet_hosts()` return the usable host addresses of a network in CIDR notation or of an interface's subnet, with a configurable size limit
* shell.py: `which()` locates an executable in PATH
* ssh.py: new module to run commands (`run()`) and copy files (`scp()`, `rsync()`) over SSH, assembling the command lines from individual options
* url.py: `fetch()` / `fetch_json()` take a `method` argument to force the HTTP method, enabling a bodyless POST

### Fixed

* huawei.py: the session cookie is read regardless of how the storage system cases the response header
* redfish.py: a sensor reporting an empty min/max range, which some firmware uses as a "no limit" placeholder, no longer raises a false warning ([#1211](https://github.com/Linuxfabrik/monitoring-plugins/issues/1211))
* url.py: a caller-supplied `Content-Length` is ignored and recomputed from the request body, and response header names are exposed in lower case
* veeam.py: authentication against the Veeam Enterprise Manager API no longer fails with a `415 Unsupported Media Type` or a false "unauthorized"
* Installing the library from source no longer hangs, which also unblocks the API documentation build
* The remaining ruff lint violations are resolved, including a bare `except` in disk.py and shared mutable default arguments in url.py and rocket.py ([#118](https://github.com/Linuxfabrik/lib/issues/118))


## [v4.2.0] - 2026-06-02

### Added

* db_sqlite.py: `get_db_path()` resolves the absolute path of a database without opening it, so a caller that seeds, migrates or removes a database file has a single source of truth

### Security

* db_sqlite.py: SQLite databases are created in a private, per-user `0700` directory under the system temporary directory instead of directly in the shared `/tmp`. This closes a local symlink attack on the predictable database paths ([GHSA-r35r-fpx2-jgr4](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-r35r-fpx2-jgr4), thanks to [OoYo0uto](https://github.com/OoYo0uto))


## [v4.1.0] - 2026-05-29

### Added

* db_mysql.py: `get_server_info()` and `get_flavor()` report the installed MySQL/MariaDB server's flavor and version without a database connection, by parsing the `--version` banner of `mysqld`, `mariadbd`, `mariadb` or `mysql`. Useful where systemd-based detection is unreliable, as on Fedora, which aliases `mysql.service` to `mariadb.service`

### Fixed

* db_sqlite.py: a consumer caching trend data no longer fails with "attempt to write a readonly database" when first run as one user and later scheduled under another. Each user gets its own cache file ([#181](https://github.com/Linuxfabrik/lib/issues/181))

### Security

* Bump `idna` to 3.16 in the Python 3.9 lockfile, closing a moderate vulnerability where crafted input to `idna.encode()` could bypass the CVE-2024-3651 fix


## [v4.0.2] - 2026-05-18

### Fixed

* url.py: `import lib.url` no longer aborts on Python below 3.7, such as RHEL 8's default `python3`. A caller passing `tls_min` / `tls_max` gets a clear `RuntimeError` naming the missing requirement. The supported minimum stays Python 3.9


## [v4.0.1] - 2026-05-18

### Fixed

* db_mysql.py: `connect()` aligns the session's character set and collation with the `mysql` system schema, so queries against `mysql.user` and `mysql.global_priv` no longer abort with ER 1267 ("Illegal mix of collations") on MariaDB 10.4+. Fixes all `mysql-*` plugins ([monitoring-plugins#1139](https://github.com/Linuxfabrik/monitoring-plugins/issues/1139))


## [v4.0.0] - 2026-05-15

### Breaking Changes

* base.py: the module-level constant `X86_64` is renamed to `IS_64BIT`. The underlying check is True on any 64-bit Python build, not only Intel/AMD. Logic unchanged, consumers must update their imports
* lftest.py: `run_mariadb()` / `run_mariadb_from_containerfile()` are renamed to `run_mysql_compatible()` / `run_mysql_compatible_from_containerfile()`, since both upstream MySQL and MariaDB images are supported. The old names stay as aliases for one release, and `MARIADB_LTS_IMAGES` is gone

### Added

* db_mysql.py: `check_privileges(conn, *required)` replaces `check_select_privileges()`. Without arguments it keeps the functional smoke test, with arguments it parses `SHOW GRANTS FOR CURRENT_USER()` and names every missing privilege. Each argument is a privilege or an any-of group, for cross-version aliases such as `REPLICATION CLIENT` / `SLAVE MONITOR` / `REPLICA MONITOR`
* db_mysql.py: `get_all_status()`, `get_all_variables()`, `get_replica_status()` and `has_is_role_column()` consolidate patterns several consumers implement by hand
* db_sqlite.py: `per_second_deltas()` persists cumulative counters in a local cache and returns their per-second rates against the previous run, so a consumer emits rates as perfdata instead of `uom='c'` counters and a Grafana panel needs no `non_negative_difference()` workaround
* lftest.py: `run_mysql_compatible_from_containerfile()` builds a per-consumer Containerfile, so each consumer owns its supported MariaDB / MySQL LTS coverage instead of relying on a hardcoded image list in the lib
* net.py: `fetch()` and `fetch_socket()` take a `dialog` for multi-step request/response conversations, which covers NUT, SMTP, POP3, IMAP and FTP without per-consumer socket handling. `fetch(tls=True)` replaces the now deprecated `fetch_ssl()`
* time.py: `now(as_type='utc')` returns the current UTC time as a naive `datetime`, for fields defined as UTC by spec such as x509 `notBefore` / `notAfter`
* url.py: `fetch()` and `fetch_json()` speak HTTP/1.0, 1.1 and 2 via `httpx`, with `http_version`, `tls_min` and `tls_max` for protocol pinning. `extended=True` also returns the negotiated TLS version, the ALPN protocol, the server certificate in DER form and a per-phase `timings` dict, ready for certificate inspection and HTTPS-availability monitoring

### Changed

* pyproject.toml: `pypsrp` and `pywinrm` are declared as direct dependencies, so they no longer have to be pinned in every downstream project consuming `lib.winrm`
* requirements: one hash-pinned lockfile per supported Python LTS under `lockfiles/pyXX/`, replacing the single `requirements.txt`. Dependabot watches each separately, except `lockfiles/py39/`, which is regenerated by hand because automated bumps would break `pip install --require-hashes` on RHEL 8 / Debian 11
* url.py: `fetch()` switched its engine from stdlib `urllib` to `httpx`. Behaviour for existing callers is preserved, except that `response_header` in the extended dict is now a plain dict

### Deprecated

* db_mysql.py: `check_select_privileges()` is a backwards-compatible shim delegating to `check_privileges(conn)`, and will be removed in a future major release

### Fixed

* base.py: `oao()` HTML-escapes `&`, `<` and `>` into entities instead of replacing `<` and `>` with apostrophes, which used to turn `<= 10` into `'= 10` and destroy shell snippets in consumer output
* db_sqlite.py: `per_second_deltas()` no longer crashes on a cache table schema mismatch from an earlier consumer version
* url.py: `fetch()` with digest authentication actually honours `insecure=True`, and with `no_proxy=True` actually applies the `timeout`
* url.py: `import lib.url` no longer fails where `httpx` is not installed; `fetch()` returns a clear error message instead. A consumer pulling `lib.url` only transitively keeps working


## [v3.4.1] - 2026-05-07

### Fixed

* librenms.py: `get_state()` also maps the LibreNMS alert states `WORSE`, `BETTER` and `CHANGED` to WARN/CRIT. Only `ACTIVE` was treated as alerting, so open alerts in any of those three states were silently reported as OK

### Security

* **ci**: the `GITHUB_TOKEN` permissions in the dependabot-auto-merge workflow are scoped to the job level, with top-level `read-all`, addressing the OpenSSF Scorecard `Token-Permissions` finding


## [v3.4.0] - 2026-04-22

### Added

* time.py: `macro2timestr(s, format='')` expands time macros in a string - `{today}`, `{yesterday}` and single strftime components such as `{%Y}` or `{%m}`. An unknown `{...}` token passes through unchanged


## [v3.3.0] - 2026-04-19

### Added

* args.py: a generic `--check-security` help text, so version-style consumers describe an upstream security-update check the same way


## [v3.2.0] - 2026-04-14

### Added

* url.py: `split_basic_auth(url)` splits the userinfo out of a URL like `https://user:secret@host/path` and returns the stripped URL plus the matching `Authorization` header. This lets an app accept HTTP basic auth via the URL itself, which keeps the credentials out of `ps` listings, out of the request line and out of any proxy access log


## [v3.1.1] - 2026-04-14

### Changed

* human.py: `human2seconds()` and `humanduration2seconds()` also accept the Unix-style lowercase day and week markers `d` and `w`, so a duration string from a third-party tool needs no normalizing first. The canonical uppercase `D` / `W` keep working
* nextcloud.py: `run_occ()` no longer relies on `occ` being executable. It locates `php` and invokes `sudo -u \#<uid> php <occ> <cmd>`, and returns a descriptive error if no `php` is in `PATH`

### Security

* CI supply chain: the `pre-commit` install in the pre-commit-autoupdate workflow is hash-pinned and `dependabot/fetch-metadata` is pinned to a commit SHA, so every GitHub Action in `.github/workflows/` is pinned by hash. The policy is documented in CONTRIBUTING.md under "CI Supply Chain"


## [v3.1.0] - 2026-04-13

### Added

* disk.py: `dir_exists()` as the directory-only counterpart to `file_exists()`, which wraps `os.path.isfile()` and therefore returns `False` for a directory
* lftest.py: `attach_tests()` attaches one `test_*` method per entry of a consumer's `TESTS` list, so discovery and reporting show the actual number of fixtures instead of a single aggregate test. `attach_each()` does the same for an arbitrary list
* lftest.py: `run_mariadb()` context manager and `MARIADB_LTS_IMAGES` constant for container-based MariaDB integration tests


## [v3.0.0] - 2026-04-13

### Removed

* Support for Python older than 3.9 is dropped. This matches the oldest still-supported enterprise Linux (RHEL 8) and lets the codebase use modern syntax and standard-library features

### Added

* args.py: `HELP_TEXTS` covers all common parameters (always-ok, critical, warning, insecure, no-proxy, timeout, url, ignore-regex, match, lengthy, count, test and more)
* disk.py: `get_owner()`
* lftest.py: `run()` for declarative, data-driven unit tests using `subTest()`
* nextcloud.py: new library
* txt.py: `exception2text()`
* winrm.py: `run_ps()` takes a `WINRM_CONFIGURATION_NAME` option and runs PowerShell directly instead of wrapping it in Invoke-Expression
* CI: ruff, bandit and vulture run as pre-commit hooks, and the API documentation is built and deployed to GitHub Pages automatically ([#117](https://github.com/Linuxfabrik/lib/issues/117))

### Changed

* base.py: `get_worst()` accepts any number of states, so combining three or more no longer needs a nested call
* base.py: `get_perfdata()` sanitizes labels by stripping single quotes and replacing `=` with `_`, and drops the trailing semicolons
* base.py: `get_table()` is faster on large tables
* lftest.py: `test()` accepts `args` with fewer than three elements, so a consumer can be invoked as `--test=path/to/fixture` without the trailing `,,0`
* powershell.py: `run_ps()` always returns a dict
* winrm.py: `run_cmd()` and `run_ps()` are JEA-aware and Kerberos-aware
* txt.py: `filter_mltext()` is faster, and the Python 2 codepaths in `to_text()` / `to_bytes()` are gone
* Pre-built documentation is removed from the repository, it is now deployed via GitHub Actions

### Fixed

* base.py: `oao()` and `cu()` escape HTML characters in the output message and in the error message, not just in the traceback, to prevent injection in web UIs
* base.py: `get_state()` returns UNKNOWN on a malformed range spec instead of calling `sys.exit()`
* base.py: `get_table()` uses the right separator for the second data row when called without a header
* cache.py: a cache entry is valid up to and including its `expire` timestamp instead of expiring one second early, matching HTTP `Cache-Control: max-age` and Redis `EXPIRE` semantics ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* grassfish.py: the unused `match()` helper referencing undefined names is removed
* human.py: `bits2human()`, `bytes2human()` and `bps2human()` scale a negative value to a unit matching its magnitude, so `bytes2human(-1048576)` returns `-1.0MiB` instead of `-1048576.0B`. This matters for counter deltas that can legitimately be negative ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* net.py: `get_netinfo()` no longer calls a non-existent `get_ip_public()` and swallows the resulting `NameError` by returning `[]`. It leaves `public_address` as `None`; a caller that needs it uses `get_public_ip()`
* shell.py: `shell_exec()` applies the timeout to the `shell=True` path, and closes the upstream process's `stdout` after connecting it to the next pipeline stage, which used to leak a file descriptor per stage ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* txt.py: `sanitize_sensitive_data()` redacts the secret value instead of the key name, and also covers JSON-style fields and HTTP Authorization headers
* txt.py: `exception2text()` imports `traceback`, so its fallback path is no longer dead code, and `pluralize()` strips whitespace from comma-separated suffix parts
* url.py: `fetch()` and `fetch_json()` no longer use mutable default arguments for `header` and `data`
* winrm.py: `run_cmd()` passes its parameters correctly when using pypsrp

### Security

* The remaining bandit low/medium findings are annotated with `# nosec BXXX` and a short justification, so bandit runs clean at `--severity-level=low --confidence-level=low` over the whole lib


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


[Unreleased]: https://github.com/Linuxfabrik/lib/compare/v7.1.1...HEAD
[v7.1.1]: https://github.com/Linuxfabrik/lib/compare/v7.1.0...v7.1.1
[v7.1.0]: https://github.com/Linuxfabrik/lib/compare/v7.0.0...v7.1.0
[v7.0.0]: https://github.com/Linuxfabrik/lib/compare/v6.1.0...v7.0.0
[v6.1.0]: https://github.com/Linuxfabrik/lib/compare/v6.0.0...v6.1.0
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
