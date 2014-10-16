from __future__ import absolute_import
import abc
import json
import pprint
from splash import defaults
from splash.browser_tab import BrowserTab


class RenderError(Exception):
    pass


class RenderScript(object):
    """
    Interface that all render scripts must implement.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, network_manager, splash_proxy_factory, render_options, verbosity):
        self.tab = BrowserTab(
            network_manager=network_manager,
            splash_proxy_factory=splash_proxy_factory,
            verbosity=verbosity,
            render_options=render_options,
        )
        self.render_options = render_options
        self.verbosity = verbosity
        self.deferred = self.tab.deferred

    @abc.abstractmethod
    def start(self, **kwarge):
        """ This method is called by Pool when script should begin """
        pass

    def close(self):
        """
        This method is called by a Pool after the rendering is done and
        the RenderScript object is no longer needed.
        """
        self.tab._close()

    @abc.abstractmethod
    def get_result(self):
        """
        This method is called to get the result after the requested page is
        downloaded and rendered. Subclasses should implement it to customize
        which data to return.
        """
        pass

    def log(self, text, min_level=2):
        self.tab.logger.log(text, min_level=min_level)


class DefaultRenderScript(RenderScript):
    """
    DefaultRenderScript object renders a webpage using "standard" render
    scenario:

    * load an URL;
    * wait for all redirects, wait for a specified time;
    * optionally execute custom javascript in page context;
    * return the result.

    This class is not used directly; its subclasses are used.
    Subclasses choose how to return the result (as html, json, png).
    """

    def start(self, url, baseurl=None, wait=None, viewport=None,
                  js_source=None, js_profile=None, images=None, console=False,
                  headers=None, http_method='GET', body=None):

        self.url = url
        self.wait_time = defaults.WAIT_TIME if wait is None else wait
        self.js_source = js_source
        self.js_profile = js_profile
        self.console = console
        self.viewport = defaults.VIEWPORT if viewport is None else viewport

        if images is not None:
            self.tab.set_images_enabled(images)

        self.tab.set_default_headers(headers)
        if self.viewport != 'full':
            self.tab.set_viewport(self.viewport)

        self.tab.goto(
            url=url,
            callback=self.on_goto_load_finished,
            errback=self.on_goto_load_error,
            baseurl=baseurl,
            http_method=http_method,
            body=body,
        )

    def on_goto_load_finished(self):
        if self.wait_time == 0:
            self.log("loadFinished; not waiting")
            self._loadFinishedOK()
        else:
            time_ms = int(self.wait_time * 1000)
            self.log("loadFinished; waiting %sms" % time_ms)
            self.tab.wait(time_ms, self._loadFinishedOK)

    def on_goto_load_error(self):
        self.tab.return_error(RenderError())

    def _loadFinishedOK(self):
        self.log("_loadFinishedOK")

        if self.tab._closing:
            self.log("loadFinishedOK is ignored because RenderScript is closing", min_level=3)
            return

        self.tab.stop_loading()

        self.tab.store_har_timing("_onPrepareStart")
        try:
            self._prepare_render()
            self.tab.return_result(self.get_result())
        except:
            self.tab.return_error()

    def _runjs(self, js_source, js_profile):
        js_output, js_console_output = None, None
        if js_source:
            if self.console:
                self.tab._jsconsole_enable()

            if js_profile:
                self.tab.inject_js_libs(js_profile)

            js_output = self.tab.evaluate(js_source)  #.encode('utf8')
            if self.console:
                js_console_output = self.tab._jsconsole_messages()

        self.tab.store_har_timing('_onCustomJsExecuted')
        return js_output, js_console_output

    def _prepare_render(self):
        if self.viewport == 'full':
            self.tab.set_viewport(self.viewport)
        self.js_output, self.js_console_output = self._runjs(self.js_source, self.js_profile)


class HtmlRender(DefaultRenderScript):
    def get_result(self):
        return self.tab.html()


class PngRender(DefaultRenderScript):

    def start(self, **kwargs):
        self.width = kwargs.pop('width')
        self.height = kwargs.pop('height')
        return super(PngRender, self).start(**kwargs)

    def get_result(self):
        return self.tab.png(self.width, self.height)


class JsonRender(DefaultRenderScript):

    def start(self, **kwargs):
        self.width = kwargs.pop('width')
        self.height = kwargs.pop('height')
        self.include = {
            inc: kwargs.pop(inc)
            for inc in ['html', 'png', 'iframes', 'script', 'history', 'har']
        }
        self.include['console'] = kwargs.get('console')
        super(JsonRender, self).start(**kwargs)

    def get_result(self):
        res = {}

        if self.include['png']:
            res['png'] = self.tab.png(self.width, self.height, b64=True)

        if self.include['script'] and self.js_output:
            res['script'] = self.js_output

        if self.include['console'] and self.js_console_output:
            res['console'] = self.js_console_output

        res.update(self.tab.iframes_info(
            children=self.include['iframes'],
            html=self.include['html'],
        ))

        if self.include['history']:
            res['history'] = self.tab.history()

        if self.include['har']:
            res['har'] = self.tab.har()

        # import pprint
        # pprint.pprint(res)
        return json.dumps(res)


class HarRender(DefaultRenderScript):
    def get_result(self):
        return json.dumps(self.tab.har())

