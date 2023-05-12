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
__version__ = '2023051201'

import codecs
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


def extract_str(s, from_txt, to_txt, include_fromto=False, be_tolerant=True):
    """Extracts text between `from_txt` to `to_txt`.
    If `include_fromto` is set to False (default), text is returned without both search terms,
    otherwise `from_txt` and `to_txt` are included.
    If `from_txt` is not found, always an empty string is returned.
    If `to_txt` is not found and `be_tolerant` is set to True (default), text is returned from
    `from_txt` til the end of input text. Otherwise an empty text is returned.

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
    >>> s = '  Time zone: UTC (UTC, +0000)\nSystem clock synchronized: yes\n  NTP service: active\n'
    >>> extract_str(s, 'System clock synchronized: ', '\n', include_fromto=True)
    'System clock synchronized: yes\n'
    """
    pos1 = s.find(from_txt)
    if pos1 == -1:
        # nothing found
        return ''
    pos2 = s.find(to_txt, pos1+len(from_txt))
    # to_txt not found:
    if pos2 == -1 and be_tolerant and not include_fromto:
        return s[pos1+len(from_txt):]
    if pos2 == -1 and be_tolerant and include_fromto:
        return s[pos1:]
    if pos2 == -1 and not be_tolerant:
        return ''
    # from_txt and to_txt found:
    if not include_fromto:
        return s[pos1+len(from_txt):pos2-len(to_txt)+ 1]
    return s[pos1:pos2+len(to_txt)]


def filter_mltext(_input, ignore):
    """Filter multi-line text, remove lines with matches a simple text ignore pattern (no regex).
    `ignore` has to be a list.

    >>> filter_mltext('abcde', 'a')  # "ignore" has to be a list
    ''

    >>> s = 'Lorem ipsum\ndolor sit amet\nconsectetur adipisicing'
    >>> filter_mltext(s, ['ipsum'])
    'dolor sit amet\nconsectetur adipisicing\n'
    >>> filter_mltext(s, ['dol'])
    'Lorem ipsum\nconsectetur adipisicing\n'
    >>> filter_mltext(s, ['Dol'])
    'Lorem ipsum\ndolor sit amet\nconsectetur adipisicing\n'
    >>> filter_mltext(s, ['d'])
    'Lorem ipsum\n'

    >>> s = 'Lorem ipsum'
    >>> filter_mltext(s, ['Dol'])
    'Lorem ipsum\n'
    >>> filter_mltext(s, ['ipsum'])
    ''
    """
    filtered_input = ''
    for line in _input.splitlines():
        if not any(i_line in line for i_line in ignore):
            filtered_input += line + '\n'
    return filtered_input


