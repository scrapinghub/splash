"""
This module contains Splash twisted.web Resources (HTTP API endpoints
exposed to the user).
"""
from __future__ import absolute_import
import os
import gc
import time
import json
import resource

from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.internet import reactor, defer
from twisted.python import log
import six

import splash
from splash.argument_cache import ArgumentCache
from splash.qtrender import (
    HtmlRender, PngRender, JsonRender, HarRender, JpegRender
)
from splash.lua import is_supported as lua_is_supported
from splash.utils import (
    get_num_fds,
    get_leaks,
    BinaryCapsule,
    SplashJSONEncoder,
    get_ru_maxrss,
    to_bytes)
from splash import sentry
from splash.render_options import RenderOptions
from splash.qtutils import clear_caches
from splash.exceptions import (
    BadOption, RenderError, InternalError,
    GlobalTimeoutError, UnsupportedContentType,
    ExpiredArguments,
)

if lua_is_supported():
    from splash.qtrender_lua import LuaRender
else:
    LuaRender = None


class _ValidatingResource(Resource):
    def render(self, request):
        try:
            return Resource.render(self, request)
        except BadOption as e:
            self._write_error(request, 400, e)
            self._log_stats(request, {}, error=self._format_error(400, e))
            return b"\n"

    def _write_error_content(self, request, code, err,
                             content_type=b'text/plain'):
        request.setHeader(b"content-type", content_type)
        request.setResponseCode(code)
        content = json.dumps(err).encode('utf8')
        request.write(content)
        return err

    def _write_error(self, request, code, exc):
        """Can be overridden by subclasses format errors differently"""
        err = self._format_error(code, exc)
        return self._write_error_content(request, code, err,
                                         content_type=b"application/json")

    def _format_error(self, code, exc):
        err = {
            "error": code,
            "type": exc.__class__.__name__,
            "description": (exc.__doc__ or '').strip(),
            "info": None,
        }
        if len(exc.args) == 1:
            err['info'] = exc.args[0]
        elif len(exc.args) > 1:
            err['info'] = exc.args
        return err


