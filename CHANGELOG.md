# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project does NOT adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


[Unreleased]: https://github.com/Linuxfabrik/monitoring-plugins/compare/2023030601...HEAD


## [Unreleased]

### Added

* qts.py, a library for interacting with the QNAP QTS API
* endoflifedate.py (built automatically; version string only changes when products are added or deleted)
* [Published on PyPI](https://pypi.org/project/linuxfabrik-lib/), you may now use `pip install linuxfabrik-lib`


### Changed

* base.py: cu() appends an optional message, making it a true errormsg function
* version.py: check_eol() also fetches and caches info from https://endoflife.date/api



## 2023051201

### Breaking Changes

* Remove all Python 2 based plugins and libraries from the project, and therefore remove the "3" suffix from all Python3-based plugins and libraries as well (fix [#589](https://github.com/Linuxfabrik/monitoring-plugins/issues/589))
* db_mysql.py: Change from username/password authentication to option file authentication in `connect()`


### Added

* args.py: Add `number_unit_method` type (used in `disk-usage` monitoring plugin)
* disk.py: Add read_env()
* version.py


### Changed

* base.py: Improve str2state()


### Fixed

* smb.py: Type object 'SMBDirEntry' has no attribute 'from_filename'



## 2023030801

### Breaking Changes

* db_mysql3: Change from username/password authentication to option file authentication in connect()
* net3: Rename get_ip_public() to get_public_ip()
* net3: Rename ip_to_cdir() to netmask_to_cdir()


### Added

* dmidecode3.py
* grassfish3.py


### Changed

* base3.py: Make get_worst() more robust
* human3.py: human2bytes() is now also able to interpret "3.0M"
* infomaniak3.py: Apply new API version
* shell3.py: shell_exec() also handles timeouts
* wildfly3.py: Update



## 2022072001

### Added

* distro3.py


### Changed

* cache3.py: Use more unique default names for sqlite databases
* db_mysql3.py: Enhanced for new mysql-checks
* db_mysql3.py: Switch from mysql.connector to PyMySQL  ([#570](https://github.com/Linuxfabrik/monitoring-plugins/issues/570))
* db_mysql3.py: Use more unique default names for sqlite databases
* disk3.py: Add file_exists() function
* Revert Python 3.6+ `f`-strings to use `.format()` to be more conservative



## 2022022801

### Added

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



## 2021101401

### Added

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



## 2020052801

### Added

* db_mysql
* feedparser
* icinga



## 2020042001

### Changed

* base.py: Added shell_exec().
* net.py
* url.py



## 2020041501

### Added

* args.py
* base.py
* cache.py
* db_sqlite.py
* disk.py
* net.py
* rocket.py
* url.py



## 2020022801

Initial release.



