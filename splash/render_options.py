# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import json

import six

from splash import defaults
from splash.utils import to_bytes, path_join_secure
from splash.exceptions import BadOption


class RenderOptions(object):
    """
    Options that control how to render a response.
    """

    _REQUIRED = object()

    def __init__(self, data, max_timeout):
        self.data = data
        self.max_timeout = max_timeout

    @classmethod
    def raise_error(cls, argument, description, type='bad_argument', **kwargs):
        params = {
            'type': type,
            'argument': argument,
            'description': description
        }
        params.update(kwargs)
        raise BadOption(params)

    @classmethod
    def fromrequest(cls, request, max_timeout):
        """
        Initialize options from a Twisted Request.
        """

        # 1. GET / POST data
        data = {key.decode('utf-8'): values[0].decode('utf-8') for key, values
                in request.args.items()}
        if request.method == b'POST':
            content_type = request.getHeader(b'content-type')
            if content_type:
                request.content.seek(0)

                # 2. application/json POST data
                if b'application/json' in content_type:
                    try:
                        content = request.content.read().decode('utf-8')
                        data.update(json.loads(content, encoding='utf8'))
                    except ValueError as e:
                        raise BadOption({
                            'type': 'invalid_json',
                            'description': "Can't decode JSON",
                            'message': str(e),
                        })

                # 3. js_source from application/javascript POST requests
                if b'application/javascript' in content_type:
                    data['js_source'] = request.content.read().decode('utf-8')
                request.content.seek(0)

        data['uid'] = id(request)
        return cls(data, max_timeout)

    def get_expired_args(self, cache):
        """
        Return a list of argument names from load_args which can't be loaded
        """
        return cache.get_missing(self.get_load_args().items())

    def save_args_to_cache(self, cache):
        """
        Process save_args and put all values to cache.
        Return a list of (name, key) pairs.
        """
        save_args = self.get_save_args()
        save_values = [self.data.get(name) for name in save_args]
        keys = cache.add_many(save_values)
        return list(zip(save_args, keys))

    def load_cached_args(self, cache):
        load_args = self.get_load_args()
        for name, key in (load_args or {}).items():
            self.data[name] = cache[key]

    def get(self, name, default=_REQUIRED, type=six.text_type, range=None):
        value = self.data.get(name)
        if value is not None:
            if type is not None:
                try:
                    value = type(value)
                except ValueError:
                    msg = "Argument %r has a wrong type" % (name,)
                    self.raise_error(name, msg, required_type=type.__name__)
            if range is not None and not (range[0] <= value <= range[1]):
                self.raise_error(name, 'Argument is out of the allowed range',
                                 min=range[0], max=range[1], value=value)
            return value
        elif default is self._REQUIRED:
            self.raise_error(name, 'Required argument is missing: %s' % name,
                             type='argument_required')
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
        return self.get("wait", defaults.WAIT_TIME, type=float,
                        range=(0, defaults.MAX_WAIT_TIME))

    def get_timeout(self):
        default = min(self.max_timeout, defaults.TIMEOUT)
        return self.get("timeout", default, type=float,
                        range=(0, self.max_timeout))

    def get_resource_timeout(self):
        return self.get("resource_timeout", defaults.RESOURCE_TIMEOUT,
                        type=float, range=(0, 1e6))

    def get_response_body(self):
        return self._get_bool("response_body", defaults.RESPONSE_BODY_ENABLED)

    def get_images(self):
        return self._get_bool("images", defaults.AUTOLOAD_IMAGES)

    def get_proxy(self):
        return self.get("proxy", default=None)

    def get_js_source(self):
        return self.get("js_source", default=None)

    def get_width(self):
        return self.get("width", None, type=int, range=(1, defaults.MAX_WIDTH))

    def get_height(self):
        return self.get("height", None, type=int,
                        range=(1, defaults.MAX_HEIGTH))

    def get_scale_method(self):
        scale_method = self.get("scale_method", defaults.IMAGE_SCALE_METHOD)
        allowed_scale_methods = ['raster', 'vector']
        if scale_method not in allowed_scale_methods:
            self.raise_error(
                argument='scale_method',
                description="Invalid 'scale_method': %s" % scale_method,
                allowed=allowed_scale_methods,
                received=scale_method,
            )

        return scale_method

    def get_quality(self):
        return self.get("quality", defaults.JPEG_QUALITY, type=int, range=(0, 100))

    def get_http_method(self):
        method = self.get("http_method", "GET")
        if method.upper() not in ["POST", "GET"]:
            self.raise_error("http_method", "Unsupported HTTP method {}".format(method))
        return method

    def get_body(self):
        body = self.get("body", None, to_bytes)
        method = self.get("http_method", "GET").upper()
        if method == 'GET' and body:
            self.raise_error("body", "GET request should not have a body")
        return body

    def get_render_all(self, wait=None):
        result = self._get_bool("render_all", False)
        if result == 1 and wait == 0:
            self.raise_error("render_all",
                             "Pass non-zero 'wait' to render full webpage")
        return result

    def get_lua_source(self):
        return self.get("lua_source")

    def get_js_profile(self, js_profiles_path):
        js_profile = self.get("js", default=None)
        if not js_profile:
            return js_profile

        if js_profiles_path is None:
            self.raise_error('js',
                             'Javascript profiles are not enabled on server')

        try:
            profile_dir = path_join_secure(js_profiles_path, js_profile)
        except ValueError as e:
            # security check fails
            print(e)
            self.raise_error('js', 'Javascript profile does not exist')

        if not os.path.isdir(profile_dir):
            self.raise_error('js', 'Javascript profile does not exist')

        return profile_dir

    def get_headers(self):
        headers = self.get("headers", default=None, type=None)

        if headers is None:
            return headers

        if not isinstance(headers, (list, tuple, dict)):
            self.raise_error(
                argument='headers',
                description="'headers' must be either a JSON array of "
                            "(name, value) pairs or a JSON object"
            )

        if isinstance(headers, (list, tuple)):
            for el in headers:
                string_only = all(isinstance(e, six.string_types) for e in el)
                if not (isinstance(el, (list, tuple)) and len(el) == 2 and string_only):
                    self.raise_error(
                        argument='headers',
                        description="'headers' must be either a JSON array of "
                                    "(name, value) pairs or a JSON object"
                    )

        return headers

    def get_save_args(self):
        save_args = self.get("save_args", default=None, type=None)
        if save_args is None:
            return []

        if isinstance(save_args, six.text_type):
            # comma-separated string
            save_args = save_args.split(',')

        if not isinstance(save_args, list):
            self.raise_error(
                argument="save_args",
                description="'save_args' should be either a comma-separated "
                            "string or a JSON array with argument names",
            )

        # JSON array
        if not all(isinstance(a, six.text_type) for a in save_args):
            self.raise_error(
                argument="save_args",
                description="'save_args' should be a list of strings",
            )
        return save_args

    def get_load_args(self):
        load_args = self.get("load_args", default=None, type=None)
        if load_args is None:
            return {}

        if isinstance(load_args, six.text_type):
            try:
                load_args = dict(
                    kv.split("=", 1) for kv in load_args.split(';')
                )
            except ValueError:
                self.raise_error(
                    argument="load_args",
                    description="'load_args' string value is not a "
                                "semicolon-separated list of name=hash pairs"
                )

        if not isinstance(load_args, dict):
            self.raise_error(
                argument="load_args",
                description="'load_args' should be either a JSON object with "
                            "argument hashes or a semicolon-separated list "
                            "of name=hash pairs"
            )

        return load_args

    def get_viewport(self, wait=None):
        viewport = self.get("viewport", defaults.VIEWPORT_SIZE)

        if viewport == 'full':
            if wait == 0:
                self.raise_error("viewport",
                                 "Pass non-zero 'wait' to render full webpage")
        else:
            try:
                validate_size_str(viewport)
            except ValueError as e:
                self.raise_error("viewport", str(e))
        return viewport

    def get_filters(self, pool=None, adblock_rules=None):
        filter_names = self.get('filters', '')
        filter_names = [f for f in filter_names.split(',') if f]

        if pool is None and adblock_rules is None:  # skip validation
            return filter_names

        if not filter_names:
            return filter_names

        if pool is not None:
            adblock_rules = pool.network_manager_factory.adblock_rules
            if adblock_rules is None:
                self.raise_error(
                    "filters",
                    "Invalid filter names: %s" % (filter_names,)
                )

        if adblock_rules is not None:
            unknown_filters = adblock_rules.get_unknown_filters(filter_names)
            if unknown_filters:
                self.raise_error(
                    "filters",
                    "Invalid filter names: %s" % (unknown_filters,)
                )

        return filter_names

    def get_allowed_domains(self):
        allowed_domains = self.get("allowed_domains", default=None)
        if allowed_domains is not None:
            return allowed_domains.split(',')

    def get_allowed_content_types(self):
        content_types = self.get("allowed_content_types", default=['*'])
        if isinstance(content_types, six.text_type):
            content_types = list(filter(None, content_types.split(',')))
        return content_types

    def get_forbidden_content_types(self):
        content_types = self.get("forbidden_content_types", default=[])
        if isinstance(content_types, six.text_type):
            content_types = list(filter(None, content_types.split(',')))
        return content_types

    def get_common_params(self, js_profiles_path):
        wait = self.get_wait()
        return {
            'url': self.get_url(),
            'baseurl': self.get_baseurl(),
            'wait': wait,
            'resource_timeout': self.get_resource_timeout(),
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

    def get_image_params(self):
        return {
            'width': self.get_width(),
            'height': self.get_height(),
            'scale_method': self.get_scale_method()
        }

    def get_png_params(self):
        return self.get_image_params()

    def get_jpeg_params(self):
        params = {'quality': self.get_quality()}
        params.update(self.get_image_params())
        return params

    def get_include_params(self):
        return dict(
            html=self._get_bool("html", defaults.DO_HTML),
            iframes=self._get_bool("iframes", defaults.DO_IFRAMES),
            png=self._get_bool("png", defaults.DO_PNG),
            jpeg=self._get_bool("jpeg", defaults.DO_JPEG),
            script=self._get_bool("script", defaults.SHOW_SCRIPT),
            console=self._get_bool("console", defaults.SHOW_CONSOLE),
            history=self._get_bool("history", defaults.SHOW_HISTORY),
            har=self._get_bool("har", defaults.SHOW_HAR),
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
