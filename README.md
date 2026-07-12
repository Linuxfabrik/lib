<h1 align="center">
  Linuxfabrik Python Libraries
</h1>
<p align="center">
  Python 3.9+ modules for Linuxfabrik projects: DB access, SQLite KVS caching, WinRM, SMB, shell execution, 15+ API integrations (Icinga2, Veeam, Nextcloud, ...). Available on PyPI.
  <span>&#8226;</span>
  <b>made by <a href="https://linuxfabrik.ch/">Linuxfabrik</a></b>
</p>
<div align="center">

![GitHub Stars](https://img.shields.io/github/stars/linuxfabrik/lib)
[![Star History Chart](https://api.star-history.com/chart?repos=Linuxfabrik/lib&type=date&legend=top-left&sealed_token=6SUm1801mnVVflh1FjdwjwI1jTKV5frTQxeT9BI5GQvcCSalOiWVA9ZX6pLrUmxtmvs1v6KGVThzjW1gGciZf7jpiQbS4713HMIMiGkG-9v7I5GQhnnPIw)](https://www.star-history.com/?repos=Linuxfabrik%2Flib&type=date&legend=top-left)
![License](https://img.shields.io/github/license/linuxfabrik/lib)
![Version](https://img.shields.io/github/v/release/linuxfabrik/lib?sort=semver)
[![PyPI](https://img.shields.io/pypi/v/linuxfabrik-lib)](https://pypi.org/project/linuxfabrik-lib/)
![Python](https://img.shields.io/badge/Python-3.9+-3776ab)
![GitHub Issues](https://img.shields.io/github/issues/linuxfabrik/lib)
[![GitHubSponsors](https://img.shields.io/github/sponsors/Linuxfabrik?label=GitHub%20Sponsors)](https://github.com/sponsors/Linuxfabrik)
[![PayPal](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=7AW3VVX62TR4A&source=url)

</div>

<br />


# Linuxfabrik Python Libraries

A mature, production-grade Python library collection providing 40 modules with 300+ functions for system administration, monitoring, and infrastructure automation. These libraries are used across several Linuxfabrik projects -- most prominently the [Linuxfabrik Monitoring Plugins](https://github.com/Linuxfabrik/monitoring-plugins) (Nagios/Icinga check plugins), but also in [ChecklistFabrik](https://github.com/Linuxfabrik/checklistfabrik) and other tools.

> If these libraries help you developing your own monitoring plugins, system tools or infrastructure automation, please give it a star.

The library requires Python 3.9+ and runs on every platform.


## Documentation

Full documentation is available at [linuxfabrik.github.io/lib](https://linuxfabrik.github.io/lib/). It is automatically built and deployed on every push to `main`.


## Installation

Add `linuxfabrik-lib` as a dependency to your project, or install it manually:

```bash
pip install --user linuxfabrik-lib
```


## Design Principles

These libraries are built with a clear set of priorities:

* **Procedural by design.** The libraries deliberately use a procedural/functional style rather than object-oriented programming. Pure functions with explicit inputs and outputs are easier to read, test, and reason about. This is especially true for the most prominent use case -- monitoring plugins -- which are short-lived, linear processes with no complex state to manage over time, where unnecessary abstraction layers would add overhead without tangible benefit.
* **Broad compatibility.** Python 3.9+ is the minimum, ensuring the libraries work on RHEL 8 and every major distribution without requiring newer runtimes.
* **Cross-platform.** Core functions behave identically on Linux, Windows, and macOS. Platform-specific code (WinRM, PowerShell, SMB) is cleanly separated.
* **Minimal dependencies.** We avoid pulling in large dependency trees. External packages are used only when the alternative would be unreliable or significantly more complex.
* **Consistent error handling.** Most functions return `(success, result)` tuples. The caller decides whether to continue or exit -- the library never exits on its own. The `base.coe()` ("Continue or Exit") helper makes this pattern concise.
* **Automatic redaction.** Sensitive data (passwords, tokens, API keys) in error messages is automatically sanitized before output.
* **Nagios/Icinga conventions.** State constants, threshold evaluation, performance data formatting, and range parsing follow the [Monitoring Plugins Development Guidelines](https://www.monitoring-plugins.org/doc/guidelines.html).
* **Defensive defaults.** Functions use sensible timeouts, safe SSL settings, and locked-down defaults so that plugins work out of the box without extensive configuration.


## Library Index


### Core Utilities

| Module | Description | Key Functions |
|--------|-------------|---------------|
| **args.py** | Extends `argparse` with custom input types for monitoring thresholds and a registry of reusable `--help` texts. | `csv()`, `float_or_none()`, `help()`, `int_or_none()`, `number_unit_method()` |
| **base.py** | The central library for plugin development. Provides state evaluation, threshold comparison, performance data formatting, ASCII table output, and the `coe()` error-handling pattern. | `coe()`, `cu()`, `get_perfdata()`, `get_state()`, `get_table()`, `get_worst()`, `oao()`, `state2str()` |
| **globals.py** | Defines the four Nagios/Icinga plugin states: `STATE_OK` (0), `STATE_WARN` (1), `STATE_CRIT` (2), `STATE_UNKNOWN` (3). | -- |
| **human.py** | Converts raw numbers, byte sizes, bit rates, and durations to human-readable representations and back. Supports binary/SI prefixes and Nagios range syntax with units. | `bits2human()`, `bps2human()`, `bytes2human()`, `human2bytes()`, `human2seconds()`, `humanrange2bytes()`, `number2human()`, `seconds2human()` |
| **lftest.py** | Test harness for data-driven plugin unit tests, spinning up throwaway containers (including MySQL/MariaDB) as fixtures. | `attach_each()`, `attach_tests()`, `run()`, `run_container()`, `run_mysql_compatible_from_containerfile()`, `test()` |
| **time.py** | Date/time conversions between UNIX epochs, ISO strings, and datetime objects, plus time-macro expansion and time differences. Timezone-aware. | `epoch2iso()`, `now()`, `timestr2datetime()`, `timestrdiff()` |
| **txt.py** | Text processing: regex compilation, substring extraction, multi-line parsing, sensitive data redaction, pluralization, and byte/text encoding conversion. | `compile_regex()`, `extract_str()`, `match_regex()`, `mltext2array()`, `pluralize()`, `to_bytes()`, `to_text()` |
| **version.py** | Software version parsing, comparison, and End-of-Life checking against [endoflife.date](https://endoflife.date). | `check_eol()`, `version()`, `version2float()` |


### Data Access & Caching

| Module | Description | Key Functions |
|--------|-------------|---------------|
| **cache.py** | A simple SQLite-based key-value store with optional key expiration. Used for persisting state between plugin runs. | `get()`, `set()` |
| **db_mysql.py** | MySQL/MariaDB client with connection management, query execution, privilege checking, and server flavor/status/variable/replication inspection. | `check_privileges()`, `connect()`, `get_all_variables()`, `get_engines()`, `get_replica_status()`, `lod2dict()`, `select()` |
| **db_sqlite.py** | Full SQLite interface: table/index creation, CRUD operations, CSV import, regex support, and per-second counter deltas for time-series data. | `connect()`, `create_index()`, `create_table()`, `cut()`, `delete()`, `insert()`, `per_second_deltas()`, `select()` |


### System & OS

| Module | Description | Key Functions |
|--------|-------------|---------------|
| **disk.py** | File I/O, directory walking, CSV/environment file parsing, block device and partition listing, and temp directory management. | `dir_exists()`, `file_exists()`, `get_real_disks()`, `get_tmpdir()`, `grep_file()`, `read_file()` |
| **distro.py** | Linux distribution detection. Returns normalized facts including distribution name, version, and Ansible-compatible `os_family`. | `get_distribution_facts()` |
| **dmidecode.py** | Parses `dmidecode` output into structured data. Extracts CPU, RAM, firmware, serial number, manufacturer, and model information. | `cpu_speed()`, `cpu_type()`, `firmware()`, `get_data()`, `manufacturer()`, `model()`, `ram()`, `serno()` |
| **endoflifedate.py** | Bundled End-of-Life data from [endoflife.date](https://endoflife.date) for offline version checks when internet access is unavailable. | -- |
| **psutil.py** | Wrapper around `psutil` for retrieving mounted disk partitions with device, mount point, and filesystem type. | `get_partitions()` |
| **shell.py** | Runs external commands from an argv list without a shell, guards option-style CLI values, and locates executables in `PATH`. | `safe_cli_value()`, `shell_exec()`, `which()` |


### Networking & HTTP

| Module | Description | Key Functions |
|--------|-------------|---------------|
| **feedparser.py** | Parses Atom and RSS feeds from URLs using BeautifulSoup. | `parse()` |
| **net.py** | Low-level networking: TCP/UDP/TLS and Unix domain sockets, public IP lookup, subnet enumeration, netmask conversion, and hostname validation. | `cidr_to_hosts()`, `fetch()`, `fetch_socket()`, `get_public_ip()`, `get_subnet_hosts()`, `ip_to_cidr()` |
| **ssh.py** | Runs commands and copies files over SSH by building shell-free `ssh`/`scp`/`rsync` argument lists. | `build_options()`, `rsync()`, `run()`, `scp()`, `target()` |
| **url.py** | HTTP/1.x and HTTP/2 client (httpx) for HTML, JSON, or raw data. Supports GET/POST, Basic/Digest authentication, TLS version pinning, proxy control, and connection telemetry. | `fetch()`, `fetch_json()`, `get_latest_version_from_github()`, `split_basic_auth()`, `strip_tags()` |


### Windows Integration

| Module | Description | Key Functions |
|--------|-------------|---------------|
| **powershell.py** | Executes PowerShell commands locally (on Windows hosts). | `run_ps()` |
| **smb.py** | Native SMB/CIFS file access: list, glob, and open files on remote shares with encryption support. | `glob()`, `open_file()` |
| **winrm.py** | Executes commands and PowerShell scripts on remote Windows hosts via WinRM/PSRP, preferring pypsrp with a pywinrm fallback. | `run_cmd()`, `run_ps()` |


### API Integrations

| Module | Description | Key Functions |
|--------|-------------|---------------|
| **bexio.py** | [Bexio](https://www.bexio.com/) business software REST API (contacts, invoices, projects, items, timesheets, and more). | `call_api()`, `fetch_accounts()`, `fetch_contacts()`, `fetch_invoices()`, `fetch_projects()`, `get_all()` |
| **grassfish.py** | [Grassfish](https://www.grassfish.com/) digital signage REST API. | `fetch_json()`, `set_player_defaults()`, `set_screen_defaults()` |
| **huawei.py** | Huawei [OceanStor/Dorado](https://www.huawei.com/) storage REST API, decoding its numeric status, model, and hardware codes. | `get_data()`, `get_health_status()`, `get_running_status()`, `get_uuid()` |
| **icinga.py** | [Icinga2](https://icinga.com/) REST API client for querying services and managing acknowledgements and downtimes. | `get_service()`, `remove_ack()`, `remove_downtime()`, `set_ack()`, `set_downtime()` |
| **infomaniak.py** | [Infomaniak](https://www.infomaniak.com/) Swiss Backup REST API for events, backup products, and slots. | `get_events()`, `get_swiss_backup_products()`, `get_swiss_backup_slots()` |
| **jitsi.py** | [Jitsi Meet](https://jitsi.org/) server statistics endpoint, with optional HTTP Basic auth. | `get_data()` |
| **keycloak.py** | [Keycloak](https://www.keycloak.org/) identity provider with OIDC discovery, admin-token retrieval, and Admin REST API access. | `discover_oidc_endpoints()`, `get_data()`, `obtain_admin_token()` |
| **librenms.py** | [LibreNMS](https://www.librenms.org/) monitoring API, mapping its alert states to Nagios states. | `get_data()`, `get_prop()`, `get_state()` |
| **nextcloud.py** | [Nextcloud](https://nextcloud.com/) `occ` command execution as the `config.php` owner, parsing JSON or text output. | `run_occ()` |
| **nodebb.py** | [NodeBB](https://nodebb.org/) forum API, using a Bearer user token. | `get_data()` |
| **qts.py** | QNAP [QTS](https://www.qnap.com/) NAS API with session authentication. | `get_auth_sid()` |
| **redfish.py** | [Redfish](https://www.dmtf.org/standards/redfish) BMC API for chassis, systems, storage, managers, and sensors, deriving Nagios states and perfdata. | `get_auth_header()`, `get_perfdata()`, `get_state()`, `get_systems()` |
| **rocket.py** | [Rocket.Chat](https://www.rocket.chat/) REST API for login, room/group history, statistics, and incoming webhooks. | `get_groups_history()`, `get_rooms_get()`, `get_rooms_info()`, `get_stats()`, `get_token()`, `send2webhook()` |
| **uptimerobot.py** | [UptimeRobot](https://uptimerobot.com/) API for monitors, alert contacts, maintenance windows, and status pages. | `delete_monitor()`, `edit_monitor()`, `get_account_details()`, `get_alert_contacts()`, `get_monitors()`, `get_mwindows()`, `get_psps()`, `new_monitor()` |
| **veeam.py** | [Veeam](https://www.veeam.com/) Backup & Replication Enterprise Manager REST API. | `get_token()` |
| **wildfly.py** | [WildFly/JBoss](https://www.wildfly.org/) management API with digest auth (standalone and domain mode). | `get_data()` |


## Usage Example

A typical monitoring plugin using these libraries:

```python
import lib.args
import lib.base
import lib.url
from lib.globals import (STATE_CRIT, STATE_OK, STATE_UNKNOWN, STATE_WARN)

def main():
    # Parse arguments with custom threshold types
    parser = lib.args.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--warning', type=lib.args.float_or_none, default=80)
    parser.add_argument('--critical', type=lib.args.float_or_none, default=90)
    args = parser.parse_args()

    # Fetch data (coe = "Continue or Exit")
    result = lib.base.coe(lib.url.fetch_json(args.url))

    # Evaluate thresholds
    state = lib.base.get_state(result['usage'], args.warning, args.critical)
    perfdata = lib.base.get_perfdata('usage', result['usage'], '%', args.warning, args.critical, 0, 100)

    # Output and exit
    lib.base.oao('Usage is {}%'.format(result['usage']), state, perfdata)

if __name__ == '__main__':
    main()
```


## Tips & Tricks

Count the function calls to any "lib" library in your project and sort by frequency:

```bash
grep -rhoP '\Wlib\.[a-zA-Z0-9_\.]+' * | sed 's/^[^a-zA-Z0-9]*//' | sort | uniq -c | sort -nr
```
