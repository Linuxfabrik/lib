#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This library parses data returned from the Redfish API."""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026071404'

import base64
import json
import urllib.parse

from . import base, cache, human, time, txt, url
from .globals import STATE_CRIT, STATE_OK, STATE_WARN

# Shared cache database filename for the Redfish fetch layer. The fetch helpers below cache by URL,
# but only when a caller opts in by passing a non-zero `cache_expire` (the plugins pass one); with
# the default `cache_expire=0` they fetch straight through and touch no cache. Several checks read
# the same data from one controller each cycle (its session token, its `$expand` support, the
# Systems or Managers collection and their members), so the first check to miss the cache fetches
# and fills it and every sibling check reuses the entry instead of hitting the controller again.
# Kept out of the default cache database so those response bodies do not mingle with other cached
# data. Named here so every plugin and this library agree on the same file and can share entries.
CACHE_FILENAME = 'linuxfabrik-monitoring-plugins-redfish.db'

# Upper bound for the Redfish `$expand` `$levels` we ask for, even when a controller advertises a
# higher `MaxLevels`. A single deeply expanded document already inlines every member a check reads;
# going deeper only inflates the response (and the controller's work) without a caller that needs
# it. Three levels reach the deepest tree we walk (Systems -> Storage -> Drives/Volumes).
MAX_EXPAND_LEVELS = 3

# `$expand` suffix used when the controller does not advertise its expand support (or the service
# root cannot be read): ask for one level of subordinate members. `fetch_collection()` falls back
# to a plain request if the controller rejects it, so this stays safe on controllers without
# `$expand`.
DEFAULT_EXPAND = '?$expand=.($levels=1)'

CHASSIS_FAN_KEYS = (
    'FanName',
    'HotPluggable',
    'LowerThresholdCritical',
    'LowerThresholdFatal',
    'LowerThresholdNonCritical',
    'Name',
    'PhysicalContext',
    'Reading',
    'ReadingUnits',
    'SensorNumber',
    'UpperThresholdCritical',
    'UpperThresholdFatal',
    'UpperThresholdNonCritical',
)

CHASSIS_FAN_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_KEYS = (
    'AssetTag',
    'ChassisType',
    'Id',
    'IndicatorLED',
    'Manufacturer',
    'Model',
    'PartNumber',
    'PowerState',
    'SerialNumber',
    'SKU',
)

