# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

**Highlights:** Files a privileged process reads on a caller's behalf are now checked on the handle that was actually opened, so swapping a directory in the path no longer redirects the read. `run_occ()` no longer lets an account without access to a Nextcloud installation choose the code or the account `occ` runs as. Consumers start faster, a typical local check saves 9 to 17 ms of CPU time per run.

### Added

* disk.py: `open_file()` opens a file, optionally confined to allowed roots, `resolve_trusted_path()` resolves a path only if nobody but root and the given owners can change it, and `get_fingerprint()` takes an open file

### Changed

* args.py, base.py, txt.py: import faster, and `sanitize_sensitive_data()` is faster on long output

### Security

* disk.py: `read_file()` and `read_env()` with `allowed_roots` no longer read a file outside the roots when a directory in the path is swapped during the open, and refuse FIFOs and devices
* logsource.py: `read()` takes everything it needs from one checked handle, so neither a log nor a rotated predecessor can be swapped for a file outside the allowed roots
* nextcloud.py: `run_occ()` refuses an installation that anybody but root and the owner of `config/config.php` can change, and a symlinked `config.php`


## [v8.2.0] - 2026-09-22

### Added

* huawei_dorado.py: `get_expboard_model()` and `get_hypermetro_domain_running_status()`

### Changed

* huawei_dorado.py: `get_data()` keeps its session after a request that timed out

### Fixed

* huawei_dorado.py: `get_hypermetro_domain_running_status()`, and the average I/O size of `get_performance()`
* lftest.py: `prepare_container_env()` no longer runs on import, which made the docker-\* consumers talk to the wrong socket


## [v8.1.0] - 2026-09-22

### Added

* url.py: `fetch()` and `fetch_json()` take `retry_if`, `fetch_json()` takes `allow_empty`

### Changed

* feedparser.py, url.py: `fetch_soup()` and `fetch()` repeat only a failure that may clear up

### Fixed

* redfish.py: `get_auth_header()` opens a session when the login answers without a body
* shell.py: `shell_exec()` leaves no zombie behind after a timeout


## [v8.0.0] - 2026-09-21

### Breaking Changes

* Twenty functions without a consumer are gone, in `args.py`, `base.py`, `db_mysql.py`, `disk.py`, `dmidecode.py`, `huawei_dorado.py`, `huawei_pacific.py`, `icinga.py`, `librenms.py`, `rocket.py` and `txt.py`
* net.py: `fetch_ssl()`, `is_valid_hostname()`, `is_valid_absolute_hostname()`, `is_valid_relative_hostname()` and `netmask_to_cidr()` are gone. Use `fetch(tls=True)` and `ip_to_cidr()`

### Added

* args.py: `duration()`, further shared help texts
* base.py: `range2txt()` and `resolve_time_threshold()`
* container.py: new module for the answers every consumer of a container engine gives alike
* db_sqlite.py: `connect(in_memory=True)`, `cut_per_sensor()`, `first_seen()` and `forget_sensors()`
* disk.py: `under_root()` and `is_symlink()`, `read_file()` and `read_env()` take `allowed_roots` and `nofollow`
* endoflifedate.py: offline data for Metabase
* keycloak.py: `get_server_info_section()`
* kvm.py: new module for libvirt hosts
* lftest.py: `container_runtime_available()`, `require_container_runtime()`, `test_http_response()`, and `test_text()` takes `missing_ok`
* logmatch.py: new module for remembering what was found in a log across runs
* logsource.py: new module for reading a file, a systemd unit or a container log incrementally
* lvm.py: new module for LVM hosts
* mail.py: `send()` takes `encryption` and `insecure`
* net.py: `get_proxy()`
* openstack.py: new module for OpenStack clouds
* psi.py: new module for the pressure stall information below `/proc/pressure`
* psutil.py: `get_process_accounts()`
* redfish.py: `start_trace()`, `record_responses()`, `format_responses()` and `replay()`
* shell.py: `quote_cli_value()`
* task.py: new module for work that cannot be interrupted from inside the process
* txt.py: `shorten_list()`
* url.py: `server_product()`, `fetch()` and `fetch_json()` take `cacert` and `max_bytes`, `fetch()` takes `retries`
* user.py: new module for what a host says about a local account
* version.py: `cycle_bounds()`

### Changed

