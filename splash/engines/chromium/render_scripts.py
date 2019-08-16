# -*- coding: utf-8 -*-
import abc

from twisted.internet import defer
from twisted.python.failure import Failure

from splash import defaults
from splash.engines.chromium import ChromiumBrowserTab
from splash.errors import BadOption, InternalError
from splash.render_scripts import (
    BaseRenderScript,
    BaseFixedRenderScript,
    stop_on_error,
)


class ChromiumRenderScript(BaseRenderScript):
    """ Base class for Chromium-based render scripts """
    def __init__(self, render_options, verbosity, **kwargs):
        super().__init__(render_options, verbosity)
        self.tab = ChromiumBrowserTab(
            render_options=render_options,
            verbosity=verbosity,
        )


class ChromiumDefaultRenderScript(ChromiumRenderScript, BaseFixedRenderScript):

    def start(self, url, baseurl=None, wait=None, viewport=None,
              js_source=None, js_profile=None, images=None, console=False,
              headers=None, http_method='GET', body=None,
              render_all=False, resource_timeout=None, request_body=False,
              response_body=False, html5_media=False, http2=True):
        self.url = url
        self.wait_time = defaults.WAIT_TIME if wait is None else wait
        # self.js_source = js_source
        # self.js_profile = js_profile
        # self.console = console
        self.viewport = defaults.VIEWPORT_SIZE if viewport is None else viewport
        self.render_all = render_all or viewport == 'full'

        # FIXME: BadOption errors are logged as unhandled errors
        if baseurl is not None:
            raise BadOption("baseurl is not implemented")

        if js_source is not None:
            raise BadOption("js_source is not implemented")

        if js_profile is not None:
            raise BadOption("js_profile is not implemented")

        if images is False:
            raise BadOption("images is not implemented")

        if console is True:
            raise BadOption("console is not implemented")

        if headers is not None:
            raise BadOption("headers is not implemented")

        if http_method != 'GET':
            raise BadOption("http_method is not implemented")

        if body is not None:
            raise BadOption("body is not implemented")

        if resource_timeout is not None and resource_timeout > 0:
            raise BadOption("resource_timeout is not implemented")

        if request_body is True:
            raise BadOption("request_body is not implemented")

        if response_body is True:
            raise BadOption("response_body is not implemented")

        if html5_media is True:
            raise BadOption("html5_media is not implemented")

        if render_all is True:
            raise BadOption("render_all is not implemented")

        # if resource_timeout:
        #     self.tab.set_resource_timeout(resource_timeout)

        # if images is not None:
        #     self.tab.set_images_enabled(images)

        if self.viewport != 'full':
            self.tab.set_viewport(self.viewport)

        # self.tab.set_request_body_enabled(request_body)
        # self.tab.set_response_body_enabled(response_body)
        # self.tab.set_html5_media_enabled(html5_media)

        if not http2:
            raise BadOption("Disabling of http2 is not implemented "
                            "for Chromium")

        self.tab.go(
            url=url,
            callback=self.on_goto_load_finished,
            errback=self.on_goto_load_error,
            # baseurl=baseurl,
            # http_method=http_method,
            # body=body,
            # headers=headers,
        )

    @stop_on_error
    def _load_finished_ok(self):
        super()._load_finished_ok()
        # self.tab.store_har_timing("_onPrepareStart")

        # self._prepare_render()
        if self.viewport == 'full':
            self.tab.set_viewport(self.viewport)

        d = defer.maybeDeferred(self.get_result)
        d.addCallback(self.return_result)
        d.addErrback(self._return_internal_error)

    def _return_internal_error(self, failure: Failure):
        self.return_error(InternalError(str(failure.value)))

    @abc.abstractmethod
    def get_result(self):
        return None


class ChromiumRenderHtmlScript(ChromiumDefaultRenderScript):
    def get_result(self):
        return self.tab.html()


class _ChromiumRenderImageScript(ChromiumDefaultRenderScript):
    def start(self, **kwargs):
        self.width = kwargs.pop('width')
        self.height = kwargs.pop('height')
        self.scale_method = kwargs.pop('scale_method')
        return super().start(**kwargs)


class ChromiumRenderPngScript(_ChromiumRenderImageScript):
    def get_result(self):
        return self.tab.png(self.width, self.height,
                            render_all=self.render_all,
                            scale_method=self.scale_method)


class ChromiumRenderJpegScript(_ChromiumRenderImageScript):
    def start(self, **kwargs):
        self.quality = kwargs.pop('quality')
        return super().start(**kwargs)

    def get_result(self):
        return self.tab.jpeg(
            self.width, self.height, render_all=self.render_all,
            scale_method=self.scale_method, quality=self.quality)


