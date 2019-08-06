# -*- coding: utf-8 -*-
from twisted.python import log
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile


class ChromiumWebPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, verbosity: int = 0) -> None:
        super(QWebEnginePage, self).__init__(profile, None)
        self.verbosity = verbosity
        profile.setParent(self)

    def javaScriptAlert(self, url, msg):
        # TODO: callback
        if self.verbosity > 1:
            log.msg("javaScriptAlert, url=%r, msg=%r" % (url, msg))
        return

    def javaScriptConfirm(self, url, msg):
        if self.verbosity > 1:
            log.msg("javaScriptConfirm, url=%r, msg=%r" % (url, msg))
        return False

    def javaScriptPrompt(self, url, msg, default=None):
        if self.verbosity > 1:
            log.msg("javaScriptPrompt, url=%r, msg=%r, default=%r" % (
                    url, msg, default))
        return False, ''