* all HTTP-speaking modules: `fetch()` and its callers take a `proxy` next to `no_proxy`
* db_sqlite.py: `compute_load()` leaves out a sensor whose counter started over
* lftest.py: the container helpers skip a test instead of failing it
* mail.py: `send()` returns the answer of the server as text
* psutil.py: `get_partitions()` also returns the mount options and takes `include_all`
* redfish.py: `get_expand_suffix()` asks for a single `$expand` level, `get_auth_header()` renews the lifetime of a cached token ([#350](https://github.com/Linuxfabrik/lib/issues/350))
* url.py: `fetch()` needs httpx 0.26 or newer, and refuses a response body larger than 64 MiB

### Fixed

* base.py: `get_state()`, `match_range()`, and output on Windows, now UTF-8 without extra empty lines
* db_sqlite.py: `per_second_deltas()`, `regexp()`
* human.py: `human2bytes()`, `humanrange2bytes()`, `humanrange2seconds()`, `number2human()`, `seconds2human()`
* net.py: `get_public_ip()`, `get_proxy()`, `fetch_socket()`
* redfish.py: `get_auth_header()` keeps a session token for as long as the controller keeps the session
* shell.py: `shell_exec()` keeps to its `timeout` even when the killed command cannot die ([monitoring-plugins#681](https://github.com/Linuxfabrik/monitoring-plugins/issues/681))
* time.py: `timestr2datetime()` and `timestr2epoch()` read an offset written without a colon, and ISO 8601 on RHEL 8
* url.py: `fetch(extended=True)`
* version.py: `check_eol()`
* winrm.py: `run_cmd()`

### Security

* shell.py: `shell_exec()` names only the program when a command cannot be started
* url.py: `fetch()` no longer resends a request body to another host on a redirect ([GHSA-pq9x-4pp3-p5r9](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-pq9x-4pp3-p5r9)), and honours a `no_proxy` exception written as a network
* winrm.py: `run_cmd()` and `run_ps()` pass every argument and parameter value as one literal


## [v7.1.0] - 2026-08-14

### Added

* base.py: `cu()` takes a `traceback` to leave the stack trace out of the message

### Fixed

* base.py: `get_table()`


## [v7.0.0] - 2026-08-14

### Breaking Changes

* distro.py: `get_distribution_facts()` reports `distribution_release` as the release name, like the Ansible fact of that name
* huawei_dorado.py: `get_data()` takes URL parameters on the endpoint, `get_logic_type()` is `get_enclosure_logic_type()`, `get_role()` is `get_controller_role()`
* version.py: `get_os_info()` is gone, read the `os_info` key of `distro.get_distribution_facts()`

### Added

* args.py: `load_secret()`, `MATCH_IGNORE_PRECEDENCE`, further shared help texts
* base.py: `verbose()`, and `get_table()` takes `hide_empty`, `max_rows` and `missing`
* cache.py: `get()` takes `allow_stale`, plus `prune()`
* db_sqlite.py: `connect()` takes a `timeout`
* disk.py: `get_package()`, `get_fingerprint()` takes an `algorithm`, `read_file()` a `max_bytes`, `shorten_path()` a `truncate`
* distro.py: `get_distribution_facts()` recognizes a further set of distributions and derivatives
* feedparser.py: `fetch_soup()` and `parse_soup()` hand back the feed's own markup, plus `retries`
* huawei_dorado.py, huawei_pacific.py: `as_code()`, `assert_ok()`, `get_all_data()`, the envelope readers and a full set of status translators
* huawei_dorado.py: `get_performance()`, `get_performance_perfdata()`, `as_temperature()`, `field()`, `get_account_state()`, `sectors2bytes()`
* huawei_pacific.py: `get_data()` takes a `base_path`, plus `get_cluster_nodes()`, `get_node_names_by_ip()`, `get_performance()`, `get_quota_bytes()` and `get_warranty_status()`
* lftest.py: `test_json()` and `test_text()`
* nextcloud.py: `run_occ()` takes a `timeout`
* shell.py: `shell_exec()` takes a `run_as_session`
* txt.py: `shorten()`, `strip_ansi()` and `unescape()`
* url.py: `compare_github_refs()`, `get_latest_tag_from_github()` and `github_token_header()`
* wordpress.py: new module reading a local WordPress installation from the filesystem

### Changed

* args.py: the shared `--unreachable-severity` help text covers any unreachable online source
* base.py: `oao()` only escapes a `<` that would open an HTML tag
* disk.py: `walk_directory()` relativizes its paths
* huawei_dorado.py, huawei_pacific.py: `get_creds()` keeps the token in the library's own cache file, `get_data()` takes a `max_attempts`
* huawei_dorado.py: `get_creds()` takes the device ID as optional, `get_running_status_state()` reports a dead power feed, a stopped component, an overheated disk and a broken replication as CRITICAL
* lftest.py: `run()` treats `assert-retc` as optional
* nextcloud.py: `run_occ()` skips `sudo` where it already runs as the owner of `config.php`
* url.py: the GitHub helpers name a repository without releases, a rejected token and an exhausted rate limit as such

### Fixed

* base.py: `get_perfdata()`
* db_sqlite.py: `compute_load()`, `create_index()`, `cut()`, `import_csv()`, `per_second_deltas()`, `regexp()`, `rm_db()`. A failed statement discards the database only on a schema mismatch or an unreadable file
* distro.py: `get_distribution_facts()` reports the OS family of Alpine, Amazon Linux and SUSE, and names a distribution without `/etc/os-release`
* huawei_dorado.py, huawei_pacific.py: `get_creds()` closes the session on the appliance instead of leaving it to time out, `get_data()` retries a rejected request
* huawei_dorado.py: `get_controller_model()`, `get_enclosure_model()`, `get_interface_model()`, `get_interface_runmode()` and `get_running_status()` know the V700 hardware
* huawei_pacific.py: `get_alarm_severity()`, `get_alarm_status()`, `get_cluster_nodes()`
* nextcloud.py: `run_occ()`
* time.py: `timestr2epoch()` parses an ISO 8601 timestamp with nanosecond precision
* wordpress.py: `get_plugins()`, `get_site_url()`

### Security

* Lockfiles pin the build-time packages as well ([#156](https://github.com/Linuxfabrik/lib/issues/156))
* Python 3.9 lockfile bumps the cryptography library past a padding oracle in its PKCS#7 decryption
* db_sqlite.py: every statement function quotes table, index and column names
* shell.py: `shell_exec()` redacts the arguments of a command that could not be started
* ssh.py: `run()`, `scp()` and `rsync()` hand the SSH password to `sshpass` through the environment
* txt.py: `sanitize_sensitive_data()` also redacts HTTP basic credentials, a credential inside a URL, a mapping and an argument list
* url.py: `fetch()` no longer echoes the request body of a failed request


## [v6.1.0] - 2026-08-04

### Added

* args.py: `epilog()` and `HelpFormatter`, further shared help texts
* base.py: `oao()` takes a `no_perfdata`
* db_mysql.py: `get_replica_hosts()`, `get_version()`, and `get_server_info()` returns a `version_tuple`
* disk.py: `get_fingerprint()`, `get_inode_usage()`, `glob()`, `stat()`, `is_within()`, and `read_file()` takes a `binary`
* icinga.py: `build_icingaweb2_url()`, `get_logo()` and `render_notification_mail()`
* mail.py: new module, `send()` sends plain-text and HTML email via SMTP
* openmetrics.py: new module reading the OpenMetrics and Prometheus text formats
* redfish.py: `fetch_collection()`, `fetch_members()`, `fetch_resource()`, `get_expand_suffix()` and `get_auth_header()`, sharing session and data through the cache
* rocket.py: `send_message()`

### Changed

* db_mysql.py: `get_flavor()` and `get_version()` share one flavor rule
* disk.py: `shorten_path()` takes a `max_len`
* version.py: importing the module no longer drags in the cache, SQLite and HTTP machinery

### Fixed

* db_sqlite.py: `get_db_path()` rejects a database filename that is not a plain basename
* keycloak.py: `obtain_admin_token()` asks the monitored Keycloak itself for the token ([GHSA-88fj-95f7-w68m](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-88fj-95f7-w68m))
* lftest.py: `test()` confines a fixture read to the calling script's own `unit-test/` directory ([GHSA-rh9c-rqvg-f7pr](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-rh9c-rqvg-f7pr))


## [v6.0.0] - 2026-07-07

### Breaking Changes

* huawei.py: renamed to `huawei_dorado.py`, change the import to `lib.huawei_dorado`

### Added

* args.py: further shared help texts
* bexio.py: new module, `call_api()` plus one function per bexio endpoint
* huawei_pacific.py: new module for Huawei OceanStor Pacific
* redfish.py: `build_url()` rejects a link that is not relative ([GHSA-96fx-pqc3-28xv](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-96fx-pqc3-28xv))
* shell.py: `shell_exec()` takes a `run_as`
* url.py: `fetch()` and `fetch_json()` take a `response_on_error`
* version.py: `check_eol()` takes an `unreachable_severity`

### Changed

* args.py: the developer-only `--test` is hidden from `--help`
* redfish.py: `get_auth_header()` keeps a cached token only as long as the controller's own session timeout ([#246](https://github.com/Linuxfabrik/lib/issues/246))

### Fixed

* bexio.py: `call_api()` sends an explicit JSON content-type header
* huawei_dorado.py: `get_data()` recovers from a session the appliance no longer accepts, `get_running_status()` covers the documented status list
* powershell.py, shell.py, winrm.py: `run_ps()`, `shell_exec()` and `run_cmd()` read non-UTF-8 output as Latin-1 ([#256](https://github.com/Linuxfabrik/lib/issues/256))
* url.py: `fetch()` reads a response without a declared charset as Latin-1

### Security

* url.py: `fetch()` no longer forwards credential headers to another host on a redirect ([GHSA-4jc5-g844-4x33](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-4jc5-g844-4x33))


## [v5.1.0] - 2026-06-24

### Added

* endoflifedate.py: bundled offline End-of-Life data for Apache Tomcat
* txt.py: `compile_regex()` takes a `flags`

### Fixed

* db_sqlite.py: `connect()` self-heals a cached database after a schema change between releases
* lftest.py, time.py: both import again on Python older than 3.10 and 3.9 respectively

### Security

* Python 3.9 lockfile bumps the cryptography library to a release shipping a patched OpenSSL


## [v5.0.0] - 2026-06-12

### Breaking Changes

* shell.py: `shell_exec()` requires the command as an argument list and always runs with `shell=False`
* ssh.py: `build_options()` and `target()` return argument lists, `run()`, `scp()` and `rsync()` drop `use_shell`

### Added

* shell.py: `safe_cli_value()` rejects a value a called program could misread as an option

### Changed

* distro.py, version.py: `get_distribution_facts()` and `get_os_info()` read `/etc/os-release` without a shell

### Removed

* shell.py: `get_command_output()` is gone, use `shell_exec()`

### Fixed

* base.py: `oao()` normalizes CRLF and stray CR to LF
* endoflifedate.py: the Apache httpd and Rocket.Chat offline data is keyed under their current endoflife.date URLs
* lftest.py, url.py: both parse under RHEL 8's default Python 3.6 again
* shell.py: `shell_exec()` decodes piped output on Windows with the console code page ([monitoring-plugins#681](https://github.com/Linuxfabrik/monitoring-plugins/issues/681))


## [v4.4.0] - 2026-06-09

### Added

* disk.py: `shorten_path()`
* redfish.py: `get_auth_header()`, `get_chassis_power_powercontrol()`, `get_manager()`, `get_systems_ethernetinterfaces()`, `get_systems_memory()`, `get_systems_processors()`, `get_systems_storage_volumes()` and `get_updateservice_firmwareinventory()`

### Changed

* net.py: `get_netinfo()` and `get_subnet_hosts()` read via psutil, which drops the `netifaces` dependency
* redfish.py: `get_chassis_thermal_fans()` normalizes RPM and percent, `get_manager_logservices_sel_entries()` filters by regex and age, `get_systems_storage_drives()` also reports `PowerOnHours` and the temperature
* time.py: `timestr2epoch()` takes `pattern='iso8601'`
* url.py: `fetch_json()` takes a `retries`


## [v4.3.0] - 2026-06-06

### Added

* disk.py: `copy_dir()`, `copy_file()`, `get_block_devices()`, `make_temp_dir()`, `mkdir()` and `rm_dir()`
* lftest.py: `network()`, plus `network` and `network_alias` on `run_container()`
* net.py: `cidr_to_hosts()` and `get_subnet_hosts()`
* shell.py: `which()`
* ssh.py: new module to run commands (`run()`) and copy files (`scp()`, `rsync()`) over SSH
* url.py: `fetch()` and `fetch_json()` take a `method`

### Fixed

* huawei.py: `get_creds()`
* redfish.py: `get_sensor_state()` no longer warns on a sensor reporting an empty min/max range ([#1211](https://github.com/Linuxfabrik/monitoring-plugins/issues/1211))
* url.py: `fetch()`
* veeam.py: `get_token()`
* Installing the library from source no longer hangs, which also unblocks the API documentation build
* The remaining ruff lint violations are resolved ([#118](https://github.com/Linuxfabrik/lib/issues/118))


## [v4.2.0] - 2026-06-02

### Added

* db_sqlite.py: `get_db_path()`

### Security

* db_sqlite.py: `connect()` creates a database in a private per-user directory instead of directly in `/tmp` ([GHSA-r35r-fpx2-jgr4](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-r35r-fpx2-jgr4), thanks to [OoYo0uto](https://github.com/OoYo0uto))


## [v4.1.0] - 2026-05-29

### Added

* db_mysql.py: `get_server_info()` and `get_flavor()` report flavor and version without a database connection

### Fixed

* db_sqlite.py: `connect()` gives each user its own cache file ([#181](https://github.com/Linuxfabrik/lib/issues/181))

### Security

* Bump `idna` to 3.16 in the Python 3.9 lockfile


## [v4.0.2] - 2026-05-18

### Fixed

* url.py: `import lib.url` no longer aborts on Python below 3.7. The supported minimum stays Python 3.9


## [v4.0.1] - 2026-05-18

### Fixed

* db_mysql.py: `connect()` aligns the session's character set and collation with the `mysql` system schema ([monitoring-plugins#1139](https://github.com/Linuxfabrik/monitoring-plugins/issues/1139))


## [v4.0.0] - 2026-05-15

### Breaking Changes

* base.py: the constant `X86_64` is renamed to `IS_64BIT`
* lftest.py: `run_mariadb()` and `run_mariadb_from_containerfile()` are renamed to `run_mysql_compatible()` and `run_mysql_compatible_from_containerfile()`, `MARIADB_LTS_IMAGES` is gone

### Added

* db_mysql.py: `check_privileges()` replaces `check_select_privileges()` and names every missing privilege, plus `get_all_status()`, `get_all_variables()`, `get_replica_status()` and `has_is_role_column()`
* db_sqlite.py: `per_second_deltas()` turns cumulative counters into per-second rates against the previous run
* lftest.py: `run_mysql_compatible_from_containerfile()`
* net.py: `fetch()` and `fetch_socket()` take a `dialog` for multi-step conversations, `fetch(tls=True)` replaces `fetch_ssl()`
* time.py: `now()` takes `as_type='utc'`
* url.py: `fetch()` and `fetch_json()` speak HTTP/1.0, 1.1 and 2 via httpx, with `http_version`, `tls_min` and `tls_max`; `extended=True` also returns the TLS version, the ALPN protocol, the certificate and `timings`

### Changed

* pyproject.toml: `pypsrp` and `pywinrm` are declared as direct dependencies
* requirements: one hash-pinned lockfile per supported Python under `lockfiles/pyXX/`
* url.py: `fetch()` switched its engine from `urllib` to `httpx`, `response_header` is a plain dict now

### Deprecated

* db_mysql.py: `check_select_privileges()` is a shim for `check_privileges()`

### Fixed

* base.py: `oao()` HTML-escapes `&`, `<` and `>` into entities
* db_sqlite.py: `per_second_deltas()`
* url.py: `fetch()` honours `insecure` with digest authentication and `timeout` with `no_proxy`, and `import lib.url` works without httpx installed


## [v3.4.1] - 2026-05-07

### Fixed

* librenms.py: `get_state()` also maps the alert states `WORSE`, `BETTER` and `CHANGED`

### Security

* ci: the `GITHUB_TOKEN` permissions in the dependabot-auto-merge workflow are scoped to the job


## [v3.4.0] - 2026-04-22

### Added

* time.py: `macro2timestr()` expands `{today}`, `{yesterday}` and single strftime components


## [v3.3.0] - 2026-04-19

### Added

* args.py: a generic `--check-security` help text


## [v3.2.0] - 2026-04-14

### Added

* url.py: `split_basic_auth()` splits the userinfo out of a URL into a stripped URL plus an `Authorization` header


## [v3.1.1] - 2026-04-14

### Changed

* human.py: `human2seconds()` and `humanduration2seconds()` also accept the lowercase `d` and `w`
* nextcloud.py: `run_occ()` locates `php` instead of relying on an executable `occ`

### Security

* CI supply chain: every GitHub Action in `.github/workflows/` is pinned by hash


## [v3.1.0] - 2026-04-13

### Added

* disk.py: `dir_exists()`
* lftest.py: `attach_tests()` and `attach_each()`, plus `run_mariadb()` and `MARIADB_LTS_IMAGES`


## [v3.0.0] - 2026-04-13

### Removed

* Support for Python older than 3.9 is dropped

### Added

* args.py: `HELP_TEXTS` covers all common parameters
* disk.py: `get_owner()`
* lftest.py: `run()` for declarative, data-driven unit tests
* nextcloud.py: new module, `run_occ()` runs a Nextcloud `occ` command
* txt.py: `exception2text()`
* winrm.py: `run_ps()` takes a `WINRM_CONFIGURATION_NAME` and runs PowerShell directly
* CI: ruff, bandit and vulture run as pre-commit hooks, and the API documentation is deployed to GitHub Pages ([#117](https://github.com/Linuxfabrik/lib/issues/117))

### Changed

* base.py: `get_worst()` takes any number of states, `get_perfdata()` sanitizes its labels, `get_table()` is faster on large tables
* lftest.py: `test()` accepts `args` with fewer than three elements
* powershell.py: `run_ps()` always returns a dict
* txt.py: `filter_mltext()` is faster, the Python 2 codepaths of `to_text()` and `to_bytes()` are gone
* winrm.py: `run_cmd()` and `run_ps()` are JEA-aware and Kerberos-aware
* Pre-built documentation is removed from the repository

### Fixed

* base.py: `get_state()`, `get_table()`, and `oao()` / `cu()` escape HTML in every message
* cache.py: `get()` treats an entry as valid up to and including its `expire` ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* grassfish.py: the unused `match()` helper is gone
* human.py: `bits2human()`, `bytes2human()` and `bps2human()` scale a negative value ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* net.py: `get_netinfo()` leaves `public_address` as `None`
* shell.py: `shell_exec()` applies the timeout to the `shell=True` path and no longer leaks a file descriptor per pipeline stage ([#120](https://github.com/Linuxfabrik/lib/issues/120))
* txt.py: `exception2text()`, `pluralize()`, `sanitize_sensitive_data()`
* url.py: `fetch()`, `fetch_json()`
* winrm.py: `run_cmd()`

### Security

* The remaining bandit findings are annotated with `# nosec BXXX` and a short justification



## [v2.4.0] - 2025-09-17

### Added

* args.py: `HELP_TEXTS` gains `--stratum` and `--verbose`
* rocket.py: `get_groups_history()`, `get_rooms_info()` and `send2webhook()`
* time.py: `get_weekday()`

### Changed

* dmidecode.py: `dmidecode_parse()` collapses identical CPU and memory records into one representative entry, counted in `dedup_count`

### Fixed

* base.py: `get_table()` no longer modifies the input `data`
* redfish.py: `get_sensor_state()` applies the caller's thresholds before the state the sensor reports


## [v2.3.0] - 2025-06-20

### Added

* endoflifedate.py: bundled offline End-of-Life data for Icinga

### Changed

* shell.py: `shell_exec()` takes an optional `lc_all='C'`

### Fixed

* distro.py: `get_distribution_facts()` reports the right `os_family` for Devuan ([#87](https://github.com/Linuxfabrik/lib/issues/87))


## [v2.2.1] - 2025-05-30

### Fixed

* net.py: `fetch_ssl()` uses `ssl.PROTOCOL_TLS_CLIENT`


## [v2.2.0] - 2025-05-30

### Added

* time.py: `get_timezone()`
* tools/update-endoflifedate: add Valkey

### Changed

* net.py: `fetch_ssl()` requires TLS 1.2+
* txt.py: `sanitize_sensitive_data()` covers more secret spellings


## [v2.1.1.15] - 2025-05-07

### Changed

* net.py: `fetch_socket()` and `fetch_ssl()` are added, `fetch()` is improved


## [v2.1.1.7] - 2025-04-21

### Changed

* distro.py: `get_os_info()` moves here from version.py
* human.py: `bits2human()` drops the %-syntax from its parameters
* Improve code style across all modules


## [v2.1.1.5] - 2025-04-19

### Added

* txt.py: `sanitize_sensitive_data()`

### Changed

* base.py, url.py: `oao()`, `cu()`, `fetch()` and `fetch_json()` pass their messages through `txt.sanitize_sensitive_data()`
* disk.py: `get_real_disks()` ignores loop devices
* shell.py: `shell_exec()` drops the Windows `chcp` output from the result
* docs: improve and convert docstrings to Markdown, create `docs` folder using `pdoc`

### Fixed

* shell.py: `shell_exec()` decodes Windows output via codepage 65001, so special characters survive


## [v2.1.0.7] - 2025-04-08

### Fixed

* disk.py: `udevadm()` locates the binary instead of using a static path ([#85](https://github.com/Linuxfabrik/lib/issues/85))


## [v2.1.0.4] - 2025-03-29

### Added

* uptimerobot.py: `delete_psp()`, `edit_psp()`, `get_psps()` and `new_psp()` for public status pages


## [v2.1.0.0] - 2025-03-23

### Added

* uptimerobot.py: new module for the UptimeRobot API


## [v2.0.0.7] - 2025-03-10

### Added

* tools/update-endoflifedate: add OpenVPN

### Fixed

* txt.py: `extract_str()` returns the full text between the markers when `to_txt` is longer than one character


## [v2.0.0.0] - 2025-02-15

### Breaking Changes

* Rename test.py to lftest.py, `nuitka` fails to compile the old name on Windows
* Switch from [calendar versioning](https://calver.org/) to [semantic versioning](https://semver.org/), for [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) and Windows MSI requirements

### Added

* keycloak.py: new module for the Keycloak API

### Changed

* db_sqlite.py: `create_index()`, `cut()`, `delete()`, `insert()`, `replace()` and `select()` delete the database file on an `OperationalError` by default. Disable with `delete_db_on_operational_error=False`
* librenms.py: `get_state()` returns `STATE_OK` instead of `STATE_UNKNOWN`
* url.py: `fetch()` and `fetch_json()` report clearer error messages

### Fixed

* disk.py: `udevadm()` no longer raises a `ValueError` when a value contains `=`


## [2024060401] - 2024-06-04

Minor improvements, barely any changes.


## [2024052901] - 2024-05-29

### Breaking Changes

* librenms.py: `get_state()` expects numeric status codes

### Added

* args.py: `help()`
* base.py: `str2bool()`
* disk.py: `get_real_disks()`, `udevadm()`
* human.py: `human2seconds()`
* txt.py: `get_dm_name()`, `match_regex()`

### Changed

* base.py: `oao()` replaces a `|` in the output with `! `, the character being reserved as the performance data separator
* db_sqlite.py: `connect()` raises its timeout to 5 seconds, `close()` returns `False` on failure
* grassfish.py: `fetch_json()` takes `insecure=False, no_proxy=False, timeout=8`
* huawei.py: `get_creds()` and `get_data()` drop their hardcoded `insecure`
* icinga.py: every function drops its hardcoded `insecure` and takes `insecure=False, no_proxy=False, timeout=3`
* infomaniak.py: every function takes `insecure=False, no_proxy=False, timeout=8`
* jitsi.py: `get_data()` drops its hardcoded `insecure` and evaluates `no_proxy`
* librenms.py: `get_data()` handles its parameters better
* net.py: `get_public_ip()` takes `insecure=False, no_proxy=False, timeout=3`
* nodebb.py: `get_data()` evaluates `no_proxy`
* rocket.py: every function takes `insecure=False, no_proxy=False, timeout=3`
* veeam.py: `get_token()` drops its hardcoded `insecure` and evaluates `no_proxy`
* version.py: `check_eol()` takes `insecure=False, no_proxy=False, timeout=8`
* wildfly.py: `get_data()` evaluates `insecure` and `no_proxy`

### Fixed

* base.py: `lookup_lod()` uses the default parameter ([#82](https://github.com/Linuxfabrik/lib/issues/82))
* db_mysql.py: `select()` passes its bind data correctly
* feedparser.py: `parse_atom()` falls back to `lastBuildDate` where a feed publishes no `pubDate`, as Azure's status RSS does ([monitoring-plugins#756](https://github.com/Linuxfabrik/monitoring-plugins/issues/756))


## [2023112901] - 2023-11-29

### Added

* endoflifedate.py: new auto-built module for end-of-life date tracking
* [Published on PyPI](https://pypi.org/project/linuxfabrik-lib/), installable via `pip install linuxfabrik-lib`
* qts.py: new module for the QNAP QTS API
* tools/update-endoflifedate: tool to update endoflifedate.py

### Changed

* base.py: `cu()` appends an optional message, making it a true error message function, and `oao()` suffixes ' (always ok)' if `always_ok=True`
* shell.py: `shell_exec()` merges the OS environment with the variables set via `env`
* version.py: `check_eol()` also fetches and caches https://endoflife.date/api


## [2023051201] - 2023-05-12

### Breaking Changes

* db_mysql.py: `connect()` changes from username/password to option file authentication
* Remove all Python 2 based modules, and remove the "3" suffix from all Python 3 based modules ([monitoring-plugins#589](https://github.com/Linuxfabrik/monitoring-plugins/issues/589))

### Added

* args.py: `number_unit_method` type
* disk.py: `read_env()`
* version.py: new module

### Changed

* base.py: `str2state()` is more robust

### Fixed

* smb.py: `open_file()` calls `SMBDirEntry.from_path()`, the name smbclient actually exposes


## [2023030801] - 2023-03-08

### Breaking Changes

* db_mysql3: `connect()` changes from username/password to option file authentication
* net3: `get_ip_public()` is renamed to `get_public_ip()`, `ip_to_cdir()` to `netmask_to_cdir()`

### Added

* dmidecode3.py: new module
* grassfish3.py: new module

### Changed

* base3.py: `get_worst()` is more robust
* human3.py: `human2bytes()` handles values like "3.0M"
* infomaniak3.py: `get_products()` speaks the current API version
* shell3.py: `shell_exec()` also handles timeouts
* wildfly3.py: `get_data()` assembles the URL in the right order


## [2022072001] - 2022-07-20

### Added

* distro3.py: new module

### Changed

* cache3.py: `get()` and `set()` default to a more unique SQLite database name
* db_mysql3.py: `check_select_privileges()` and `vars2dict()` are added, `connect()` and `select()` are reworked, and the driver switches from `mysql.connector` to `PyMySQL` ([monitoring-plugins#570](https://github.com/Linuxfabrik/monitoring-plugins/issues/570))
* db_sqlite3.py: `connect()` defaults to a more unique SQLite database name
* disk3.py: `file_exists()`
* Revert Python 3.6+ f-strings to `.format()` for broader compatibility


## [2022022801] - 2022-02-28

### Added

* human3.py: new module for converting raw numbers and times to human-readable representations
* shell3.py: new module for shell communication
* time3.py: new module for date/time functions
* txt3.py: new module for text handling, encoding, and decoding
* redfish.py: `get_systems*()` for the Systems collection
* winrm.py: run shell commands ([#41](https://github.com/Linuxfabrik/lib/issues/41))
* powershell.py: PowerShell support ([#40](https://github.com/Linuxfabrik/lib/issues/40))

### Changed

* base3: `filter_str()` and `sha1sum()` move to db_sqlite3.py ([#50](https://github.com/Linuxfabrik/lib/issues/50), [#52](https://github.com/Linuxfabrik/lib/issues/52)), `get_owner()` moves out of the lib ([#53](https://github.com/Linuxfabrik/lib/issues/53)), and the `x2human` / `human2x`, date/time, shell and text functions move to human.py, time3.py, shell3.py and txt3.py ([#49](https://github.com/Linuxfabrik/lib/issues/49), [#51](https://github.com/Linuxfabrik/lib/issues/51), [#55](https://github.com/Linuxfabrik/lib/issues/55), [#56](https://github.com/Linuxfabrik/lib/issues/56))
* Lint all modules ([#57](https://github.com/Linuxfabrik/lib/issues/57))
* Standardize try-except import statements ([#60](https://github.com/Linuxfabrik/lib/issues/60))
* txt3: handles all encoding and decoding ([#59](https://github.com/Linuxfabrik/lib/issues/59))
* url3.py: `fetch_json()` is extended, making `fetch_json_ext()` obsolete
* veeam: `get_token()` uses the new `fetch_json()` instead of `fetch_json_ext()` ([#42](https://github.com/Linuxfabrik/lib/issues/42))

### Removed

* base3: `yesterday()` ([#54](https://github.com/Linuxfabrik/lib/issues/54))

### Fixed

* base: `hashlib.md5()` works on FIPS-compliant systems ([#30](https://github.com/Linuxfabrik/lib/issues/30), [#43](https://github.com/Linuxfabrik/lib/issues/43))
* base2: `get_table()` ([#61](https://github.com/Linuxfabrik/lib/issues/61))
* url3.py: `fetch()` returns text instead of bytes ([#44](https://github.com/Linuxfabrik/lib/issues/44), [#47](https://github.com/Linuxfabrik/lib/issues/47), [#62](https://github.com/Linuxfabrik/lib/issues/62))
* veeam.py, veeam3.py, huawei3.py: `get_token()`, `getheader()` ([#45](https://github.com/Linuxfabrik/lib/issues/45), [#46](https://github.com/Linuxfabrik/lib/issues/46))
* Various fixes after linting


## [2021101401] - 2021-10-14

### Added

* base: `utc_offset()` ([#35](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/35))
* db_sqlite: REGEXP function ([#36](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/36))
* jitsi.py: new module
* nodebb.py: new module
* test.py: new module for unit testing
* veeam.py: new module

### Changed

* base2: improve Unicode, UTF-8, and ASCII handling
* base: `get_state()` can evaluate against a range ([#34](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/34)), `get_table()` draws its lines better and uses ASCII characters only, for the broadest terminal compatibility ([#7](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/7), [#33](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/33)), and `version()` / `version2float()` are more robust ([#26](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/26), [#28](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/28))
* cache: `get()` and `set()` take the cache filename ([#21](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/21))
* db_sqlite: `select()` supports `LIKE` statements using a regexp
* url: `fetch()` and `fetch_json()` can also return the HTTP status code and the response headers ([#32](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/32)), and `fetch()` sends a `User-Agent: Linuxfabrik Monitoring Plugins` header ([#24](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/24))

### Fixed

* base: `get_table()` handles the length of UTF-8 correctly ([#8](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/8))
* base2: Unicode and encoding handling ([#37](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/37), [#38](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/38))
* cache3: module import ([#29](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/29))
* db_sqlite: 8-bit bytestrings error with text_factory ([#20](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/20))
* disk: `read_csv()` ([#25](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/25))
* librenms3.py: `get_data()` ([#27](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/27))
* net: `fetch()` and the socket `recv()` timeout ([#22](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/22), [#23](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/23))


## [2020052801] - 2020-05-28

### Added

* db_mysql.py: new module
* feedparser.py: new module
* icinga.py: new module


## 2020042001 - 2020-04-20

### Changed

* base.py: `shell_exec()`
* net.py: improvements
* url.py: improvements


## [2020041501] - 2020-04-15

### Added

* args.py: new module
* base.py: new module
* cache.py: new module
* db_sqlite.py: new module
* disk.py: new module
* net.py: new module
* rocket.py: new module
* url.py: new module


## [2020022801] - 2020-02-28

Initial release.


[Unreleased]: https://github.com/Linuxfabrik/lib/compare/v8.2.0...HEAD
[v8.2.0]: https://github.com/Linuxfabrik/lib/compare/v8.1.0...v8.2.0
[v8.1.0]: https://github.com/Linuxfabrik/lib/compare/v8.0.0...v8.1.0
[v8.0.0]: https://github.com/Linuxfabrik/lib/compare/v7.1.0...v8.0.0
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
