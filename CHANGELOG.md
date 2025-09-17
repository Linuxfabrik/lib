# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)


## [Unreleased]

tbd


## [v2.4.0] - 2025-09-17


### Added ("feat")

* endoflifedate.py: add Icinga
* rocket.py: add `get_groups_history()`, `get_rooms_info()`, `send2webhook()`
* time.py: add `get_weekday()`


### Fixed ("fix")

* base.py: `get_table()` does not modify `data` any longer
* redfish.py: make lib more robust and check the sensor state against the user's thresholds first


### Changed ("refactor", "chore" etc.)

* args.py: add `--stratum` parameter
* args.py: add `--verbose` parameter
* dmidecode.py: collapse near-duplicate data in an admin-friendly way



## [v2.3.0] - 2025-06-20

### Added ("feat")

* endoflifedate.py: add Icinga


### Fixed ("fix")

* distro.py: incorrect os_family for Devuan in `get_distribution_facts()` ([#87](https://github.com/Linuxfabrik/lib/issues/87))


### Changed ("refactor", "chore" etc.)

* shell.py: new optional parameter `lc_all='C'` for `shell_exec()`



## [v2.2.1] - 2025-05-30

### Fixed ("fix")

* net.py: use `ssl.PROTOCOL_TLS_CLIENT` as "best practice" in `fetch_ssl()`



## [v2.2.0] - 2025-05-30

### Added ("feat")

* time.py: add `get_timezone()`


### Changed ("refactor", "chore" etc.)

* net.py: force `fetch_ssl()` to use TLS 1.2+
* txt.py: enhance sanitize regex



## [v2.1.1.15] - 2025-05-07

### Changed ("refactor", "chore" etc.)

* net.py: add fetch_socket() and fetch_ssl(), improve fetch()



## [v2.1.1.7] - 2025-04-21

### Changed ("refactor", "chore" etc.)

* args.py: improve code-style
* base.py: improve code-style
* cache.py: improve code-style
* db_mysql.py: improve code-style
* db_sqlite.py: improve code-style
* disk.py: improve code-style
* distro.py: improve code-style
* distro.py: move get_os_info() from version.py to distro.py
* dmidecode.py: improve code-style
* feedparser.py: improve code-style
* grassfish.py: improve code-style
* huawei.py: improve code-style
* human.py: change parameters for bits2human() (no weird %-syntax for users to worry about)
* human.py: improve code-style
* icinga.py: improve code-style
* infomaniak.py: improve code-style
* jitsi.py: improve code-style
* keycloak.py: improve code-style
* lftest.py: improve code-style
* librenms.py: improve code-style
* net.py: improve code-style
* nodebb.py: improve code-style
* psutil.py: improve code-style
* qts.py: improve code-style
* redfish.py: improve code-style
* rocket.py: improve code-style
* shell.py: improve code-style
* smb.py: improve code-style
* time.py: improve code-style
* txt.py: improve code-style
* uptimerobot.py: improve code-style
* url.py: improve code-style
* veeam.py: improve code-style
* version.py: improve code-style
* wildfly.py: improve code-style
* winrm.py: improve code-style



## [v2.1.1.5] - 2025-04-19

### Fixed ("fix")

* shell.py: Fix special character decoding in Windows output by explicitly switching to codepage 65001


### Changed ("refactor", "chore" etc.)

* docs: improve and convert doc strings to markdown for some libs and create new `docs` folder using `pdoc`
* base.py, url.py: make use of txt.sanitize_sensitive_data()
* txt.py: add sanitize_sensitive_data()



## [v2.1.0.7] - 2025-04-08

### Fixed ("fix")

* disk.py: Fix static path to udevadm ([#85](https://github.com/Linuxfabrik/lib/issues/85))



## [v2.1.0.4] - 2025-03-29

### Changed ("refactor", "chore" etc.)

* uptimerobot.py



## [v2.1.0.0] - 2025-03-23

### Added ("feat")

* add uptimerobot.py


### Changed ("refactor", "chore" etc.)

* base.py: improve doc strings



## [v2.0.0.7] - 2025-03-10

### Fixed ("fix")

* txt.py: extract_str()


### Changed ("refactor", "chore" etc.)

* endoflifedate.py: bump version numbers
* tools/update-endoflifedate: add openvpn
* time.py: improve doc strings
* docs: update README



## [v2.0.0.0] - 2025-02-15

### Breaking Changes

Build, CI/CD:

* Due to the new [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) and version string requirements in Windows MSI setup files, the project switches from [calendar versioning](https://calver.org/) to [semantic versioning](https://semver.org/).

* Not a breaking change, but a behavior change in db_sqlite.py: The functions

    * create_index()
    * cut()
    * delete()
    * insert()
    * replace()
    * select()

    now **delete** the underlying sqlite db file by default when they encounter an `OperationalError`. For example, you get this error when you run new SQL code that references columns in an older, existing db file that don't exist there. With this change, it is not necessary to manually delete db files after upgrading to new versions of your software that use newer db layouts. This behavior can be disabled with `delete_db_on_operational_error=False`.

* Renamed test.py to lftest.py due to `nuitka.Errors.NuitkaOptimizationError: duplicate locals name` on Windows


### Added ("feat")

* keycloak.py: This library collects some Keycloak related functions that are needed by more than one Keycloak plugin.


### Changed ("refactor", "chore" etc.)

* librenms.py: `get_state()` returns STATE_OK instead of STATE_UNKNOWN
* url.py: Improve error messages and comments


### Fixed

* disk.py: fix ValueError if the value contains =



## [2024060401] - 2024-06-04

Minor improvements, barely any changes.



## [2024052901] - 2024-05-29

### Breaking Changes

* librenms.py: get_state() now expects numeric status codes


### Changed ("enhancement")

* args.py: Add `help()`
* base.py: lookup_lod() never uses the default parameter ([#82](https://github.com/Linuxfabrik/lib/issues/82))
* base.py: oao() replaces `|` character in output with `! `, because it is reserved to separate plugin output from performance data (and there is no way to escape it).
* base.py: Add str2bool()
* db_mysql.py: Fix select() and providing data
* db_sqlite.py: connect(): Increase connect timeout to 5 secs; close(): return false on failure 
* disk.py: Add `get_real_disks()`, `udevadm()`
* grassfish.py: Add `insecure=False, no_proxy=False, timeout=8` to `fetch_json()`
* huawei.py: No more hardcoded `insecure` parameter in `get_creds()` and `get_data()`
* human.py: Add human2seconds()
* icinga.py: No more hardcoded `insecure` parameter; add `insecure=False, no_proxy=False, timeout=3` to all functions
* infomaniak.py: add `insecure=False, no_proxy=False, timeout=8` to all functions
* jitsi.py: No more hardcoded `insecure` and evaluate `no_proxy` in `get_data()`
* librenms.py: Improve get_data() parameter handling
* net.py: Add `insecure=False, no_proxy=False, timeout=3` to `get_public_ip()`
* nodebb.py: Evaluate `no_proxy` in `get_data()`
* rocket.py: add `insecure=False, no_proxy=False, timeout=3` to all functions
* txt.py: Add `get_dm_name(dm_device)`, `match_regex(regex, string, key='')`
* veeam.py: No more hardcoded `insecure` and also evaluate `no_proxy` in `get_token()`
* version.py: Add `insecure=False, no_proxy=False, timeout=8` to `check_eol()`
* wildfly.py: Evaluate `insecure` and `no_proxy` in `get_data()`


### Fixed

* feed.py: Incompatible with Azure status RSS ([#756](https://github.com/Linuxfabrik/monitoring-plugins/issues/756))



## [2023112901] - 2023-11-29

### Added ("feat")

* qts.py: A library for interacting with the QNAP QTS API
* endoflifedate.py (built automatically; version string only changes when products are added or deleted)
* [Published on PyPI](https://pypi.org/project/linuxfabrik-lib/), you may now use `pip install linuxfabrik-lib`
* tools/update-endoflifedate, which - like its name says - can be used to update endoflifedate.py


### Changed

* base.py: cu() appends an optional message, making it a true errormsg function
* base.py: oao() prints/suffixes ' (always ok)' if `always_ok=True`
* shell.py: shell_exec() merges the OS environment variables with the ones set by the env parameter
* version.py: check_eol() also fetches and caches info from https://endoflife.date/api



## [2023051201] - 2023-05-12

### Breaking Changes

* Remove all Python 2 based plugins and libraries from the project, and therefore remove the "3" suffix from all Python3-based plugins and libraries as well ([#589](https://github.com/Linuxfabrik/monitoring-plugins/issues/589))
* db_mysql.py: Change from username/password authentication to option file authentication in `connect()`


### Added ("feat")

* args.py: Add `number_unit_method` type (used in `disk-usage` monitoring plugin)
* disk.py: Add read_env()
* version.py


### Changed

* base.py: Improve str2state()


### Fixed

* smb.py: Type object 'SMBDirEntry' has no attribute 'from_filename'



## [2023030801] - 2023-03-08

### Breaking Changes

* db_mysql3: Change from username/password authentication to option file authentication in connect()
* net3: Rename get_ip_public() to get_public_ip()
* net3: Rename ip_to_cdir() to netmask_to_cdir()


### Added ("feat")

* dmidecode3.py
* grassfish3.py


### Changed

* base3.py: Make get_worst() more robust
* human3.py: human2bytes() is now also able to interpret "3.0M"
* infomaniak3.py: Apply new API version
* shell3.py: shell_exec() also handles timeouts
* wildfly3.py: Update



## [2022072001] - 2022-07-20

### Added ("feat")

* distro3.py


### Changed

* cache3.py: Use more unique default names for sqlite databases
* db_mysql3.py: Enhanced for new mysql-checks
* db_mysql3.py: Switch from mysql.connector to PyMySQL ([#570](https://github.com/Linuxfabrik/monitoring-plugins/issues/570))
* db_mysql3.py: Use more unique default names for sqlite databases
* disk3.py: Add file_exists() function
* Revert Python 3.6+ `f`-strings to use `.format()` to be more conservative



## [2022022801] - 2022-02-28

### Added ("feat")

* human3.py: Collects functions to convert raw numbers, times etc. to a human readable representation.
* shell3.py: Communicates with the Shell.
* time3.py: Provides date/time functions.
* txt3.py: Text-related functions, handles stable encoding and decoding.


### Changed

* Added "get_systems\*()" functions for Systems collection
* base3: Move "x2human" and "human2x" Functions to a new "human.py" Library ([#49](https://github.com/Linuxfabrik/lib/issues/49))
* base3: Move Date/Time-related Functions to a new "time3.py" Library ([#55](https://github.com/Linuxfabrik/lib/issues/55))
* base3: Move filter_str() to db_sqlite3.py ([#52](https://github.com/Linuxfabrik/lib/issues/52))
* base3: Move get_owner() to nextcloud-version3 ([#53](https://github.com/Linuxfabrik/lib/issues/53))
* base3: Move sha1sum() to db_sqlite3.py ([#50](https://github.com/Linuxfabrik/lib/issues/50))
* base3: Move Shell-related Functions to a new "shell3.py" Library ([#56](https://github.com/Linuxfabrik/lib/issues/56))
* base3: Move Text-related Functions to a new "txt3.py" Library ([#51](https://github.com/Linuxfabrik/lib/issues/51))
* base3: Remove function yesterday() - not needed anywhere ([#54](https://github.com/Linuxfabrik/lib/issues/54))
* base: tuple object does not support item assignment ([#43](https://github.com/Linuxfabrik/lib/issues/43))
* bugfixing after pylinting
* extended fetch_json() to make fetch_json_ext() obsolete
* hashlib.md5() on FIPS compliant systems ([#30](https://github.com/Linuxfabrik/lib/issues/30))
* Let the new txt3 library do all encoding and decoding ([#59](https://github.com/Linuxfabrik/lib/issues/59))
* librenms-alerts2: --lengthy causes error ([#61](https://github.com/Linuxfabrik/lib/issues/61))
* nginx-status: TypeError: a bytes-like object is required, not 'str' ([#47](https://github.com/Linuxfabrik/lib/issues/47))
* pylint all Libraries ([#57](https://github.com/Linuxfabrik/lib/issues/57))
* renamed function and added exception handling
* Standardize the try-except import statements if checking for "do I have the lib?" ([#60](https://github.com/Linuxfabrik/lib/issues/60))
* Support PowerShell ([#40](https://github.com/Linuxfabrik/lib/issues/40))
* url3.py: AttributeError: 'str' object has no attribute 'to_bytes' ([#62](https://github.com/Linuxfabrik/lib/issues/62))
* url3: TypeError: a bytes-like object is required, not str ([#44](https://github.com/Linuxfabrik/lib/issues/44))
* veeam.py: ValueError: need more than 2 values to unpack ([x45](https://github.com/Linuxfabrik/lib/issues/45))
* veeam3.py, huawei3.py: In Python 3, getheader() should be get() ([#46](https://github.com/Linuxfabrik/lib/issues/46))
* veeam: Use new fetch_json() instead of fetch_json_ext() ([#42](https://github.com/Linuxfabrik/lib/issues/42))
* winrm: Add function to run shell commands ([#41](https://github.com/Linuxfabrik/lib/issues/41))



## [2021101401] - 2021-10-14

### Added ("feat")

* nodebb
* jitsi
* test (to improve unit testing)
* veeam


### Changed

* base2 (the Python 2 variant): Now handles Unicode, UTF-8 and ASCII better than before.
* db_sqlite: Supports `LIKE` statements using a regexp.


### Fixed

* base2: AttributeError: 'exceptions.ValueError' object has no attribute 'encode' ([#37](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/37))
* base2: UnicodeDecodeError: 'ascii' codec can't decode byte 0xc2 in position 25: ordinal not in range(128) ([#38](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/38))
* base: Add UTC Offset information function utc_offset() ([#35](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/35))
* base: get_state() should be able to get the state against a range ([#34](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/34))
* base: get_table() does not handle length of utf-8 correctly ([#8](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/8))
* base: improve line drawing in get_table() ([#7](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/7))
* base: make version() more robust ([#28](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/28))
* base: version2float() - replace everything except numbers and a decimal point ([#26](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/26))
* cache3: NameError: name 'base' is not defined ([#29](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/29))
* cache: Make filename for cache configurable ([#21](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/21))
* db_sqlite: Add REGEXP function ([#36](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/36))
* db_sqlite: You must not use 8-bit bytestrings unless you use a text_factory that can interpret 8-bit bytestrings ([#20](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/20))
* disk: Problems with read_csv() ([#25](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/25))
* Error in librenms3.py ([#27](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/27))
* get_table(): Just use ASCII chars, as this is the lowest common denominator across all terminals ([#33](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/33))
* net: chunk = s.recv(1024) timeout: timed out ([#23](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/23))
* net: in fetch(), port and timeout must be of type integer ([#22](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/22))
* url: Identify as Linuxfabrik Monitoring-Plugin ([#24](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/24))
* url: if needed, make fetch() and fetch_json() also return HTTP status code and response headers ([#32](https://git.linuxfabrik.ch/linuxfabrik/lib/-/issues/32))



## [2020052801] - 2020-05-28

### Added ("feat")

* db_mysql
* feedparser
* icinga



## 2020042001 - 2020-04-20

### Changed

* base.py: Added shell_exec().
* net.py
* url.py



## [2020041501] - 2020-04-15

### Added ("feat")

* args.py
* base.py
* cache.py
* db_sqlite.py
* disk.py
* net.py
* rocket.py
* url.py



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
