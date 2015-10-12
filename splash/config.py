# -*- coding: utf-8 -*-

import __builtin__
import ast
import ConfigParser
import os

from . import defaults


class ConfigError(Exception):
    pass

global CONFIG_PATH


class Settings(object):
    """Handles config files and default values of config settings."""

    NO_CONFIG_FILE_MSG = "Config file doesn't exist at %s"

    def __init__(self):
        try:
            self.config_path = CONFIG_PATH
        except NameError:
            # CONFIG_PATH is not defined. User hasn't passed in a config file.
            self.config_path = None
        self.defaults = {}
        for name in dir(defaults):
            if name.isupper():
                self.defaults[name] = getattr(defaults, name)
        parser = ConfigParser.SafeConfigParser()
        # don't convert keys to lowercase.
        parser.optionxform = str
        if parser.read(self._get_configfile_paths()):
            # Safely evaluate configuration values.
            self.cfg = {key: ast.literal_eval(val) for (key, val) in parser.items('settings')}
        else:
            self.cfg = {}

    def _get_configfile_paths(self):
        """Returns a list of config file paths."""
        if self.config_path:
            config_dir_path = os.path.abspath(os.path.expanduser(self.config_path))
            configfile_path = os.path.abspath(os.path.join(config_dir_path, 'splash.cfg'))
            if not os.path.isfile(configfile_path):
                # file doesn't exist
                raise ConfigError(self.NO_CONFIG_FILE_MSG % configfile_path)
            else:
                return configfile_path
        else:
            xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or \
                os.path.expanduser('~/.config')
            return ['/etc/splash.cfg',
                    'C:\\splash\splash.cfg',
                    os.path.join(xdg_config_home, 'splash.cfg'),
                    os.path.expanduser('~/.splash.cfg')]

    def __getattr__(self, item):
        val = self.cfg.get(item, None)
        if val is None:
            val = self.defaults.get(item, None)
        if val is None:
            raise AttributeError("There is no settings named %s" % item)
        return val

settings = Settings()
