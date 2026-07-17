#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.md

"""Reads the OpenMetrics and Prometheus text exposition formats, the payload that a `/metrics`
endpoint serves, and turns it into plain Python data.

The two formats are close relatives and this module accepts both. Where they disagree, the
`dialect` parameter of `parse()` decides. The grammar implemented here follows the reference
parsers (`model/textparse` in prometheus/prometheus and the `prometheus_client` Python package),
which are stricter than most hand-written parsers about escaping and looser than the OpenMetrics
specification about whitespace.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026071708'


import math
import re

DIALECT_OPENMETRICS = 'openmetrics'
DIALECT_PROMETHEUS = 'prometheus'

# A sample whose name neither carries a `# TYPE` of its own nor belongs to a metric family that
# does. Both formats allow metadata to be missing entirely, so this is a normal case, not an
# error. It is also how the `unknown` and `untyped` type names are reported.
TYPE_UNKNOWN = 'unknown'

# The possible values of a sample's `type`. Not the set of names a `# TYPE` line may carry: the
# formats spell TYPE_UNKNOWN differently (`unknown` here, `untyped` in the Prometheus format) and
# only OpenMetrics knows `gaugehistogram`, `info` and `stateset`.
TYPES = frozenset((
    'counter',
    'gauge',
    'gaugehistogram',
    'histogram',
    'info',
    'stateset',
    'summary',
    TYPE_UNKNOWN,
))


def _match_labels(labels, wanted):
    """Report whether every label in `wanted` is present in `labels` with the same value."""
    return all(labels.get(key) == value for key, value in wanted.items())


def get_samples(samples, name, labels=None):
    """
    Pick the samples of one metric out of a parsed payload.

    An endpoint answers with everything it knows about, so a caller interested in a single
    metric has to select it. Selecting by name alone yields one entry per label combination the
    endpoint reported, which for many metrics is more than one entry. Narrow it down by passing
    the labels that identify the wanted combination.

    ### Parameters
    - **samples** (`list`):
      The samples as returned by `parse()`.
    - **name** (`str`):
      The metric name to select, matched exactly.
    - **labels** (`dict`, optional):
      Labels the sample has to carry, as a subset: a sample matches if it has at least these
      labels with these values, and it may carry any number of other labels. Defaults to `None`,
      which matches every label combination.

    ### Returns
    - **list**: The matching samples, in the order the payload listed them.

    ### Notes
    - An empty result says "nothing matched", which does not distinguish a metric that is absent
      from one that is present under other labels. Where that difference matters, ask for the
      name alone first.
    - The samples are the ones `parse()` returned, not copies. Changing one changes the parsed
      payload.

    ### Example
    >>> get_samples(samples, 'nextcloud_app_enabled')
    >>> get_samples(samples, 'nextcloud_app_enabled', labels={'app_id': 'spreed'})
    """
    if labels is None:
        labels = {}
    return [
        sample for sample in samples
        if sample['name'] == name and _match_labels(sample['labels'], labels)
    ]


def get_value(samples, name, labels=None, default=None):
    """
    Pick the value of a single sample out of a parsed payload.

    Shortcut around `get_samples()` for the common case of a metric that reports one number.

    ### Parameters
    - **samples** (`list`):
      The samples as returned by `parse()`.
    - **name** (`str`):
      The metric name to select, matched exactly.
    - **labels** (`dict`, optional):
      Labels the sample has to carry, as a subset. Defaults to `None`, matching any.
    - **default** (`any type`, optional):
      What to return if nothing matches. Defaults to `None`.

    ### Returns
    - **float | any type**: The value of the first matching sample, otherwise `default`.

    ### Notes
    - Returns the *first* match, so a name that matches several label combinations returns an
      arbitrary one of them. Use `get_samples()` where more than one match is possible.
    - The value is a float even where the metric is conceptually an integer, because both text
      formats define every value as a float. A metric reporting 0 is therefore falsy, as is a
      missing one under the default `default`. Pass a `default` that cannot be confused with a
      value where that difference matters.

    ### Example
    >>> get_value(samples, 'nextcloud_app_enabled', labels={'app_id': 'spreed'})
    1.0
    """
    for sample in get_samples(samples, name, labels=labels):
        return sample['value']
    return default


# The three escape sequences below are the only ones either format defines. An unknown sequence
# such as `\t` or `\x` is not an error and not a tab or a hex escape either: it stays verbatim,
# backslash included. Note that this rules out str.replace() chains, which would turn the
# literal `\\n` (backslash, backslash, n) into a newline instead of into `\n` (backslash, n).
_ESCAPES = {'\\': '\\', '"': '"', 'n': '\n'}


def _unescape(text, quotes=True):
    """Resolve the escape sequences of a label value or a metadata text.

    `quotes` tells whether `\\"` is one of them. It is, everywhere except in the `# HELP` text of
    the Prometheus format, which leaves it as it is.
    """
    if '\\' not in text:
        return text
    out = []
    i = 0
    while i < len(text):
        char = text[i]
        if char != '\\' or i + 1 >= len(text):
            out.append(char)
            i += 1
            continue
        escaped = _ESCAPES.get(text[i + 1])
        if escaped is None or (text[i + 1] == '"' and not quotes):
            # Not an escape sequence. Emit the backslash and carry on with the character behind
            # it, which may well start a sequence of its own.
            out.append(char)
            i += 1
            continue
        out.append(escaped)
        i += 2
    return ''.join(out)


def _read_quoted(text, i):
    """Read the quoted string starting at `text[i]`, returning its value and the offset behind
    it, or `(None, -1)` if it is unterminated.
    """
    j = i + 1
    while j < len(text):
        char = text[j]
        if char == '\\':
            # Skip the escaped character, so that an escaped quote does not end the string.
            j += 2
            continue
        if char == '"':
            return _unescape(text[i + 1:j]), j + 1
        j += 1
    return None, -1


# A name that is not quoted is limited to this charset. Label names may not contain a colon,
# metric names may. Both formats allow any other name to be written as a quoted string instead.
_LABEL_NAME_REGEX = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*', re.ASCII)
_METRIC_NAME_REGEX = re.compile(r'[a-zA-Z_:][a-zA-Z0-9_:]*', re.ASCII)


# A label set naming the same label twice. Both formats want label names unique within a label
# set, and a dict cannot hold the two values anyway, so such a sample cannot be reported. It is
# dropped on its own rather than taking the payload with it: the line is well-formed and fully
# understood, so the reader has not lost its place in the payload and everything around it still
# states the truth. It is also what the sample meets further along in practice, Prometheus reading
# such a payload and rejecting only this one sample when it stores it.
_DUPLICATE_LABEL = object()


def _parse_labels(text, dialect):
    """Parse the inside of a `{...}` label set.

    Returns a `(success, result)` tuple, where result is a `(name, labels, duplicate)` tuple on
    success. `name` is the metric name if the label set carries one (the form used for names
    outside the legacy charset), otherwise `None`. `duplicate` tells whether the label set named
    the same label twice, which leaves `labels` holding an arbitrary one of the two values and so
    fit to be dropped rather than reported.

    `dialect` decides whether the comma between two entries may be left out, which the Prometheus
    grammar allows and the OpenMetrics one does not.

    `__name__` is left where it is, as an ordinary label. It is how the Prometheus data model
    carries a metric name, but no text grammar gives it that job: a name is written in front of
    the label set or, for names outside the legacy charset, as a quoted string inside it, and
    OpenMetrics reserves every `__` label name without ever defining this one. Reading it as a
    name would accept a payload no compliant endpoint emits.

    The two unterminated-quote paths below cannot be reached through `parse()`, which locates the
    closing brace with `_find_brace_close()` first and so has already rejected every unbalanced
    quote. They are kept because they are this function's own contract rather than its caller's:
    without them an unterminated quote would leave an offset of -1 to index with, which reads the
    label set backwards instead of failing.
    """
    name = None
    labels = {}
    duplicate = False
    i = 0
    while True:
        while i < len(text) and text[i] in ' \t':
            i += 1
        if i >= len(text):
            break
        quoted = text[i] == '"'
        if quoted:
            key, i = _read_quoted(text, i)
            if i < 0:
                return False, 'unterminated quoted name in a label set'
        else:
            match = _LABEL_NAME_REGEX.match(text, i)
            if not match:
                return False, f'expected a label name at "{text[i:i + 16]}"'
            key = match.group(0)
            i = match.end()
        while i < len(text) and text[i] in ' \t':
            i += 1
        if i < len(text) and text[i] == '=':
            i += 1
            while i < len(text) and text[i] in ' \t':
                i += 1
            if i >= len(text) or text[i] != '"':
                return False, f'expected a quoted value for label "{key}"'
            value, i = _read_quoted(text, i)
            if i < 0:
                return False, f'unterminated value for label "{key}"'
            if key in labels:
                # Not returning here: the rest of the label set still has to be read, so that a
                # sample carrying both a duplicate label and a syntax error behind it fails the
                # payload the way that syntax error alone would. Keeping either value would be a
                # guess about which the endpoint meant, so the sample goes on the floor whole.
                duplicate = True
            labels[key] = value
        elif quoted and (i >= len(text) or text[i] == ','):
            # A quoted string that is not followed by "=" is the metric name, which may sit at
            # any position of the label set, not just the first.
            if name is not None:
                return False, f'metric name already set inside the label set, got "{key}" too'
            name = key
        else:
            return False, f'expected "=" behind label name "{key}"'
        while i < len(text) and text[i] in ' \t':
            i += 1
        if i >= len(text):
            break
        if text[i] == ',':
            # A trailing comma is allowed: the loop above ends on it.
            i += 1
        elif dialect == DIALECT_OPENMETRICS:
            # The two grammars disagree about whether the comma is optional. OpenMetrics wants it
            # and its reference parser rejects a label set that leaves one out, so reading
            # `a="1" b="2"` as two labels here would invent a structure out of a payload that says
            # something else. The Prometheus grammar takes the entries apart without it and its
            # reference parser reads them as two labels, so the loop carries on to the next entry
            # rather than lose the whole payload over a separator that format does not require.
            return False, f'expected "," between the entries of a label set at "{text[i:i + 16]}"'
    return True, (name, labels, duplicate)


def _find_brace_close(text, i):
    """Return the offset of the `}` closing the label set that opens at `text[i]`, or -1.

    Scanning for the next `}` is not good enough: a quoted name or value may contain braces of
    its own, unescaped.
    """
    j = i + 1
    while j < len(text):
        char = text[j]
        if char == '"':
            _, j = _read_quoted(text, j)
            if j < 0:
                return -1
            continue
        if char == '}':
            return j
        j += 1
    return -1


# The number grammar of both formats, which is narrower than what Python's float() reads. Spelled
# out rather than filtered, because float() takes digit separators (`1_2`) and non-ASCII digits
# (`١٢٣`), neither of which either format defines. Accepting those would read a number where the
# endpoint sent something else entirely.
_FLOAT_REGEX = re.compile(
    r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[-+]?(?:inf(?:inity)?|nan)',
    re.ASCII | re.IGNORECASE,
)


def _parse_float(text):
    """Parse a value or a timestamp. Returns a `(success, result)` tuple."""
    if not _FLOAT_REGEX.fullmatch(text):
        return False, f'not a number: "{text}"'
    return True, float(text)


# Which sample names a metric family owns, beyond the family name itself, per declared type. A
# `# TYPE` line names the family, not the samples, so this is how a sample finds the metadata
# describing it. Gating by type matters: a gauge named `a` owns no `a_bucket`, so an `a_bucket`
# next to it is a family of its own and not a gauge.
_TYPE_SUFFIXES = {
    'counter': ('_created', '_total'),
    'gaugehistogram': ('_bucket', '_gcount', '_gsum'),
    'histogram': ('_bucket', '_count', '_created', '_sum'),
    'info': ('_info',),
    'summary': ('_count', '_created', '_sum'),
}

_FAMILY_SUFFIXES = tuple(sorted({s for suffixes in _TYPE_SUFFIXES.values() for s in suffixes}))


def _get_meta(meta, name):
    """Return the metadata describing the sample `name`: the family's, with the sample's own laid
    over it.
    """
    entry = meta.get(name, {})
    if 'type' in entry:
        # A sample that declares a type of its own is a metric family in its own right, whatever
        # its name resembles, so nothing of the other one describes it.
        return entry
    for suffix in _FAMILY_SUFFIXES:
        if not name.endswith(suffix):
            continue
        family = meta.get(name[:-len(suffix)])
        if family is None or suffix not in _TYPE_SUFFIXES.get(family.get('type'), ()):
            continue
        # A `# HELP` naming the sample rather than the family must not cost the sample the
        # family's type, so merge rather than let either one win outright.
        merged = dict(family)
        merged.update(entry)
        return merged
    return entry


def _parse_meta_name(text):
    """Read the metric name a `# HELP`, `# TYPE` or `# UNIT` line describes, returning the name
    and the offset behind it, or `(None, -1)`.
    """
    if text.startswith('"'):
        name, offset = _read_quoted(text, 0)
    else:
        match = _METRIC_NAME_REGEX.match(text)
        if not match:
            return None, -1
        name, offset = match.group(0), match.end()
    if offset < 0:
        return None, -1
    if offset < len(text) and text[offset] not in ' \t':
        # The name goes on past what was read, so what was read is not the name: an unquoted one
        # would be leaving the legacy charset, a quoted one would be missing the separator that
        # both grammars require. Taking the part that was read would silently describe a
        # different metric than the line names.
        return None, -1
    return name, offset


# Every type name a `# TYPE` line may carry, per dialect. The lists overlap on the types both
# formats share and differ everywhere the formats disagree, so a payload declaring a type only
# one of them knows cannot be of the other.
_TYPE_NAMES = {
    DIALECT_OPENMETRICS: TYPES,
    DIALECT_PROMETHEUS: frozenset(('counter', 'gauge', 'histogram', 'summary', 'untyped')),
}

_META_REGEX = re.compile(r'#[ \t]+(HELP|TYPE|UNIT)[ \t]+')


def _parse_meta(line, meta, dialect):
    """Parse a `# HELP`, `# TYPE` or `# UNIT` line into `meta`. Returns a `(success, result)`
    tuple.
    """
    match = _META_REGEX.match(line)
    if not match:
        # Not metadata, so a comment. The Prometheus format lets one say anything at all. The
        # OpenMetrics format has no comments at all and its reference parser rejects this. Losing
        # every sample of a payload over a line that carries no measurement would report nothing
        # where the rest of the payload states the truth, so skip it in both dialects.
        return True, None
    keyword = match.group(1)
    if keyword == 'UNIT' and dialect == DIALECT_PROMETHEUS:
        # The Prometheus format has no units, so this is a comment that happens to look like one.
        return True, None
    name, offset = _parse_meta_name(line[match.end():])
    if offset < 0:
        return False, f'expected a metric name in {keyword}, got "{line}"'
    # Strip the separator only, never `str.strip()`'s default: that also takes a non-breaking
    # space, a form feed and a line separator, which both grammars count as ordinary text. It
    # would cut them off a help text and, worse, turn `gauge<NBSP>` into a type that validates.
    text = line[match.end() + offset:].strip(' \t')
    if not text and keyword in ('HELP', 'UNIT'):
        # An empty text says as much as no line at all, and the specification asks for exactly
        # that reading. Reporting `''` instead of `None` would tell a caller testing for absence
        # that the endpoint stated something, and would let an empty line following a filled one
        # erase what that one said.
        return True, None
    entry = meta.setdefault(name, {})
    if keyword == 'HELP':
        # The Prometheus format is alone in leaving `\"` alone in a help text.
        entry['help'] = _unescape(text, quotes=dialect != DIALECT_PROMETHEUS)
        return True, None
    if keyword == 'UNIT':
        if not name.endswith(f'_{text}'):
            # The format carries a unit in the metric name and has `# UNIT` name the part that
            # holds it. One that is not that part describes some other metric than this line
            # names, so it is not this metric's unit.
            return False, f'unit "{text}" is not a suffix of metric "{name}"'
        entry['unit'] = text
        return True, None
    metric_type = text
    if metric_type not in _TYPE_NAMES[dialect]:
        return False, f'invalid metric type "{metric_type}" for metric "{name}"'
    if metric_type == 'untyped':
        metric_type = TYPE_UNKNOWN
    entry['type'] = metric_type
    return True, None


# A timestamp of the Prometheus format is a count of whole milliseconds held in a signed 64 bit
# integer, written as digits and nothing else, not even a sign. The OpenMetrics format counts
# seconds instead and takes any number there.
_PROMETHEUS_TIMESTAMP_REGEX = re.compile(r'\d+', re.ASCII)
_INT64_MAX = 2 ** 63 - 1


def _parse_timestamp(text, dialect):
    """Parse a timestamp into seconds. Returns a `(success, result)` tuple."""
    if dialect == DIALECT_PROMETHEUS:
        if not _PROMETHEUS_TIMESTAMP_REGEX.fullmatch(text):
            return False, f'expected digits for a timestamp in milliseconds, got "{text}"'
        milliseconds = int(text)
        if milliseconds > _INT64_MAX:
            # Python would carry this, the format would not, so it is not a point in time but a
            # digit run that happens to look like one.
            return False, f'timestamp out of range: "{text}"'
        return True, milliseconds / 1000.0
    success, timestamp = _parse_float(text)
    if not success:
        return False, timestamp
    if not math.isfinite(timestamp):
        # A value may be NaN or infinite, a point in time may not.
        return False, f'invalid timestamp "{text}"'
    return True, timestamp


# The separator between a sample and its exemplar. Search for it behind the label set only: a
# label value may contain anything at all, this sequence included. Behind the label set, only the
# value and the timestamp remain, and neither may contain a hash, so the first match is the
# separator.
_EXEMPLAR_REGEX = re.compile(r'[ \t]+#[ \t]*\{')

# What separates a value from its timestamp: a space in both formats, and a tab in the Prometheus
# one only, where OpenMetrics counts a tab as part of the value. Nothing else separates them, so
# str.split() is wrong here: it would take a non-breaking space for a separator and read
# `1<NBSP>2` as two fields where the endpoint sent one, inventing a timestamp out of a bad value.
_FIELD_REGEX = {
    DIALECT_OPENMETRICS: re.compile(r' +'),
    DIALECT_PROMETHEUS: re.compile(r'[ \t]+'),
}


def _parse_sample(line, meta, dialect):
    """Parse one sample line. Returns a `(success, result)` tuple, where result is the sample on
    success, or `_DUPLICATE_LABEL` where the line is well-formed but names a label twice.
    """
    name = None
    labels = {}
    duplicate = False
    if line.startswith('{'):
        offset = 0
    else:
        match = _METRIC_NAME_REGEX.match(line)
        if not match:
            return False, f'expected a metric name, got "{line}"'
        name = match.group(0)
        offset = match.end()
        while offset < len(line) and line[offset] in ' \t':
            offset += 1
    if offset < len(line) and line[offset] == '{':
        close = _find_brace_close(line, offset)
        if close < 0:
            return False, f'unterminated label set in "{line}"'
        success, result = _parse_labels(line[offset + 1:close], dialect)
        if not success:
            return False, result
        # Not acting on `duplicate` here: the value and the timestamp behind the label set still
        # have to be read, so that a sample carrying a duplicate label and an unparseable value
        # fails the payload the way that value alone would.
        quoted_name, labels, duplicate = result
        if quoted_name is not None:
            if name is not None:
                return False, (f'metric name already given in front of the label set, got a '
                               f'second one inside it: "{quoted_name}"')
            name = quoted_name
        offset = close + 1
    if not name:
        # Not `name is None`: a quoted name may also be the empty string, which no grammar
        # allows (both want at least one character) and which would report a nameless sample.
        return False, f'metric name not set in "{line}"'
    rest = line[offset:]
    exemplar = _EXEMPLAR_REGEX.search(rest)
    if exemplar:
        # An exemplar links a sample to a trace. It says nothing about the value, so it is read
        # off the line and dropped rather than reported.
        rest = rest[:exemplar.start()]
    rest = rest.strip(' \t')
    fields = _FIELD_REGEX[dialect].split(rest) if rest else []
    if not fields:
        return False, f'expected a value behind metric "{name}"'
    if len(fields) > 2:
        return False, f'expected nothing behind the timestamp of "{name}", got "{fields[2]}"'
    success, value = _parse_float(fields[0])
    if not success:
        return False, value
    timestamp = None
    if len(fields) == 2:
        success, timestamp = _parse_timestamp(fields[1], dialect)
        if not success:
            return False, timestamp
    if duplicate:
        # Everything the line says has been read by now, so nothing about it is left to fail on.
        return True, _DUPLICATE_LABEL
    entry = _get_meta(meta, name)
    return True, {
        'name': name,
        'labels': labels,
        'value': value,
        'timestamp': timestamp,
        'type': entry.get('type', TYPE_UNKNOWN),
        'help': entry.get('help'),
        'unit': entry.get('unit'),
    }


# `# EOF` terminates an OpenMetrics payload. It is also a legal comment in a Prometheus one, so
# take it as the marker only where it terminates the payload rather than wherever it turns up.
_EOF_MARKER = '# EOF'


def parse(data, dialect=None):
    """
    Read an OpenMetrics or Prometheus text payload into a list of samples.

    Both formats describe a metric with optional `# HELP`, `# TYPE` and `# UNIT` metadata,
    followed by one sample line per label combination. This reports one entry per sample line,
    with the metadata of its metric family already attached, so that a caller never has to
    correlate the two itself.

    Where the formats disagree, `dialect` decides. They differ in six ways: a timestamp counts
    whole milliseconds in Prometheus and any number of seconds in OpenMetrics, a tab separates a
    value from its timestamp in Prometheus while OpenMetrics reads it as part of the value, a
    `\\"` in a help text stays as it is in Prometheus only, the comma between two entries of a
    label set may be left out in Prometheus only, only OpenMetrics knows units and the
    `gaugehistogram`, `info` and `stateset` types, and only Prometheus spells `TYPE_UNKNOWN` as
    `untyped`. Reporting the timestamp of the wrong format would be off by a factor of 1000
    without anything looking wrong, so tell this function which format it reads whenever that is
    known, for instance from the `Content-Type` the endpoint answered with.

    ### Parameters
    - **data** (`str`):
      The payload to read.
    - **dialect** (`str`, optional):
      `'openmetrics'`, `'prometheus'`, or `None` to tell the two apart by whether the payload
      ends in the `# EOF` marker that OpenMetrics requires and Prometheus does not know.
      Defaults to `None`.

    ### Returns
    - **tuple**:
        - tuple[0] (**bool**): True if the payload could be read, otherwise False.
        - tuple[1] (**list | str**):
          - If successful, one dict per sample, in the order the payload listed them, with the
            keys `name` (`str`), `labels` (`dict`), `value` (`float`), `timestamp` (`float` in
            seconds, or `None` if the sample carried none), `type` (one of `TYPES`), `help`
            (`str` or `None`) and `unit` (`str` or `None`).
          - If unsuccessful, an error message string.

    ### Notes
    - Autodetection reads the marker and nothing else, so it is wrong in both directions and
      wrong silently, because a timestamp of the other format parses rather than fails. A
      truncated OpenMetrics payload lacks the marker and is read as Prometheus, putting every
      timestamp 1000 times too far in the past; a Prometheus payload whose last line happens to
      be the comment `# EOF`, which that format allows to say anything at all, is read as
      OpenMetrics, putting every timestamp 1000 times too far in the future. Passing `dialect`
      rules both out, so pass it wherever the format is known, for instance from the
      `Content-Type` the endpoint answered with.
    - Whitespace is taken the lenient way the Prometheus reference parser takes it, in both
      dialects. A payload that a strict OpenMetrics reader would reject over spacing is read
      here. As a consequence, a help text keeps neither its leading nor its trailing spaces.
    - Beyond whitespace, two more line classes are read in the OpenMetrics dialect that its
      reference parser rejects: a blank line, and a comment other than `# HELP`, `# TYPE`,
      `# UNIT` and `# EOF`. Neither carries a measurement, so neither is worth losing every
      sample of the payload over.
    - A sample keeps the name the payload gave it, verbatim. Worth knowing when coming from the
      `prometheus_client` package, which reports a counter under the `_total` name the
      specification asks for even where the endpoint left the suffix out, and so reports a name
      that was never served. Endpoints doing this are not a corner case (Grafana and MinIO both
      do), so select a counter by the name the endpoint actually sends.
    - An empty `# HELP` or `# UNIT` text is reported as `None`, the same as a missing one, which
      is the reading the OpenMetrics specification asks for.
    - A value is always a float, including where the metric counts whole things, because that is
      how both formats define it. `NaN`, `+Inf` and `-Inf` are values like any other.
    - Exemplars are skipped rather than parsed: everything from the exemplar separator to the end
      of the line is dropped unread, so a malformed one does not fail the payload. They point at
      trace data and say nothing about the value. This also reads them in the Prometheus dialect,
      which has no exemplars and whose reference parser rejects them, because an endpoint serving
      OpenMetrics under a `text/plain` content type is a thing that happens. Native histograms, an
      experimental Prometheus extension neither format specifies, are not read at all and fail the
      payload.
    - Neither format forbids a payload from reporting the same name and labels twice. Such
      samples are reported as they arrive, rather than deduplicated.
    - A sample whose label set names the same label twice is dropped, and dropped silently, while
      the rest of the payload is read. Both formats want label names unique within a label set,
      and the two values cannot both be reported anyway, so there is nothing to report for that
      one sample; failing the whole payload over it would throw away every other sample the
      endpoint got right. This is the only line a well-formed payload loses without saying so,
      and it is the one shape where the reader understands the line completely and still cannot
      put it into words. Where the difference matters, ask for the metric by name first: an empty
      result then says the sample is missing, whatever the reason.
    - This reads a payload, it does not judge it. What a sample says has to be well-formed, so an
      unparseable value or an unknown type is an error, and the payload is lost with it, because
      past a line the grammar cannot take apart the reader no longer knows where it is. What a
      payload
      *means* is not checked: a counter may arrive negative, a histogram may be missing its
      `+Inf` bucket, a metric family may be spread over the payload rather than kept together.
      Endpoints in the field send all of that, and the specification forbids all of it. A reader
      that insisted would report nothing at all where a tolerant one reports the truth.

    ### Example
    >>> success, samples = parse(payload, dialect='openmetrics')
    >>> success, samples = parse(payload)
    """
    if not isinstance(data, str):
        return False, 'expected a string to parse'
    # str.splitlines() is wrong here: it breaks on a form feed, a line separator and seven more
    # characters that both grammars take for ordinary content of a label value or a help text.
    # An endpoint that put one there would see the line torn in two, and the tail read as a
    # sample of its own that nobody ever exposed.
    lines = [line.strip(' \t\r') for line in data.split('\n')]
    while lines and not lines[-1]:
        lines.pop()
    has_eof = bool(lines) and lines[-1] == _EOF_MARKER
    if dialect is None:
        dialect = DIALECT_OPENMETRICS if has_eof else DIALECT_PROMETHEUS
    elif dialect not in (DIALECT_OPENMETRICS, DIALECT_PROMETHEUS):
        return False, f'unknown dialect "{dialect}"'
    if dialect == DIALECT_OPENMETRICS:
        if not has_eof:
            return False, 'data does not end with # EOF'
        lines.pop()
        if _EOF_MARKER in lines:
            return False, 'unexpected data after # EOF'
    meta = {}
    samples = []
    for line in lines:
        if not line:
            continue
        if line.startswith('#'):
            success, result = _parse_meta(line, meta, dialect)
        else:
            success, result = _parse_sample(line, meta, dialect)
            if success and result is not _DUPLICATE_LABEL:
                samples.append(result)
        if not success:
            return False, result
    return True, samples
