#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""A collection of text functions.

The functions "to_text()" and "to_bytes()" were originally copied
from Ansible's module_utils/_text.py (BSD license), then simplified
for Python 3 only.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2026030301'

import operator
import re
import traceback

_SURROGATE_ERRORS = frozenset((
    None,
    'surrogate_or_replace',
    'surrogate_or_strict',
    'surrogate_then_replace',
))

SENSITIVE_FIELDS_PATTERN = re.compile(
    r'(?i)(\b(?:password|pass|token|key|secret|api[_-]?key|access[_-]?token)\b\s*=\s*|sshpass\s+-p\s*)[^\s&]+'
)
# Explanation:
# (?i)                      # Case-insensitive mode
# (                         # ┌ Capture group 1: the prefix (key=)
#   \b                      # │ Word boundary
#   (?:password|pass|token|key|secret|api[_-]?key|access[_-]?token)
#                           # │   One of the sensitive names:
#                           # │   – password
#                           # │   – pass
#                           # │   – token
#                           # │   – key
#                           # │   – secret
#                           # │   – api_key or api-key
#                           # │   – access_token or access-token
#   \b\s*=\s*               # │ Word boundary, optional ws, '=', optional ws
#  |                        # ├ OR
#   sshpass\s+-p\s*         # │ Literal "sshpass -p" (1+ space before -p)
# )                         # └ End of capture group 1
# [^\s&]+                   # The secret value (not captured, will be replaced)


def compile_regex(regex, key=''):
    """
    Return a compiled regex from a string or list of strings.

    Optionally, add a key qualifier or string to help identify the regex in case of an error.

    ### Parameters
    - **regex** (`str` or `list`): A regex string or a list of regex strings to compile.
    - **key** (`str`, optional): A label or identifier string for better error messages. Defaults to ''.

    ### Returns
    - **tuple** or **list of tuples**:  
      - For a single regex string:  
        `(True, compiled_regex)` on success, or `(False, error_message)` on failure.
      - For a list of regex strings:  
        A list of such (success, result) tuples.

    ### Example
    >>> compile_regex(r'^[a-z]+$')
    (True, re.compile('^[a-z]+$'))

    >>> compile_regex([r'^[a-z]+$', r'\\d+'])
    [(True, re.compile('^[a-z]+$')), (True, re.compile('\\d+'))]
    """

    def _compile(rgx):
        try:
            return True, re.compile(rgx)
        except re.error as e:
            return False, f'`{rgx}`{f" ({key})" if key else ""} contains one or more errors: {e}'

    return _compile(regex) if isinstance(regex, str) else [_compile(rgx) for rgx in regex]


def exception2text(e):
    """
    Convert an exception into a concise, human-readable string.

    Produces the format `"ExceptionType: message"`. If the exception’s `__str__`
    is empty, it falls back to Python’s `traceback.format_exception_only()` to
    obtain a meaningful message. As a last resort, it returns `repr(e)` to avoid
    losing error context.

    ### Parameters
    - **e** (`Exception`): The exception instance to stringify.

    ### Returns
    - **str**: A stable, readable string such as `"ValueError: invalid literal for int() with base 10: 'x'"`.

    ### Example
    >>> try:
    ...     int("x")
    ... except Exception as exc:
    ...     exception2text(exc)
    "ValueError: invalid literal for int() with base 10: 'x'"

    >>> class EmptyStrError(Exception):
    ...     def __str__(self): return ""
    ...
    >>> exception2text(EmptyStrError())
    "EmptyStrError: EmptyStrError()"
    """
    try:
        msg = str(e)
        if not msg:
            # Some exceptions have empty __str__; use Python's formatter
            msg = ''.join(traceback.format_exception_only(type(e), e)).strip()
        return f"{type(e).__name__}: {msg}"
    except Exception:
        # Absolute fallback
        return repr(e)


