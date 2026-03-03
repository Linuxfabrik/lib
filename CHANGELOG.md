# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

* disk.py: add `get_owner()`
* nextcloud.py: new library
* txt.py: add `exception2text()`
* winrm.py: add `WINRM_CONFIGURATION_NAME` option to `run_ps()`
* winrm.py: execute ps in `run_ps()` directly without Invoke-Expression wrapping

### Changed

* base.py: deduplicate `get_state()` operator logic using `operator` module
* base.py: deduplicate `sum_dict()` by delegating to `sum_lod()`
* base.py: improve `get_table()` performance for large tables
* base.py: move `parse_range()` and state name mapping to module level
* base.py: remove unused `collections` import
* base.py: strip trailing semicolons in `get_perfdata()` output
* db_sqlite.py: reduce unnecessary dictionary object creation
* human.py: pre-compute mappings as module constants
* powershell.py: `run_ps()` now always returns a dict
* winrm.py: make `run_cmd()` and `run_ps()` JEA-aware
* winrm.py: make `run_cmd()` and `run_ps()` Kerberos-aware

### Fixed

* base.py: fix `get_table()` using wrong separator for the second data row when called without a header
* powershell.py: fix outdated shebang line
* txt.py: fix `sanitize_sensitive_data()` replacing the key name instead of the secret value
* winrm.py: pass parameters correctly in `run_cmd()` when using pypsrp


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

* Switch from [calendar versioning](https://calver.org/) to [semantic versioning](https://semver.org/) due to [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) and Windows MSI requirements.
* Rename test.py to lftest.py due to `nuitka` compilation error on Windows.

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
* qts.py: new library for the QNAP QTS API
* tools/update-endoflifedate: tool to update endoflifedate.py
* [Published on PyPI](https://pypi.org/project/linuxfabrik-lib/), installable via `pip install linuxfabrik-lib`

### Changed

* base.py: `cu()` appends an optional message, making it a true error message function
* base.py: `oao()` prints/suffixes ' (always ok)' if `always_ok=True`
* shell.py: `shell_exec()` merges OS environment variables with those set by the `env` parameter
* version.py: `check_eol()` also fetches and caches info from https://endoflife.date/api


## [2023051201] - 2023-05-12

### Breaking Changes

* Remove all Python 2 based plugins and libraries, and remove the "3" suffix from all Python 3 based libraries ([#589](https://github.com/Linuxfabrik/monitoring-plugins/issues/589))
* db_mysql.py: change from username/password to option file authentication in `connect()`

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

* base3: move `x2human` and `human2x` functions to new human.py library ([#49](https://github.com/Linuxfabrik/lib/issues/49))
* base3: move date/time functions to new time3.py library ([#55](https://github.com/Linuxfabrik/lib/issues/55))
* base3: move `filter_str()` to db_sqlite3.py ([#52](https://github.com/Linuxfabrik/lib/issues/52))
* base3: move `get_owner()` to nextcloud-version3 ([#53](https://github.com/Linuxfabrik/lib/issues/53))
* base3: move `sha1sum()` to db_sqlite3.py ([#50](https://github.com/Linuxfabrik/lib/issues/50))
* base3: move shell functions to new shell3.py library ([#56](https://github.com/Linuxfabrik/lib/issues/56))
* base3: move text functions to new txt3.py library ([#51](https://github.com/Linuxfabrik/lib/issues/51))
* txt3: handle all encoding and decoding ([#59](https://github.com/Linuxfabrik/lib/issues/59))
* url3.py: extend `fetch_json()` to make `fetch_json_ext()` obsolete
* veeam: use new `fetch_json()` instead of `fetch_json_ext()` ([#42](https://github.com/Linuxfabrik/lib/issues/42))
* Standardize try-except import statements ([#60](https://github.com/Linuxfabrik/lib/issues/60))
* Lint all libraries ([#57](https://github.com/Linuxfabrik/lib/issues/57))

### Removed

* base3: remove `yesterday()` function ([#54](https://github.com/Linuxfabrik/lib/issues/54))

### Fixed

* base: fix tuple item assignment error ([#43](https://github.com/Linuxfabrik/lib/issues/43))
* base: fix `hashlib.md5()` on FIPS-compliant systems ([#30](https://github.com/Linuxfabrik/lib/issues/30))
* librenms-alerts2: `--lengthy` causes error ([#61](https://github.com/Linuxfabrik/lib/issues/61))
* nginx-status: `TypeError`: a bytes-like object is required, not 'str' ([#47](https://github.com/Linuxfabrik/lib/issues/47))
* url3.py: `AttributeError`: 'str' object has no attribute 'to_bytes' ([#62](https://github.com/Linuxfabrik/lib/issues/62))
* url3: `TypeError`: a bytes-like object is required, not str ([#44](https://github.com/Linuxfabrik/lib/issues/44))
* veeam.py: `ValueError`: need more than 2 values to unpack ([#45](https://github.com/Linuxfabrik/lib/issues/45))
* veeam3.py, huawei3.py: `getheader()` should be `get()` in Python 3 ([#46](https://github.com/Linuxfabrik/lib/issues/46))
* Various fixes after linting


## [2021101401] - 2021-10-14

### Added

* jitsi.py: new library
* nodebb.py: new library
* test.py: new library for unit testing
* veeam.py: new library
* base: add `utc_offset()` function ([#35](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/35))
* db_sqlite: add REGEXP function ([#36](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/36))

### Changed

* base2: improve Unicode, UTF-8, and ASCII handling
* base: `get_state()` can now evaluate against a range ([#34](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/34))
* base: improve line drawing in `get_table()` ([#7](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/7))
* base: make `version()` more robust ([#28](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/28))
* base: `version2float()` now strips everything except numbers and decimal points ([#26](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/26))
* cache: make filename for cache configurable ([#21](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/21))
* db_sqlite: support `LIKE` statements using a regexp
* get_table(): use ASCII characters only for broadest terminal compatibility ([#33](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/33))
* url: identify as Linuxfabrik Monitoring Plugin ([#24](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/24))
* url: `fetch()` and `fetch_json()` can now also return HTTP status code and response headers ([#32](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/32))

### Fixed

* base2: `AttributeError`: 'exceptions.ValueError' object has no attribute 'encode' ([#37](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/37))
* base2: `UnicodeDecodeError`: 'ascii' codec can't decode byte 0xc2 ([#38](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/38))
* base: `get_table()` does not handle length of UTF-8 correctly ([#8](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/8))
* cache3: `NameError`: name 'base' is not defined ([#29](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/29))
* db_sqlite: 8-bit bytestrings error with text_factory ([#20](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/20))
* disk: problems with `read_csv()` ([#25](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/25))
* librenms3.py: fix error ([#27](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/27))
* net: socket `recv()` timeout ([#23](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/23))
* net: `fetch()` port and timeout must be integers ([#22](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/22))


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


[Unreleased]: https://github.com/Linuxfabrik/lib/compare/v2.4.0...HEAD
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
