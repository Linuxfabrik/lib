#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""A collection of text functions.

The functions "to_text()" and "to_bytes()" are copied from
/usr/lib/python3.10/site-packages/ansible/module_utils/_text.py (BSD license).
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2025041901'

import codecs
import re
try:
    codecs.lookup_error('surrogateescape')
    HAS_SURROGATEESCAPE = True
except LookupError:
    HAS_SURROGATEESCAPE = False
import operator

string_types = str
integer_types = int
class_types = type
text_type = str
binary_type = bytes

_COMPOSED_ERROR_HANDLERS = frozenset((None, 'surrogate_or_replace',
                                      'surrogate_or_strict',
                                      'surrogate_then_replace'))


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

    def cr(regex, key=''):
        """Return a compiled regex from a string.
        """
        try:
            return (True, re.compile(regex))
        except re.error as e:
            return (False, '`{}`{} contains one or more errors: {}'.format(
                regex,
                ' ({})'.format(key) if key else '',
                e,
            ))

    if isinstance(regex, str):
        return cr(regex, key=key)
    else:
        return [cr(item, key=key) for item in regex]


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
        # 'from_txt' not found
        return ''
    pos2 = s.find(to_txt, pos1 + len(from_txt))
    # 'to_txt' not found:
    if pos2 == -1 and be_tolerant and not include_fromto:
        return s[pos1 + len(from_txt):]
    if pos2 == -1 and be_tolerant and include_fromto:
        return s[pos1:]
    if pos2 == -1 and not be_tolerant:
        return ''
    # Both 'from_txt' and 'to_txt' are found:
    if not include_fromto:
        return s[pos1 + len(from_txt):pos2]
    return s[pos1:pos2 + len(to_txt)]


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

    >>> s = 'Lorem ipsum\\ndolor sit amet\\nconsectetur adipisicing'
    >>> filter_mltext(s, ['ipsum'])
    'dolor sit amet\\nconsectetur adipisicing\\n'

    >>> filter_mltext(s, ['dol'])
    'Lorem ipsum\\nconsectetur adipisicing\\n'

    >>> filter_mltext(s, ['Dol'])
    'Lorem ipsum\\ndolor sit amet\\nconsectetur adipisicing\\n'

    >>> filter_mltext(s, ['d'])
    'Lorem ipsum\\n'

    >>> s = 'Lorem ipsum'
    >>> filter_mltext(s, ['Dol'])
    'Lorem ipsum\\n'

    >>> filter_mltext(s, ['ipsum'])
    ''
    """
    filtered_input = ''
    for line in _input.splitlines():
        if not any(i_line in line for i_line in ignore):
            filtered_input += line + '\n'
    return filtered_input


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
        return (True, re.match(regex, string))
    except re.error as e:
        return (False, '`{}` contains one or more errors: {}'.format(
            regex,
            ' ({})'.format(key) if key else '',
            e,
        ))


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
    >>> s = '1662130953 timedatex\\n1662130757 python3-pip-wheel\\n1662130975 python3-dateutil\\n'

    >>> mltext2array(s, skip_header=False, sort_key=0)
    [['1662130757', 'python3-pip-wheel'], ['1662130953', 'timedatex'], ['1662130975', 'python3-dateutil']]

    >>> mltext2array(s, skip_header=False, sort_key=1)
    [['1662130975', 'python3-dateutil'], ['1662130757', 'python3-pip-wheel'], ['1662130953', 'timedatex']]
    """
    _input = _input.strip(' \t\n\r').split('\n')
    lines = []
    if skip_header:
        del _input[0]
    for row in _input:
        lines.append(row.split())
    if sort_key != -1:
        lines = sorted(lines, key=operator.itemgetter(sort_key))
    return lines


def multi_replace(text, repl_map):
    """
    Replace all occurrences in a string based on the provided mapping.

    ### Parameters
    - **text** (`str`): The input text in which to perform replacements.
    - **repl_map** (`dict`): A dictionary where each key is a substring to replace, and each value
      is its replacement.

    ### Returns
    - **str**: The text after all replacements have been applied.

    ### Example
    >>> multi_replace('Hello World!', {'Hello': 'Hi', 'World': 'Universe'})
    'Hi Universe!'
    """
    for old, new in repl_map.items():
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
    if ',' in suffix:
        singular, plural = suffix.split(',')
    else:
        singular, plural = '', suffix
    if int(value) == 1:
        return noun + singular
    return noun + plural