class BaseRenderResource(_ValidatingResource):

    isLeaf = True
    content_type = "text/html; charset=utf-8"

    def __init__(self, pool, max_timeout, argument_cache):
        Resource.__init__(self)
        self.pool = pool
        self.js_profiles_path = self.pool.js_profiles_path
        self.max_timeout = max_timeout
        self.argument_cache = argument_cache

    def render_GET(self, request):
        #log.msg("%s %s %s %s" % (id(request), request.method, request.path, request.args))
        request.starttime = time.time()
        render_options = RenderOptions.fromrequest(request, self.max_timeout)

        # process argument cache
        original_options = render_options.data.copy()
        expired_args = render_options.get_expired_args(self.argument_cache)
        if expired_args:
            error = self._write_expired_args(request, expired_args)
            self._log_stats(request, original_options, error)
            return b"\n"

        saved_args = render_options.save_args_to_cache(self.argument_cache)
        if saved_args:
            value = ';'.join("{}={}".format(name, value)
                             for name, value in saved_args)
            request.setHeader(b'X-Splash-Saved-Arguments', value.encode('utf8'))
        render_options.load_cached_args(self.argument_cache)

        # check arguments before starting the render
        render_options.get_filters(self.pool)

        timeout = render_options.get_timeout()
        wait_time = render_options.get_wait()

        pool_d = self._get_render(request, render_options)
        timer = reactor.callLater(timeout+wait_time, pool_d.cancel)
        request.notifyFinish().addErrback(self._request_failed, pool_d, timer)

        pool_d.addCallback(self._cancel_timer, timer)
        pool_d.addCallback(self._write_output, request)
        pool_d.addErrback(self._on_timeout_error, request, timeout=timeout)
        pool_d.addErrback(self._on_render_error, request)
        pool_d.addErrback(self._on_bad_request, request)
        pool_d.addErrback(self._on_internal_error, request)
        pool_d.addBoth(self._finish_request, request,
                       options=original_options)
        return NOT_DONE_YET

    def render_POST(self, request):
        request_content_type = request.getHeader(b'content-type').decode('latin1')
        supported_types = ['application/javascript', 'application/json']
        if not any(ct in request_content_type for ct in supported_types):
            ex = UnsupportedContentType({
                'supported': supported_types,
                'received': request_content_type,
            })
            return self._write_error(request, 415, ex)

        return self.render_GET(request)

    def _cancel_timer(self, _, timer):
        #log.msg("_cancelTimer")
        timer.cancel()
        return _

    def _request_failed(self, _, pool_d, timer):
        log.msg("Client disconnected: %s" % _.value)
        timer.cancel()
        pool_d.cancel()

    def _write_output(self, data, request, content_type=None):

        # log.msg("_writeOutput: %s" % id(request))
        # log.msg("%r %r" % (data, content_type))

        if content_type is None:
            content_type = self.content_type

        if isinstance(data, (dict, list)):
            data = json.dumps(data, cls=SplashJSONEncoder)
            return self._write_output(data, request, b"application/json")

        if isinstance(data, tuple) and len(data) == 4:
            data, content_type, headers, status_code = data

            request.setResponseCode(status_code)
            for name, value in headers:
                request.setHeader(name, value)
            return self._write_output(data, request, content_type)

        if data is None or isinstance(data, (bool, six.integer_types, float)):
            return self._write_output(str(data), request, content_type)

        if isinstance(data, BinaryCapsule):
            return self._write_output(data.data, request, data.content_type)

        if not isinstance(data, bytes):
            data = data.encode('utf8')

        if not isinstance(content_type, bytes):
            content_type = content_type.encode('latin1')

        request.setHeader(b"content-type", content_type)

        if not isinstance(data, bytes):
            # Twisted expects bytes as response
            data = data.encode('utf-8')

        request.write(data)

    def _write_expired_args(self, request, expired_args):
        ex = ExpiredArguments({'expired': expired_args})
        return self._write_error(request, 498, ex)

    def _log_stats(self, request, options, error=None):
        msg = {
            # Anything we retrieve from Twisted request object contains bytes.
            # We have to convert it to unicode first for json.dump to succeed.
            "path": request.path.decode('utf-8'),
            "rendertime": time.time() - request.starttime,
            "maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "load": os.getloadavg(),
            "fds": get_num_fds(),
            "active": len(self.pool.active),
            "qsize": len(self.pool.queue.pending),
            "_id": id(request),
            "method": request.method.decode('ascii'),
            "timestamp": int(time.time()),
            "user-agent": (request.getHeader(b"user-agent").decode('utf-8')
                           if request.getHeader(b"user-agent") else None),
            "args": options,
            "status_code": request.code,
            "client_ip": request.client.host
        }
        if error:
            msg["error"] = error
        msg = json.dumps(msg).encode("utf8")
        log.msg(msg, system="events")

    def _on_timeout_error(self, failure, request, timeout=None):
        failure.trap(defer.CancelledError)
        ex = GlobalTimeoutError({'timeout': timeout})
        return self._write_error(request, 504, ex)

    def _on_render_error(self, failure, request):
        failure.trap(RenderError)
        # log.msg("_on_render_error: %s" % id(request))
        return self._write_error(request, 502, failure.value)

    def _on_internal_error(self, failure, request):
        log.err()
        # failure.printTraceback()
        sentry.capture(failure)
        # only propagate str value to avoid exposing internal details
        ex = InternalError(str(failure.value))
        return self._write_error(request, 500, ex)

    def _on_bad_request(self, failure, request):
        failure.trap(BadOption)
        # log.msg("_on_bad_request: %s" % id(request))
        return self._write_error(request, 400, failure.value)

    def _finish_request(self, failure, request, options):
        self._log_stats(request, options, error=failure)
        if not request._disconnected:
            request.finish()

        # log.msg("_finishRequest: %s" % id(request))

    def _get_render(self, request, options):
        raise NotImplementedError()