def extract_str(s, from_txt, to_txt, include_fromto=False, be_tolerant=True):
    """
    Extracts a substring from `s` that lies between the markers `from_txt` and `to_txt`.

    The extraction rules are:
      - If `from_txt` is not found in `s`, returns an empty string.
      - If `to_txt` is not found:
          - When `be_tolerant` is True (default):
              • If `include_fromto` is False: return substring from after `from_txt` to the end.
              • If `include_fromto` is True: return substring including `from_txt` to the end.
          - When `be_tolerant` is False: returns an empty string.
      - If both markers are found:
          - If `include_fromto` is False (default): return text between `from_txt` and `to_txt`.
          - If `include_fromto` is True: return text including `from_txt` and `to_txt`.

    ### Parameters
    - **s** (`str`): The input string.
    - **from_txt** (`str`): The starting marker.
    - **to_txt** (`str`): The ending marker.
    - **include_fromto** (`bool`, optional): Whether to include the markers in the result.
      Defaults to False.
    - **be_tolerant** (`bool`, optional): Whether to return remaining string if `to_txt` isn't
      found. Defaults to True.

    ### Returns
    - **str**: The extracted substring, or an empty string if markers are missing
      (depending on tolerance).

    ### Example
    >>> extract_str('abcde', 'x', 'y')
    ''

    >>> extract_str('abcde', 'b', 'x')
    'cde'

    >>> extract_str('abcde', 'b', 'b')
    'cde'

    >>> extract_str('abcde', 'b', 'x', include_fromto=True)
    'bcde'

    >>> extract_str('abcde', 'b', 'x', include_fromto=True, be_tolerant=False)
    ''

    >>> extract_str('abcde', 'b', 'd')
    'c'

    >>> extract_str('abcde', 'b', 'd', include_fromto=True)
    'bcd'

    >>> s = 'Time zone: UTC (UTC,+0000)\\nSystem clock synchronized: yes\\n  NTP service: active\\n'
    >>> extract_str(s, 'System clock synchronized: ', '\\n', include_fromto=True)
    'System clock synchronized: yes\\n'
    """
    pos1 = s.find(from_txt)
    if pos1 == -1:
        return ''

    start = pos1 if include_fromto else pos1 + len(from_txt)
    pos2 = s.find(to_txt, start)

    if pos2 != -1:
        end = pos2 + len(to_txt) if include_fromto else pos2
        return s[start:end]
    if not be_tolerant:
        return ''
    if include_fromto:
        return s[pos1:]
    return s[pos1 + len(from_txt):]


def filter_mltext(_input, ignore):
    """
    Filter multi-line text, removing lines that match any simple text pattern from the ignore list
    (no regex).

    `ignore` must be provided as a list of strings.

    ### Parameters
    - **_input** (`str`): The multi-line input text to filter.
    - **ignore** (`list`): A list of strings; lines containing any of these substrings will be
      removed.

    ### Returns
    - **str**: The filtered multi-line text.

    ### Example
    >>> filter_mltext('abcde', 'a')  # "ignore" has to be a list
    ''

    >>> s = 'Lorem ipsum\\n\\ndolor sit amet\\n\\nconsectetur adipisicing'
    >>> filter_mltext(s, ['ipsum'])
    '\\ndolor sit amet\\n\\nconsectetur adipisicing\\n'

    >>> filter_mltext(s, ['dol'])
    'Lorem ipsum\\n\\n\\nconsectetur adipisicing\\n'

    >>> filter_mltext(s, ['Dol'])
    'Lorem ipsum\\n\\ndolor sit amet\\n\\nconsectetur adipisicing\\n'

    >>> filter_mltext(s, ['d'])
    'Lorem ipsum\\n\\n\\n'

    >>> s = 'Lorem ipsum'
    >>> filter_mltext(s, ['Dol'])
    'Lorem ipsum\\n'

    >>> filter_mltext(s, ['ipsum'])
    ''
    """
    lines = [
        line for line in _input.splitlines()
        if not any(i_line in line for i_line in ignore)
    ]
    return '\n'.join(lines) + '\n' if lines else ''


def match_regex(regex, string, key=''):
    """
    Match a regex on a string.

    Optionally, add a key qualifier or string to help identify the regex in case of an error.

    ### Parameters
    - **regex** (`str`): The regular expression pattern to match.
    - **string** (`str`): The string to apply the regex match on.
    - **key** (`str`, optional): An optional label or identifier for better error messages.
      Defaults to ''.

    ### Returns
    - **tuple**: 
      - On success: (True, match_object)
      - On regex error: (False, error_message)

    ### Example
    >>> match_regex(r'^abc$', 'abc')
    (True, <re.Match object>)

    >>> match_regex(r'[', 'text', key='example')
    (False, '`[` contains one or more errors:  (example)')
    """
    try:
        return True, re.match(regex, string)
    except re.error as e:
        key_str = f' ({key})' if key else ''
        return False, f'`{regex}` contains one or more errors:{key_str} {e}'


