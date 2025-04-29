# Linuxfabrik's Python Libraries

These Python libraries are used in several Linuxfabrik projects, including the [Linuxfabrik Monitoring Plugins project](https://github.com/Linuxfabrik/monitoring-plugins). Requires Python 3.6+ (default Python version on RHEL 8).


## Installation

`pip install linuxfabrik-lib`


## Documentation

[API Documentation](https://linuxfabrik.github.io/lib/) (hosted on GitHub Pages).

The HTML documentation is created using [https://pdoc.dev/](https://pdoc.dev/):

```
pip install pdoc
pdoc --output-dir docs \
    args.py \
    base.py \
    cache.py \
    db_mysql.py \
    db_sqlite.py \
    disk.py \
    distro.py \
    dmidecode.py \
    feedparser.py \
    globals.py \
    grassfish.py \
    huawei.py \
    human.py \
    icinga.py \
    infomaniak.py \
    jitsi.py \
    keycloak.py \
    lftest.py \
    librenms.py \
    net.py \
    nodebb.py \
    powershell.py \
    psutil.py \
    qts.py \
    redfish.py \
    rocket.py \
    shell.py \
    smb.py \
    time.py \
    txt.py \
    uptimerobot.py \
    url.py \
    veeam.py \
    version.py \
    wildfly.py \
    winrm.py
```


## Library Index

* args.py:  
Extends argparse by new input argument data types on demand.

* base.py:  
Provides very common every-day functions.

* cache.py:  
Simple Cache in the form of a Key-Value Store (KVS) like Redis, based on SQLite, optionally supporting expiration of keys. No detailed error handling here. If the cache does not work, we (currently) don't report the reason and simply return `False`.

* db_mysql.py:  
Library for accessing MySQL/MariaDB servers.

* db_sqlite.py:  
Library for accessing SQLite databases.

* disk.py:  
Offers file and disk related functions, like getting a list of partitions, grepping a file, etc.

* distro.py:  
Provides information about the Linux distribution it runs on, such as a reliable machine-readable distro ID and "os_family" (known from Ansible).

* dmidecode.py:  
Library for parsing information from dmidecode. Have a look at `man dmidecode` for details about dmidecode.

* endoflifedate.py:  
This library stores information from https://endoflife.date/api/ for offline usage and therefore needs to be updated periodically when version checks don't have access to the Internet.

* feedparser.py:  
Parse Atom and RSS feeds in Python.

* globals.py:  
This library defines the global plugin states, based on the POSIX spec of returning a positive value and just like in `monitoring-plugins/plugins-scripts/utils.sh.in`, except that we do not make use of `STATE_DEPENDENT`.

* grassfish.py:  
Provides functions using the Grassfish REST-API.

* huawei.py:  
This library collects some Huawei related functions that are needed by Huawei check plugins.

* human.py:  
Functions to convert raw numbers, times etc. to a human readable representation (and sometimes back).

* icinga.py:  
This module tries to make accessing the Icinga2 API easier.

* infomaniak.py:  
Provides functions using the Infomanik REST-API.

* jitsi.py:  
This library collects some Jitsi related functions that are needed by more than one Jitsi plugin.

* keycloak.py:  
This library collects some Keycloak related functions that are needed by more than one Keycloak plugin.

* lftest.py:  
Provides test functions for unit tests.

* librenms.py:  
This library collects some LibreNMS related functions that are needed by LibreNMS check plugins.

* net.py:  
Provides network related functions and variables.

* nodebb.py:  
This library collects some NodeBB related functions that are needed by more than one NodeBB plugin.

* powershell.py:  
This library collects some Microsoft PowerShell related functions.

* psutil.py:  
Wrapper library for functions from psutil.

* redfish.py:  
This library parses data returned from the Redfish API.

* rocket.py:  
This library collects some Rocket.Chat related functions that are needed by more than one Rocket.Chat plugin.

* shell.py:  
Communicates with the Shell.

* smb.py:  
Provides functions to establish native SMB connections.

* time.py:  
Provides datetime functions.

* txt.py:  
A collection of text functions.

* uptimerobot.py:  
Interacts with the UptimeRobot API.

* url.py:  
Get for example HTML or JSON from an URL.

* veeam.py:  
This library interacts with the Veeam Enterprise Manager API.

* version.py:  
Provides functions for handling software versions.

* wildfly.py:  
This library collects some WildFly/JBoss related functions that are needed by more than one WildFly/JBoss plugin.

* winrm.py:  
This library collects some Microsoft WinRM related functions.


## Tips & Tricks

* Counts the function calls to any "lib" library in your project and sorts the results by frequency in descending order:  
  `grep -rhoP '\Wlib\.[a-zA-Z0-9_\.]+' * | sed 's/^[^a-zA-Z0-9]*//' | sort | uniq -c | sort -nr`
