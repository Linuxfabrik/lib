#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library stores information from https://endoflife.date/api/ for offline usage
and therefore needs to be updated periodically when version checks don't have access to the
Internet."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2023081702'

ENDOFLIFE_DATE = {

    'https://endoflife.date/api/apache.json': [
      {
        "cycle": "2.4",
        "releaseDate": "2012-02-21",
        "eol": False,
        "latest": "2.4.57",
        "latestReleaseDate": "2023-04-06",
        "link": "https://downloads.apache.org/httpd/Announcement2.4.html",
        "lts": False
      },
      {
        "cycle": "2.2",
        "releaseDate": "2005-12-01",
        "eol": "2017-07-11",
        "latest": "2.2.34",
        "latestReleaseDate": "2017-07-11",
        "lts": False
      },
      {
        "cycle": "2.0",
        "releaseDate": "2002-04-06",
        "eol": "2013-07-10",
        "latest": "2.0.65",
        "latestReleaseDate": "2013-07-10",
        "lts": False
      },
      {
        "cycle": "1.3",
        "releaseDate": "1998-06-06",
        "eol": "2010-02-03",
        "latest": "1.3.42",
        "latestReleaseDate": "2010-02-03",
        "lts": False
      }
    ],


    'https://endoflife.date/api/fedora.json': [
      {
        "cycle": "38",
        "releaseDate": "2023-04-18",
        "eol": "2024-05-18",
        "latest": "38",
        "latestReleaseDate": "2023-04-18",
        "lts": False
      },
      {
        "cycle": "37",
        "releaseDate": "2022-11-15",
        "eol": "2023-12-15",
        "latest": "37",
        "latestReleaseDate": "2022-11-15",
        "lts": False
      },
      {
        "cycle": "36",
        "releaseDate": "2022-05-10",
        "eol": "2023-05-18",
        "latest": "36",
        "latestReleaseDate": "2022-05-10",
        "lts": False
      },
      {
        "cycle": "35",
        "releaseDate": "2021-11-02",
        "eol": "2022-12-13",
        "latest": "35",
        "latestReleaseDate": "2021-11-02",
        "lts": False
      },
      {
        "cycle": "34",
        "releaseDate": "2021-04-27",
        "eol": "2022-06-07",
        "latest": "34",
        "latestReleaseDate": "2021-04-27",
        "lts": False
      },
      {
        "cycle": "33",
        "releaseDate": "2020-10-27",
        "eol": "2021-11-30",
        "latest": "33",
        "latestReleaseDate": "2020-10-27",
        "lts": False
      },
      {
        "cycle": "32",
        "releaseDate": "2020-04-28",
        "eol": "2021-05-25",
        "latest": "32",
        "latestReleaseDate": "2020-04-28",
        "lts": False
      },
      {
        "cycle": "31",
        "releaseDate": "2019-10-29",
        "eol": "2020-11-30",
        "latest": "31",
        "latestReleaseDate": "2019-10-29",
        "lts": False
      },
      {
        "cycle": "30",
        "releaseDate": "2019-04-30",
        "eol": "2020-05-26",
        "latest": "30",
        "latestReleaseDate": "2019-04-30",
        "lts": False
      },
      {
        "cycle": "29",
        "releaseDate": "2018-10-30",
        "eol": "2019-11-26",
        "latest": "29",
        "latestReleaseDate": "2018-10-30",
        "lts": False
      },
      {
        "cycle": "28",
        "releaseDate": "2018-05-01",
        "eol": "2019-05-28",
        "latest": "28",
        "latestReleaseDate": "2018-05-01",
        "lts": False
      }
    ],


    'https://endoflife.date/api/fortios.json': [
      {
        "cycle": "7.4",
        "eol": "2027-11-11",
        "support": "2026-05-11",
        "releaseDate": "2023-05-11",
        "lts": False
      },
      {
        "cycle": "7.2",
        "eol": "2026-09-30",
        "support": "2025-03-31",
        "releaseDate": "2022-03-31",
        "lts": False
      },
      {
        "cycle": "7.0",
        "eol": "2025-09-30",
        "support": "2024-03-30",
        "releaseDate": "2021-03-30",
        "lts": False
      },
      {
        "cycle": "6.4",
        "eol": "2024-09-30",
        "support": "2023-03-31",
        "releaseDate": "2020-03-31",
        "lts": False
      },
      {
        "cycle": "6.2",
        "eol": "2023-09-28",
        "support": "2022-03-28",
        "releaseDate": "2019-03-28",
        "lts": False
      },
      {
        "cycle": "6.0",
        "eol": "2022-09-29",
        "support": "2021-03-29",
        "releaseDate": "2018-03-29",
        "lts": False
      }
    ],


    'https://endoflife.date/api/gitlab.json': [
      {
        "cycle": "16.2",
        "releaseDate": "2023-07-21",
        "support": "2023-08-22",
        "eol": "2023-10-22",
        "latest": "16.2.3",
        "latestReleaseDate": "2023-08-03",
        "lts": False
      },
      {
        "cycle": "16.1",
        "releaseDate": "2023-06-21",
        "support": "2023-07-22",
        "eol": "2023-09-22",
        "latest": "16.1.4",
        "latestReleaseDate": "2023-08-03",
        "lts": False
      },
      {
        "cycle": "16.0",
        "releaseDate": "2023-05-18",
        "support": "2023-06-22",
        "eol": "2023-08-22",
        "latest": "16.0.8",
        "latestReleaseDate": "2023-08-01",
        "lts": False
      },
      {
        "cycle": "15.11",
        "releaseDate": "2023-04-21",
        "support": "2023-05-22",
        "eol": "2023-07-22",
        "latest": "15.11.13",
        "latestReleaseDate": "2023-07-27",
        "lts": False
      },
      {
        "cycle": "15.10",
        "releaseDate": "2023-03-21",
        "support": "2023-04-22",
        "eol": "2023-06-22",
        "latest": "15.10.8",
        "latestReleaseDate": "2023-06-05",
        "lts": False
      },
      {
        "cycle": "15.9",
        "support": "2023-03-22",
        "eol": "2023-05-22",
        "latest": "15.9.8",
        "latestReleaseDate": "2023-05-10",
        "releaseDate": "2023-02-21",
        "lts": False
      },
      {
        "cycle": "15.8",
        "support": "2023-02-22",
        "eol": "2023-04-22",
        "latest": "15.8.6",
        "latestReleaseDate": "2023-04-18",
        "releaseDate": "2023-01-20",
        "lts": False
      },
      {
        "cycle": "15.7",
        "support": "2023-01-22",
        "eol": "2023-03-22",
        "latest": "15.7.9",
        "latestReleaseDate": "2023-04-20",
        "releaseDate": "2022-12-21",
        "lts": False
      },
      {
        "cycle": "15.6",
        "support": "2022-12-22",
        "eol": "2023-02-22",
        "latest": "15.6.8",
        "latestReleaseDate": "2023-02-10",
        "releaseDate": "2022-11-21",
        "lts": False
      },
      {
        "cycle": "15.5",
        "support": "2022-11-22",
        "eol": "2023-01-22",
        "latest": "15.5.9",
        "latestReleaseDate": "2023-01-12",
        "releaseDate": "2022-10-21",
        "lts": False
      },
      {
        "cycle": "15.4",
        "support": "2022-10-22",
        "eol": "2022-12-22",
        "latest": "15.4.6",
        "latestReleaseDate": "2022-11-30",
        "releaseDate": "2022-09-21",
        "lts": False
      },
      {
        "cycle": "15.3",
        "support": "2022-09-22",
        "eol": "2022-11-22",
        "latest": "15.3.5",
        "latestReleaseDate": "2022-11-02",
        "releaseDate": "2022-08-19",
        "lts": False
      },
      {
        "cycle": "15.2",
        "support": "2022-08-22",
        "eol": "2022-10-22",
        "latest": "15.2.5",
        "latestReleaseDate": "2022-09-29",
        "releaseDate": "2022-07-21",
        "lts": False
      },
      {
        "cycle": "15.1",
        "support": "2022-07-22",
        "eol": "2022-09-22",
        "latest": "15.1.6",
        "latestReleaseDate": "2022-08-30",
        "releaseDate": "2022-06-21",
        "lts": False
      },
      {
        "cycle": "15.0",
        "support": "2022-06-22",
        "eol": "2022-08-22",
        "latest": "15.0.5",
        "latestReleaseDate": "2022-07-28",
        "releaseDate": "2022-05-20",
        "lts": False
      },
      {
        "cycle": "14.10",
        "support": "2022-05-22",
        "eol": "2022-07-22",
        "latest": "14.10.5",
        "latestReleaseDate": "2022-06-30",
        "releaseDate": "2022-04-21",
        "lts": False
      },
      {
        "cycle": "14.9",
        "support": "2022-04-22",
        "eol": "2022-06-22",
        "latest": "14.9.5",
        "latestReleaseDate": "2022-06-01",
        "releaseDate": "2022-03-21",
        "lts": False
      },
      {
        "cycle": "14.8",
        "support": "2022-03-22",
        "eol": "2022-05-22",
        "latest": "14.8.6",
        "latestReleaseDate": "2022-04-29",
        "releaseDate": "2022-02-21",
        "lts": False
      },
      {
        "cycle": "14.7",
        "support": "2022-02-22",
        "eol": "2022-04-22",
        "latest": "14.7.7",
        "latestReleaseDate": "2022-03-31",
        "releaseDate": "2022-01-21",
        "lts": False
      },
      {
        "cycle": "14.6",
        "support": "2022-01-22",
        "eol": "2022-03-22",
        "latest": "14.6.7",
        "latestReleaseDate": "2022-03-31",
        "releaseDate": "2021-12-21",
        "lts": False
      },
      {
        "cycle": "14.5",
        "support": "2021-12-22",
        "eol": "2022-02-22",
        "latest": "14.5.4",
        "latestReleaseDate": "2022-02-03",
        "releaseDate": "2021-11-19",
        "lts": False
      },
      {
        "cycle": "14.4",
        "support": "2021-11-22",
        "eol": "2022-01-22",
        "latest": "14.4.5",
        "latestReleaseDate": "2022-01-11",
        "releaseDate": "2021-10-21",
        "lts": False
      },
      {
        "cycle": "14.3",
        "support": "2021-10-22",
        "eol": "2021-12-22",
        "latest": "14.3.6",
        "latestReleaseDate": "2021-12-03",
        "releaseDate": "2021-09-21",
        "lts": False
      },
      {
        "cycle": "14.2",
        "support": "2021-09-22",
        "eol": "2021-11-22",
        "latest": "14.2.7",
        "latestReleaseDate": "2021-11-26",
        "releaseDate": "2021-08-20",
        "lts": False
      },
      {
        "cycle": "14.1",
        "support": "2021-08-22",
        "eol": "2021-10-22",
        "latest": "14.1.8",
        "latestReleaseDate": "2021-11-15",
        "releaseDate": "2021-07-21",
        "lts": False
      },
      {
        "cycle": "14.0",
        "support": "2021-07-22",
        "eol": "2021-09-22",
        "latest": "14.0.12",
        "latestReleaseDate": "2021-11-05",
        "releaseDate": "2021-06-21",
        "lts": False
      },
      {
        "cycle": "13.12",
        "support": "2021-06-22",
        "eol": "2021-08-22",
        "latest": "13.12.15",
        "latestReleaseDate": "2021-11-03",
        "releaseDate": "2021-05-21",
        "lts": False
      },
      {
        "cycle": "13.11",
        "support": "2021-05-22",
        "eol": "2021-07-22",
        "latest": "13.11.7",
        "latestReleaseDate": "2021-07-07",
        "releaseDate": "2021-04-21",
        "lts": False
      },
      {
        "cycle": "13.10",
        "support": "2021-04-22",
        "eol": "2021-06-22",
        "latest": "13.10.5",
        "latestReleaseDate": "2021-06-01",
        "releaseDate": "2021-03-18",
        "lts": False
      }
    ],


    'https://endoflife.date/api/grafana.json': [
      {
        "cycle": "10.0",
        "releaseDate": "2023-06-09",
        "support": True,
        "eol": False,
        "latest": "10.0.1",
        "latestReleaseDate": "2023-06-22",
        "lts": False
      },
      {
        "cycle": "9.5",
        "releaseDate": "2023-04-06",
        "support": "2023-06-09",
        "eol": False,
        "latest": "9.5.5",
        "latestReleaseDate": "2023-06-22",
        "lts": False
      },
      {
        "cycle": "9.4",
        "releaseDate": "2023-02-27",
        "support": "2023-04-06",
        "eol": "2023-06-09",
        "latest": "9.4.13",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "9.3",
        "releaseDate": "2022-11-29",
        "support": "2023-02-27",
        "eol": "2023-04-06",
        "latest": "9.3.16",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "9.2",
        "releaseDate": "2022-10-11",
        "support": "2022-11-29",
        "eol": "2023-02-27",
        "latest": "9.2.20",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "9.1",
        "releaseDate": "2022-08-16",
        "support": "2022-10-11",
        "eol": "2022-11-29",
        "latest": "9.1.8",
        "latestReleaseDate": "2022-10-11",
        "lts": False
      },
      {
        "cycle": "9.0",
        "releaseDate": "2022-06-13",
        "support": "2022-08-16",
        "eol": "2022-10-11",
        "latest": "9.0.9",
        "latestReleaseDate": "2022-09-20",
        "lts": False
      },
      {
        "cycle": "8",
        "releaseDate": "2021-06-08",
        "support": "2022-06-13",
        "eol": False,
        "latest": "8.5.27",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "7",
        "releaseDate": "2020-05-15",
        "support": "2021-06-08",
        "eol": "2022-06-14",
        "latest": "7.5.17",
        "latestReleaseDate": "2022-09-26",
        "lts": False
      },
      {
        "cycle": "6",
        "releaseDate": "2019-02-25",
        "support": "2020-05-15",
        "eol": "2021-06-08",
        "latest": "6.7.6",
        "latestReleaseDate": "2021-03-18",
        "lts": False
      }
    ],


    'https://endoflife.date/api/keycloak.json': [
      {
        "cycle": "22.0",
        "releaseDate": "2023-07-11",
        "eol": False,
        "latest": "22.0.1",
        "latestReleaseDate": "2023-07-18",
        "lts": False
      },
      {
        "cycle": "21.1",
        "releaseDate": "2023-04-19",
        "eol": "2023-07-11",
        "latest": "21.1.2",
        "latestReleaseDate": "2023-06-28",
        "lts": False
      },
      {
        "cycle": "21.0",
        "releaseDate": "2023-02-23",
        "eol": "2023-04-19",
        "latest": "21.0.2",
        "latestReleaseDate": "2023-03-30",
        "lts": False
      },
      {
        "cycle": "20.0",
        "releaseDate": "2022-11-01",
        "eol": "2023-02-23",
        "latest": "20.0.5",
        "latestReleaseDate": "2023-02-21",
        "lts": False
      },
      {
        "cycle": "19.0",
        "releaseDate": "2022-07-27",
        "eol": "2022-11-01",
        "latest": "19.0.3",
        "latestReleaseDate": "2022-10-06",
        "lts": False
      },
      {
        "cycle": "18.0",
        "releaseDate": "2022-04-20",
        "eol": "2022-07-27",
        "latest": "18.0.2",
        "latestReleaseDate": "2022-06-24",
        "lts": False
      },
      {
        "cycle": "17.0",
        "releaseDate": "2022-03-11",
        "eol": "2022-04-20",
        "latest": "17.0.1",
        "latestReleaseDate": "2022-03-23",
        "lts": False
      },
      {
        "cycle": "16.1",
        "releaseDate": "2021-12-20",
        "eol": "2022-03-11",
        "latest": "16.1.1",
        "latestReleaseDate": "2022-01-25",
        "lts": False
      },
      {
        "cycle": "16.0",
        "releaseDate": "2021-12-17",
        "eol": "2021-12-20",
        "latest": "16.0.0",
        "latestReleaseDate": "2021-12-17",
        "lts": False
      },
      {
        "cycle": "15.1",
        "releaseDate": "2021-12-10",
        "eol": "2021-12-17",
        "latest": "15.1.1",
        "latestReleaseDate": "2021-12-17",
        "lts": False
      },
      {
        "cycle": "15.0",
        "releaseDate": "2021-07-30",
        "eol": "2021-12-10",
        "latest": "15.0.2",
        "latestReleaseDate": "2021-08-20",
        "lts": False
      },
      {
        "cycle": "14.0",
        "releaseDate": "2021-06-18",
        "eol": "2021-07-15",
        "latest": "14.0.0",
        "latestReleaseDate": "2021-06-18",
        "lts": False
      },
      {
        "cycle": "13.0",
        "releaseDate": "2021-05-06",
        "eol": "2021-06-18",
        "latest": "13.0.1",
        "latestReleaseDate": "2021-05-25",
        "lts": False
      },
      {
        "cycle": "12.0",
        "releaseDate": "2020-12-16",
        "eol": "2021-05-06",
        "latest": "12.0.4",
        "latestReleaseDate": "2021-03-01",
        "lts": False
      },
      {
        "cycle": "11.0",
        "releaseDate": "2020-07-22",
        "eol": "2020-12-16",
        "latest": "11.0.3",
        "latestReleaseDate": "2020-11-05",
        "lts": False
      },
      {
        "cycle": "10.0",
        "releaseDate": "2020-04-29",
        "eol": "2020-07-22",
        "latest": "10.0.2",
        "latestReleaseDate": "2020-06-02",
        "lts": False
      }
    ],


    'https://endoflife.date/api/mariadb.json': [
      {
        "cycle": "11.0",
        "releaseDate": "2023-06-06",
        "eol": "2024-06-07",
        "latest": "11.0.2",
        "latestReleaseDate": "2023-06-06",
        "lts": False
      },
      {
        "cycle": "10.11",
        "releaseDate": "2023-02-16",
        "eol": "2028-02-16",
        "latest": "10.11.4",
        "lts": True,
        "latestReleaseDate": "2023-06-07"
      },
      {
        "cycle": "10.10",
        "releaseDate": "2022-11-07",
        "eol": "2023-11-17",
        "latest": "10.10.5",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "10.9",
        "releaseDate": "2022-08-15",
        "eol": "2023-08-22",
        "latest": "10.9.7",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "10.8",
        "releaseDate": "2022-05-20",
        "eol": "2023-05-20",
        "latest": "10.8.8",
        "latestReleaseDate": "2023-05-10",
        "lts": False
      },
      {
        "cycle": "10.7",
        "releaseDate": "2022-02-08",
        "eol": "2023-02-09",
        "latest": "10.7.8",
        "latestReleaseDate": "2023-02-06",
        "lts": False
      },
      {
        "cycle": "10.6",
        "releaseDate": "2021-07-05",
        "eol": "2026-07-06",
        "latest": "10.6.14",
        "lts": True,
        "latestReleaseDate": "2023-06-07"
      },
      {
        "cycle": "10.5",
        "releaseDate": "2020-06-23",
        "eol": "2025-06-24",
        "latest": "10.5.21",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "10.4",
        "releaseDate": "2019-06-17",
        "eol": "2024-06-18",
        "latest": "10.4.30",
        "latestReleaseDate": "2023-06-07",
        "lts": False
      },
      {
        "cycle": "10.3",
        "releaseDate": "2018-05-23",
        "eol": "2023-05-25",
        "latest": "10.3.39",
        "latestReleaseDate": "2023-05-10",
        "lts": False
      },
      {
        "cycle": "10.2",
        "releaseDate": "2017-05-15",
        "eol": "2022-05-23",
        "latest": "10.2.44",
        "latestReleaseDate": "2022-05-20",
        "lts": False
      },
      {
        "cycle": "10.1",
        "releaseDate": "2016-09-29",
        "eol": "2020-10-17",
        "latest": "10.1.48",
        "latestReleaseDate": "2020-10-30",
        "lts": False
      },
      {
        "cycle": "10.0",
        "releaseDate": "2014-06-12",
        "eol": "2019-03-31",
        "latest": "10.0.38",
        "latestReleaseDate": "2019-01-29",
        "lts": False
      },
      {
        "cycle": "5.5",
        "eol": "2020-04-11",
        "releaseDate": "2013-01-29",
        "latest": "5.5.68",
        "lts": True,
        "latestReleaseDate": "2020-05-06"
      }
    ],


    'https://endoflife.date/api/mysql.json': [
      {
        "cycle": "8.1",
        "latest": "8.1.0",
        "support": True,
        "eol": False,
        "latestReleaseDate": "2023-06-21",
        "releaseDate": "2023-06-21",
        "lts": False
      },
      {
        "cycle": "8.0",
        "latest": "8.0.34",
        "support": "2025-04-30",
        "eol": "2026-04-30",
        "lts": "2023-07-18",
        "latestReleaseDate": "2023-06-22",
        "releaseDate": "2018-04-08"
      },
      {
        "cycle": "5.7",
        "latest": "5.7.43",
        "support": "2020-10-31",
        "eol": "2023-10-31",
        "latestReleaseDate": "2023-06-21",
        "releaseDate": "2015-10-09",
        "lts": False
      },
      {
        "cycle": "5.6",
        "latest": "5.6.51",
        "support": "2018-02-28",
        "eol": "2021-02-28",
        "latestReleaseDate": "2021-01-05",
        "releaseDate": "2013-02-01",
        "lts": False
      },
      {
        "cycle": "5.5",
        "latest": "5.5.63",
        "support": "2015-12-31",
        "eol": "2018-12-31",
        "latestReleaseDate": "2018-12-21",
        "releaseDate": "2010-12-03",
        "lts": False
      }
    ],


    'https://endoflife.date/api/nextcloud.json': [
      {
        "cycle": "27",
        "releaseDate": "2023-06-12",
        "eol": "2024-06-01",
        "latest": "27.0.2",
        "latestReleaseDate": "2023-08-08",
        "lts": False
      },
      {
        "cycle": "26",
        "releaseDate": "2023-03-21",
        "eol": "2024-03-01",
        "latest": "26.0.4",
        "latestReleaseDate": "2023-07-20",
        "lts": False
      },
      {
        "cycle": "25",
        "releaseDate": "2022-10-18",
        "eol": "2023-10-01",
        "latest": "25.0.9",
        "latestReleaseDate": "2023-07-20",
        "lts": False
      },
      {
        "cycle": "24",
        "releaseDate": "2022-05-02",
        "eol": "2023-05-01",
        "latest": "24.0.12",
        "latestReleaseDate": "2023-04-19",
        "lts": False
      },
      {
        "cycle": "23",
        "releaseDate": "2021-11-26",
        "eol": "2022-12-01",
        "latest": "23.0.12",
        "latestReleaseDate": "2022-12-08",
        "lts": False
      },
      {
        "cycle": "22",
        "releaseDate": "2021-07-05",
        "eol": "2022-07-01",
        "latest": "22.2.10",
        "latestReleaseDate": "2022-07-18",
        "lts": False
      },
      {
        "cycle": "21",
        "releaseDate": "2021-02-19",
        "eol": "2022-02-01",
        "latest": "21.0.9",
        "latestReleaseDate": "2022-02-15",
        "lts": False
      },
      {
        "cycle": "20",
        "releaseDate": "2020-10-02",
        "eol": "2021-01-01",
        "latest": "20.0.14",
        "latestReleaseDate": "2021-11-11",
        "lts": False
      },
      {
        "cycle": "19",
        "releaseDate": "2020-05-26",
        "eol": "2021-06-01",
        "latest": "19.0.13",
        "latestReleaseDate": "2021-07-01",
        "lts": False
      },
      {
        "cycle": "18",
        "releaseDate": "2020-01-17",
        "eol": "2021-01-01",
        "latest": "18.0.14",
        "latestReleaseDate": "2021-01-25",
        "lts": False
      },
      {
        "cycle": "17",
        "releaseDate": "2019-09-26",
        "eol": "2020-01-01",
        "latest": "17.0.10",
        "latestReleaseDate": "2020-10-08",
        "lts": False
      },
      {
        "cycle": "16",
        "releaseDate": "2019-04-24",
        "eol": "2020-06-01",
        "latest": "16.0.11",
        "latestReleaseDate": "2020-06-04",
        "lts": False
      }
    ],


    'https://endoflife.date/api/php.json': [
      {
        "cycle": "8.2",
        "support": "2024-12-08",
        "eol": "2025-12-08",
        "latest": "8.2.8",
        "latestReleaseDate": "2023-07-06",
        "releaseDate": "2022-12-08",
        "lts": False
      },
      {
        "cycle": "8.1",
        "support": "2023-11-25",
        "eol": "2024-11-25",
        "latest": "8.1.21",
        "latestReleaseDate": "2023-07-06",
        "releaseDate": "2021-11-25",
        "lts": False
      },
      {
        "cycle": "8.0",
        "support": "2022-11-26",
        "eol": "2023-11-26",
        "latest": "8.0.29",
        "latestReleaseDate": "2023-06-08",
        "releaseDate": "2020-11-26",
        "lts": False
      },
      {
        "cycle": "7.4",
        "support": "2021-11-28",
        "eol": "2022-11-28",
        "latest": "7.4.33",
        "latestReleaseDate": "2022-11-03",
        "releaseDate": "2019-11-28",
        "lts": False
      },
      {
        "cycle": "7.3",
        "support": "2020-12-06",
        "eol": "2021-12-06",
        "latest": "7.3.33",
        "latestReleaseDate": "2021-11-18",
        "releaseDate": "2018-12-06",
        "lts": False
      },
      {
        "cycle": "7.2",
        "support": "2019-11-30",
        "eol": "2020-11-30",
        "latest": "7.2.34",
        "latestReleaseDate": "2020-10-01",
        "releaseDate": "2017-11-30",
        "lts": False
      },
      {
        "cycle": "7.1",
        "support": "2018-12-01",
        "eol": "2019-12-01",
        "latest": "7.1.33",
        "latestReleaseDate": "2019-10-24",
        "releaseDate": "2016-12-01",
        "lts": False
      },
      {
        "cycle": "7.0",
        "support": "2018-01-04",
        "eol": "2019-01-10",
        "latest": "7.0.33",
        "latestReleaseDate": "2019-01-10",
        "releaseDate": "2015-12-03",
        "lts": False
      },
      {
        "cycle": "5.6",
        "support": "2017-01-19",
        "eol": "2018-12-31",
        "latest": "5.6.40",
        "latestReleaseDate": "2019-01-10",
        "releaseDate": "2014-08-28",
        "lts": False
      },
      {
        "cycle": "5.5",
        "support": "2015-07-10",
        "eol": "2016-07-21",
        "latest": "5.5.38",
        "latestReleaseDate": "2016-07-21",
        "releaseDate": "2013-06-20",
        "lts": False
      },
      {
        "cycle": "5.4",
        "support": "2014-09-14",
        "eol": "2015-09-14",
        "latest": "5.4.45",
        "latestReleaseDate": "2015-09-03",
        "releaseDate": "2012-03-01",
        "lts": False
      },
      {
        "cycle": "5.3",
        "support": "2011-06-30",
        "eol": "2014-08-14",
        "latest": "5.3.29",
        "latestReleaseDate": "2014-08-14",
        "releaseDate": "2009-06-30",
        "lts": False
      },
      {
        "cycle": "5.2",
        "support": "2008-11-02",
        "eol": "2011-01-06",
        "latest": "5.2.17",
        "latestReleaseDate": "2011-01-06",
        "releaseDate": "2006-11-02",
        "lts": False
      },
      {
        "cycle": "5.1",
        "support": "2006-08-24",
        "eol": "2006-08-24",
        "latest": "5.1.6",
        "latestReleaseDate": "2006-08-24",
        "releaseDate": "2005-11-24",
        "lts": False
      },
      {
        "cycle": "5.0",
        "support": "2005-09-05",
        "eol": "2005-09-05",
        "latest": "5.0.5",
        "latestReleaseDate": "2005-09-05",
        "releaseDate": "2004-07-13",
        "lts": False
      }
    ],


    'https://endoflife.date/api/postfix.json': [
      {
        "cycle": "3.8",
        "releaseDate": "2023-04-17",
        "eol": False,
        "latest": "3.8.1",
        "latestReleaseDate": "2023-06-06",
        "link": "https://www.postfix.org/announcements/postfix-3.8.1.html",
        "lts": False
      },
      {
        "cycle": "3.7",
        "eol": False,
        "latest": "3.7.6",
        "latestReleaseDate": "2023-06-06",
        "releaseDate": "2022-02-06",
        "link": "https://www.postfix.org/announcements/postfix-3.8.1.html",
        "lts": False
      },
      {
        "cycle": "3.6",
        "eol": False,
        "latest": "3.6.10",
        "latestReleaseDate": "2023-06-06",
        "releaseDate": "2021-04-29",
        "link": "https://www.postfix.org/announcements/postfix-3.8.1.html",
        "lts": False
      },
      {
        "cycle": "3.5",
        "eol": False,
        "latest": "3.5.20",
        "latestReleaseDate": "2023-06-06",
        "releaseDate": "2020-03-15",
        "link": "https://www.postfix.org/announcements/postfix-3.8.1.html",
        "lts": False
      },
      {
        "cycle": "3.4",
        "eol": "2023-04-17",
        "latest": "3.4.29",
        "latestReleaseDate": "2023-04-19",
        "releaseDate": "2019-02-27",
        "link": "https://www.postfix.org/announcements/postfix-3.7.5.html",
        "lts": False
      },
      {
        "cycle": "3.3",
        "eol": "2022-02-05",
        "latest": "3.3.22",
        "latestReleaseDate": "2022-02-06",
        "releaseDate": "2018-02-22",
        "link": "https://www.postfix.org/announcements/postfix-3.6.5.html",
        "lts": False
      },
      {
        "cycle": "3.2",
        "eol": "2021-04-29",
        "latest": "3.2.22",
        "latestReleaseDate": "2021-04-12",
        "releaseDate": "2017-02-28",
        "link": "https://www.postfix.org/announcements/postfix-3.5.10.html",
        "lts": False
      },
      {
        "cycle": "3.1",
        "eol": "2020-03-15",
        "latest": "3.1.15",
        "latestReleaseDate": "2020-02-03",
        "releaseDate": "2016-02-24",
        "link": "https://www.postfix.org/announcements/postfix-3.4.9.html",
        "lts": False
      },
      {
        "cycle": "3.0",
        "eol": "2019-02-27",
        "latest": "3.0.15",
        "latestReleaseDate": "2019-02-26",
        "releaseDate": "2015-02-08",
        "link": "https://www.postfix.org/announcements/postfix-3.3.3.html",
        "lts": False
      },
      {
        "cycle": "2.11",
        "eol": "2018-02-21",
        "latest": "2.11.11",
        "latestReleaseDate": "2018-01-28",
        "releaseDate": "2014-01-15",
        "link": "https://www.postfix.org/announcements/postfix-3.2.5.html",
        "lts": False
      },
      {
        "cycle": "2.10",
        "eol": "2017-02-28",
        "latest": "2.10.10",
        "latestReleaseDate": "2016-05-15",
        "releaseDate": "2013-02-11",
        "link": "https://www.postfix.org/announcements/postfix-3.1.1.html",
        "lts": False
      },
      {
        "cycle": "2.9",
        "eol": "2016-02-24",
        "latest": "2.9.15",
        "latestReleaseDate": "2015-10-10",
        "releaseDate": "2012-02-01",
        "link": "https://www.postfix.org/announcements/postfix-3.0.3.html",
        "lts": False
      },
      {
        "cycle": "2.8",
        "eol": "2015-02-08",
        "latest": "2.8.20",
        "latestReleaseDate": "2015-02-08",
        "releaseDate": "2011-01-20",
        "link": "https://www.postfix.org/announcements/postfix-2.11.4.html",
        "lts": False
      },
      {
        "cycle": "2.6",
        "releaseDate": "2009-05-12",
        "eol": "2013-02-11",
        "latest": "2.6.19",
        "latestReleaseDate": "2013-02-04",
        "link": "https://www.postfix.org/announcements/postfix-2.9.6.html",
        "lts": False
      },
      {
        "cycle": "2.5",
        "releaseDate": "2008-01-24",
        "eol": "2012-02-06",
        "latest": "2.5.17",
        "latestReleaseDate": "2012-02-06",
        "link": "https://www.postfix.org/announcements/postfix-2.7.8.html",
        "lts": False
      }
    ],


    'https://endoflife.date/api/postgresql.json': [
      {
        "cycle": "15",
        "eol": "2027-11-11",
        "latest": "15.3",
        "latestReleaseDate": "2023-05-08",
        "releaseDate": "2022-10-10",
        "lts": False
      },
      {
        "cycle": "14",
        "eol": "2026-09-30",
        "latest": "14.8",
        "latestReleaseDate": "2023-05-08",
        "releaseDate": "2021-09-27",
        "lts": False
      },
      {
        "cycle": "13",
        "eol": "2025-11-13",
        "latest": "13.11",
        "latestReleaseDate": "2023-05-08",
        "releaseDate": "2020-09-21",
        "lts": False
      },
      {
        "cycle": "12",
        "eol": "2024-11-14",
        "latest": "12.15",
        "latestReleaseDate": "2023-05-08",
        "releaseDate": "2019-09-30",
        "lts": False
      },
      {
        "cycle": "11",
        "eol": "2023-11-09",
        "latest": "11.20",
        "latestReleaseDate": "2023-05-08",
        "releaseDate": "2018-10-15",
        "lts": False
      },
      {
        "cycle": "10",
        "eol": "2022-11-10",
        "latest": "10.23",
        "latestReleaseDate": "2022-11-07",
        "releaseDate": "2017-10-02",
        "lts": False
      },
      {
        "cycle": "9.6",
        "eol": "2021-11-11",
        "latest": "9.6.24",
        "latestReleaseDate": "2021-11-08",
        "releaseDate": "2016-09-26",
        "lts": False
      },
      {
        "cycle": "9.5",
        "eol": "2021-02-11",
        "latest": "9.5.25",
        "latestReleaseDate": "2021-02-08",
        "releaseDate": "2016-01-04",
        "lts": False
      },
      {
        "cycle": "9.4",
        "eol": "2020-02-13",
        "latest": "9.4.26",
        "latestReleaseDate": "2020-02-10",
        "releaseDate": "2014-12-15",
        "lts": False
      },
      {
        "cycle": "9.3",
        "eol": "2018-11-08",
        "latest": "9.3.25",
        "latestReleaseDate": "2018-11-05",
        "releaseDate": "2013-09-02",
        "lts": False
      },
      {
        "cycle": "9.2",
        "eol": "2017-11-09",
        "latest": "9.2.24",
        "latestReleaseDate": "2017-11-06",
        "releaseDate": "2012-09-06",
        "lts": False
      },
      {
        "cycle": "9.1",
        "eol": "2016-10-27",
        "latest": "9.1.24",
        "latestReleaseDate": "2016-10-24",
        "releaseDate": "2011-09-08",
        "lts": False
      },
      {
        "cycle": "9.0",
        "eol": "2015-10-08",
        "latest": "9.0.23",
        "latestReleaseDate": "2015-10-05",
        "releaseDate": "2010-09-17",
        "lts": False
      },
      {
        "cycle": "8.4",
        "eol": "2014-07-24",
        "latest": "8.4.22",
        "latestReleaseDate": "2014-07-21",
        "releaseDate": "2009-06-27",
        "lts": False
      },
      {
        "cycle": "8.3",
        "eol": "2013-02-07",
        "latest": "8.3.23",
        "latestReleaseDate": "2013-02-04",
        "releaseDate": "2008-02-01",
        "lts": False
      },
      {
        "cycle": "8.2",
        "eol": "2011-12-05",
        "latest": "8.2.23",
        "latestReleaseDate": "2011-12-01",
        "releaseDate": "2006-12-02",
        "lts": False
      },
      {
        "cycle": "8.1",
        "eol": "2010-11-08",
        "latest": "8.1.23",
        "latestReleaseDate": "2010-12-13",
        "releaseDate": "2005-11-05",
        "lts": False
      },
      {
        "cycle": "8.0",
        "eol": "2010-10-01",
        "latest": "8.0.26",
        "latestReleaseDate": "2010-10-01",
        "releaseDate": "2005-01-17",
        "lts": False
      }
    ],


    'https://endoflife.date/api/rhel.json': [
      {
        "cycle": "9",
        "support": "2027-05-31",
        "eol": "2032-05-31",
        "extendedSupport": "2035-05-31",
        "latest": "9.2",
        "releaseDate": "2022-05-17",
        "lts": "2032-05-31",
        "latestReleaseDate": "2023-05-10"
      },
      {
        "cycle": "8",
        "support": "2024-05-31",
        "eol": "2029-05-31",
        "extendedSupport": "2032-05-31",
        "latest": "8.8",
        "releaseDate": "2019-05-07",
        "lts": "2029-05-31",
        "latestReleaseDate": "2023-05-16"
      },
      {
        "cycle": "7",
        "support": "2019-08-06",
        "eol": "2024-06-30",
        "extendedSupport": "2028-06-30",
        "latest": "7.9",
        "releaseDate": "2013-12-11",
        "lts": "2024-06-30",
        "latestReleaseDate": "2020-09-29"
      },
      {
        "cycle": "6",
        "support": "2016-05-10",
        "eol": "2020-11-30",
        "extendedSupport": "2024-06-30",
        "releaseDate": "2010-11-09",
        "lts": "2020-11-30",
        "latestReleaseDate": "2018-06-19",
        "latest": "6.10"
      },
      {
        "cycle": "5",
        "support": "2013-01-08",
        "eol": "2017-03-31",
        "extendedSupport": "2020-11-30",
        "releaseDate": "2007-03-15",
        "lts": "2017-03-31",
        "latestReleaseDate": "2014-09-16",
        "latest": "5.11"
      },
      {
        "cycle": "4",
        "support": "2009-03-31",
        "eol": "2012-02-29",
        "extendedSupport": "2017-03-31",
        "releaseDate": "2005-02-15",
        "latestReleaseDate": "2011-02-16",
        "latest": "4.9",
        "lts": False
      }
    ],


    'https://endoflife.date/api/wordpress.json': [
      {
        "cycle": "6.3",
        "supportedPHPVersions": "7.0, 7.1, 7.2, 7.3, 7.4, 8.0, 8.1, 8.2",
        "releaseDate": "2023-08-08",
        "support": True,
        "eol": False,
        "latest": "6.3",
        "latestReleaseDate": "2023-08-08",
        "lts": False
      },
      {
        "cycle": "6.2",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0, 8.1, 8.2",
        "releaseDate": "2023-03-29",
        "support": "2023-08-08",
        "eol": False,
        "latest": "6.2.2",
        "latestReleaseDate": "2023-05-20",
        "lts": False
      },
      {
        "cycle": "6.1",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0, 8.1, 8.2",
        "releaseDate": "2022-11-02",
        "support": "2023-03-29",
        "eol": False,
        "latest": "6.1.3",
        "latestReleaseDate": "2023-05-20",
        "lts": False
      },
      {
        "cycle": "6.0",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0, 8.1",
        "releaseDate": "2022-05-24",
        "support": "2022-11-01",
        "eol": False,
        "latest": "6.0.5",
        "latestReleaseDate": "2023-05-20",
        "lts": False
      },
      {
        "cycle": "5.9",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0, 8.1",
        "releaseDate": "2022-01-25",
        "support": "2022-05-24",
        "eol": False,
        "latest": "5.9.7",
        "latestReleaseDate": "2023-05-20",
        "lts": False
      },
      {
        "cycle": "5.8",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0",
        "releaseDate": "2021-07-20",
        "support": "2022-01-25",
        "eol": False,
        "latest": "5.8.7",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.7",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0",
        "releaseDate": "2021-03-09",
        "support": "2021-07-20",
        "eol": False,
        "latest": "5.7.9",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.6",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0",
        "releaseDate": "2020-12-08",
        "support": "2021-03-09",
        "eol": False,
        "latest": "5.6.11",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.5",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4",
        "releaseDate": "2020-08-11",
        "support": "2020-12-08",
        "eol": False,
        "latest": "5.5.12",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.4",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4",
        "releaseDate": "2020-03-31",
        "support": "2020-08-11",
        "eol": False,
        "latest": "5.4.13",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.3",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3, 7.4",
        "releaseDate": "2019-11-12",
        "support": "2020-03-31",
        "eol": False,
        "latest": "5.3.15",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.2",
        "supportedPHPVersions": "5.6, 7.0, 7.1, 7.2, 7.3",
        "releaseDate": "2019-05-07",
        "support": "2019-11-12",
        "eol": False,
        "latest": "5.2.18",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.1",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0, 7.1, 7.2, 7.3",
        "releaseDate": "2019-02-21",
        "support": "2019-05-07",
        "eol": False,
        "latest": "5.1.16",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "5.0",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0, 7.1, 7.2, 7.3",
        "releaseDate": "2018-12-06",
        "support": "2019-02-21",
        "eol": False,
        "latest": "5.0.19",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.9",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0, 7.1, 7.2",
        "releaseDate": "2017-11-16",
        "support": "2018-12-06",
        "eol": False,
        "latest": "4.9.23",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.8",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0, 7.1",
        "releaseDate": "2017-06-08",
        "support": "2017-11-16",
        "eol": False,
        "latest": "4.8.22",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.7",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0, 7.1",
        "releaseDate": "2016-12-06",
        "support": "2017-06-08",
        "eol": False,
        "latest": "4.7.26",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.6",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0",
        "releaseDate": "2016-08-16",
        "support": "2016-12-06",
        "eol": False,
        "latest": "4.6.26",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.5",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0",
        "releaseDate": "2016-04-12",
        "support": "2016-08-16",
        "eol": False,
        "latest": "4.5.29",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.4",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6, 7.0",
        "releaseDate": "2015-12-09",
        "support": "2016-04-12",
        "eol": False,
        "latest": "4.4.30",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.3",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6",
        "releaseDate": "2015-08-18",
        "support": "2015-12-08",
        "eol": False,
        "latest": "4.3.31",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.2",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6",
        "releaseDate": "2015-04-23",
        "support": "2015-08-18",
        "eol": False,
        "latest": "4.2.35",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.1",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5, 5.6",
        "releaseDate": "2014-12-18",
        "support": "2015-04-23",
        "eol": False,
        "latest": "4.1.38",
        "latestReleaseDate": "2023-05-16",
        "lts": False
      },
      {
        "cycle": "4.0",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5",
        "releaseDate": "2014-09-04",
        "support": "2014-12-18",
        "eol": "2022-12-01",
        "latest": "4.0.38",
        "latestReleaseDate": "2022-11-30",
        "lts": False
      },
      {
        "cycle": "3.9",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5",
        "releaseDate": "2014-04-16",
        "support": "2014-09-04",
        "eol": "2022-12-01",
        "latest": "3.9.40",
        "latestReleaseDate": "2022-11-30",
        "lts": False
      },
      {
        "cycle": "3.8",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5",
        "releaseDate": "2013-12-12",
        "support": "2014-04-16",
        "eol": "2022-12-01",
        "latest": "3.8.41",
        "latestReleaseDate": "2022-11-30",
        "lts": False
      },
      {
        "cycle": "3.7",
        "supportedPHPVersions": "5.2, 5.3, 5.4, 5.5",
        "releaseDate": "2013-10-24",
        "support": "2013-12-12",
        "eol": "2022-12-01",
        "latest": "3.7.41",
        "latestReleaseDate": "2022-11-30",
        "lts": False
      },
      {
        "cycle": "3.6",
        "releaseDate": "2013-08-01",
        "support": "2013-10-24",
        "eol": "2013-10-24",
        "latest": "3.6.1",
        "latestReleaseDate": "2013-09-11",
        "lts": False
      }
    ],

}
