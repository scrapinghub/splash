# -*- coding: utf-8 -*-
from twisted.python import log


class SplashLogger:
    """
    Logging object for Splash.

    XXX: should we just switch to stdlib logging?
    """
    def __init__(self, uid, verbosity: int) -> None:
        self.uid = uid
        self.verbosity = verbosity

    def log(self, message, min_level: int = None) -> None:
        if min_level is not None and self.verbosity < min_level:
            return

        if isinstance(message, str):
            message = message.encode('unicode-escape').decode('ascii')

        message = "[%s] %s" % (self.uid, message)
        log.msg(message, system='render')


class DummyLogger:
    """ Logger to use when no logger is passed into rendering functions. """
    def log(self, *args, **kwargs):
        pass
