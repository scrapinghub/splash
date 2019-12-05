# -*- coding: utf-8 -*-
import abc
import json

from splash import defaults
from splash.engines.webkit import WebkitBrowserTab
from splash.render_scripts import (
    BaseRenderScript,
    BaseFixedRenderScript,
    stop_on_error,
)


class WebkitRenderScript(BaseRenderScript):
    """ Base class for Webkit-based render scripts """
    def __init__(self, render_options, verbosity, network_manager,
                 splash_proxy_factory):
        super().__init__(render_options, verbosity)
        self.tab = WebkitBrowserTab(
            render_options=render_options,
            verbosity=verbosity,
            network_manager=network_manager,
            splash_proxy_factory=splash_proxy_factory,
        )


class WebkitDefaultRenderScript(WebkitRenderScript, BaseFixedRenderScript):
    """
    WebkitDefaultRenderScript object renders a webpage using "standard" render
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
              render_all=False, resource_timeout=None, request_body=False,
              response_body=False, html5_media=False, http2=False):
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

        self.tab.set_request_body_enabled(request_body)
        self.tab.set_response_body_enabled(response_body)
        self.tab.set_html5_media_enabled(html5_media)
        self.tab.set_http2_enabled(http2)

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

    @stop_on_error
    def _load_finished_ok(self):
        super()._load_finished_ok()
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


class HtmlRender(WebkitDefaultRenderScript):
    def get_result(self):
        return self.tab.html()


class ImageRender(WebkitDefaultRenderScript):

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
            kwargs['request_body'] = False
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


class HarRender(WebkitDefaultRenderScript):
    def get_result(self):
        return json.dumps(self.tab.har())