CHASSIS_NESTED_KEYS = {
    'Sensors_@odata.id': ('Sensors', '@odata.id'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

CHASSIS_POWER_CONTROL_KEYS = (
    'MemberId',
    'Name',
    'PowerCapacityWatts',
    'PowerConsumedWatts',
)

CHASSIS_POWER_CONTROL_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_POWER_KEYS = (
    'FirmwareVersion',
    'LastPowerOutputWatts',
    'LineInputVoltage',
    'LineInputVoltageType',
    'Manufacturer',
    'Model',
    'PartNumber',
    'PowerCapacityWatts',
    'PowerSupplyType',
    'SerialNumber',
    'SparePartNumber',
)

CHASSIS_POWER_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_SENSOR_KEYS = (
    'Id',
    'Name',
    'PhysicalContext',
    'Reading',
    'ReadingRangeMax',
    'ReadingRangeMin',
    'ReadingUnits',
)

CHASSIS_SENSOR_NESTED_KEYS = {
    'Thresholds_LowerCaution': ('Thresholds', 'LowerCaution', 'Reading'),
    'Thresholds_LowerCautionUser': ('Thresholds', 'LowerCautionUser', 'Reading'),
    'Thresholds_LowerCritical': ('Thresholds', 'LowerCritical', 'Reading'),
    'Thresholds_LowerCriticalUser': ('Thresholds', 'LowerCriticalUser', 'Reading'),
    'Thresholds_UpperCaution': ('Thresholds', 'UpperCaution', 'Reading'),
    'Thresholds_UpperCautionUser': ('Thresholds', 'UpperCautionUser', 'Reading'),
    'Thresholds_UpperCritical': ('Thresholds', 'UpperCritical', 'Reading'),
    'Thresholds_UpperCriticalUser': ('Thresholds', 'UpperCriticalUser', 'Reading'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

CHASSIS_THERMAL_REDUNDANCY_KEYS = ('Mode', 'Name')

CHASSIS_THERMAL_REDUNDANCY_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_THERMAL_TEMP_KEYS = (
    'LowerThresholdCritical',
    'LowerThresholdFatal',
    'LowerThresholdNonCritical',
    'Name',
    'PhysicalContext',
    'ReadingCelsius',
    'UpperThresholdCritical',
    'UpperThresholdFatal',
    'UpperThresholdNonCritical',
)

CHASSIS_THERMAL_TEMP_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

CHASSIS_VOLTAGE_KEYS = (
    'LowerThresholdCritical',
    'LowerThresholdFatal',
    'LowerThresholdNonCritical',
    'Name',
    'PhysicalContext',
    'ReadingVolts',
    'UpperThresholdCritical',
    'UpperThresholdFatal',
    'UpperThresholdNonCritical',
)

CHASSIS_VOLTAGE_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
}

ETHERNET_KEYS = (
    'Description',
    'FQDN',
    'FullDuplex',
    'HostName',
    'Id',
    'LinkStatus',
    'MACAddress',
    'Name',
    'PermanentMACAddress',
    'SpeedMbps',
)

ETHERNET_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

FIRMWARE_KEYS = (
    'Id',
    'Manufacturer',
    'Name',
    'ReleaseDate',
    'SoftwareId',
    'Updateable',
    'Version',
)

FIRMWARE_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

MANAGER_KEYS = (
    'FirmwareVersion',
    'Id',
    'ManagerType',
    'Model',
    'Name',
    'PowerState',
    'UUID',
)

MANAGER_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

MEMORY_KEYS = (
    'BaseModuleType',
    'CapacityMiB',
    'ErrorCorrection',
    'Id',
    'Manufacturer',
    'MemoryDeviceType',
    'MemoryType',
    'Name',
    'OperatingSpeedMhz',
    'PartNumber',
    'RankCount',
    'SerialNumber',
)

MEMORY_NESTED_KEYS = {
    'Location_ServiceLabel': ('Location', 'PartLocation', 'ServiceLabel'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

# Some controllers leave the standard Status.State/Health empty on memory
# modules and report the real condition only in an OEM-specific field. These
# tables fold those vendor operational values back onto the standard Redfish
# vocabulary so the generic get_state() can evaluate them. Modules in an absent
# state are skipped by the callers; healthy operational states map to "Enabled",
# everything else is surfaced as a problem.
MEMORY_OEM_ABSENT_STATES = ('Absent', 'EmptyOrNotInstalled', 'NotPresent')
MEMORY_OEM_HEALTHY_HEALTH = ('enabled', 'nominal', 'ok')
MEMORY_OEM_HEALTHY_STATES = ('Enabled', 'GoodInUse', 'Operable', 'Quiesced')

PROCESSOR_KEYS = (
    'Id',
    'InstructionSet',
    'Manufacturer',
    'MaxSpeedMHz',
    'Model',
    'Name',
    'ProcessorArchitecture',
    'ProcessorType',
    'Socket',
    'TotalCores',
    'TotalThreads',
)

PROCESSOR_NESTED_KEYS = {
    'Location_ServiceLabel': ('Location', 'PartLocation', 'ServiceLabel'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

SEVERITY_TO_STATE = {
    'critical': STATE_CRIT,
    'warning': STATE_WARN,
}

SYSTEMS_KEYS = (
    'BiosVersion',
    'HostName',
    'Id',
    'IndicatorLED',
    'Manufacturer',
    'Model',
    'PowerState',
    'SerialNumber',
    'SKU',
)

SYSTEMS_NESTED_KEYS = {
    'EthernetInterfaces_@odata.id': ('EthernetInterfaces', '@odata.id'),
    'Memory_@odata.id': ('Memory', '@odata.id'),
    'Processors_@odata.id': ('Processors', '@odata.id'),
    'ProcessorSummary_Count': ('ProcessorSummary', 'Count'),
    'ProcessorSummary_LogicalProcessorCount': (
        'ProcessorSummary',
        'LogicalProcessorCount',
    ),
    'ProcessorSummary_Model': ('ProcessorSummary', 'Model'),
    'Storage_@odata.id': ('Storage', '@odata.id'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

SYSTEMS_STORAGE_DRIVES_KEYS = (
    'BlockSizeBytes',
    'CapableSpeedGbs',
    'Description',
    'EncryptionAbility',
    'EncryptionStatus',
    'FailurePredicted',
    'HotspareType',
    'Id',
    'Manufacturer',
    'MediaType',
    'Model',
    'Name',
    'NegotiatedSpeedGbs',
    'PartNumber',
    'PowerOnHours',
    'PredictedMediaLifeLeftPercent',
    'Protocol',
    'Revision',
    'RotationSpeedRPM',
    'SerialNumber',
    'WriteCacheEnabled',
)

SYSTEMS_STORAGE_DRIVES_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

SYSTEMS_STORAGE_KEYS = ('Description', 'Drives@odata.count', 'Id', 'Name')

SYSTEMS_STORAGE_NESTED_KEYS = {
    'Volumes_@odata.id': ('Volumes', '@odata.id'),
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}

VOLUME_KEYS = (
    'CapacityBytes',
    'Encrypted',
    'Id',
    'Name',
    'RAIDType',
    'VolumeType',
)

VOLUME_NESTED_KEYS = {
    'Status_State': ('Status', 'State'),
    'Status_Health': ('Status', 'Health'),
    'Status_HealthRollup': ('Status', 'HealthRollup'),
}


def _cache_read(cache_key, cache_expire, cache_filename):
    """Return the cached JSON value stored under `cache_key`, or `None` on a miss.

    Returns `None` when caching is off (`cache_expire` is `0`) or the key is absent, so callers
    treat both the same and fetch. A stored value is deserialized from JSON before it is returned.
    """
    if not cache_expire:
        return None
    cached = cache.get(cache_key, filename=cache_filename)
    return json.loads(cached) if cached else None


def _cache_write(data, cache_key, cache_expire, cache_filename):
    """Store `data` as JSON under `cache_key` for `cache_expire` seconds, when caching is on.

    A no-op when caching is off (`cache_expire` is `0`) or `data` is not a JSON-serializable
    container, so a failed fetch never poisons the cache.
    """
    if cache_expire and isinstance(data, (dict, list)):
        cache.set(
            cache_key,
            json.dumps(data),
            time.now() + cache_expire,
            filename=cache_filename,
        )


# The "Status" property is common to many Redfish schema, and contains:
#
#   Health: This represents the health state of this resource in the absence
#           of its dependent resources
#   * Critical  A critical condition exists that requires immediate attention.
#   * OK        Normal.
#   * Warning   A condition exists that requires attention
#
#   HealthRollup: This represents the overall health state from the view of this
#                 resource
#   * Critical  A critical condition exists that requires immediate attention.
#   * OK        Normal.
#   * Warning   A condition exists that requires attention.
#
#   State:
#   * Absent                This function or resource is not present or not detected.
#   * Deferring             The element will not process any commands but will queue new
#                           requests.
#   * Disabled              This function or resource has been disabled.
#   * Enabled               This function or resource has been enabled.
#   * InTest                This function or resource is undergoing testing.
#   * Quiesced              The element is enabled but only processes a restricted set of
#                           commands.
#   * StandbyOffline        This function or resource is enabled, but awaiting an external action to
#                           activate it.
#   * StandbySpare          This function or resource is part of a redundancy set and is awaiting a
#                           failover or other external action to activate it.
#   * Starting              This function or resource is starting.
#   * UnavailableOffline    This function or resource is present but cannot be used.
#   * Updating              The element is updating and may be unavailable or degraded.


def build_url(base_url, odata_id):
    """
    Build an absolute Redfish URL from the operator-supplied base URL and a server-supplied
    `@odata.id` link, always taking scheme and host from the base URL.

    Redfish responses reference sub-resources by an `@odata.id` field that is expected to be a
    server-relative path such as `/redfish/v1/Systems/1`. Concatenating it onto the base URL
    without validation lets a malicious or compromised controller inject a different authority
    (for example an `@host` userinfo prefix that turns `https://bmc` + `@evil/x` into
    `https://bmc@evil/x`), turning the next authenticated request into a server-side request
    forgery that also forwards the Redfish auth header to the attacker-chosen host
    (CWE-918/CWE-20). This helper rejects any `@odata.id` that is not a single-slash-rooted
    relative path and pins scheme and host to `base_url`, so a response can never redirect the
    request to another host.

    ### Parameters
    - **base_url** (`str`): The operator-supplied Redfish base URL, e.g. `https://bmc`.
    - **odata_id** (`str`): The `@odata.id` value taken from the controller's response.

    ### Returns
    - **tuple** (`bool`, `str`):
      - `(True, url)` with the safe absolute URL on success.
      - `(False, error)` if `odata_id` is not a server-relative path.

    ### Example
    >>> build_url('https://bmc', '/redfish/v1/Systems/1')
    (True, 'https://bmc/redfish/v1/Systems/1')
    >>> build_url('https://bmc', '@evil.example.com/x')
    (False, "Refusing non-relative Redfish @odata.id link: '@evil.example.com/x'")
    """
    if (
        not isinstance(odata_id, str)
        or not odata_id.startswith('/')
        or odata_id.startswith('//')
    ):
        return False, f'Refusing non-relative Redfish @odata.id link: {odata_id!r}'
    parts = urllib.parse.urlsplit(base_url)
    return True, f'{parts.scheme}://{parts.netloc}{odata_id}'


def fetch_collection(
    collection_url,
    expand=DEFAULT_EXPAND,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Fetch a Redfish collection, asking the controller to inline its members in one request.

    A Redfish collection (for example `Sensors`, `Memory`, `Drives` or `FirmwareInventory`) lists
    its members as bare `@odata.id` references, so reading every member classically costs one
    request for the collection plus one request per member. On a controller with dozens of members
    that fan-out dominates the check runtime and, on a slow management controller, can exceed the
    monitoring server's check timeout.

    This helper appends the Redfish `$expand` query `expand` (default: one level of subordinate
    members), which asks the controller to return the full member objects inline. When the
    controller honours it, the whole collection is read in a single request; callers detect the
    inlined members with `is_member_expanded()` and skip the per-member requests. When the
    controller rejects `$expand` (some implementations answer with an HTTP error), this helper
    transparently retries the plain request, so the returned document is the same either way, just
    without the inlined members.

    Callers pass the `expand` suffix that `get_expand_suffix()` derived from the controller's
    advertised support, so a single request inlines as much of the subtree as the controller can.

    When `cache_expire` is non-zero the parsed collection is cached under `redfish-<collection_url>`
    (keyed by the plain URL, not the `$expand` variant) and reused by any sibling check reading the
    same collection within the window, so identical reads across a host's Redfish checks hit the
    cache instead of the controller. A failed fetch is never cached.

    ### Parameters
    - **collection_url** (`str`): The absolute URL of the collection resource, as produced by
      `build_url()`. Must not already carry a query string.
    - **expand** (`str`, optional): The `$expand` query suffix to append (default `DEFAULT_EXPAND`).
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **tuple** (`bool`, `dict` | `str`):
      - `(True, collection)` with the parsed collection document on success. Its `Members` may or
        may not be expanded, depending on controller support.
      - `(False, error)` if the collection cannot be read even without `$expand`.

    ### Example
    >>> success, collection = fetch_collection('https://bmc/redfish/v1/Chassis/1U/Sensors')
    >>> members = collection.get('Members', [])
    """
    cache_key = f'redfish-{collection_url}'
    cached = _cache_read(cache_key, cache_expire, cache_filename)
    if cached is not None:
        return True, cached
    # `expand` is the `$expand` query suffix (default: one level of subordinate members). It is
    # derived from the controller's advertised expand support by `get_expand_suffix()`, so it is
    # our own literal and cannot smuggle in a different authority the way an `@odata.id` could.
    success, collection = url.fetch_json(
        f'{collection_url}{expand}',
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        retries=retries,
    )
    if not (success and isinstance(collection, dict)):
        # controller rejected or could not answer the $expand query: read it plainly
        success, collection = url.fetch_json(
            collection_url,
            header=header,
            insecure=insecure,
            no_proxy=no_proxy,
            timeout=timeout,
            retries=retries,
        )
    if success and isinstance(collection, dict):
        _cache_write(collection, cache_key, cache_expire, cache_filename)
        return True, collection
    return success, collection


def fetch_members(
    members,
    base_url,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Return every member reference of a Redfish collection as a fully populated dict.

    A collection lists its members as reference stubs (`{"@odata.id": "..."}`). With the Redfish
    `$expand` query (see `fetch_collection()`) the controller inlines the full member objects
    instead. This helper accepts either form and normalizes it: members that already arrived
    expanded are returned untouched, and members that are still bare references are fetched
    individually. It also accepts inline reference arrays that are not part of a collection's
    `Members` list, such as a storage member's `Drives` array.

    Each follow-up request goes through `build_url()`, so a malicious or compromised controller
    cannot redirect it to another host (see `build_url()` for the SSRF rationale).

    When `cache_expire` is non-zero each fetched member is cached under `redfish-<member_url>` and
    reused by any sibling check that reads the same member within the window. On a controller without
    `$expand` support several checks otherwise re-fetch the same members every cycle, so this is what
    keeps a fleet of Redfish checks from hammering the controller. Already-inlined members are not
    re-cached (they came from an already-cached collection), and a failed fetch is never cached.

    ### Parameters
    - **members** (`list`): The member references, e.g. `collection.get('Members', [])` or a
      storage member's `Drives` list. Each item is a dict, expanded or a bare `@odata.id` stub.
    - **base_url** (`str`): The operator-supplied Redfish base URL, used to pin the host of every
      follow-up request.
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **tuple** (`bool`, `list` | `str`):
      - `(True, [member_dict, ...])` on success (the list is empty when `members` is empty).
      - `(False, error)` if a bare reference is malformed or cannot be fetched.

    ### Example
    >>> success, collection = fetch_collection('https://bmc/redfish/v1/Chassis/1U/Sensors')
    >>> success, sensors = fetch_members(collection.get('Members', []), 'https://bmc')
    """
    result = []
    for member in members:
        if not isinstance(member, dict):
            continue
        if is_member_expanded(member):
            # the controller already inlined this member via $expand
            result.append(member)
            continue
        # bare reference: fetch the member individually, pinning the host
        success, member_url = build_url(base_url, member.get('@odata.id'))
        if not success:
            return False, member_url
        cache_key = f'redfish-{member_url}'
        member_data = _cache_read(cache_key, cache_expire, cache_filename)
        if member_data is None:
            success, member_data = url.fetch_json(
                member_url,
                header=header,
                insecure=insecure,
                no_proxy=no_proxy,
                timeout=timeout,
                retries=retries,
            )
            if not success or not isinstance(member_data, dict):
                return False, member_data
            _cache_write(member_data, cache_key, cache_expire, cache_filename)
        result.append(member_data)
    return True, result


def fetch_resource(
    resource_url,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Fetch a single Redfish resource by URL, optionally serving and filling a shared cache.

    Unlike `fetch_collection()` this adds no `$expand` query; it is for reading an individual
    resource such as the service root a caller inspects to detect the controller vendor. When
    `cache_expire` is non-zero the parsed document is cached under `redfish-<resource_url>` and
    reused by any sibling check that reads the same URL within the window, so identical reads across
    a host's Redfish checks hit the cache instead of the controller. A failed fetch is never cached.

    ### Parameters
    - **resource_url** (`str`): The absolute URL of the resource.
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **tuple** (`bool`, `dict` | `str`):
      - `(True, resource)` with the parsed resource document on success.
      - `(False, error)` if the resource cannot be read.

    ### Example
    >>> success, root = fetch_resource('https://bmc/redfish/v1/')
    """
    cache_key = f'redfish-{resource_url}'
    cached = _cache_read(cache_key, cache_expire, cache_filename)
    if cached is not None:
        return True, cached
    success, resource = url.fetch_json(
        resource_url,
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        retries=retries,
    )
    if success and isinstance(resource, dict):
        _cache_write(resource, cache_key, cache_expire, cache_filename)
    return success, resource


def get_auth_header(args, cache_expire=0, cache_filename=CACHE_FILENAME):
    """
    Build the authentication header for Redfish API requests, reusing a cached session token.

    Redfish supports two authentication schemes: HTTP Basic auth (credentials are sent on every
    request) and session-based auth (a token is obtained once from the SessionService and then
    presented as `X-Auth-Token`). Some management controllers create and log a new internal
    session for every Basic-auth request, which floods their session table or audit log. To avoid
    that, this function establishes a session once and, when `cache_expire` is non-zero, caches the
    token under `redfish-<URL>-<USERNAME>-token` so this run's later requests and the sibling
    Redfish checks on the host present the same token instead of each creating a new session.

    It degrades gracefully: when a session cannot be created (e.g. the implementation does not
    offer the SessionService) it falls back to HTTP Basic auth, and when no credentials are given
    (e.g. against an anonymous mockup) it returns an empty header. Only the session token is cached;
    the Basic and empty headers carry no token.

    The cached token's lifetime is bounded by the controller's own `SessionTimeout` (an inactivity
    timeout in seconds, read back from the SessionService) minus a `TIMEOUT`-sized safety margin, so
    a token is never reused after the controller would already have dropped the session, which
    otherwise surfaces as a "401 Unauthorized". `cache_expire` caps that lifetime from above; the
    effective lifetime is the smaller of the two. When caching is off (`cache_expire` is `0`) the
    SessionService is not even probed, since there is no lifetime to bound.

    ### Parameters
    - **args** (object): must provide `URL`, `USERNAME`, `PASSWORD`, `INSECURE`, `NO_PROXY` and
      `TIMEOUT`.
    - **cache_expire** (`int`, optional): Token cache lifetime cap in seconds; `0` (default) fetches
      a fresh session and does not cache the token.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **dict**: a header fragment to merge into the request headers, one of
      `{'X-Auth-Token': '...'}`, `{'Authorization': 'Basic ...'}` or `{}`.

    ### Example
    >>> header = {'Accept': 'application/json'}
    >>> header.update(get_auth_header(args, cache_expire=300))
    """
    if not (args.USERNAME and args.PASSWORD):
        return {}

    token_key = f'redfish-{args.URL}-{args.USERNAME}-token'
    if cache_expire:
        cached_token = cache.get(token_key, filename=cache_filename)
        if cached_token:
            return {'X-Auth-Token': cached_token}

    # no cached token: create a new session via the SessionService
    success, result = url.fetch_json(
        f'{args.URL}/redfish/v1/SessionService/Sessions',
        data={'UserName': args.USERNAME, 'Password': args.PASSWORD},
        encoding='serialized-json',
        extended=True,
        header={'Accept': 'application/json', 'Content-Type': 'application/json'},
        insecure=args.INSECURE,
        no_proxy=args.NO_PROXY,
        timeout=args.TIMEOUT,
        method='POST',
    )
    # lib.url lower-cases all response header names (RFC 9110, section 5.1).
    token = ''
    if success and isinstance(result, dict):
        token = result.get('response_header', {}).get('x-auth-token', '')
    if token:
        if cache_expire:
            # Bound the cached token's lifetime by the controller's own inactivity
            # timeout (SessionTimeout, in seconds) so a sibling check never reuses
            # the token after the controller would already have dropped the
            # session. cache_expire caps it from above.
            token_ttl = cache_expire
            success, result = url.fetch_json(
                f'{args.URL}/redfish/v1/SessionService',
                encoding='serialized-json',
                header={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'X-Auth-Token': token,
                },
                insecure=args.INSECURE,
                no_proxy=args.NO_PROXY,
                timeout=args.TIMEOUT,
            )
            session_timeout = 0
            if success and isinstance(result, dict):
                try:
                    session_timeout = int(result.get('SessionTimeout') or 0)
                except (TypeError, ValueError):
                    session_timeout = 0
            if session_timeout > 0:
                # Subtract a TIMEOUT-sized margin so a token cached at the very edge
                # of the window still reaches the controller before it drops the
                # session. Never drop below one second.
                token_ttl = min(token_ttl, max(session_timeout - args.TIMEOUT, 1))
            cache.set(
                token_key, token, time.now() + token_ttl, filename=cache_filename
            )
        return {'X-Auth-Token': token}

    # session creation failed: fall back to HTTP Basic auth
    encoded = txt.to_text(
        base64.b64encode(txt.to_bytes(f'{args.USERNAME}:{args.PASSWORD}'))
    )
    return {'Authorization': f'Basic {encoded}'}


def get_chassis(redfish):
    """
    Extract chassis information from a Redfish API response.

    This function retrieves specific chassis details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish chassis data.

    ### Returns
    - **dict**: A dictionary containing the following chassis details:
      - **AssetTag** (`str`): The asset tag of the chassis.
      - **ChassisType** (`str`): The type of the chassis.
      - **Id** (`str`): The ID of the chassis.
      - **IndicatorLED** (`str`): The status of the indicator LED.
      - **Manufacturer** (`str`): The manufacturer of the chassis.
      - **Model** (`str`): The model of the chassis.
      - **PartNumber** (`str`): The part number of the chassis.
      - **PowerState** (`str`): The power state of the chassis (e.g., "On").
      - **SerialNumber** (`str`): The serial number of the chassis.
      - **SKU** (`str`): The SKU of the chassis.
      - **Sensors_@odata.id** (`str`): The sensors' OData ID.
      - **Status_State** (`str`): The state of the chassis (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the chassis (e.g., "OK").
      - **Status_HealthRollup** (`str`): The health rollup status of the chassis (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'AssetTag': '12345',
    ...     'ChassisType': 'Rackmount',
    ...     'Id': '1',
    ...     'PowerState': 'On',
    ... }
    >>> get_chassis(redfish_data)
    {'AssetTag': '12345', 'ChassisType': 'Rackmount', 'Id': '1', 'PowerState': 'On', ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_KEYS}
    for output_key, (parent_key, child_key) in CHASSIS_NESTED_KEYS.items():
        data[output_key] = redfish.get(parent_key, {}).get(child_key, '')
    return data


def get_chassis_power_powercontrol(redfish):
    """
    Extract power control (overall power consumption) information from a Redfish API response.

    The legacy Power resource exposes one or more `PowerControl` entries that report the aggregate
    power consumption of the chassis. This function projects a single such entry into a flat
    dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing a single Redfish `PowerControl` entry.

    ### Returns
    - **dict**: A dictionary containing the following power control details:
      - **MemberId** (`str`): The identifier of the power control entry.
      - **Name** (`str`): The name of the power control entry.
      - **PowerCapacityWatts** (`str`): The total power capacity in watts.
      - **PowerConsumedWatts** (`str`): The currently consumed power in watts.
      - **Status_State** (`str`): The state of the power control entry (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the power control entry (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Name': 'System Power Control',
    ...     'PowerConsumedWatts': 344,
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_chassis_power_powercontrol(redfish_data)
    {'Name': 'System Power Control', 'PowerConsumedWatts': 344, ..., 'Status_State': 'Enabled', ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_POWER_CONTROL_KEYS}

    for out_key, path in CHASSIS_POWER_CONTROL_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_chassis_power_powersupplies(redfish):
    """
    Extract power supply information from a Redfish API response.

    This function retrieves specific power supply details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish power supply data.

    ### Returns
    - **dict**: A dictionary containing the following power supply details:
      - **FirmwareVersion** (`str`): The firmware version of the power supply.
      - **LastPowerOutputWatts** (`str`): The last reported power output in watts.
      - **LineInputVoltage** (`str`): The input voltage of the power supply.
      - **LineInputVoltageType** (`str`): The type of input voltage.
      - **Manufacturer** (`str`): The manufacturer of the power supply.
      - **Model** (`str`): The model of the power supply.
      - **PartNumber** (`str`): The part number of the power supply.
      - **PowerCapacityWatts** (`str`): The power capacity of the power supply in watts.
      - **PowerSupplyType** (`str`): The type of power supply.
      - **SerialNumber** (`str`): The serial number of the power supply.
      - **SparePartNumber** (`str`): The spare part number of the power supply.
      - **Status_State** (`str`): The state of the power supply (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the power supply (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'FirmwareVersion': '1.0',
    ...     'LastPowerOutputWatts': 200,
    ...     'PowerCapacityWatts': 500,
    ... }
    >>> get_chassis_power_powersupplies(redfish_data)
    {'FirmwareVersion': '1.0', 'LastPowerOutputWatts': 200, 'PowerCapacityWatts': 500, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_POWER_KEYS}
    if data['LastPowerOutputWatts'] in ('', None):
        data['LastPowerOutputWatts'] = redfish.get('PowerOutputWatts', '')

    for output_key, (parent_key, child_key) in CHASSIS_POWER_NESTED_KEYS.items():
        data[output_key] = redfish.get(parent_key, {}).get(child_key, '')

    return data


def get_chassis_power_voltages(redfish):
    """
    Extract power voltage information from a Redfish API response.

    This function retrieves specific power voltage details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish power voltage data.

    ### Returns
    - **dict**: A dictionary containing the following power voltage details:
      - **LowerThresholdCritical** (`str`): The critical lower threshold voltage.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold voltage.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold voltage.
      - **Name** (`str`): The name of the voltage.
      - **PhysicalContext** (`str`): The physical context of the voltage.
      - **ReadingVolts** (`str`): The current voltage reading.
      - **UpperThresholdCritical** (`str`): The critical upper threshold voltage.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold voltage.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold voltage.
      - **Status_State** (`str`): The state of the voltage (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the voltage (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'LowerThresholdCritical': 10,
    ...     'ReadingVolts': 12,
    ...     'UpperThresholdCritical': 15,
    ... }
    >>> get_chassis_power_voltages(redfish_data)
    {'LowerThresholdCritical': 10, 'ReadingVolts': 12, 'UpperThresholdCritical': 15, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_VOLTAGE_KEYS}

    for output_key, (parent_key, child_key) in CHASSIS_VOLTAGE_NESTED_KEYS.items():
        data[output_key] = redfish.get(parent_key, {}).get(child_key, '')

    return data


def get_chassis_sensors(redfish):
    """
    Extract sensor information from a Redfish API response.

    This function retrieves specific sensor details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish sensor data.

    ### Returns
    - **dict**: A dictionary containing the following sensor details:
      - **Id** (`str`): The ID of the sensor.
      - **Name** (`str`): The name of the sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **Reading** (`str`): The current reading of the sensor.
      - **ReadingRangeMax** (`str`): The maximum reading range of the sensor.
      - **ReadingRangeMin** (`str`): The minimum reading range of the sensor.
      - **ReadingUnits** (`str`): The units of the sensor reading.
      - **Thresholds_LowerCaution** (`str`): The lower caution threshold for the sensor.
      - **Thresholds_LowerCritical** (`str`): The lower critical threshold for the sensor.
      - **Thresholds_UpperCaution** (`str`): The upper caution threshold for the sensor.
      - **Thresholds_UpperCritical** (`str`): The upper critical threshold for the sensor.
      - **Status_State** (`str`): The state of the sensor (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the sensor (e.g., "OK").
      - **Status_HealthRollup** (`str`): The health rollup status of the sensor (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Id': 'sensor1',
    ...     'Reading': 75,
    ...     'ReadingRangeMax': 100,
    ...     'Thresholds_LowerCaution': 30,
    ... }
    >>> get_chassis_sensors(redfish_data)
    {'Id': 'sensor1', 'Reading': 75, 'ReadingRangeMax': 100, 'Thresholds_LowerCaution': 30, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_SENSOR_KEYS}

    for out_key, path in CHASSIS_SENSOR_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_chassis_thermal_fans(redfish):
    """
    Extract thermal fan information from a Redfish API response.

    This function retrieves specific thermal fan details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal fan data.

    ### Returns
    - **dict**: A dictionary containing the following thermal fan details:
      - **FanName** (`str`): The name of the fan.
      - **HotPluggable** (`str`): Indicates if the fan is hot pluggable.
      - **LowerThresholdCritical** (`str`): The critical lower threshold for the fan's reading.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold for the fan's reading.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold for the fan's
         reading.
      - **Name** (`str`): The name of the sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **Reading** (`str`): The current reading of the fan.
      - **ReadingUnits** (`str`): The units of the fan's reading.
      - **SensorNumber** (`str`): The number of the fan's sensor.
      - **UpperThresholdCritical** (`str`): The critical upper threshold for the fan's reading.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold for the fan's reading.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold for the fan's
         reading.
      - **Status_State** (`str`): The state of the fan (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the fan (e.g., "OK").

    ### Example
    >>> redfish_data = {'FanName': 'Fan1', 'Reading': 80, 'UpperThresholdCritical': 100}
    >>> get_chassis_thermal_fans(redfish_data)
    {'FanName': 'Fan1', 'Reading': 80, 'UpperThresholdCritical': 100, ...}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_FAN_KEYS}

    for out_key, path in CHASSIS_FAN_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    # vendor quirk: Dell, Fujitsu and Huawei report fan speed in RPM under
    # "ReadingRPM"; HP and Lenovo report a percentage. Normalize both onto
    # Reading / ReadingUnits so get_perfdata() and the table see one shape.
    if redfish.get('ReadingRPM') is not None or redfish.get('ReadingUnits') == 'RPM':
        reading = redfish.get('ReadingRPM')
        data['Reading'] = redfish.get('Reading', '') if reading is None else reading
        data['ReadingUnits'] = 'RPM'
    elif redfish.get('ReadingUnits') == 'Percent':
        data['ReadingUnits'] = '%'

    return data


def get_chassis_thermal_redundancy(redfish):
    """
    Extract thermal redundancy information from a Redfish API response.

    This function retrieves specific thermal redundancy details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal redundancy data.

    ### Returns
    - **dict**: A dictionary containing the following thermal redundancy details:
      - **Mode** (`str`): The mode of the thermal redundancy.
      - **Name** (`str`): The name of the thermal redundancy.
      - **Status_State** (`str`): The state of the thermal redundancy (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the thermal redundancy (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Mode': 'Active',
    ...     'Name': 'Thermal Redundancy',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_chassis_thermal_redundancy(redfish_data)
    {'Mode': 'Active', 'Name': 'Thermal Redundancy', 'Status_State': 'Enabled', 'Status_Health': 'OK'}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_THERMAL_REDUNDANCY_KEYS}

    for out_key, path in CHASSIS_THERMAL_REDUNDANCY_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_chassis_thermal_temperatures(redfish):
    """
    Extract thermal temperature information from a Redfish API response.

    This function retrieves specific thermal temperature details from a Redfish response and returns
    them as a dictionary.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish thermal temperature data.

    ### Returns
    - **dict**: A dictionary containing the following thermal temperature details:
      - **LowerThresholdCritical** (`str`): The critical lower threshold temperature.
      - **LowerThresholdFatal** (`str`): The fatal lower threshold temperature.
      - **LowerThresholdNonCritical** (`str`): The non-critical lower threshold temperature.
      - **Name** (`str`): The name of the thermal temperature sensor.
      - **PhysicalContext** (`str`): The physical context of the sensor.
      - **ReadingCelsius** (`str`): The current temperature reading in Celsius.
      - **UpperThresholdCritical** (`str`): The critical upper threshold temperature.
      - **UpperThresholdFatal** (`str`): The fatal upper threshold temperature.
      - **UpperThresholdNonCritical** (`str`): The non-critical upper threshold temperature.
      - **Status_State** (`str`): The state of the thermal sensor (e.g., "Enabled").
      - **Status_Health** (`str`): The health status of the thermal sensor (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'LowerThresholdCritical': '10',
    ...     'LowerThresholdFatal': '5',
    ...     'LowerThresholdNonCritical': '15',
    ...     'Name': 'Thermal Sensor',
    ...     'ReadingCelsius': '22',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_chassis_thermal_temperatures(redfish_data)
    {'LowerThresholdCritical': '10', 'LowerThresholdFatal': '5', 'LowerThresholdNonCritical': '15', 'Name': 'Thermal Sensor', 'ReadingCelsius': '22', 'Status_State': 'Enabled', 'Status_Health': 'OK'}
    """
    data = {key: redfish.get(key, '') for key in CHASSIS_THERMAL_TEMP_KEYS}

    for out_key, path in CHASSIS_THERMAL_TEMP_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_expand_suffix(
    base_url,
    header=None,
    insecure=False,
    no_proxy=False,
    timeout=8,
    retries=0,
    cache_expire=0,
    cache_filename=CACHE_FILENAME,
):
    """
    Return the deepest Redfish `$expand` query the controller advertises, as a URL suffix.

    Reading the service root `/redfish/v1` once, this inspects
    `ProtocolFeaturesSupported.ExpandQuery` and builds the most generic `$expand` suffix the
    controller supports, so a single request inlines as much of a collection's subtree as possible
    (see `fetch_collection()`). `ExpandAll` selects the `*` operator (subordinate resources and
    links, so linked resources such as a storage controller's `Drives` are inlined too); otherwise
    the `.` operator (subordinate resources only) is used. `Levels`/`MaxLevels` add a `$levels`
    clause, capped at `MAX_EXPAND_LEVELS`.

    When `cache_expire` is non-zero the derived suffix is cached under `redfish-expand-<base_url>`
    and reused by the sibling Redfish checks on the host within the window, so the service root is
    probed once per cycle instead of by every check. On any failure (root not readable, no expand
    support advertised) it returns `DEFAULT_EXPAND`; `fetch_collection()` falls back to a plain
    request should the controller reject even that.

    ### Parameters
    - **base_url** (`str`): The operator-supplied Redfish base URL, e.g. `https://bmc`.
    - **header** (`dict`, optional): Request headers (including the auth header).
    - **insecure**, **no_proxy**, **timeout**, **retries**: Forwarded to `url.fetch_json()`.
    - **cache_expire** (`int`, optional): Cache lifetime in seconds; `0` (default) disables caching.
    - **cache_filename** (`str`, optional): Cache database filename (default `CACHE_FILENAME`).

    ### Returns
    - **str**: A `$expand` query suffix such as `?$expand=*($levels=1)`, or `DEFAULT_EXPAND` when
      the controller's support is unknown.
    """
    expand_key = f'redfish-expand-{base_url}'
    if cache_expire:
        cached = cache.get(expand_key, filename=cache_filename)
        if cached:
            return cached
    suffix = DEFAULT_EXPAND
    success, root = url.fetch_json(
        f'{base_url}/redfish/v1',
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
        retries=retries,
    )
    expand = {}
    if success and isinstance(root, dict):
        features = root.get('ProtocolFeaturesSupported', {})
        if isinstance(features, dict):
            expand = features.get('ExpandQuery', {}) or {}
    if isinstance(expand, dict) and (expand.get('ExpandAll') or expand.get('NoLinks')):
        # `*` inlines subordinate resources and links (e.g. Drives); `.` only subordinate resources
        operator = '*' if expand.get('ExpandAll') else '.'
        if expand.get('Levels'):
            levels = min(int(expand.get('MaxLevels', 1) or 1), MAX_EXPAND_LEVELS)
            suffix = f'?$expand={operator}($levels={levels})'
        else:
            suffix = f'?$expand={operator}'
    if cache_expire:
        cache.set(expand_key, suffix, time.now() + cache_expire, filename=cache_filename)
    return suffix


def get_manager(redfish):
    """
    Retrieves manager (BMC) details from a Redfish API response.

    This function processes a Redfish manager resource (e.g., a BMC, iLO, or iDRAC) and extracts
    the attributes relevant for health monitoring and identification.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish manager data, typically a single member
      of the `Managers` collection.

    ### Returns
    - **dict**: A dictionary containing the following manager details:
      - `FirmwareVersion`: The firmware version of the manager.
      - `Id`: The unique identifier of the manager.
      - `ManagerType`: The type of the manager (e.g., "BMC").
      - `Model`: The model of the manager.
      - `Name`: The name of the manager.
      - `PowerState`: The power state of the manager (e.g., "On").
      - `UUID`: The UUID of the manager.
      - `Status_State`: The state of the manager (e.g., "Enabled").
      - `Status_Health`: The health status of the manager (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the manager (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'FirmwareVersion': '1.45',
    ...     'ManagerType': 'BMC',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_manager(redfish_data)
    {'FirmwareVersion': '1.45', 'ManagerType': 'BMC', ..., 'Status_State': 'Enabled', ...}
    """
    data = {key: redfish.get(key, '') for key in MANAGER_KEYS}

    for out_key, path in MANAGER_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_manager_logservices_sel_entries(
    redfish, match=None, ignore=None, cutoff_epoch=0
):
    """
    Fetch and format SEL (System Event Log) entries from the Redfish API.

    Processes each entry by severity and formats the non-OK ones into a message string, returning
    the worst state across them. Entries can be filtered and aged out before they contribute:

    - **ignore**: drop entries whose `Message` matches any of these compiled regular expressions.
    - **match**: when given, keep only entries whose `Message` matches at least one of these
      compiled regular expressions.
    - **cutoff_epoch**: when non-zero, drop (and count) entries whose `Created` timestamp is older
      than this Unix epoch, so a long-since resolved event no longer keeps the state non-OK.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing the Redfish log entries under the 'Members' key.
    - **match** (`list`, optional): Compiled regular expressions; keep only matching messages.
    - **ignore** (`list`, optional): Compiled regular expressions; drop matching messages.
    - **cutoff_epoch** (`int` or `float`, optional): Drop entries created before this epoch.
      `0` (default) disables aging.

    ### Returns
    - **tuple**:
      - **msg** (`str`): A formatted string of the reported entries (created time, message, state).
      - **state** (`int`): The worst state across the reported entries:
        - `STATE_OK` (0): nothing to report.
        - `STATE_WARN` (1): some entries are warnings.
        - `STATE_CRIT` (2): some entries are critical.
      - **aged_out** (`int`): How many non-OK entries were suppressed because they were older than
        `cutoff_epoch`.

    ### Example
    >>> redfish_data = {
    ...     'Members': [
    ...         {
    ...             'Created': '2021-08-01',
    ...             'Message': 'Temperature is high',
    ...             'Severity': 'Critical',
    ...         },
    ...         {
    ...             'Created': '2021-08-02',
    ...             'Message': 'Fan speed normal',
    ...             'Severity': 'OK',
    ...         },
    ...     ]
    ... }
    >>> get_manager_logservices_sel_entries(redfish_data)
    ('* 2021-08-01: Temperature is high [CRITICAL]\n', 2, 0)
    """
    lines = []
    state = STATE_OK
    aged_out = 0
    utc = time.get_timezone('UTC')
    for entry in redfish.get('Members', []):
        severity = entry.get('Severity', '').lower()
        if severity == 'ok':
            continue
        message = entry.get('Message', '')
        # --ignore: drop entries whose message matches any ignore pattern
        if ignore and any(p.search(message) for p in ignore):
            continue
        # --match: keep only entries whose message matches a match pattern
        if match and not any(p.search(message) for p in match):
            continue
        created = entry.get('Created', '')
        # aging: drop (and count) entries older than the cutoff. A naive
        # timestamp is read as UTC, which is what controllers commonly report.
        if cutoff_epoch and created:
            try:
                entry_epoch = time.timestr2epoch(created, pattern='iso8601', tzinfo=utc)
            except ValueError:
                # undateable entry: keep it rather than silently suppress it
                entry_epoch = None
            if entry_epoch is not None and entry_epoch < cutoff_epoch:
                aged_out += 1
                continue
        msg_state = SEVERITY_TO_STATE.get(severity, STATE_OK)
        lines.append(
            '* {}: {}{}'.format(created, message, base.state2str(msg_state, prefix=' '))
        )
        state = base.get_worst(state, msg_state)
    return '\n'.join(lines) + ('\n' if lines else ''), state, aged_out


def get_perfdata(data, key='Reading'):
    """
    Retrieve the performance data for a specific key from the provided data.

    This function extracts performance-related values such as the reading value, thresholds, and
    range from the provided dictionary. It formats this data and returns a performance data string,
    suitable for monitoring.

    ### Parameters
    - **data** (`dict`): A dictionary containing performance data and related information.
    - **key** (`str`, optional): The key in the dictionary whose value should be extracted.
      Defaults to `'Reading'`.

    ### Returns
    - **str**: A formatted string containing performance data in the format:
      `'label=value[unit];[warn];[crit];[min];[max]'`, or an empty string if the required data is invalid or missing.

    ### Example
    >>> data = {
    ...     'Name': 'Temperature Sensor 1',
    ...     'PhysicalContext': 'Chassis',
    ...     'Reading': 75.0,
    ...     'ReadingUnits': '%',
    ...     'Thresholds_UpperCaution': 80,
    ...     'Thresholds_UpperCritical': 90,
    ...     'ReadingRangeMin': 0,
    ...     'ReadingRangeMax': 100,
    ... }
    >>> get_perfdata(data)
    'Chassis_Temperature_Sensor_1=75.0%;80;90;0;100'
    """
    value = data.get(key)
    if not isinstance(value, (int, float)):
        return ''

    name = data.get('Name', '')
    physical_context = data.get('PhysicalContext', '')
    uom = '%' if data.get('ReadingUnits') == '%' else None
    warn = data.get('Thresholds_UpperCaution') or None
    crit = data.get('Thresholds_UpperCritical') or None
    _min = data.get('ReadingRangeMin') or None
    _max = data.get('ReadingRangeMax') or None

    label = f'{physical_context}_{name}'.replace(' ', '_')
    return base.get_perfdata(label, value, uom, warn, crit, _min, _max)


def get_sensor_state(data, key='Reading'):
    """
    Determine the state of a Redfish sensor according to status, health, thresholds, and range.

    This function evaluates the sensor reading in the following order:

    1. **Status_State**
       If `data['Status_State']` is not `'Enabled'` or `'Quiesced'`, the sensor is considered OK.
    2. **Status_HealthRollup / Status_Health**
       - Returns STATE_CRIT if either is `'Critical'`.
       - Returns STATE_WARN if either is `'Warning'`.
    3. **Thresholds** (with user-defined overrides)
       Checks in this sequence for any defined thresholds:
       - **User-defined critical** (`Thresholds_LowerCriticalUser`, `Thresholds_UpperCriticalUser`) → STATE_CRIT
       - **Default critical**      (`Thresholds_LowerCritical`,     `Thresholds_UpperCritical`)     → STATE_CRIT
       - **User-defined caution**  (`Thresholds_LowerCautionUser`,  `Thresholds_UpperCautionUser`)  → STATE_WARN
       - **Default caution**       (`Thresholds_LowerCaution`,      `Thresholds_UpperCaution`)      → STATE_WARN
       Otherwise, if any thresholds were present but none breached, returns STATE_OK.
    4. **ReadingRange** (last-resort sanity check)
       If both `ReadingRangeMin` and `ReadingRangeMax` are defined and differ, returns STATE_WARN
       if the reading lies outside that range; otherwise STATE_OK.
       A range whose min equals its max has zero width and cannot describe a valid operating
       window. Some implementations report identical min/max (often 255) as a sentinel for
       "not available", "no limit defined" or "unsupported for this sensor type". Treating that
       as a real range would flag every reading outside that single point, so it is ignored.
    5. **Default**
       If no other checks apply, returns STATE_OK.

    ### Parameters
    - **data** (`dict`): Sensor data containing keys such as:
        - `'Reading'` (float or numeric string)
        - `'Status_State'`, `'Status_HealthRollup'`, `'Status_Health'`
        - Default thresholds: `'Thresholds_LowerCritical'`, `'Thresholds_UpperCritical'`,
          `'Thresholds_LowerCaution'`, `'Thresholds_UpperCaution'`
        - User thresholds: `'Thresholds_LowerCriticalUser'`, `'Thresholds_UpperCriticalUser'`,
          `'Thresholds_LowerCautionUser'`, `'Thresholds_UpperCautionUser'`
        - Reading ranges: `'ReadingRangeMin'`, `'ReadingRangeMax'`.
    - **key** (`str`, optional): The key in `data` whose value is the sensor reading.
      Defaults to `'Reading'`.

    ### Returns
    - **int**: One of:
        - `STATE_OK`   (0)
        - `STATE_WARN` (1)
        - `STATE_CRIT` (2)

    ### Example
    >>> sample = {
    ...     'Reading': 95.0,
    ...     'Status_State': 'Enabled',
    ...     'Status_Health': '',
    ...     'Status_HealthRollup': '',
    ...     'Thresholds_UpperCriticalUser': 85,
    ...     'Thresholds_UpperCritical': 90,
    ...     'Thresholds_UpperCaution': 80,
    ...     'Thresholds_LowerCritical': 10,
    ...     'Thresholds_LowerCaution': 20,
    ... }
    >>> get_sensor_state(sample)
    2  # STATE_CRIT (reading > user-defined upper critical)
    """

    # helper to parse floats, treating '', None, or bad strings as None
    def _parse(val):
        if val in (None, ''):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    # read the actual sensor reading
    raw = data.get(key)
    try:
        reading = float(raw)
    except (TypeError, ValueError):
        return STATE_OK

    # get redfish's states first
    if data.get('Status_State') not in ('Enabled', 'Quiesced'):
        return STATE_OK

    for field in ('Status_HealthRollup', 'Status_Health'):
        value = data.get(field)
        if value:
            value = value.lower()
            if value == 'critical':
                return STATE_CRIT
            if value == 'warning':
                return STATE_WARN

    # parse thresholds
    low_caut = _parse(data.get('Thresholds_LowerCaution'))
    low_caut_usr = _parse(data.get('Thresholds_LowerCautionUser'))
    low_crit = _parse(data.get('Thresholds_LowerCritical'))
    low_crit_usr = _parse(data.get('Thresholds_LowerCriticalUser'))
    up_caut = _parse(data.get('Thresholds_UpperCaution'))
    up_caut_usr = _parse(data.get('Thresholds_UpperCautionUser'))
    up_crit = _parse(data.get('Thresholds_UpperCritical'))
    up_crit_usr = _parse(data.get('Thresholds_UpperCriticalUser'))

    # if *any* thresholds are defined, use threshold logic
    if any(
        t is not None
        for t in (
            low_caut,
            low_caut_usr,
            low_crit,
            low_crit_usr,
            up_caut,
            up_caut_usr,
            up_crit,
            up_crit_usr,
        )
    ):
        # critical bounds first
        # (user-defined thresholds exist too and should normally override the default
        # thresholds if present)
        if (low_crit_usr is not None and reading < low_crit_usr) or (
            up_crit_usr is not None and reading > up_crit_usr
        ):
            return STATE_CRIT

        if (low_crit is not None and reading < low_crit) or (
            up_crit is not None and reading > up_crit
        ):
            return STATE_CRIT

        # then caution bounds
        if (low_caut_usr is not None and reading < low_caut_usr) or (
            up_caut_usr is not None and reading > up_caut_usr
        ):
            return STATE_WARN

        if (low_caut is not None and reading < low_caut) or (
            up_caut is not None and reading > up_caut
        ):
            return STATE_WARN

        # otherwise we're inside all defined thresholds
        return STATE_OK

    # we're using ReadingRangeMin/Max purely as a last-resort sanity check,
    # since Redfish doesn't specify health semantics for that. A zero-width range
    # (min == max) is treated as "no range defined" (see docstring step 4).
    range_min = _parse(data.get('ReadingRangeMin'))
    range_max = _parse(data.get('ReadingRangeMax'))
    if range_min is not None and range_max is not None and range_min != range_max:
        if reading < range_min or reading > range_max:
            return STATE_WARN
        return STATE_OK

    # nothing defined to check against
    return STATE_OK


def get_state(data):
    """
    Determine the state of an entity based on its health and status.

    This function checks the `Status_State` and `Status_HealthRollup` values in the provided data
    dictionary and returns a state based on these values. It assigns `STATE_CRIT` if the status or
    health rollup indicates a critical state, `STATE_WARN` for warning states, or `STATE_OK` if no
    critical or warning states are found.

    ### Parameters
    - **data** (`dict`): A dictionary containing the status and health information of the entity
      (e.g., `Status_State`, `Status_Health`, `Status_HealthRollup`).

    ### Returns
    - **int**: The state of the entity, which can be:
      - `STATE_OK` (0): If the entity is in a normal or healthy state.
      - `STATE_WARN` (1): If the entity's health or status indicates a warning.
      - `STATE_CRIT` (2): If the entity's health or status indicates a critical state.

    ### Example
    >>> data = {
    ...     'Status_State': 'Enabled',
    ...     'Status_Health': 'Warning',
    ...     'Status_HealthRollup': 'Critical',
    ... }
    >>> get_state(data)
    2  # STATE_CRIT
    """
    if data.get('Status_State') not in ('Enabled', 'Quiesced'):
        return STATE_OK

    for field in ('Status_HealthRollup', 'Status_Health'):
        value = data.get(field)
        if value:
            value = value.lower()
            if value == 'critical':
                return STATE_CRIT
            if value == 'warning':
                return STATE_WARN

    return STATE_OK


def get_systems(redfish):
    """
    Retrieves system information from the Redfish API response.

    This function processes a Redfish API response to extract system details such as BIOS version,
    host name, manufacturer, model, processor summary, power state, and system health status.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing system-related
      information such as BIOS version, processor details, and status information.

    ### Returns
    - **dict**: A dictionary containing the following system details:
      - `BiosVersion`: The BIOS version.
      - `HostName`: The system's host name.
      - `Id`: The unique identifier for the system.
      - `IndicatorLED`: The system's indicator LED state.
      - `Manufacturer`: The manufacturer of the system.
      - `Model`: The model of the system.
      - `PowerState`: The current power state of the system (e.g., "On").
      - `ProcessorSummary_Count`: The number of processors.
      - `ProcessorSummary_LogicalProcessorCount`: The number of logical processors.
      - `ProcessorSummary_Model`: The model of the processor.
      - `SerialNumber`: The system's serial number.
      - `SKU`: The system's SKU (Stock Keeping Unit).
      - `Storage_@odata.id`: The OData ID for the system's storage.
      - `Status_State`: The system's status state (e.g., "Enabled").
      - `Status_Health`: The system's health status (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the system.

    ### Example
    >>> redfish_data = {
    ...     'BiosVersion': '1.0.0',
    ...     'HostName': 'System1',
    ...     'Id': '12345',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ...     'ProcessorSummary': {
    ...         'Count': 2,
    ...         'LogicalProcessorCount': 4,
    ...         'Model': 'Intel Xeon',
    ...     },
    ...     'PowerState': 'On',
    ... }
    >>> get_systems(redfish_data)
    {
        'BiosVersion': '1.0.0',
        'HostName': 'System1',
        'Id': '12345',
        'IndicatorLED': '',
        'Manufacturer': '',
        'Model': '',
        'PowerState': 'On',
        'ProcessorSummary_Count': 2,
        'ProcessorSummary_LogicalProcessorCount': 4,
        'ProcessorSummary_Model': 'Intel Xeon',
        'SerialNumber': '',
        'SKU': '',
        'Storage_@odata.id': '',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {key: redfish.get(key, '') for key in SYSTEMS_KEYS}

    for out_key, path in SYSTEMS_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_ethernetinterfaces(redfish):
    """
    Retrieves Ethernet interface details from a Redfish API response.

    This function processes a Redfish Ethernet interface resource and extracts the attributes
    relevant for health monitoring and identification, such as MAC address, link status, and speed.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish Ethernet interface data, typically a
      single member of an `EthernetInterfaces` collection.

    ### Returns
    - **dict**: A dictionary containing the following Ethernet interface details:
      - `Description`: A description of the interface.
      - `FQDN`: The fully qualified domain name of the interface.
      - `FullDuplex`: Whether the interface operates in full-duplex mode.
      - `HostName`: The host name configured on the interface.
      - `Id`: The unique identifier of the interface.
      - `LinkStatus`: The link status of the interface (e.g., "LinkUp").
      - `MACAddress`: The currently configured MAC address.
      - `Name`: The name of the interface.
      - `PermanentMACAddress`: The permanent (factory) MAC address.
      - `SpeedMbps`: The link speed in megabits per second.
      - `Status_State`: The state of the interface (e.g., "Enabled").
      - `Status_Health`: The health status of the interface (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the interface (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'MACAddress': '12:44:6A:3B:04:11',
    ...     'LinkStatus': 'LinkUp',
    ...     'SpeedMbps': 1000,
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_ethernetinterfaces(redfish_data)
    {'MACAddress': '12:44:6A:3B:04:11', 'LinkStatus': 'LinkUp', 'SpeedMbps': 1000, ...}
    """
    data = {key: redfish.get(key, '') for key in ETHERNET_KEYS}

    for out_key, path in ETHERNET_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_memory(redfish):
    """
    Retrieves memory module (DIMM) details from a Redfish API response.

    This function processes a Redfish memory resource and extracts the attributes relevant for
    health monitoring and identification, such as capacity, type, speed, manufacturer, and status.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish memory data, typically a single member
      of the `Memory` collection.

    ### Returns
    - **dict**: A dictionary containing the following memory details:
      - `BaseModuleType`: The form factor of the module (e.g., "RDIMM").
      - `CapacityMiB`: The capacity in human-readable format (converted from mebibytes).
      - `ErrorCorrection`: The error correction scheme (e.g., "MultiBitECC").
      - `Id`: The unique identifier of the memory module.
      - `Location_ServiceLabel`: The service label of the slot (e.g., "DIMM 1").
      - `Manufacturer`: The manufacturer of the module.
      - `MemoryDeviceType`: The device type (e.g., "DDR4").
      - `MemoryType`: The memory media type (e.g., "DRAM").
      - `Name`: The name of the module.
      - `OperatingSpeedMhz`: The operating speed in megahertz.
      - `PartNumber`: The part number of the module.
      - `RankCount`: The number of ranks.
      - `SerialNumber`: The serial number of the module.
      - `Status_State`: The state of the module (e.g., "Enabled").
      - `Status_Health`: The health status of the module (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the module (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'CapacityMiB': 32768,
    ...     'MemoryDeviceType': 'DDR4',
    ...     'Name': 'DIMM Slot 1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_memory(redfish_data)
    {'CapacityMiB': '32.0GiB', 'MemoryDeviceType': 'DDR4', 'Name': 'DIMM Slot 1', ...}
    """
    data = {key: redfish.get(key, '') for key in MEMORY_KEYS}

    for out_key, path in MEMORY_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    # the vendor is detected from the member's own Oem block, so the projection
    # stays self-contained (dict in, dict out)
    vendor = get_vendor(redfish)

    # vendor quirk: some controllers report the module size as "SizeMB"; Dell
    # iDRAC 8 even reports decimal MB instead of binary MiB, so a value that is
    # not a clean MiB multiple is converted back to a MiB count.
    capacity = redfish.get('SizeMB') or redfish.get('CapacityMiB')
    if capacity:
        capacity = int(capacity)
        if vendor == 'dell' and capacity % 1024 != 0:
            capacity = round(capacity * 1024**2 / 1000**2)
        data['CapacityMiB'] = human.bytes2human(capacity * 1024 * 1024)
    else:
        data['CapacityMiB'] = ''

    # vendor quirk: when the standard Status block is empty, fold the
    # OEM-specific status field into Status_State / Status_Health.
    oem = redfish.get('Oem') or {}
    oem_block = next(iter(oem.values()), {}) if isinstance(oem, dict) else {}
    if not isinstance(oem_block, dict):
        oem_block = {}

    oem_state = ''
    if vendor == 'hpe':
        oem_state = oem_block.get('DIMMStatus', '')
    elif vendor == 'fujitsu' and oem_block.get('SignalStatus'):
        oem_state = oem_block.get('SignalStatus', '')
        # Fujitsu reports the health verdict separately in LegacyStatus
        legacy = oem_block.get('LegacyStatus')
        if legacy:
            data['Status_Health'] = (
                'OK' if legacy.lower() in MEMORY_OEM_HEALTHY_HEALTH else 'Critical'
            )
    elif redfish.get('DIMMStatus'):
        oem_state = redfish.get('DIMMStatus', '')

    if oem_state:
        if oem_state in MEMORY_OEM_ABSENT_STATES:
            data['Status_State'] = 'Absent'
        elif oem_state in MEMORY_OEM_HEALTHY_STATES:
            data['Status_State'] = 'Enabled'
            if not data['Status_Health']:
                data['Status_Health'] = 'OK'
        else:
            # an unrecognized operational value means the module needs attention
            data['Status_State'] = 'Enabled'
            if data['Status_Health'] in ('', 'OK'):
                data['Status_Health'] = 'Critical'

    return data


def get_systems_processors(redfish):
    """
    Retrieves processor (CPU) details from a Redfish API response.

    This function processes a Redfish processor resource and extracts the attributes relevant for
    health monitoring and identification, such as model, core count, speed, and status.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish processor data, typically a single
      member of the `Processors` collection.

    ### Returns
    - **dict**: A dictionary containing the following processor details:
      - `Id`: The unique identifier of the processor.
      - `InstructionSet`: The instruction set (e.g., "x86-64").
      - `Manufacturer`: The manufacturer of the processor.
      - `MaxSpeedMHz`: The maximum clock speed in megahertz.
      - `Model`: The model of the processor.
      - `Name`: The name of the processor.
      - `ProcessorArchitecture`: The architecture (e.g., "x86").
      - `ProcessorType`: The type of processor (e.g., "CPU", "FPGA").
      - `Socket`: The socket the processor is installed in.
      - `TotalCores`: The number of cores.
      - `TotalThreads`: The number of threads.
      - `Location_ServiceLabel`: The service label of the socket (e.g., "CPU 1").
      - `Status_State`: The state of the processor (e.g., "Enabled").
      - `Status_Health`: The health status of the processor (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the processor (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Model': 'Multi-Core Intel(R) Xeon(R) processor 7xxx Series',
    ...     'Socket': 'CPU 1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_processors(redfish_data)
    {'Model': 'Multi-Core Intel(R) Xeon(R) processor 7xxx Series', 'Socket': 'CPU 1', ...}
    """
    data = {key: redfish.get(key, '') for key in PROCESSOR_KEYS}

    for out_key, path in PROCESSOR_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_storage(redfish):
    """
    Retrieves storage system information from the Redfish API response.

    This function processes a Redfish API response to extract storage-related system details such
    as the storage description, number of drives, storage ID, name, and health status.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing storage-related
      information such as description, status, and health.

    ### Returns
    - **dict**: A dictionary containing the following storage system details:
      - `Description`: A description of the storage system.
      - `Drives@odata.count`: The number of drives in the storage system.
      - `Id`: The unique identifier for the storage system.
      - `Name`: The name of the storage system.
      - `Status_State`: The status state of the storage system (e.g., "Enabled").
      - `Status_Health`: The health status of the storage system (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the storage system.

    ### Example
    >>> redfish_data = {
    ...     'Description': 'RAID Storage',
    ...     'Drives@odata.count': 5,
    ...     'Id': '6789',
    ...     'Name': 'StorageSystem1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ... }
    >>> get_systems_storage(redfish_data)
    {
        'Description': 'RAID Storage',
        'Drives@odata.count': 5,
        'Id': '6789',
        'Name': 'StorageSystem1',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {key: redfish.get(key, '') for key in SYSTEMS_STORAGE_KEYS}

    for out_key, path in SYSTEMS_STORAGE_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_systems_storage_drives(redfish):
    """
    Retrieves storage drive details from the Redfish API response.

    This function processes the Redfish API response to extract information about storage drives,
    including attributes such as capacity, encryption status, failure prediction, speed, and other
    properties.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing details about
      storage drives such as capacity, health status, and manufacturer.

    ### Returns
    - **dict**: A dictionary containing the following storage drive details:
      - `BlockSizeBytes`: The block size of the storage drive in bytes.
      - `CapableSpeedGbs`: The capable speed of the drive in gigabits per second (Gbps).
      - `CapacityBytes`: The capacity of the drive in human-readable format (converted from bytes).
      - `Description`: A description of the storage drive.
      - `EncryptionAbility`: The encryption ability status of the storage drive.
      - `EncryptionStatus`: The current encryption status of the storage drive.
      - `FailurePredicted`: A boolean indicating whether failure of the drive is predicted.
      - `HotspareType`: The type of hot spare (if any) associated with the drive.
      - `Id`: The unique identifier for the storage drive.
      - `Manufacturer`: The manufacturer of the storage drive.
      - `MediaType`: The type of media used by the storage drive (e.g., SSD, HDD).
      - `Model`: The model of the storage drive.
      - `Name`: The name of the storage drive.
      - `NegotiatedSpeedGbs`: The negotiated speed of the drive in gigabits per second (Gbps).
      - `PartNumber`: The part number of the storage drive.
      - `PowerOnHours`: The number of hours the drive has been powered on.
      - `PredictedMediaLifeLeftPercent`: The predicted remaining life of the storage media in
         percentage.
      - `Protocol`: The protocol used by the storage drive (e.g., SATA, NVMe).
      - `Revision`: The revision number of the storage drive.
      - `RotationSpeedRPM`: The rotational speed of the drive (if applicable) in revolutions per
         minute (RPM).
      - `SerialNumber`: The serial number of the storage drive.
      - `WriteCacheEnabled`: A boolean indicating whether write cache is enabled on the drive.
      - `Status_State`: The state of the storage drive (e.g., "Enabled").
      - `Status_Health`: The health status of the storage drive (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the storage drive (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'CapacityBytes': 500000000000,
    ...     'Description': 'SSD Drive',
    ...     'Manufacturer': 'Samsung',
    ...     'Model': '970 EVO',
    ...     'SerialNumber': '1234567890',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK', 'HealthRollup': 'OK'},
    ... }
    >>> get_systems_storage_drives(redfish_data)
    {
        'CapacityBytes': '500.0 GB',
        'Description': 'SSD Drive',
        'Manufacturer': 'Samsung',
        'Model': '970 EVO',
        'SerialNumber': '1234567890',
        'Status_State': 'Enabled',
        'Status_Health': 'OK',
        'Status_HealthRollup': 'OK',
    }
    """
    data = {key: redfish.get(key, '') for key in SYSTEMS_STORAGE_DRIVES_KEYS}

    for out_key, path in SYSTEMS_STORAGE_DRIVES_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    capacity = redfish.get('CapacityBytes')
    data['CapacityBytes'] = human.bytes2human(capacity) if capacity else ''

    # vendor quirk: drive temperature is not a standard Drive property. HPE
    # SmartStorage exposes "CurrentTemperatureCelsius"; other vendors put it in
    # their OEM block as TemperatureCelsius / TemperatureC. Expose it (in
    # degrees Celsius) so it can be trended as a gauge.
    oem = redfish.get('Oem') or {}
    oem_block = next(iter(oem.values()), {}) if isinstance(oem, dict) else {}
    if not isinstance(oem_block, dict):
        oem_block = {}
    temperature = (
        redfish.get('CurrentTemperatureCelsius')
        or oem_block.get('TemperatureCelsius')
        or oem_block.get('TemperatureC')
    )
    data['Temperature'] = temperature if isinstance(temperature, (int, float)) else ''

    return data


def get_systems_storage_volumes(redfish):
    """
    Retrieves volume (logical drive) details from a Redfish API response.

    This function processes a Redfish volume resource and extracts the attributes relevant for
    health monitoring and identification, such as capacity, RAID type, and status.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish volume data, typically a single member
      of a `Volumes` collection.

    ### Returns
    - **dict**: A dictionary containing the following volume details:
      - `CapacityBytes`: The capacity of the volume in human-readable format (converted from bytes).
      - `Encrypted`: Whether the volume is encrypted.
      - `Id`: The unique identifier of the volume.
      - `Name`: The name of the volume.
      - `RAIDType`: The RAID type of the volume (e.g., "RAID1").
      - `VolumeType`: The volume type (deprecated in favor of `RAIDType`).
      - `Status_State`: The state of the volume (e.g., "Enabled").
      - `Status_Health`: The health status of the volume (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the volume (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'CapacityBytes': 1000000000000,
    ...     'Name': 'Virtual Disk 0',
    ...     'RAIDType': 'RAID1',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_systems_storage_volumes(redfish_data)
    {'CapacityBytes': '931.3GiB', 'Name': 'Virtual Disk 0', 'RAIDType': 'RAID1', ...}
    """
    data = {key: redfish.get(key, '') for key in VOLUME_KEYS}

    for out_key, path in VOLUME_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    capacity = redfish.get('CapacityBytes')
    data['CapacityBytes'] = human.bytes2human(capacity) if capacity else ''

    return data


def get_updateservice_firmwareinventory(redfish):
    """
    Retrieves firmware inventory details from a Redfish API response.

    This function processes a Redfish software inventory resource (a firmware component) and
    extracts the attributes relevant for version reporting and health monitoring.

    ### Parameters
    - **redfish** (`dict`): A dictionary containing Redfish firmware data, typically a single member
      of the `FirmwareInventory` collection.

    ### Returns
    - **dict**: A dictionary containing the following firmware details:
      - `Id`: The unique identifier of the firmware component.
      - `Manufacturer`: The manufacturer of the firmware component.
      - `Name`: The name of the firmware component.
      - `ReleaseDate`: The release date of the firmware.
      - `SoftwareId`: The software identifier.
      - `Updateable`: Whether the component can be updated through the update service.
      - `Version`: The installed firmware version.
      - `Status_State`: The state of the firmware component (e.g., "Enabled").
      - `Status_Health`: The health status of the firmware component (e.g., "OK").
      - `Status_HealthRollup`: The rollup health status of the firmware component (e.g., "OK").

    ### Example
    >>> redfish_data = {
    ...     'Name': 'Contoso BIOS Firmware',
    ...     'Version': 'P79 v1.45',
    ...     'Status': {'State': 'Enabled', 'Health': 'OK'},
    ... }
    >>> get_updateservice_firmwareinventory(redfish_data)
    {'Name': 'Contoso BIOS Firmware', 'Version': 'P79 v1.45', ..., 'Status_State': 'Enabled', ...}
    """
    data = {key: redfish.get(key, '') for key in FIRMWARE_KEYS}

    for out_key, path in FIRMWARE_NESTED_KEYS.items():
        ref = redfish
        for step in path:
            ref = ref.get(step, {})
        data[out_key] = ref if isinstance(ref, (str, int, float)) else ''

    return data


def get_vendor(redfish):
    """
    Retrieves the vendor information from the Redfish API response.

    This function checks for the 'Vendor' key in the Redfish API response. If it's not found,
    it looks in the  'Oem' dictionary for the first key and uses that as the vendor. If no vendor
    information is available, it returns 'generic'.

    ### Parameters
    - **redfish** (`dict`): The Redfish API response data, typically containing information about
      the system, including vendor details.

    ### Returns
    - **str**: The vendor name in lowercase, or 'generic' if no vendor information is found.

    ### Example
    >>> redfish_data = {
    ...     'Vendor': 'DELL',
    ... }
    >>> get_vendor(redfish_data)
    'dell'

    >>> redfish_data = {
    ...     'Oem': {'SomeOtherVendor': 'details'},
    ... }
    >>> get_vendor(redfish_data)
    'someothervendor'

    >>> redfish_data = {}
    >>> get_vendor(redfish_data)
    'generic'
    """
    vendor = redfish.get('Vendor')
    if not vendor:
        oem = redfish.get('Oem') or {}
        vendor = next(iter(oem), '')
    return vendor.lower() if vendor else 'generic'


def is_member_expanded(member):
    """
    Report whether a Redfish collection member arrived fully populated or as a bare reference.

    A collection normally lists its members as reference stubs (`{"@odata.id": "..."}`). With the
    Redfish `$expand` query the controller inlines the full member object instead. A member counts
    as expanded once it carries at least one property beyond the OData annotation keys (those
    starting with `@odata`), because a real resource always exposes fields such as `Id`, `Name` or
    `Status`. Used by `fetch_members()` to decide whether a follow-up request is still needed.

    ### Parameters
    - **member** (`dict`): A single entry from a collection's `Members` list (or an inline
      reference array).

    ### Returns
    - **bool**: `True` if the member is already populated, `False` if it is a bare reference.

    ### Example
    >>> is_member_expanded({'@odata.id': '/redfish/v1/Chassis/1U/Sensors/0'})
    False
    >>> is_member_expanded({'@odata.id': '/redfish/v1/Chassis/1U/Sensors/0', 'Reading': 22.5})
    True
    """
    if not isinstance(member, dict):
        return False
    return any(not key.startswith('@odata') for key in member)