# from /usr/lib/python3.10/site-packages/ansible/module_utils/_text.py
def to_bytes(obj, encoding='utf-8', errors=None, nonstring='simplerepr'):
    """
    Make sure that a string is a byte string.

    This function ensures the given object is converted into a byte string, handling encoding errors
    and non-string types according to provided options.

    ### Parameters
    - **obj** (`any`): The object to convert to a byte string. Typically a text or byte string.
    - **encoding** (`str`, optional): Encoding to use for conversion. Defaults to `'utf-8'`.
    - **errors** (`str`, optional): Error handling strategy during encoding.  
      Supports standard codecs handlers and special strategies:  
      - `surrogate_or_strict`
      - `surrogate_or_replace`
      - `surrogate_then_replace` (default in Ansible 2.3+).
    - **nonstring** (`str`, optional): Strategy if `obj` is not a string.  
      Options:
      - `simplerepr`: `str(obj)` and convert.
      - `empty`: Return an empty byte string.
      - `passthru`: Return `obj` unchanged.
      - `strict`: Raise a `TypeError`.  
      Defaults to `'simplerepr'`.

    ### Returns
    - **bytes** or **other type**: Typically a byte string. For non-strings, behavior depends on
      `nonstring` setting.

    ### Notes
    - If passed a byte string, no re-encoding is performed.
    - On encoding error with `surrogate_then_replace`, the function will fallback gracefully.
    - To ensure a byte string is in a specific encoding, re-encode using `to_bytes(to_text(...))`.

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
    if isinstance(obj, binary_type):
        return obj

    # We're given a text string
    # If it has surrogates, we know because it will decode
    original_errors = errors
    if errors in _COMPOSED_ERROR_HANDLERS:
        if HAS_SURROGATEESCAPE:
            errors = 'surrogateescape'
        elif errors == 'surrogate_or_strict':
            errors = 'strict'
        else:
            errors = 'replace'

    if isinstance(obj, text_type):
        try:
            # Try this first as it's the fastest
            return obj.encode(encoding, errors)
        except UnicodeEncodeError:
            if original_errors in (None, 'surrogate_then_replace'):
                # We should only reach this if encoding was non-utf8 original_errors was
                # surrogate_then_escape and errors was surrogateescape

                # Slow but works
                return_string = obj.encode('utf-8', 'surrogateescape')
                return_string = return_string.decode('utf-8', 'replace')
                return return_string.encode(encoding, 'replace')
            raise

    # Note: We do these last even though we have to call to_bytes again on the
    # value because we're optimizing the common case
    if nonstring == 'simplerepr':
        try:
            value = str(obj)
        except UnicodeError:
            try:
                value = repr(obj)
            except UnicodeError:
                # Giving up
                return to_bytes('')
    elif nonstring == 'passthru':
        return obj
    elif nonstring == 'empty':
        # python2.4 doesn't have b''
        return to_bytes('')
    elif nonstring == 'strict':
        raise TypeError('obj must be a string type')
    else:
        raise TypeError('Invalid value %s for to_bytes\' nonstring parameter' % nonstring)

    return to_bytes(value, encoding, errors)


# from /usr/lib/python3.10/site-packages/ansible/module_utils/_text.py
def to_text(obj, encoding='utf-8', errors=None, nonstring='simplerepr'):
    """
    Make sure that a string is a text string.

    This function ensures the given object is converted into a Unicode text string,
    handling decoding errors and non-string types according to the provided options.

    ### Parameters
    - **obj** (`any`): The object to convert to a text string. Typically a byte or text string.
    - **encoding** (`str`, optional): Encoding to use when decoding byte strings. Defaults to
      `'utf-8'`.
    - **errors** (`str`, optional): Error handling strategy during decoding.  
      Supports standard codecs handlers and special strategies:
      - `surrogate_or_strict`
      - `surrogate_or_replace`
      - `surrogate_then_replace` (default in Ansible 2.3+).
    - **nonstring** (`str`, optional): Strategy for handling non-string types:
      - `simplerepr`: Default; uses `str(obj)` and converts.
      - `empty`: Return an empty text string.
      - `passthru`: Return the original object.
      - `strict`: Raise a `TypeError`.  
      Defaults to `'simplerepr'`.

    ### Returns
    - **str** or **other type**:  
      - Typically returns a text string.
      - May return other types depending on `nonstring` strategy.  
      - Never returns a byte string.

    ### Notes
    - If passed a text string, returns it unchanged.
    - On decoding error with `surrogate_then_replace`, fallback gracefully.
    - From Ansible 2.3 onwards, the default error handler is `surrogate_then_replace`.

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
    if isinstance(obj, text_type):
        return obj

    if errors in _COMPOSED_ERROR_HANDLERS:
        if HAS_SURROGATEESCAPE:
            errors = 'surrogateescape'
        elif errors == 'surrogate_or_strict':
            errors = 'strict'
        else:
            errors = 'replace'

    if isinstance(obj, binary_type):
        # Note: We don't need special handling for surrogate_then_replace
        # because all bytes will either be made into surrogates or are valid
        # to decode.
        return obj.decode(encoding, errors)

    # Note: We do these last even though we have to call to_text again on the
    # value because we're optimizing the common case
    if nonstring == 'simplerepr':
        try:
            value = str(obj)
        except UnicodeError:
            try:
                value = repr(obj)
            except UnicodeError:
                # Giving up
                return ''
    elif nonstring == 'passthru':
        return obj
    elif nonstring == 'empty':
        return ''
    elif nonstring == 'strict':
        raise TypeError('obj must be a string type')
    else:
        raise TypeError('Invalid value %s for to_text\'s nonstring parameter' % nonstring)

    return to_text(value, encoding, errors)


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
    return ' '.join(sorted(set(words), key=words.index))


to_native = to_text
# PY2: to_native = to_bytes