def mltext2array(_input, skip_header=False, sort_key=-1):
    """
    Convert multi-line text into an array (list of lists), splitting by whitespace.

    Allows optional skipping of the first line (as header) and sorting by a specific column.

    ### Parameters
    - **_input** (`str`): The multi-line input text to process.
    - **skip_header** (`bool`, optional): If True, skip the first line. Defaults to False.
    - **sort_key** (`int`, optional): Index of the column to sort by. Set to -1 to disable sorting.
      Defaults to -1.

    ### Returns
    - **list of list**: A list where each inner list represents a line split by whitespace.

    ### Example
    >>> s = '1662130953 timedatex\\n1662130757 python3-pip-wheel\\n1662130975 python3-dateutil'

    >>> mltext2array(s, skip_header=False, sort_key=0)
    [['1662130757', 'python3-pip-wheel'], ['1662130953', 'timedatex'], ['1662130975', 'python3-dateutil']]

    >>> mltext2array(s, skip_header=False, sort_key=1)
    [['1662130975', 'python3-dateutil'], ['1662130757', 'python3-pip-wheel'], ['1662130953', 'timedatex']]
    """
    lines = _input.strip().splitlines()
    if skip_header:
        lines = lines[1:]
    result = [line.split() for line in lines]
    if sort_key != -1:
        result.sort(key=operator.itemgetter(sort_key))
    return result


def multi_replace(text, replacements):
    """
    Replace all occurrences in a string based on the provided mapping.

    ### Parameters
    - **text** (`str`): The input text in which to perform replacements.
    - **replacements** (`dict`): A dictionary where each key is a substring to replace,
      and each value is its replacement.

    ### Returns
    - **str**: The text after all replacements have been applied.

    ### Example
    >>> multi_replace('Hello World!', {'Hello': 'Hi', 'World': 'Universe'})
    'Hi Universe!'
    """
    for old, new in replacements.items():
        text = text.replace(old, str(new))
    return text


def pluralize(noun, value, suffix='s'):
    """
    Returns a plural suffix if the value is not 1. By default, 's' is used as the suffix.

    Based on:  
    https://kite.com/python/docs/django.template.defaultfilters.pluralize

    ### Parameters
    - **noun** (`str`): The base noun to pluralize.
    - **value** (`int`): The numeric value to determine singular or plural form.
    - **suffix** (`str`, optional): 
      - If a simple string (e.g., `'s'` or `'es'`), it is appended when plural.
      - If a comma-separated string (e.g., `'y,ies'`), the first part is used for singular, the
        second for plural.
      Defaults to `'s'`.

    ### Returns
    - **str**: The correctly pluralized word.

    ### Example
    >>> pluralize('vote', 0)
    'votes'

    >>> pluralize('vote', 1)
    'vote'

    >>> pluralize('vote', 2)
    'votes'

    If a specific suffix is provided:

    >>> pluralize('class', 0, 'es')
    'classes'

    >>> pluralize('class', 1, 'es')
    'class'

    >>> pluralize('class', 2, 'es')
    'classes'

    If the suffix contains a comma (singular,plural forms):

    >>> pluralize('cand', 0, 'y,ies')
    'candies'

    >>> pluralize('cand', 1, 'y,ies')
    'candy'

    >>> pluralize('cand', 2, 'y,ies')
    'candies'

    >>> pluralize('', 1, 'is,are')
    'is'

    >>> pluralize('', 2, 'is,are')
    'are'
    """
    if int(value) == 1:
        return f'{noun}{suffix.split(",")[0]}' if ',' in suffix else noun
    return f'{noun}{suffix.split(",")[1]}' if ',' in suffix else f'{noun}{suffix}'


def sanitize_sensitive_data(msg, replacement='******'):
    """
    Redact sensitive information such as passwords, tokens, and keys from a message string.

    This function searches for common sensitive fields in the input text (e.g., 'password',
    'token', 'key') and replaces their values with asterisks or a custom string to prevent
    accidental exposure.

    ### Parameters
    - **msg** (`str` or `any`): The input message that may contain sensitive data.  
      If not a string, it is returned unchanged.
    - **replacement** (`str`, optional): The string to replace sensitive values with.
      Defaults to '******'.

    ### Returns
    - **str** or **original type**: The sanitized string with sensitive values redacted,
      or the original object if it is not a string.

    ### Notes
    - Matching is case-insensitive and tolerant of whitespace around '='.
    - Only parameters in the format key=value are sanitized.
    - Fields sanitized: 'password', 'pass', 'token', 'key', 'secret', 'api-key',
      'access_token', and similar variants.

    ### Example
    >>> sanitize_sensitive_data('user=admin&password=secret123')
    'user=admin&password=******'

    >>> sanitize_sensitive_data('Authorization token=abcde12345', replacement='REDACTED')
    'Authorization token=REDACTED'

    >>> sanitize_sensitive_data('api_key = xyz987')
    'api_key = ******'
    """
    if not isinstance(msg, str):
        return msg
    return SENSITIVE_FIELDS_PATTERN.sub(rf'\1{replacement}', msg)


