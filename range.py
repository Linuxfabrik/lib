#! /usr/bin/env python2
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://git.linuxfabrik.ch/linuxfabrik-icinga-plugins/checks-linux/-/blob/master/CONTRIBUTING.md

# Inspired by https://github.com/mpounsett/nagiosplugin/blob/master/nagiosplugin/range.py

__author__  = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2020040202'


def parse(spec):
    if spec is None or spec.lower() == 'none':
        return None
    if type(spec) is not str:
        spec = str(spec)
    invert = False
    if spec.startswith('@'):
        invert = True
        spec = spec[1:]
    if ':' in spec:
        try:
            start, end = spec.split(':')
        except:
            raise ValueError('not using range definition correctly')
    else:
        start, end = '', spec
    if start == '~':
        start = float('-inf')
    else:
        start = parse_atom(start, 0)
    end = parse_atom(end, float('inf'))
    if start > end:
        raise ValueError('start %s must not be greater than end %s' % (
                         start, end))
    return start, end, invert


def parse_atom(atom, default):
    if atom == '':
        return default
    if '.' in atom:
        return float(atom)
    return int(atom)


def match(spec, value):
    """Decides if `value` is inside/outside the threshold spec.

    :returns: `True` if `value` is inside the bounds for a non-inverted
        `spec`, or outside the bounds for an inverted `spec`. Otherwise `False`.
    """
    if spec is None or spec.lower() == 'none':
        return True
    start, end, invert = parse(spec)
    if value < start:
        return False ^ invert
    if value > end:
        return False ^ invert
    return True ^ invert
