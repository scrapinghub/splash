# -*- coding: utf-8 -*-
from __future__ import absolute_import
import re, os, ConfigParser
from PyQt4.QtNetwork import QNetworkProxy
from splash.utils import getarg, BadRequest


class BlackWhiteSplashProxyFactory(object):
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
        protocol = unicode(query.protocolTag())
        url = unicode(query.url().toString())
        if self.shouldUseProxyList(protocol, url):
            return self._customProxyList()

        return self._defaultProxyList()

    def shouldUseProxyList(self, protocol, url):
        if not self.proxy_list:
            return False

        if protocol != 'http':  # don't try to proxy https
            return False

        if any(re.match(p, url) for p in self.blacklist):
            return False

        if any(re.match(p, url) for p in self.whitelist):
            return True

        return not bool(self.whitelist)

    def _defaultProxyList(self):
        return [QNetworkProxy(QNetworkProxy.DefaultProxy)]

    def _customProxyList(self):
        proxies = []
        for host, port, username, password in self.proxy_list:
            if username is not None and password is not None:
                proxy = QNetworkProxy(QNetworkProxy.HttpProxy,
                                      host, port, username, password)
            else:
                proxy = QNetworkProxy(QNetworkProxy.HttpProxy, host, port)
            proxies.append(proxy)
        return proxies


class ProfilesSplashProxyFactory(BlackWhiteSplashProxyFactory):
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

        [rules]
        whitelist=
            .*mywebsite\.com.*

        blacklist=
            .*\.js.*
            .*\.css.*
            .*\.png

    """
    GET_ARGUMENT = 'proxy'
    NO_PROXY_PROFILE_MSG = 'Proxy profile does not exist'

    def __init__(self, proxy_profiles_path, request):
        self.proxy_profiles_path = proxy_profiles_path
        profile_name = getarg(request, self.GET_ARGUMENT, None)
        blacklist, whitelist, proxy_list = self._getFilterParams(profile_name)
        super(ProfilesSplashProxyFactory, self).__init__(blacklist, whitelist, proxy_list)

    def _getFilterParams(self, profile_name=None):
        """
        Return (blacklist, whitelist, proxy_list) tuple
        loaded from profile ``profile_name``.
        """
        if not profile_name:
            return [], [], []
        ini_path = self._getIniPath(profile_name)
        return self._parseIni(ini_path)

    def _getIniPath(self, profile_name):
        proxy_profiles_path =  os.path.abspath(self.proxy_profiles_path)
        filename = profile_name + '.ini'
        ini_path = os.path.abspath(os.path.join(proxy_profiles_path, filename))
        if not ini_path.startswith(proxy_profiles_path + os.path.sep):
            # security check fails
            raise BadRequest(self.NO_PROXY_PROFILE_MSG)
        else:
            return ini_path

    def _parseIni(self, ini_path):
        parser = ConfigParser.ConfigParser(allow_no_value=True)
        if not parser.read(ini_path):
            raise BadRequest(self.NO_PROXY_PROFILE_MSG)

        blacklist = _get_lines(parser, 'rules', 'blacklist', [])
        whitelist = _get_lines(parser, 'rules', 'whitelist', [])
        try:
            proxy = dict(parser.items('proxy'))
        except ConfigParser.NoSectionError:
            raise BadRequest("Invalid proxy profile: no [proxy] section found")

        try:
            host = proxy['host']
        except KeyError:
            raise BadRequest("Invalid proxy profile: [proxy] host is not found")

        try:
            port = int(proxy['port'])
        except KeyError:
            raise BadRequest("Invalid proxy profile: [proxy] port is not found")
        except ValueError:
            raise BadRequest("Invalid proxy profile: [proxy] port is incorrect")

        proxy_list = [(host, port, proxy.get('username'), proxy.get('password'))]
        return blacklist, whitelist, proxy_list


def _get_lines(config_parser, section, option, default):
    try:
        lines = config_parser.get(section, option).splitlines()
        return [line for line in lines if line]
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        return default