def to_bytes(obj, encoding='utf-8', errors=None,
             nonstring='simplerepr'):
    """
    Convert an object to a byte string.

    If `obj` is already `bytes`, it is returned unchanged. If it
    is a `str`, it is encoded. Otherwise the `nonstring` strategy
    decides what happens.

    ### Parameters
    - **obj** (`any`): The object to convert.
    - **encoding** (`str`, optional): Encoding to use.
      Defaults to `'utf-8'`.
    - **errors** (`str`, optional): Error handler for encoding.
      Surrogate-related strategies (`surrogate_or_strict`,
      `surrogate_or_replace`, `surrogate_then_replace`, or
      `None`) are mapped to `'surrogateescape'`.
      Defaults to `None`.
    - **nonstring** (`str`, optional): Strategy for non-string
      objects:
      - `simplerepr`: Convert via `str(obj)`, then encode.
      - `empty`: Return `b''`.
      - `passthru`: Return `obj` unchanged.
      - `strict`: Raise a `TypeError`.
      Defaults to `'simplerepr'`.

    ### Returns
    - **bytes** or **other type**: A byte string, or the
      original object if `nonstring='passthru'`.

    ### Example
    >>> to_bytes('hello')
    b'hello'

    >>> to_bytes(1234)
    b'1234'

    >>> to_bytes('abc', encoding='latin-1')
    b'abc'

    >>> to_bytes(None, nonstring='empty')
    b''
    """
    if isinstance(obj, bytes):
        return obj

    original_errors = errors
    if errors in _SURROGATE_ERRORS:
        errors = 'surrogateescape'

    if isinstance(obj, str):
        try:
            return obj.encode(encoding, errors)
        except UnicodeEncodeError:
            if original_errors in (None, 'surrogate_then_replace'):
                return obj.encode(
                    'utf-8', 'surrogateescape',
                ).decode(
                    'utf-8', 'replace',
                ).encode(encoding, 'replace')
            raise

    if nonstring == 'simplerepr':
        return str(obj).encode(encoding, errors)
    if nonstring == 'passthru':
        return obj
    if nonstring == 'empty':
        return b''
    if nonstring == 'strict':
        raise TypeError('obj must be a string type')
    raise TypeError(
        f'Invalid value {nonstring!r} for to_bytes\''
        ' nonstring parameter'
    )


def to_text(obj, encoding='utf-8', errors=None,
            nonstring='simplerepr'):
    """
    Convert an object to a text (unicode) string.

    If `obj` is already a `str`, it is returned unchanged. If it
    is `bytes`, it is decoded. Otherwise the `nonstring` strategy
    decides what happens.

    ### Parameters
    - **obj** (`any`): The object to convert.
    - **encoding** (`str`, optional): Encoding to use when
      decoding byte strings. Defaults to `'utf-8'`.
    - **errors** (`str`, optional): Error handler for decoding.
      Surrogate-related strategies (`surrogate_or_strict`,
      `surrogate_or_replace`, `surrogate_then_replace`, or
      `None`) are mapped to `'surrogateescape'`.
      Defaults to `None`.
    - **nonstring** (`str`, optional): Strategy for non-string
      objects:
      - `simplerepr`: Convert via `str(obj)`.
      - `empty`: Return `''`.
      - `passthru`: Return `obj` unchanged.
      - `strict`: Raise a `TypeError`.
      Defaults to `'simplerepr'`.

    ### Returns
    - **str** or **other type**: A text string, or the original
      object if `nonstring='passthru'`.

    ### Example
    >>> to_text(b'hello')
    'hello'

    >>> to_text('already text')
    'already text'

    >>> to_text(1234)
    '1234'

    >>> to_text(None, nonstring='empty')
    ''
    """
    if isinstance(obj, str):
        return obj

    if errors in _SURROGATE_ERRORS:
        errors = 'surrogateescape'

    if isinstance(obj, bytes):
        return obj.decode(encoding, errors)

    if nonstring == 'simplerepr':
        return str(obj)
    if nonstring == 'passthru':
        return obj
    if nonstring == 'empty':
        return ''
    if nonstring == 'strict':
        raise TypeError('obj must be a string type')
    raise TypeError(
        f'Invalid value {nonstring!r} for to_text\'s'
        ' nonstring parameter'
    )


def uniq(string):
    """
    Removes duplicate words from a string (only the second and further duplicates).

    The original sequence of the words is preserved.

    ### Parameters
    - **string** (`str`): The input string containing words.

    ### Returns
    - **str**: A string with duplicate words removed, preserving the original order.

    ### Example
    >>> uniq('This is a test. This is a second test. And this is a third test.')
    'This is a test. second And this third'
    """
    words = string.split()
    seen = set()
    return ' '.join(w for w in words if not (w in seen or seen.add(w)))


to_native = to_text