def mltext2array(_input, skip_header=False, sort_key=-1):
    """
    >>> s = '1662130953 timedatex\n1662130757 python3-pip-wheel\n1662130975 python3-dateutil\n'
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


def pluralize(noun, value, suffix='s'):
    """Returns a plural suffix if the value is not 1. By default, 's' is used as
    the suffix.
    From https://kite.com/python/docs/django.template.defaultfilters.pluralize

    >>> pluralize('vote', 0)
    'votes'
    >>> pluralize('vote', 1)
    'vote'
    >>> pluralize('vote', 2)
    'votes'

    If an argument is provided, that string is used instead:

    >>> pluralize('class', 0, 'es')
    'classes'
    >>> pluralize('class', 1, 'es')
    'class'
    >>> pluralize('class', 2, 'es')
    'classes'

    If the provided argument contains a comma, the text before the comma is used
    for the singular case and the text after the comma is used for the plural
    case:

    >>> pluralize('cand', 0, 'y,ies)
    'candies'
    >>> pluralize('cand', 1, 'y,ies)
    'candy'
    >>> pluralize('cand', 2, 'y,ies)
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
    """Make sure that a string is a byte string

    :arg obj: An object to make sure is a byte string.  In most cases this
        will be either a text string or a byte string.  However, with
        ``nonstring='simplerepr'``, this can be used as a traceback-free
        version of ``str(obj)``.
    :kwarg encoding: The encoding to use to transform from a text string to
        a byte string.  Defaults to using 'utf-8'.
    :kwarg errors: The error handler to use if the text string is not
        encodable using the specified encoding.  Any valid `codecs error
        handler <https://docs.python.org/2/library/codecs.html#codec-base-classes>`_
        may be specified. There are three additional error strategies
        specifically aimed at helping people to port code.  The first two are:

            :surrogate_or_strict: Will use ``surrogateescape`` if it is a valid
                handler, otherwise it will use ``strict``
            :surrogate_or_replace: Will use ``surrogateescape`` if it is a valid
                handler, otherwise it will use ``replace``.

        Because ``surrogateescape`` was added in Python3 this usually means that
        Python3 will use ``surrogateescape`` and Python2 will use the fallback
        error handler. Note that the code checks for ``surrogateescape`` when the
        module is imported.  If you have a backport of ``surrogateescape`` for
        Python2, be sure to register the error handler prior to importing this
        module.

        The last error handler is:

            :surrogate_then_replace: Will use ``surrogateescape`` if it is a valid
                handler.  If encoding with ``surrogateescape`` would traceback,
                surrogates are first replaced with a replacement characters
                and then the string is encoded using ``replace`` (which replaces
                the rest of the nonencodable bytes).  If ``surrogateescape`` is
                not present it will simply use ``replace``.  (Added in Ansible 2.3)
                This strategy is designed to never traceback when it attempts
                to encode a string.

        The default until Ansible-2.2 was ``surrogate_or_replace``
        From Ansible-2.3 onwards, the default is ``surrogate_then_replace``.

    :kwarg nonstring: The strategy to use if a nonstring is specified in
        ``obj``.  Default is 'simplerepr'.  Valid values are:

        :simplerepr: The default.  This takes the ``str`` of the object and
            then returns the bytes version of that string.
        :empty: Return an empty byte string
        :passthru: Return the object passed in
        :strict: Raise a :exc:`TypeError`

    :returns: Typically this returns a byte string.  If a nonstring object is
        passed in this may be a different type depending on the strategy
        specified by nonstring.  This will never return a text string.

    .. note:: If passed a byte string, this function does not check that the
        string is valid in the specified encoding.  If it's important that the
        byte string is in the specified encoding do::

            encoded_string = to_bytes(to_text(input_string, 'latin-1'), 'utf-8')

    .. version_changed:: 2.3

        Added the ``surrogate_then_replace`` error handler and made it the default error handler.
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
    """Make sure that a string is a text string

    :arg obj: An object to make sure is a text string.  In most cases this
        will be either a text string or a byte string.  However, with
        ``nonstring='simplerepr'``, this can be used as a traceback-free
        version of ``str(obj)``.
    :kwarg encoding: The encoding to use to transform from a byte string to
        a text string.  Defaults to using 'utf-8'.
    :kwarg errors: The error handler to use if the byte string is not
        decodable using the specified encoding.  Any valid `codecs error
        handler <https://docs.python.org/2/library/codecs.html#codec-base-classes>`_
        may be specified.   We support three additional error strategies
        specifically aimed at helping people to port code:

            :surrogate_or_strict: Will use surrogateescape if it is a valid
                handler, otherwise it will use strict
            :surrogate_or_replace: Will use surrogateescape if it is a valid
                handler, otherwise it will use replace.
            :surrogate_then_replace: Does the same as surrogate_or_replace but
                `was added for symmetry with the error handlers in
                :func:`ansible.module_utils._text.to_bytes` (Added in Ansible 2.3)

        Because surrogateescape was added in Python3 this usually means that
        Python3 will use `surrogateescape` and Python2 will use the fallback
        error handler. Note that the code checks for surrogateescape when the
        module is imported.  If you have a backport of `surrogateescape` for
        python2, be sure to register the error handler prior to importing this
        module.

        The default until Ansible-2.2 was `surrogate_or_replace`
        In Ansible-2.3 this defaults to `surrogate_then_replace` for symmetry
        with :func:`ansible.module_utils._text.to_bytes` .
    :kwarg nonstring: The strategy to use if a nonstring is specified in
        ``obj``.  Default is 'simplerepr'.  Valid values are:

        :simplerepr: The default.  This takes the ``str`` of the object and
            then returns the text version of that string.
        :empty: Return an empty text string
        :passthru: Return the object passed in
        :strict: Raise a :exc:`TypeError`

    :returns: Typically this returns a text string.  If a nonstring object is
        passed in this may be a different type depending on the strategy
        specified by nonstring.  This will never return a byte string.
        From Ansible-2.3 onwards, the default is `surrogate_then_replace`.

    .. version_changed:: 2.3

        Added the surrogate_then_replace error handler and made it the default error handler.
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
    """Removes duplicate words from a string (only the second duplicates).
    The sequence of the words will not be changed.

    >>> uniq('This is a test. This is a second test. And this is a third test.')
    'This is a test. second And this third'
    """
    words = string.split()
    return ' '.join(sorted(set(words), key=words.index))


to_native = to_text
# PY2: to_native = to_bytes
