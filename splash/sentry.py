import os

class SentryLogger(object):

    def __init__(self):
        try:
            import raven
            self.enabled = True
            dsn = os.environ['SPLASH_SENTRY_DSN']
            if dsn.startswith('https'):
                dsn = dsn.replace('https://', 'twisted+https://')
            self.client = raven.Client(dsn)
        except (ImportError, KeyError):
            self.enabled = False

    def capture(self, failure):
        if self.enabled:
            self.client.captureException((failure.type, failure.value, failure.getTracebackObject()))

capture = SentryLogger().capture
