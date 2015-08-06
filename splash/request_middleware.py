# -*- coding: utf-8 -*-
"""
Classes that process (and maybe filter) requests based on
various conditions. They should be used with
:class:`splash.network_manager.SplashQNetworkAccessManager`.
"""
from __future__ import absolute_import
import re
import os
import urlparse
from twisted.python import log
from splash.qtutils import request_repr, drop_request, get_request_webframe


class AllowedDomainsMiddleware(object):
    """
    This request middleware checks ``allowed_domains`` argument
    and drops all requests to domains not in ``allowed_domains``.
    """
    def __init__(self, allow_subdomains=True, verbosity=0):
        self.allow_subdomains = allow_subdomains
        self.verbosity = verbosity

    def process(self, request, render_options, operation, data):
        allowed_domains = render_options.get_allowed_domains()
        host_re = self._get_host_regex(allowed_domains, self.allow_subdomains)
        if not host_re.match(unicode(request.url().host())):
            if self.verbosity >= 2:
                log.msg("Dropped offsite %s" % (request_repr(request, operation),), system='request_middleware')
            drop_request(request)
        return request

    def _get_host_regex(self, allowed_domains, allow_subdomains):
        """ Override this method to implement a different offsite policy """
        if not allowed_domains:
            return re.compile('')  # allow all by default
        domains = [d.replace('.', r'\.') for d in allowed_domains]
        if allow_subdomains:
            regex = r'(.*\.)?(%s)$' % '|'.join(domains)
        else:
            regex = r'(%s)$' % '|'.join(domains)
        return re.compile(regex, re.IGNORECASE)


class AllowedSchemesMiddleware(object):
    """
    This request middleware filters requests based on URI scheme.
    """
    def __init__(self, allowed_schemes, verbosity=0):
        self.allowed_schemes = set(allowed_schemes)
        self.verbosity = verbosity

    def process(self, request, render_options, operation, data):
        scheme = str(request.url().scheme()).lower()
        if scheme not in self.allowed_schemes:
            if self.verbosity >= 2:
                log.msg(
                    "Dropped %s because of URI scheme" % (request_repr(request, operation),),
                    system='request_middleware'
                )
            drop_request(request)
        return request


class RequestLoggingMiddleware(object):
    """ Request middleware for logging requests """
    def process(self, request, render_options, operation, data):
        log.msg(
            "[%s] %s" % (render_options.get_uid(), request_repr(request, operation)),
            system='network'
        )
        return request


class ResourceTimeoutMiddleware(object):
    """
    Request middleware which sets timeouts for requests based on
    ``resource_timeout`` attribute of QWebPage.
    """
    def process(self, request, render_options, operation, data):
        web_frame = get_request_webframe(request)
        if not web_frame:
            return request
        request.timeout = getattr(web_frame.page(), 'resource_timeout', 0)
        return request


class AdblockMiddleware(object):
    """ Request middleware that discards requests based on Adblock rules """

    def __init__(self, rules_registry, verbosity=0):
        self.rules = rules_registry
        self.verbosity = verbosity

    def process(self, request, render_options, operation, data):
        filter_names = render_options.get_filters(adblock_rules=self.rules)

        if filter_names == ['none']:
            return request

        if not filter_names:
            if self.rules.filter_is_known('default'):
                filter_names = ['default']
            else:
                return request

        url, options = self._url_and_adblock_options(request, render_options)
        blocking_filter = self.rules.get_blocking_filter(filter_names, url, options)
        if blocking_filter:
            if self.verbosity >= 2:
                msg = "Filter %s: dropped %s %s" % (
                    blocking_filter,
                    render_options.get_uid(),
                    request_repr(request, operation)
                )
                log.msg(msg, system='request_middleware')
            drop_request(request)
        return request

    def _url_and_adblock_options(self, request, render_options):
        url = unicode(request.url().toString())
        domain = urlparse.urlsplit(render_options.get_url()).netloc
        options = {'domain': domain}
        return url, options


class AdblockRulesRegistry(object):

    RE2_WARN_THRESHOLD = 100

    def __init__(self, path, supported_options=('domain',), verbosity=0):
        self.filters = {}
        self.verbosity = verbosity
        self.supported_options = supported_options
        self._load(path)

    def get_blocking_filter(self, filter_names, url, options):
        for name in filter_names:
            if name not in self.filters:
                if self.verbosity >= 1:
                    # this shouldn't happen because filter
                    # names must be validated earlier
                    log.msg("Invalid filter name: %s" % name)

        for name in filter_names:
            if name not in self.filters:
                continue
            if self.filters[name].should_block(url, options):
                return name

    def _load(self, path):
        try:
            import adblockparser
        except ImportError:
            log.msg('WARNING: https://github.com/scrapinghub/adblockparser '
                    'library is not available, filters are not loaded.')
            return

        for fname in os.listdir(path):
            if not fname.endswith('.txt'):
                continue
            fpath = os.path.join(path, fname)
            name = fname[:-len('.txt')]

            if not os.path.isfile(fpath):
                continue

            if self.verbosity >= 1:
                log.msg("Loading filter %s" % name)

            with open(fpath, 'rt') as f:
                lines = [line.decode('utf8').strip() for line in f]

            rules = adblockparser.AdblockRules(
                lines,
                supported_options=self.supported_options,
                skip_unsupported_rules=False,
                max_mem=512*1024*1024,  # this doesn't actually use 512M
            )
            filters_num = len(rules.rules)

            if self.verbosity >= 2:
                log.msg("%d rule(s) loaded for filter %s" % (filters_num, name))

            if not rules.uses_re2 and filters_num > self.RE2_WARN_THRESHOLD:
                log.msg('WARNING: a filter %s with %d rules loaded, but '
                        'pyre2 library is not installed. Matching may become '
                        'slow; installing https://github.com/axiak/pyre2 is '
                        'highly recommended.' % (name, filters_num))

            self.filters[name] = rules

    def filter_is_known(self, name):
        return name in self.filters

    def get_unknown_filters(self, filter_names):
        return [
            name for name in filter_names
            if not (self.filter_is_known(name) or name=='none')
        ]
