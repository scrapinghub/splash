# -*- coding: utf-8 -*-
from twisted.python import log


class SplashLogger:
    """
    Logging object for Splash.

    XXX: should we just switch to stdlib logging?
    """
    def __init__(self, uid, verbosity):
        self.uid = uid
        self.verbosity = verbosity

    def log(self, message, min_level=None):
        if min_level is not None and self.verbosity < min_level:
            return

        if isinstance(message, str):
            message = message.encode('unicode-escape').decode('ascii')

        message = "[%s] %s" % (self.uid, message)
        log.msg(message, system='render')
