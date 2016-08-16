from __future__ import absolute_import
import abc
import json
import functools
import pprint
import six

from splash import defaults
from splash.browser_tab import BrowserTab
from splash.exceptions import RenderError


def stop_on_error(meth):
    @functools.wraps(meth)
    def stop_on_error_wrapper(self, *args, **kwargs):
        try:
            return meth(self, *args, **kwargs)
        except Exception as e:
            self.return_error(e)
    return stop_on_error_wrapper


class RenderScript(six.with_metaclass(abc.ABCMeta, object)):
    """
    Interface that all render scripts must implement.
    """
    default_min_log_level = 2

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
    def start(self, **kwargs):
        """ This method is called by Pool when script should begin """
        pass

    def log(self, text, min_level=None):
        if min_level is None:
            min_level = self.default_min_log_level
        self.tab.logger.log(text, min_level=min_level)

    def return_result(self, result):
        self.tab.return_result(result)

    def return_error(self, error=None):
        self.tab.return_error(error)

    def close(self):
        """
        This method is called by a Pool after the rendering is done and
        the RenderScript object is no longer needed.
        """
        self.tab.close()


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
              headers=None, http_method='GET', body=None,
              render_all=False, resource_timeout=None, response_body=False):

        self.url = url
        self.wait_time = defaults.WAIT_TIME if wait is None else wait
        self.js_source = js_source
        self.js_profile = js_profile
        self.console = console
        self.viewport = defaults.VIEWPORT_SIZE if viewport is None else viewport
        self.render_all = render_all or viewport == 'full'

        if resource_timeout:
            self.tab.set_resource_timeout(resource_timeout)

        if images is not None:
            self.tab.set_images_enabled(images)

        if self.viewport != 'full':
            self.tab.set_viewport(self.viewport)

        self.tab.set_response_body_enabled(response_body)

        self.tab.go(
            url=url,
            callback=self.on_goto_load_finished,
            errback=self.on_goto_load_error,
            baseurl=baseurl,
            http_method=http_method,
            body=body,
            headers=headers,
        )

    @abc.abstractmethod
    def get_result(self):
        """
        This method is called to get the result after the requested page is
        downloaded and rendered. Subclasses should implement it to customize
        which data to return.
        """
        pass

    def on_goto_load_finished(self):
        if self.wait_time == 0:
            self.log("loadFinished; not waiting")
            self._loadFinishedOK()
        else:
            time_ms = int(self.wait_time * 1000)
            self.log("loadFinished; waiting %sms" % time_ms)
            self.tab.wait(
                time_ms=time_ms,
                callback=self._loadFinishedOK,
                onerror=self.on_goto_load_error,
            )

    def on_goto_load_error(self, error_info):
        ex = RenderError({
            'type': error_info.type,
            'code': error_info.code,
            'text': error_info.text,
            'url': error_info.url
        })
        self.return_error(ex)

    @stop_on_error
    def _loadFinishedOK(self):
        self.log("_loadFinishedOK")

        if self.tab._closing:
            self.log("loadFinishedOK is ignored because RenderScript is closing", min_level=3)
            return

        self.tab.stop_loading()
        self.tab.store_har_timing("_onPrepareStart")
        self._prepare_render()
        self.return_result(self.get_result())

    def _runjs(self, js_source, js_profile):
        js_output, js_console_output = None, None

        if js_source or js_profile:
            if self.console:
                self.tab._jsconsole_enable()

            if js_profile:
                # XXX: shouldn't we keep injecting scripts after redirects?
                self.tab.run_js_files(js_profile, handle_errors=False)

            if js_source:
                js_output = self.tab.evaljs(js_source, handle_errors=False)

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


class ImageRender(DefaultRenderScript):

    def start(self, **kwargs):
        self.width = kwargs.pop('width')
        self.height = kwargs.pop('height')
        self.scale_method = kwargs.pop('scale_method')
        return super(ImageRender, self).start(**kwargs)


class PngRender(ImageRender):

    def get_result(self):
        return self.tab.png(self.width, self.height,
                            render_all=self.render_all,
                            scale_method=self.scale_method)


class JpegRender(ImageRender):

    def start(self, **kwargs):
        self.quality = kwargs.pop('quality')
        return super(JpegRender, self).start(**kwargs)

    def get_result(self):
        return self.tab.jpeg(
            self.width, self.height, render_all=self.render_all,
            scale_method=self.scale_method, quality=self.quality)


class JsonRender(JpegRender):

    def start(self, **kwargs):
        include_options = ['html', 'png', 'jpeg', 'iframes',
                           'script', 'history', 'har']
        self.include = {inc: kwargs.pop(inc) for inc in include_options}
        self.include['console'] = kwargs.get('console')
        if not self.include['har'] and not self.include['history']:
            kwargs['response_body'] = False
        super(JsonRender, self).start(**kwargs)

    def get_result(self):
        res = {}

        if self.include['png']:
            res['png'] = self.tab.png(self.width, self.height, b64=True,
                                      render_all=self.render_all,
                                      scale_method=self.scale_method)
        if self.include['jpeg']:
            res['jpeg'] = self.tab.jpeg(self.width, self.height, b64=True,
                                        render_all=self.render_all,
                                        scale_method=self.scale_method,
                                        quality=self.quality)

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

        return res


class HarRender(DefaultRenderScript):
    def get_result(self):
        return json.dumps(self.tab.har())

