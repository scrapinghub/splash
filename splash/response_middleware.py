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
        for part1 in mime[0], '*':
            for part2 in mime[1], '*':
                if (part1, part2) in mime_set:
                    return True
        return False

    @staticmethod
    def split_mime(mime):
        """
        Split a mime string into type and subtype: 'text/html; charset=utf-8' -> ('text', 'html')
        """
        separator = mime.find(';')
        if separator > 0:
            mime = mime[:separator].strip()
        parts = mime.split("/")
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    def process(self, reply, render_options):
        content_type = reply.header(QNetworkRequest.ContentTypeHeader)
        if not content_type.isValid():
            return

        mimetype = self.split_mime(str(content_type.toString()))
        if mimetype is None:
            return

        allowed = render_options.get_allowed_content_types()
        forbidden = render_options.get_forbidden_content_types()
        whitelist = set(map(ContentTypeMiddleware.split_mime, allowed))
        blacklist = set(map(ContentTypeMiddleware.split_mime, forbidden))

        if self.contains(blacklist, mimetype) or not self.contains(whitelist, mimetype):
            if self.verbosity >= 2:
                request_str = request_repr(reply, reply.operation())
                msg = "Dropping %s because of Content Type" % request_str
                log.msg(msg, system='response_middleware')
            reply.abort()

