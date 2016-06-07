# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import hashlib
from collections import OrderedDict


# Add move_to_end method for python 2.7
# See https://github.com/twitter/commons/blob/master/src/python/twitter/common/collections/ordereddict.py#L284
if not hasattr(OrderedDict, 'move_to_end'):
    def move_to_end(self, key, last=True):
        link_prev, link_next, key = link = self._OrderedDict__map[key]
        link_prev[1] = link_next
        link_next[0] = link_prev
        root = self._OrderedDict__root
        if last:
            last = root[0]
            link[0] = last
            link[1] = root
            last[1] = root[0] = link
    OrderedDict.move_to_end = move_to_end


class ArgumentCache(object):
    """
    >>> cache = ArgumentCache()
    >>> "foo" in cache
    False
    >>> cache['foo']
    Traceback (most recent call last):
        ...
    KeyError: 'foo'
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

    Size of ArgumentCache can be limited:

    >>> cache = ArgumentCache(0)
    Traceback (most recent call last):
        ...
    ValueError: maxsize must be greater than 0
    >>> cache = ArgumentCache(2)  # limit it to 2 elements
    >>> cache.add_many(['value1', 'value2'])
    ['daf626c4ebd6bdd697e043111454304e5fb1459e', '849988af22dbd04d3e353caf77f9d81241ca9ee2']
    >>> len(cache)
    2
    >>> cache.add("Hello, world!")
    'bea2c9d7fd040292e0424938af39f7d6334e8d8a'
    >>> len(cache)
    2
    >>> cache["bea2c9d7fd040292e0424938af39f7d6334e8d8a"]
    'Hello, world!'
    >>> cache['849988af22dbd04d3e353caf77f9d81241ca9ee2']
    'value2'
    >>> cache['daf626c4ebd6bdd697e043111454304e5fb1459e']
    Traceback (most recent call last):
        ...
    KeyError: 'daf626c4ebd6bdd697e043111454304e5fb1459e'
    >>> cache.add("foo")
    'd465e627f9946f2fa0d2dc0fc04e5385bc6cd46d'
    >>> len(cache)
    2
    >>> 'bea2c9d7fd040292e0424938af39f7d6334e8d8a' in cache
    False
    """
    def __init__(self, maxsize=None):
        if maxsize is None:
            maxsize = float("+inf")
        if maxsize <= 0:
            raise ValueError("maxsize must be greater than 0")
        self.maxsize = maxsize
        self._values = OrderedDict()

    def add(self, value):
        key = self.get_key(value)
        if key in self._values:
            del self._values[key]
        else:
            while len(self._values) >= self.maxsize:
                self._values.popitem(last=False)
        self._values[key] = value
        return key

    def __getitem__(self, key):
        self._values.move_to_end(key)
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
