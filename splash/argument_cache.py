# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import hashlib


class ArgumentCache(object):
    """
    >>> cache = ArgumentCache()
    >>> "foo" in cache
    False
    >>> len(cache)
    0
    >>> key = cache.add("Hello, world!")
    >>> key
    'bea2c9d7fd040292e0424938af39f7d6334e8d8a'
    >>> cache[key]
    'Hello, world!'
    >>> key in cache
    True
    >>> len(cache)
    1
    >>> cache.get_missing([
    ...    ('bar', key),
    ...    ('baz', '1111111111111111111111111111111111111111'),
    ... ])
    ['baz']
    >>> cache.add_many(['value1', 'value2'])
    ['daf626c4ebd6bdd697e043111454304e5fb1459e', '849988af22dbd04d3e353caf77f9d81241ca9ee2']
    >>> cache['daf626c4ebd6bdd697e043111454304e5fb1459e']
    'value1'
    >>> cache['849988af22dbd04d3e353caf77f9d81241ca9ee2']
    'value2'
    >>> cache[key]
    'Hello, world!'
    >>> len(cache)
    3
    >>> cache.clear()
    >>> len(cache)
    0
    """
    def __init__(self):
        self._values = {}  # TODO: LRU cache

    def add(self, value):
        key = self.get_key(value)
        self._values[key] = value
        return key

    def __getitem__(self, key):
        return self._values[key]

    def __contains__(self, key):
        return key in self._values

    def __len__(self):
        return len(self._values)

    def clear(self):
        self._values.clear()

    def get_missing(self, items):
        return [name for name, key in items if key not in self]

    def add_many(self, values):
        """
        Add all values from ``values`` list to cache. Return a list of keys.
        """
        return [self.add(value) for value in values]

    @classmethod
    def get_key(cls, value):
        value_json = json.dumps(value, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(value_json.encode('utf8')).hexdigest()