class RenderHtmlResource(BaseRenderResource):
    content_type = "text/html; charset=utf-8"

    def _get_render(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        return self.pool.render(HtmlRender, options, **params)


class ExecuteLuaScriptResource(BaseRenderResource):
    content_type = "text/plain; charset=utf-8"

    def __init__(self, pool, sandboxed,
                 lua_package_path,
                 lua_sandbox_allowed_modules,
                 max_timeout,
                 argument_cache,
                 ):
        BaseRenderResource.__init__(self, pool, max_timeout, argument_cache)
        self.sandboxed = sandboxed
        self.lua_package_path = lua_package_path
        self.lua_sandbox_allowed_modules = lua_sandbox_allowed_modules

    def _get_render(self, request, options):
        params = dict(
            proxy=options.get_proxy(),
            lua_source=options.get_lua_source(),
            sandboxed=self.sandboxed,
            lua_package_path=self.lua_package_path,
            lua_sandbox_allowed_modules=self.lua_sandbox_allowed_modules,
        )
        return self.pool.render(LuaRender, options, **params)


class RenderPngResource(BaseRenderResource):
    content_type = "image/png"

    def _get_render(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        params.update(options.get_png_params())
        return self.pool.render(PngRender, options, **params)


class RenderJpegResource(BaseRenderResource):

    content_type = "image/jpeg"

    def _get_render(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        params.update(options.get_jpeg_params())
        return self.pool.render(JpegRender, options, **params)


class RenderJsonResource(BaseRenderResource):
    content_type = "application/json"

    def _get_render(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        params.update(options.get_jpeg_params())
        params.update(options.get_include_params())
        params['response_body'] = options.get_response_body()
        return self.pool.render(JsonRender, options, **params)


class RenderHarResource(BaseRenderResource):
    content_type = "application/json"

    def _get_render(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        params['response_body'] = options.get_response_body()
        return self.pool.render(HarRender, options, **params)


class DebugResource(Resource):
    isLeaf = True

    def __init__(self, pool, argument_cache, warn=False):
        Resource.__init__(self)
        self.argument_cache = argument_cache
        self.pool = pool
        self.warn = warn

    def render_GET(self, request):
        request.setHeader(b"content-type", b"application/json")
        info = {
            "leaks": get_leaks(),
            "active": [self.get_repr(r) for r in self.pool.active],
            "qsize": len(self.pool.queue.pending),
            "maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "fds": get_num_fds(),
            "argcache": len(self.argument_cache)
        }
        if self.warn:
            info['WARNING'] = "/debug endpoint is deprecated. " \
                              "Please use /_debug instead."

        return (json.dumps(info, sort_keys=True)).encode('utf-8')

    def get_repr(self, render):
        if hasattr(render, 'url'):
            return render.url
        return render.tab.url


class ClearCachesResource(Resource):
    isLeaf = True
    content_type = "application/json"

    def __init__(self, argument_cache):
        Resource.__init__(self)
        self.argument_cache = argument_cache

    def render_POST(self, request):
        argcache_size = len(self.argument_cache)
        self.argument_cache.clear()
        clear_caches()
        unreachable = gc.collect()
        return json.dumps({
            "status": "ok",
            "pyobjects_collected": unreachable,
            "cached_args_removed": argcache_size,
        }, sort_keys=True).encode('utf-8')


class PingResource(Resource):
    isLeaf = True

    def render_GET(self, request):
        request.setHeader(b"content-type", b"application/json")
        return (json.dumps({
            "status": "ok",
            "maxrss": get_ru_maxrss(),
        }, sort_keys=True)).encode('utf-8')



HARVIEWER_PATH = 'harviewer-2.0.17a' # Change to invalidate cache when updating harviewer
BOOTSTRAP_THEME = 'simplex'

CODEMIRROR_RESOURCES = """
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/codemirror.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/theme/mbo.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/addon/hint/show-hint.css" rel="stylesheet">

<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/codemirror.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/mode/lua/lua.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/addon/hint/show-hint.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/addon/hint/anyword-hint.min.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/addon/edit/matchbrackets.min.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/5.10.0/addon/edit/closebrackets.min.js"></script>

"""

def safe_json(obj):
    """ Encode JSON so that it can be embedded safely inside HTML"""
    return json.dumps(obj).replace('<', '\\u003c')


class DemoUI(_ValidatingResource):
    isLeaf = True
    content_type = "text/html; charset=utf-8"

    PATH = b'info'

    def __init__(self, pool, lua_enabled, max_timeout):
        Resource.__init__(self)
        self.pool = pool
        self.lua_enabled = lua_enabled
        self.max_timeout = max_timeout

    def _validate_params(self, request):
        options = RenderOptions.fromrequest(request, self.max_timeout)
        options.get_filters(self.pool)  # check
        params = options.get_common_params(self.pool.js_profiles_path)
        params.update({
            'save_args': options.get_save_args(),
            'load_args': options.get_load_args(),
            'timeout': options.get_timeout(),
            'response_body': options.get_response_body(),
            'har': 1,
            'png': 1,
            'html': 1,
        })
        filters = options.get('filters', default='')
        if filters:
            params['filters'] = filters

        if self.lua_enabled:
            params.update({
                'lua_source': options.get_lua_source(),
            })
        return params

    def render_GET(self, request):
        params = self._validate_params(request)
        url = params.get('url', '').strip()
        if url and not url.lower().startswith('http'):
            url = 'http://' + url
        params['url'] = url
        timeout = params['timeout']
        params = {k: v for k, v in params.items() if v is not None}

        # disable "phases" HAR Viewer feature
        request.addCookie('phaseInterval', 120000)

        return ("""<!DOCTYPE html><html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>Splash %(version)s | %(url)s</title>
            <link rel="stylesheet" href="_ui/%(harviewer_path)s/css/harViewer.css" type="text/css"/>

            <link href="//maxcdn.bootstrapcdn.com/bootswatch/3.2.0/%(theme)s/bootstrap.min.css" rel="stylesheet">
            <link rel="icon" type="image/x-icon" href="/_ui/favicon.ico">
            <script src="//code.jquery.com/jquery-1.11.1.min.js"></script>
            <script src="//code.jquery.com/jquery-migrate-1.2.1.js"></script>

            <script src="//maxcdn.bootstrapcdn.com/bootstrap/3.2.0/js/bootstrap.min.js"></script>
            %(cm_resources)s
            <link rel="stylesheet" href="/_ui/style.css">
        </head>
        <body class="harBody no-lua" style="color:#000">
            <div class="container"> <!-- style="margin: 0 auto; width: 95%%;"-->

                <div class="navbar navbar-default">
                  <div class="navbar-header">
                    <button type="button" class="navbar-toggle" data-toggle="collapse" data-target=".navbar-responsive-collapse">
                      <span class="icon-bar"></span>
                      <span class="icon-bar"></span>
                      <span class="icon-bar"></span>
                    </button>
                    <a class="navbar-brand" href="/">Splash v%(version)s</a>
                  </div>
                  <div class="navbar-collapse collapse navbar-responsive-collapse">
                    <ul class="nav navbar-nav">
                      <li><a href="http://splash.readthedocs.org">Documentation</a></li>
                      <li><a href="https://github.com/scrapinghub/splash">Source Code</a></li>
                    </ul>

                    <form class="navbar-form navbar-right" method="GET" action="/info">
                      <input type="hidden" name="wait" value="0.5">
                      <input type="hidden" name="images" value="1">
                      <input type="hidden" name="expand" value="1"> <!-- for HAR viewer -->
                      <input type="hidden" name="timeout" value="%(timeout)s">

                      <div class="btn-group" id="render-form">
                          <input class="form-control col-lg-8" type="text" placeholder="Paste an URL" type="text" name="url" value="%(url)s">

                          <a href="#" class="btn btn-default dropdown-toggle if-lua" data-toggle="dropdown">Script&nbsp;<b class="caret"></b></a>
                          <div class="dropdown-menu panel panel-default if-lua" id="lua-code-editor-panel">
                            <div class="panel-body2">
                              <textarea id="lua-code-editor" name='lua_source'></textarea>
                            </div>
                          </div>
                      </div>
                      <button class="btn btn-success" type="submit">Render!</button>
                    </form>

                    <ul class="nav navbar-nav navbar-right">
                      <li><a id="status">Initializing...</a></li>
                    </ul>

                  </div>
                </div>

                <div id="result" style="display: none;">
                    <span class="key">Splash Response</span><span class="colon">:</span>
                    <span class="obj-item"></span>
                </div>

                <div id="errorMessage" style="display:none">
                    <h4>HTTP Error <span id='errorStatus'></span></h4>
                    <h4>Type: <span id='errorType'></span></h4>
                    <p id='errorDescription' class="errorMessage"></p>
                    <p id='errorMessageText' class="errorMessage"></p>
                    <pre id='errorData'></pre>
                </div>
            </div>

            <script> var splash = %(options)s; </script>
            <script src="/_ui/main.js"> </script>
        </body>
        </html>
        """ % dict(
            version=splash.__version__,
            harviewer_path=HARVIEWER_PATH,
            options=safe_json({
                "params": params,
                "endpoint": "execute" if self.lua_enabled else "render.json",
                "harviewer_path": HARVIEWER_PATH,
                "lua_enabled": self.lua_enabled,
            }),
            timeout=timeout,
            url=url,
            theme=BOOTSTRAP_THEME,
            cm_resources=CODEMIRROR_RESOURCES if self.lua_enabled else "",
        )).encode('utf-8')


class Root(Resource):
    def __init__(self, pool, ui_enabled, lua_enabled, lua_sandbox_enabled,
                 lua_package_path,
                 lua_sandbox_allowed_modules,
                 max_timeout,
                 argument_cache_max_entries,
                 ):
        Resource.__init__(self)
        self.argument_cache = ArgumentCache(argument_cache_max_entries)
        self.ui_enabled = ui_enabled
        self.lua_enabled = lua_enabled

        _args = pool, max_timeout, self.argument_cache
        self.putChild(b"render.html", RenderHtmlResource(*_args))
        self.putChild(b"render.png", RenderPngResource(*_args))
        self.putChild(b"render.jpeg", RenderJpegResource(*_args))
        self.putChild(b"render.json", RenderJsonResource(*_args))
        self.putChild(b"render.har", RenderHarResource(*_args))

        self.putChild(b"_debug", DebugResource(pool, self.argument_cache))
        self.putChild(b"_gc", ClearCachesResource(self.argument_cache))
        self.putChild(b"_ping", PingResource())

        # backwards compatibility
        self.putChild(b"debug", DebugResource(pool, self.argument_cache, warn=True))

        if self.lua_enabled and ExecuteLuaScriptResource is not None:
            self.putChild(b"execute", ExecuteLuaScriptResource(
                pool=pool,
                sandboxed=lua_sandbox_enabled,
                lua_package_path=lua_package_path,
                lua_sandbox_allowed_modules=lua_sandbox_allowed_modules,
                max_timeout=max_timeout,
                argument_cache=self.argument_cache,
            ))

        if self.ui_enabled:
            root = os.path.dirname(__file__)
            ui = File(os.path.join(root, 'ui'))

            har_path = os.path.join(root, 'vendor', 'harviewer', 'webapp')
            ui.putChild(to_bytes(HARVIEWER_PATH), File(har_path))
            inspections_path = os.path.join(root, 'kernel', 'inspections')
            ui.putChild(b"inspections", File(inspections_path))
            examples_path = os.path.join(root, 'examples')
            ui.putChild(b"examples", File(examples_path))

            self.putChild(b"_ui", ui)
            self.putChild(DemoUI.PATH, DemoUI(
                pool=pool,
                lua_enabled=self.lua_enabled,
                max_timeout=max_timeout
            ))
        self.max_timeout = max_timeout

    def getChild(self, name, request):
        if name == b"" and self.ui_enabled:
            return self
        return Resource.getChild(self, name, request)

    def get_example_script(self):
        return """
function main(splash)
  local url = splash.args.url
  assert(splash:go(url))
  assert(splash:wait(0.5))
  return {
    html = splash:html(),
    png = splash:png(),
    har = splash:har(),
  }
end
""".strip()

    def render_GET(self, request):
        """ Index page """
        result = """<!DOCTYPE html><html>
        <head>
            <title>Splash %(version)s</title>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <link href="//maxcdn.bootstrapcdn.com/bootswatch/3.2.0/%(theme)s/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="/_ui/style.css">
            <link rel="icon" type="image/x-icon" href="/_ui/favicon.ico">
            <script src="//code.jquery.com/jquery-1.11.1.min.js"></script>
            <script src="//maxcdn.bootstrapcdn.com/bootstrap/3.2.0/js/bootstrap.min.js"></script>
            %(cm_resources)s
        </head>
        <body class="no-lua">
            <div class="container">
                <div class="page-header">
                    <h1>Splash v%(version)s</h1>
                </div>

                <div class="row">
                    <div class="col-lg-6">
                        <p class="lead">
                        Splash is a javascript rendering service.
                        It's a lightweight browser with an HTTP API,
                        implemented in Python using Twisted and QT.
                        </p>

                        <ul>
                            <li>Process multiple webpages in parallel</li>
                            <li>Get HTML results and/or take screenshots</li>
                            <li>Turn OFF images <a class="demo-link if-lua" href="#" onclick="splash.loadExample('disable-images', 'http://flickr.com')">Run live example</a> or use <a href="https://adblockplus.org">Adblock Plus</a>
                                rules to make rendering faster</li>
                            <li>Execute custom JavaScript in page context <a class="demo-link if-lua" href="#" onclick="splash.loadExample('run-js')">Run live example</a></li>
                            <li>Write Lua browsing scripts;</li>
                            <li>Get detailed rendering info in <a href="http://www.softwareishard.com/blog/har-12-spec/">HAR</a> format <a class="demo-link if-lua" href="#" onclick="splash.loadExample('har')">Run live example</a></li>
                        </ul>

                        <p class="lead">
                            Splash is free & open source.
                            Commercial support is also available by
                            <a href="http://scrapinghub.com/">Scrapinghub</a>.
                        </p>
                        <div>
                            <a class="btn btn-info" href="http://splash.readthedocs.org/">Documentation</a>
                            <div class="dropdown examples-dropdown">
                                <a class="btn btn-info if-lua dropdown-toggle" data-toggle="dropdown" href="#">Examples&nbsp;<b class="caret"></b></a>
                                <ul class="dropdown-menu panel panel-default if-lua">
                                    <li><a href="#" onclick="splash.loadExample('phantomjs-follow', '')">Count twitter followers</a></li>
                                    <li><a href="#" onclick="splash.loadExample('wait-for-element')">Wait for element</a></li>
                                    <li><a href="#" onclick="splash.loadExample('scroll', 'http://scrapinghub.com')">Scroll page</a></li>
                                    <li><a href="#" onclick="splash.loadExample('preload-jquery')">Preload jQuery</a></li>
                                    <li><a href="#" onclick="splash.loadExample('preload-functions')">Preload functions</a></li>
                                    <li><a href="#" onclick="splash.loadExample('multiple-pages', '')">Load multiple pages</a></li>
                                    <li><a href="#" onclick="splash.loadExample('count-divs')">Count DIV tags</a></li>
                                    <li><a href="#" onclick="splash.loadExample('call-later')">Call Later</a></li>
                                    <li><a href="#" onclick="splash.loadExample('render-png')">Render PNG</a></li>
                                    <li><a href="#" onclick="splash.loadExample('element-screenshot')">Take a screenshot of a single element</a></li>
                                    <li><a href="#" onclick="splash.loadExample('log-requests')">Log requested URLs</a></li>
                                    <li><a href="#" onclick="splash.loadExample('block-css')">Block CSS</a></li>
                                    <li><a href="#" onclick="splash.loadExample('with-timeout')">Execute function with timeout</a></li>
                                </ul>
                            </div>
                            <a class="btn btn-info" href="https://github.com/scrapinghub/splash">Source code</a>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <form class="form-horizontal" method="GET" action="/info">
                          <input type="hidden" name="wait" value="0.5">
                          <input type="hidden" name="images" value="1">
                          <input type="hidden" name="expand" value="1"> <!-- for HAR viewer -->
                          <input type="hidden" name="timeout" value="%(timeout)s">

                          <fieldset>
                            <div class="">
                              <div class="input-group col-lg-10">
                                <input class="form-control" type="text" placeholder="Paste an URL" value="http://google.com" name="url">
                                <span class="input-group-btn">
                                  <button class="btn btn-success" type="submit">Render me!</button>
                                </span>
                              </div>
                              <div class="input-group col-lg-10 if-lua">
                                <textarea id='lua-code-editor' name='lua_source'></textarea>
                              </div>
                            </div>
                          </fieldset>
                        </form>
                    </div>
                </div>
            </div>
            <div class="tooltip top" role="tooltip" id="example-tooltip">
                <div class="tooltip-arrow"></div>
                <div class="tooltip-inner">
            <script> var splash = %(options)s; </script>
            <script src="/_ui/main.js"> </script>
        </body>
        </html>""" % dict(
            version=splash.__version__,
            theme=BOOTSTRAP_THEME,
            options=safe_json({
                "endpoint": "execute" if self.lua_enabled else "render.json",
                "lua_enabled": self.lua_enabled,
                "example_script": self.get_example_script(),
            }),
            cm_resources=CODEMIRROR_RESOURCES,
            timeout=self.max_timeout,
        )
        return result.encode('utf8')
