# -*- coding: utf-8 -*-
"""
Splash can send outgoing network requests through an HTTP proxy server.
This modules provides classes ("proxy factories") which define
which proxies to use for a given request. QNetworkManager calls
a proxy factory for each outgoing request.

Not to be confused with Splash Proxy mode when Splash itself works as
an HTTP proxy (see :mod:`splash.proxy_server`).
"""
from __future__ import absolute_import
import re
import os

from PyQt5.QtNetwork import QNetworkProxy
import six
from six.moves.urllib.parse import urlparse
from six.moves import configparser

from splash.render_options import BadOption
from splash.qtutils import create_proxy, validate_proxy_type


class _BlackWhiteSplashProxyFactory(object):
    """
    Proxy factory that enables non-default proxy list when
    requested URL is matched by one of whitelist patterns
    while not being matched by one of the blacklist patterns.
    """
    def __init__(self, blacklist=None, whitelist=None, proxy_list=None):
        self.blacklist = blacklist or []
        self.whitelist = whitelist or []
        self.proxy_list = proxy_list or []

    def queryProxy(self, query=None, *args, **kwargs):
        protocol = six.text_type(query.protocolTag())
        url = six.text_type(query.url().toString())
        if self.shouldUseProxyList(protocol, url):
            return self._customProxyList()

        return self._defaultProxyList()

    def shouldUseProxyList(self, protocol, url):
        if not self.proxy_list:
            return False

        if protocol not in ('http', 'https'):
            # don't try to proxy unknown protocols
            return False

        if any(re.match(p, url) for p in self.blacklist):
            return False

        if any(re.match(p, url) for p in self.whitelist):
            return True

        return not bool(self.whitelist)

    def _defaultProxyList(self):
        return [QNetworkProxy(QNetworkProxy.DefaultProxy)]

    def _customProxyList(self):
        return [
            create_proxy(host, port, username, password, type)
            for host, port, username, password,type in self.proxy_list
        ]


class ProfilesSplashProxyFactory(_BlackWhiteSplashProxyFactory):
    """
    This proxy factory reads BlackWhiteQNetworkProxyFactory
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
        whitelist=
            .*mywebsite\.com.*

        blacklist=
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
        blacklist, whitelist, proxy_list = self._getFilterParams(profile_name)
        super(ProfilesSplashProxyFactory, self).__init__(blacklist, whitelist, proxy_list)

    def _getFilterParams(self, profile_name=None):
        """
        Return (blacklist, whitelist, proxy_list) tuple
        loaded from profile ``profile_name``.
        """
        if profile_name is None:
            profile_name = 'default'
            ini_path = self._getIniPath(profile_name)
            if not os.path.isfile(ini_path):
                profile_name = 'none'

        if profile_name == 'none':
            return [], [], []
        ini_path = self._getIniPath(profile_name)
        return self._parseIni(ini_path)

    def _getIniPath(self, profile_name):
        proxy_profiles_path = os.path.abspath(self.proxy_profiles_path)
        filename = profile_name + '.ini'
        ini_path = os.path.abspath(os.path.join(proxy_profiles_path, filename))
        if not ini_path.startswith(proxy_profiles_path + os.path.sep):
            # security check fails
            raise BadOption(self.NO_PROXY_PROFILE_MSG)
        else:
            return ini_path

    def _parseIni(self, ini_path):
        parser = configparser.ConfigParser(allow_no_value=True)
        if not parser.read(ini_path):
            raise BadOption(self.NO_PROXY_PROFILE_MSG)

        blacklist = _get_lines(parser, 'rules', 'blacklist', [])
        whitelist = _get_lines(parser, 'rules', 'whitelist', [])
        try:
            proxy = dict(parser.items('proxy'))
        except configparser.NoSectionError:
            raise BadOption("Invalid proxy profile: no [proxy] section found")

        try:
            host = proxy['host']
        except KeyError:
            raise BadOption("Invalid proxy profile: [proxy] host is not found")

        try:
            port = int(proxy['port'])
        except KeyError:
            raise BadOption("Invalid proxy profile: [proxy] port is not found")
        except ValueError:
            raise BadOption("Invalid proxy profile: [proxy] port is incorrect")

        if 'type' in proxy:
            validate_proxy_type(proxy['type'])

        proxy_list = [(host, port,
                       proxy.get('username'), proxy.get('password'),
                       proxy.get('type'))]
        return blacklist, whitelist, proxy_list


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
            raise BadOption('Invalid proxy URL format.')

    def queryProxy(self, *args, **kwargs):
        return [self.proxy]


def getFactory(ini_path, parameter):
    """
    Returns the appropriate factory depending on the value of
    ini_path and parameter
    """
    if parameter and re.match('^\w+://', parameter):
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
