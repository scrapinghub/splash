"""
Render scripts - objects which create a BrowserTab and use it to run
some script in a browser. These objects are used by HTTP resources to
do the work.
"""
import abc
import functools

from twisted.internet import defer

from splash.errors import RenderError
from splash.render_options import RenderOptions


def stop_on_error(meth):
    @functools.wraps(meth)
    def stop_on_error_wrapper(self, *args, **kwargs):
        try:
            return meth(self, *args, **kwargs)
        except Exception as e:
            self.return_error(e)
    return stop_on_error_wrapper


class BaseRenderScript(metaclass=abc.ABCMeta):
    """
    Interface that all render scripts must implement.
    """
    default_min_log_level = 2
    tab = None  # create self.tab in __init__ method

    @abc.abstractmethod
    def __init__(self, render_options: RenderOptions,
                 verbosity: int, **kwargs) -> None:
        """
        BaseRenderScript.__init__ is called by Pool.
        """
        self.render_options = render_options
        self.verbosity = verbosity

        # this deferred is fired with the render result when
        # the result is ready
        self.deferred = defer.Deferred()

    @abc.abstractmethod
    def start(self, **kwargs):
        """
        This method is called by Pool when script should begin.
        As a result of calling this method, self.deferred should
        be eventually fired, usually by calling self.return_result or
        self.return_error.
        """
        pass

    def log(self, text, min_level=None):
        if min_level is None:
            min_level = self.default_min_log_level
        self.tab.logger.log(text, min_level=min_level)

    def return_result(self, result):
        """ Return a result to the Pool. """
        if self._result_already_returned():
            self.tab.logger.log("error: result is already returned", min_level=1)

        self.deferred.callback(result)
        # self.deferred = None

    def return_error(self, error):
        """ Return an error to the Pool. """
        if self._result_already_returned():
            self.tab.logger.log("error: result is already returned", min_level=1)
        self.deferred.errback(error)
        # self.deferred = None

    def _result_already_returned(self):
        """ Return True if an error or a result is already returned to Pool """
        return self.deferred.called

    def close(self):
        """
        This method is called by a Pool after the rendering is done and
        the RenderScript object is no longer needed.
        """
        self.tab.close()


class BaseFixedRenderScript(BaseRenderScript):
    """ Base render script for pre-defined scenarios """

    # start() method should set self.wait_time
    wait_time = 0

    def on_goto_load_finished(self):
        """ callback for tab.go """
        if self.wait_time == 0:
            self.log("loadFinished; not waiting")
            self._load_finished_ok()
        else:
            time_ms = int(self.wait_time * 1000)
            self.log("loadFinished; waiting %sms" % time_ms)
            self.tab.wait(
                time_ms=time_ms,
                callback=self._load_finished_ok,
                onerror=self.on_goto_load_error,
            )

    def on_goto_load_error(self, error_info):
        """ errback for tab.go """
        ex = RenderError({
            'type': error_info.type,
            'code': error_info.code,
            'text': error_info.text,
            'url': error_info.url
        })
        self.return_error(ex)

    @abc.abstractmethod
    def _load_finished_ok(self):
        self.log("_loadFinishedOK")

        if self.tab.closing:
            self.log("loadFinishedOK is ignored because RenderScript is closing", min_level=3)
            return

        self.tab.stop_loading()
        # actual code should be defined in a subclass
