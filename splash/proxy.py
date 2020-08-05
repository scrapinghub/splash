# -*- coding: utf-8 -*-
"""
Splash can send outgoing network requests through an HTTP proxy server.
This modules provides classes ("proxy factories") which define
which proxies to use for a given request. QNetworkManager calls
a proxy factory for each outgoing request.
"""
import configparser
import os
import re
import warnings
from urllib.parse import urlparse

from PyQt5.QtNetwork import QNetworkProxy

from splash.render_options import RenderOptions
from splash.qtutils import create_proxy, validate_proxy_type
from splash.utils import path_join_secure


def _raise_proxy_error(description, **kwargs):
    RenderOptions.raise_error("proxy", description, **kwargs)


class _AllowDenySplashProxyFactory(object):
    """
    Proxy factory that enables non-default proxy list when
    requested URL is matched by one of the allowlist patterns
    while not being matched by one of the denylist patterns.
    """
    def __init__(self, allowlist=None, denylist=None, proxy_list=None):
        self.allowlist = allowlist or []
        self.denylist = denylist or []
        self.proxy_list = proxy_list or []

    def queryProxy(self, query=None, *args, **kwargs):
        protocol = str(query.protocolTag())
        url = str(query.url().toString())
        if self.should_use_proxy_list(protocol, url):
            return self._get_custom_proxy_list()
        return self._get_default_proxy_list()

    def should_use_proxy_list(self, protocol, url):
        if not self.proxy_list:
            return False

        if protocol not in ('http', 'https'):
            # don't try to proxy unknown protocols
            return False

        if any(re.match(p, url) for p in self.denylist):
            return False

        if any(re.match(p, url) for p in self.allowlist):
            return True

        return not bool(self.allowlist)

    def _get_default_proxy_list(self):
        return [QNetworkProxy(QNetworkProxy.DefaultProxy)]

    def _get_custom_proxy_list(self):
        return [
            create_proxy(host, port, username, password, type)
            for host, port, username, password,type in self.proxy_list
        ]


class ProfilesSplashProxyFactory(_AllowDenySplashProxyFactory):
    r"""
    This proxy factory reads _AllowDenySplashProxyFactory
    parameters from ini file; name of the profile can be set per-request
    using GET parameter.

    Example config file for 'mywebsite' proxy profile::

        ; /etc/splash/proxy-profiles/mywebsite.ini
        [proxy]
        host=proxy.crawlera.com
        port=8010
        username=username
        password=password
        type=HTTP

        [rules]
        allowlist=
            .*mywebsite\.com.*

        denylist=
            .*\.js.*
            .*\.css.*
            .*\.png

    If there is ``default.ini`` proxy profile in profiles folder
    it will be used when no profile is specified in GET parameter.
    If GET parameter is 'none' or empty ('') no proxy will be used even if
    ``default.ini`` is present.
    """
    NO_PROXY_PROFILE_MSG = 'Proxy profile does not exist'

    def __init__(self, proxy_profiles_path, profile_name):
        self.proxy_profiles_path = proxy_profiles_path
        allowlist, denylist, proxy_list = self._get_filter_params(profile_name)
        super(ProfilesSplashProxyFactory, self).__init__(
            allowlist=allowlist,
            denylist=denylist,
            proxy_list=proxy_list,
        )

    def _get_filter_params(self, profile_name=None):
        """
        Return a (allowlist, denylist, proxy_list) tuple
        loaded from profile ``profile_name``.
        """
        if profile_name is None:
            profile_name = 'default'
            ini_path = self._get_ini_path(profile_name)
            if not os.path.isfile(ini_path):
                profile_name = 'none'

        if profile_name == 'none':
            return [], [], []
        ini_path = self._get_ini_path(profile_name)
        return self._parse_ini(ini_path)

    def _get_ini_path(self, profile_name):
        filename = profile_name + '.ini'
        try:
            return path_join_secure(self.proxy_profiles_path, filename)
        except ValueError as e:
            # security check fails
            print(e)
            _raise_proxy_error(self.NO_PROXY_PROFILE_MSG)

    def _parse_ini(self, ini_path):
        parser = configparser.ConfigParser(allow_no_value=True)
        if not parser.read(ini_path):
            _raise_proxy_error(self.NO_PROXY_PROFILE_MSG)

        allowlist = _get_lines(parser, 'rules', 'whitelist', [])
        if allowlist:
            warnings.warn('{}: ‘whitelist’ is deprecated, use ‘allowlist’ '
                          'instead'.format(ini_path), DeprecationWarning)
        else:
            allowlist = _get_lines(parser, 'rules', 'allowlist', [])

        denylist = _get_lines(parser, 'rules', 'blacklist', [])
        if denylist:
            warnings.warn('{}: ‘blacklist’ is deprecated, use ‘denylist’ '
                          'instead'.format(ini_path), DeprecationWarning)
        else:
            denylist = _get_lines(parser, 'rules', 'denylist', [])

        try:
            proxy = dict(parser.items('proxy'))
        except configparser.NoSectionError:
            _raise_proxy_error("Invalid proxy profile: no [proxy] section found")

        try:
            host = proxy['host']
        except KeyError:
            _raise_proxy_error("Invalid proxy profile: [proxy] host is not found")

        try:
            port = int(proxy['port'])
        except KeyError:
            _raise_proxy_error("Invalid proxy profile: [proxy] port is not found")
        except ValueError:
            _raise_proxy_error("Invalid proxy profile: [proxy] port is not found")

        if 'type' in proxy:
            try:
                validate_proxy_type(proxy['type'])
            except ValueError as e:
                _raise_proxy_error(str(e))

        proxy_list = [(host, port,
                       proxy.get('username'), proxy.get('password'),
                       proxy.get('type'))]
        return allowlist, denylist, proxy_list


class DirectSplashProxyFactory(object):
    """
    This proxy factory will set the proxy passed to a render request
    using a parameter.

    If GET parameter is a fully qualified URL, use the specified proxy.
    The syntax to specify the proxy is:
    [protocol://][user:password@]proxyhost[:port])

    Where protocol is either ``http`` or ``socks5``. If port is not specified,
    it's assumed to be 1080.
    """
    def __init__(self, proxy):
        url = urlparse(proxy)
        if url.scheme and url.scheme in ('http', 'socks5') and url.hostname:
            self.proxy = create_proxy(
                url.hostname,
                url.port or 1080,
                username=url.username,
                password=url.password,
                type=url.scheme.upper()
            )
        else:
            _raise_proxy_error('Invalid proxy URL format.')

    def queryProxy(self, *args, **kwargs):
        return [self.proxy]


def get_factory(ini_path, parameter):
    """
    Returns the appropriate factory depending on the value of
    ini_path and parameter
    """
    if parameter and re.match(r'^\w+://', parameter):
        return DirectSplashProxyFactory(parameter)
    else:
        if ini_path:
            return ProfilesSplashProxyFactory(ini_path, parameter)
        else:
            return None


def _get_lines(config_parser, section, option, default):
    try:
        lines = config_parser.get(section, option).splitlines()
        return [line for line in lines if line]
    except (configparser.NoOptionError, configparser.NoSectionError):
        return default
