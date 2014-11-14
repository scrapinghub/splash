# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import json
from splash import defaults


class BadOption(Exception):
    pass


class RenderOptions(object):
    """
    Options that control how to render a response.
    """

    _REQUIRED = object()

    def __init__(self, data):
        self.data = data

    @classmethod
    def fromrequest(cls, request):
        """
        Initialize options from a Twisted Request.
        """

        # 1. GET / POST data
        data = {key: values[0] for key, values in request.args.items()}

        if request.method == 'POST':
            content_type = request.getHeader('content-type')
            if content_type:
                request.content.seek(0)

                # 2. application/json POST data
                if 'application/json' in content_type:
                    data.update(json.load(request.content, encoding='utf8') or {})

                # 3. js_source from application/javascript POST requests
                if 'application/javascript' in content_type:
                    data['js_source'] = request.content.read()
                request.content.seek(0)

        # 4. handle proxy requests
        if getattr(request, 'inspect_me', False):
            headers = [
                (name, value)
                for name, values in request.requestHeaders.getAllRawHeaders()
                for value in values
            ]
            data.setdefault('headers', headers)
            data.setdefault('http_method', request.method)

            request.content.seek(0)
            data.setdefault('body', request.content.read())
            request.content.seek(0)

        data['uid'] = id(request)
        return cls(data)

    def get(self, name, default=_REQUIRED, type=str, range=None):
        value = self.data.get(name)
        if value is not None:
            if type is not None:
                value = type(value)
            if range is not None and not (range[0] <= value <= range[1]):
                raise BadOption("Argument %r out of range (%d-%d)" % (name, range[0], range[1]))
            return value
        elif default is self._REQUIRED:
            raise BadOption("Missing argument: %s" % name)
        else:
            return default

    def _get_bool(self, name, default=_REQUIRED):
        return self.get(name, default, type=int, range=(0, 1))

    def _get_url(self, name, default=_REQUIRED):
        url = self.get(name, default, type=None)
        if isinstance(url, bytes):
            url = url.decode('utf8')
        return url

    def get_uid(self):
        return self.get('uid')

    def get_url(self):
        return self._get_url("url")

    def get_baseurl(self):
        return self._get_url("baseurl", default=None)

    def get_wait(self):
        return self.get("wait", defaults.WAIT_TIME, type=float, range=(0, defaults.MAX_WAIT_TIME))

    def get_timeout(self):
        return self.get("timeout", defaults.TIMEOUT, type=float, range=(0, defaults.MAX_TIMEOUT))

    def get_images(self):
        return self._get_bool("images", defaults.AUTOLOAD_IMAGES)

    def get_proxy(self):
        return self.get("proxy", default=None)

    def get_js_source(self):
        return self.get("js_source", default=None)

    def get_width(self):
        return self.get("width", None, type=int, range=(1, defaults.MAX_WIDTH))

    def get_height(self):
        return self.get("height", None, type=int, range=(1, defaults.MAX_HEIGTH))

    def get_http_method(self):
        return self.get("http_method", "GET")

    def get_body(self):
        return self.get("body", None)

    def get_lua_source(self):
        return self.get("lua_source")

    def get_js_profile(self, js_profiles_path):
        js_profile = self.get("js", default=None)
        if not js_profile:
            return js_profile

        if js_profiles_path is None:
            raise BadOption('Javascript profiles are not enabled')
        profile_dir = os.path.join(js_profiles_path, js_profile)
        if not profile_dir.startswith(js_profiles_path + os.path.sep):
            # security check fails
            raise BadOption('Javascript profile does not exist')
        if not os.path.isdir(profile_dir):
            raise BadOption('Javascript profile does not exist')
        return profile_dir

    def get_headers(self):
        headers = self.get("headers", default=None, type=None)

        if headers is None:
            return headers

        if not isinstance(headers, (list, tuple, dict)):
            raise BadOption("'headers' must be either JSON array of (name, value) pairs or JSON object")

        if isinstance(headers, (list, tuple)):
            for el in headers:
                if not (isinstance(el, (list, tuple)) and len(el) == 2 and all(isinstance(e, basestring) for e in el)):
                    raise BadOption("'headers' must be either JSON array of (name, value) pairs or JSON object")

        return headers

    def get_viewport(self, wait=None):
        viewport = self.get("viewport", defaults.VIEWPORT)

        if viewport == 'full':
            if wait == 0:
                raise BadOption("Pass non-zero 'wait' to render full webpage")
            return viewport

        max_width = defaults.VIEWPORT_MAX_WIDTH
        max_heigth = defaults.VIEWPORT_MAX_HEIGTH
        max_area = defaults.VIEWPORT_MAX_AREA
        try:
            w, h = map(int, viewport.split('x'))
            if (0 < w <= max_width) and (0 < h <= max_heigth) and (w*h < max_area):
                return viewport
            raise BadOption("Viewport is out of range (%dx%d, area=%d)" % (max_width, max_heigth, max_area))
        except ValueError:
            raise BadOption("Invalid viewport format: %s" % viewport)

    def get_filters(self, pool=None, adblock_rules=None):
        filter_names = self.get('filters', '')
        filter_names = [f for f in filter_names.split(',') if f]

        if pool is None and adblock_rules is None:  # skip validation
            return filter_names

        if not filter_names:
            return filter_names

        if pool is not None:
            network_manager = pool.network_manager
            # allow custom non-filtering network access managers
            if hasattr(network_manager, 'adblock_rules'):
                adblock_rules = network_manager.adblock_rules
                if adblock_rules is None:
                    raise BadOption("Invalid filter names: %s" % filter_names)

        if adblock_rules is not None:
            unknown_filters = adblock_rules.get_unknown_filters(filter_names)
            if unknown_filters:
                raise BadOption("Invalid filter names: %s" % unknown_filters)

        return filter_names

    def get_allowed_domains(self):
        allowed_domains = self.get("allowed_domains", default=None)
        if allowed_domains is not None:
            return allowed_domains.split(',')

    def get_common_params(self, js_profiles_path):
        wait = self.get_wait()
        return {
            'url': self.get_url(),
            'baseurl': self.get_baseurl(),
            'wait': wait,
            'viewport': self.get_viewport(wait),
            'images': self.get_images(),
            'headers': self.get_headers(),
            'proxy': self.get_proxy(),
            'js_profile': self.get_js_profile(js_profiles_path),
            'js_source': self.get_js_source(),
            'http_method': self.get_http_method(),
            'body': self.get_body(),
            # 'lua': self.get_lua(),
        }

    def get_png_params(self):
        return {'width': self.get_width(), 'height': self.get_height()}

    def get_include_params(self):
        return dict(
            html = self._get_bool("html", defaults.DO_HTML),
            iframes = self._get_bool("iframes", defaults.DO_IFRAMES),
            png = self._get_bool("png", defaults.DO_PNG),
            script = self._get_bool("script", defaults.SHOW_SCRIPT),
            console = self._get_bool("console", defaults.SHOW_CONSOLE),
            history = self._get_bool("history", defaults.SHOW_HISTORY),
            har = self._get_bool("har", defaults.SHOW_HAR),
        )
