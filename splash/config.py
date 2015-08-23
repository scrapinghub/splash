# -*- coding: utf-8 -*-

import os
import sys
import yaml
from . import defaults


class Settings(object):

    def __init__(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file_path = os.path.join(root_dir, 'config.yml')
        self.defaults = {}
        for name in dir(defaults):
            if name.isupper():
                self.defaults[name] = getattr(defaults, name)
        try:
            with open(config_file_path, 'rb') as config_file:
                self.cfg = yaml.load(config_file)
        except IOError:
            self.cfg = {}

    def __getattr__(self, item):
        val = self.cfg.get(item, None)
        if val is None:
            val = self.defaults.get(item, None)
        if val is None:
            raise AttributeError("There is no settings named %s" % item)
        return val

sys.modules[__name__] = Settings()
