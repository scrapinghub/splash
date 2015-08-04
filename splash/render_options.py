# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import json

import six

from splash import defaults
from splash.utils import bytes_to_unicode, unicode_to_bytes


class BadOption(Exception):
    pass


class RenderOptions(object):
    """
    Options that control how to render a response.
    """

    _REQUIRED = object()

    def __init__(self, data, max_timeout):
        self.data = data
        self.max_timeout = max_timeout

    @classmethod
    def fromrequest(cls, request, max_timeout):
        """
        Initialize options from a Twisted Request.
        """

        # 1. GET / POST data
        data = {key: values[0] for key, values in request.args.items()}
        if request.method == b'POST':
            content_type = request.getHeader(b'content-type')
            if content_type:
                request.content.seek(0)

                # 2. application/json POST data
                if b'application/json' in content_type:
                    try:
                        content = request.content.read().decode('utf-8')
                        data.update(unicode_to_bytes(
                            json.loads(content, encoding='utf8')))
                    except ValueError as e:
                        raise BadOption("Invalid JSON: '{}'".format(str(e)))

                # 3. js_source from application/javascript POST requests
                if b'application/javascript' in content_type:
                    data[b'js_source'] = request.content.read().decode('utf-8')
                request.content.seek(0)

        # 4. handle proxy requests
        if getattr(request, 'inspect_me', False):
            headers = [
                (name, value)
                for name, values in request.requestHeaders.getAllRawHeaders()
                for value in values
                ]
            data.setdefault(b'headers', headers)
            data.setdefault(b'http_method', request.method)

            request.content.seek(0)
            data.setdefault(b'body', request.content.read())
            request.content.seek(0)

        data[b'uid'] = id(request)
        return cls(data, max_timeout)

    def get(self, name, default=_REQUIRED, type=str, range=None):
        value = self.data.get(name)
        if value is not None:
            if type is not None:
                if type is str and isinstance(value, six.text_type):
                    value = value.encode('utf-8')
                else:
                    try:
                        # If value is Python 3 byte string, we don't want it
                        # to be converted into unicode
                        if not (type is str and isinstance(value, bytes)):
                            value = type(value)
                    except ValueError:
                        raise BadOption(
                            "Argument %r is not of expected value" % (name))
            if range is not None and not (range[0] <= value <= range[1]):
                raise BadOption("Argument %r out of range (%d-%d)" % (
                    name, range[0], range[1]))
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
        return self.get(b'uid')

    def get_url(self):
        return self._get_url(b"url")

    def get_baseurl(self):
        return self._get_url(b"baseurl", default=None)

    def get_wait(self):
        return self.get(b"wait", defaults.WAIT_TIME, type=float,
                        range=(0, defaults.MAX_WAIT_TIME))

    def get_timeout(self):
        default = min(self.max_timeout, defaults.TIMEOUT)
        return self.get(b"timeout", default, type=float,
                        range=(0, self.max_timeout))

    def get_images(self):
        return self._get_bool(b"images", defaults.AUTOLOAD_IMAGES)

    def get_proxy(self):
        proxy = self.get(b"proxy", default=None)
        if isinstance(proxy, bytes):
            proxy = proxy.decode('utf-8')
        return proxy

    def get_js_source(self):
        # we want js_source to be unicode, not bytes.
        val = self.get(b"js_source", default=None)
        if val:
            return val.decode('utf-8')
        return val

    def get_width(self):
        return self.get(b"width", None, type=int, range=(1, defaults.MAX_WIDTH))

    def get_height(self):
        return self.get(b"height", None, type=int,
                        range=(1, defaults.MAX_HEIGTH))

    def get_scale_method(self):
        scale_method = self.get(b"scale_method", defaults.PNG_SCALE_METHOD)
        if isinstance(scale_method, bytes):
            scale_method = scale_method.decode('utf-8')
        if scale_method not in ('raster', 'vector'):
            raise BadOption(
                "Invalid 'scale_method' (must be 'raster' or 'vector'): %s" %
                scale_method)
        return scale_method

    def get_http_method(self):
        val = self.get(b"http_method", "GET")
        if val != "GET":
            val = val.decode("utf-8")
        return val

    def get_body(self):
        return self.get(b"body", None)

    def get_render_all(self, wait=None):
        result = self._get_bool(b"render_all", False)
        if result == 1 and wait == 0:
            raise BadOption("Pass non-zero 'wait' to render full webpage")
        return result

    def get_lua_source(self):
        return self.get(b"lua_source")

    def get_js_profile(self, js_profiles_path):
        js_profile = self.get(b"js", default=None)
        if not js_profile:
            return js_profile

        if js_profiles_path is None:
            raise BadOption('Javascript profiles are not enabled')
        profile_dir = os.path.join(js_profiles_path, js_profile.decode('utf-8'))
        if not profile_dir.startswith(js_profiles_path + os.path.sep):
            # security check fails
            raise BadOption('Javascript profile does not exist')
        if not os.path.isdir(profile_dir):
            raise BadOption('Javascript profile does not exist')
        return profile_dir

    def get_headers(self):
        headers = self.get(b"headers", default=None, type=None)

        if headers is None:
            return headers

        if not isinstance(headers, (list, tuple, dict)):
            raise BadOption("'headers' must be either JSON array of (name, value) pairs or JSON object")

        if isinstance(headers, (list, tuple)):
            for el in headers:
                if not (isinstance(el, (list, tuple)) and len(el) == 2 and all(
                        isinstance(e, (six.string_types, six.binary_type)) for e
                        in el)):
                    raise BadOption("'headers' must be either JSON array of (name, value) pairs or JSON object")
        try:
            headers = bytes_to_unicode(headers, encoding='ascii')
        except UnicodeDecodeError:
            raise BadOption("headers can not contain non-ascii characters.")
        return headers

    def get_viewport(self, wait=None):
        viewport = self.get(b"viewport", defaults.VIEWPORT_SIZE)
        if isinstance(viewport, bytes):
            viewport = viewport.decode('utf-8')
        if viewport == 'full':
            if wait == 0:
                raise BadOption("Pass non-zero 'wait' to render full webpage")
        else:
            try:
                validate_size_str(viewport)
            except ValueError as e:
                raise BadOption(str(e))
        return viewport

    def get_filters(self, pool=None, adblock_rules=None):
        filter_names = self.get(b'filters', b'')
        filter_names = [f for f in filter_names.decode('utf-8').split(',') if f]

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
        allowed_domains = self.get(b"allowed_domains", default=None)
        if allowed_domains is not None:
            return allowed_domains.decode('utf-8').split(',')

    def get_allowed_content_types(self):
        content_types = self.get(b"allowed_content_types", default=[b'*/*'])
        if isinstance(content_types, six.binary_type):
            content_types = list(filter(None, content_types.split(b',')))
        content_types = [type.decode('utf-8') for type in content_types]
        return content_types

    def get_forbidden_content_types(self):
        content_types = self.get(b"forbidden_content_types", default=[])
        if isinstance(content_types, six.binary_type):
            content_types = list(filter(None, content_types.split(b',')))
        content_types = [type.decode('utf-8') for type in content_types]
        return content_types

    def get_common_params(self, js_profiles_path):
        wait = self.get_wait()
        return {
            'url': self.get_url(),
            'baseurl': self.get_baseurl(),
            'wait': wait,
            'viewport': self.get_viewport(wait),
            'render_all': self.get_render_all(wait),
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
        return {'width': self.get_width(), 'height': self.get_height(),
                'scale_method': self.get_scale_method()}

    def get_include_params(self):
        return dict(
            html=self._get_bool(b"html", defaults.DO_HTML),
            iframes=self._get_bool(b"iframes", defaults.DO_IFRAMES),
            png=self._get_bool(b"png", defaults.DO_PNG),
            script=self._get_bool(b"script", defaults.SHOW_SCRIPT),
            console=self._get_bool(b"console", defaults.SHOW_CONSOLE),
            history=self._get_bool(b"history", defaults.SHOW_HISTORY),
            har=self._get_bool(b"har", defaults.SHOW_HAR),
        )


def validate_size_str(size_str):
    """
    Validate size string in WxH format.

    Can be used to validate both viewport and window size strings.  Does not
    special-case ``'full'`` viewport.  Raises ``ValueError`` if anything goes
    wrong.

    :param size_str: string to validate

    """
    max_width = defaults.VIEWPORT_MAX_WIDTH
    max_heigth = defaults.VIEWPORT_MAX_HEIGTH
    max_area = defaults.VIEWPORT_MAX_AREA
    try:
        w, h = map(int, size_str.split('x'))
    except ValueError:
        raise ValueError("Invalid viewport format: %s" % size_str)
    else:
        if not ((0 < w <= max_width) and (0 < h <= max_heigth) and
                    (w * h < max_area)):
            raise ValueError("Viewport is out of range (%dx%d, area=%d)" %
                             (max_width, max_heigth, max_area))
