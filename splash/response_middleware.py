# -*- coding: utf-8 -*-
"""
Classes that process (and maybe abort) responses based on
various conditions. They should be used with
:class:`splash.network_manager.SplashQNetworkAccessManager`.
"""
from __future__ import absolute_import
from PyQt4.QtNetwork import QNetworkRequest
from splash.qtutils import request_repr
from twisted.python import log
import fnmatch


class ContentTypeMiddleware(object):
    """
    Response middleware, aborts responses depending on the content type.
    A response will be aborted (and the underlying connection closed) after
    receiving the response headers if the content type of the response is not
    in the whitelist or it's in the blacklist. Both lists support wildcards.
    """
    def __init__(self, verbosity=0):
        self.verbosity = verbosity

    @staticmethod
    def contains(mime_set, mime):
        """
        >>> ContentTypeMiddleware.contains({'*/*'}, 'any/thing')
        True
        >>> ContentTypeMiddleware.contains(set(), 'any/thing')
        False
        >>> ContentTypeMiddleware.contains({'text/css', 'image/*'}, 'image/png')
        True
        >>> ContentTypeMiddleware.contains({'*'}, 'any-thing')
        True
        """
        for pattern in mime_set:
            if fnmatch.fnmatch(mime, pattern):
                return True
        return False

    @staticmethod
    def clean_mime(mime):
        """
        Remove attributes from a mime string:
        >>> ContentTypeMiddleware.clean_mime(' text/html; charset=utf-8\t ')
        'text/html'
        """
        separator = mime.find(';')
        if separator > 0:
            mime = mime[:separator]
        return mime.strip()

    def process(self, reply, render_options):
        content_type = reply.header(QNetworkRequest.ContentTypeHeader)
        if not content_type.isValid():
            return

        mimetype = self.clean_mime(str(content_type.toString()))
        allowed = render_options.get_allowed_content_types()
        forbidden = render_options.get_forbidden_content_types()
        whitelist = set(map(ContentTypeMiddleware.clean_mime, allowed))
        blacklist = set(map(ContentTypeMiddleware.clean_mime, forbidden))

        if self.contains(blacklist, mimetype) or not self.contains(whitelist, mimetype):
            if self.verbosity >= 2:
                request_str = request_repr(reply, reply.operation())
                msg = "Dropping %s because of Content Type" % request_str
                log.msg(msg, system='response_middleware')
            reply.abort()
