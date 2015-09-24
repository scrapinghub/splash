"""
This module contains Splash twisted.web Resources (HTTP API endpoints
exposed to the user).
"""
from __future__ import absolute_import
import os
import gc
import time
import json
import types
import resource

from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.internet import reactor, defer
from twisted.python import log

import splash
from splash.qtrender import (
    HtmlRender, PngRender, JsonRender, HarRender, JpegRender
)
from splash.lua import is_supported as lua_is_supported
from splash.utils import get_num_fds, get_leaks, BinaryCapsule, SplashJSONEncoder
from splash import sentry
from splash.render_options import RenderOptions
from splash.qtutils import clear_caches
from splash.exceptions import (
    BadOption, RenderError, InternalError,
    GlobalTimeoutError, UnsupportedContentType,
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
            return self._write_error(request, 400, e)

    def _write_error_content(self, request, code, content, content_type='text/plain'):
        request.setHeader("content-type", content_type)
        request.setResponseCode(code)
        request.write(content)
        return "\n"

    def _write_error(self, request, code, exc):
        """Can be overridden by subclasses format errors differently"""
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

        return self._write_error_content(request, code, json.dumps(err),
                                         content_type="application/json")


class BaseRenderResource(_ValidatingResource):

    isLeaf = True
    content_type = "text/html; charset=utf-8"

    def __init__(self, pool, max_timeout, is_proxy_request=False):
        Resource.__init__(self)
        self.pool = pool
        self.js_profiles_path = self.pool.js_profiles_path
        self.is_proxy_request = is_proxy_request
        self.max_timeout = max_timeout

    def render_GET(self, request):
        #log.msg("%s %s %s %s" % (id(request), request.method, request.path, request.args))

        request.starttime = time.time()
        render_options = RenderOptions.fromrequest(request, self.max_timeout)

        # check arguments before starting the render
        render_options.get_filters(self.pool)

        timeout = render_options.get_timeout()
        wait_time = render_options.get_wait()

        pool_d = self._get_render(request, render_options)
        timer = reactor.callLater(timeout+wait_time, pool_d.cancel)
        pool_d.addCallback(self._cancel_timer, timer)
        pool_d.addCallback(self._write_output, request, options=render_options.data)
        pool_d.addErrback(self._on_timeout_error, request, timeout=timeout)
        pool_d.addErrback(self._on_render_error, request)
        pool_d.addErrback(self._on_bad_request, request)
        pool_d.addErrback(self._on_internal_error, request)
        pool_d.addBoth(self._finish_request, request)
        return NOT_DONE_YET

    def render_POST(self, request):
        if self.is_proxy_request:
            # If request comes from splash proxy service don't handle
            # special content-types.
            # TODO: pass http method to RenderScript explicitly.
            return self.render_GET(request)

        content_type = request.getHeader('content-type')
        supported_types = ['application/javascript', 'application/json']
        if not any(ct in content_type for ct in supported_types):
            ex = UnsupportedContentType({
                'supported': supported_types,
                'received': content_type,
            })
            return self._write_error(request, 415, ex)

        return self.render_GET(request)

    def _cancel_timer(self, _, timer):
        #log.msg("_cancelTimer")
        timer.cancel()
        return _

    def _write_output(self, data, request, content_type=None, options=None):
        # log.msg("_writeOutput: %s" % id(request))

        if content_type is None:
            content_type = self.content_type

        if isinstance(data, (dict, list)):
            data = json.dumps(data, cls=SplashJSONEncoder)
            return self._write_output(data, request, "application/json", options)

        if isinstance(data, tuple) and len(data) == 4:
            data, content_type, headers, status_code = data

            request.setResponseCode(status_code)
            for name, value in headers:
                request.setHeader(name, value)
            return self._write_output(data, request, content_type, options)

        if isinstance(data, (bool, int, long, float, types.NoneType)):
            return self._write_output(str(data), request, content_type, options)

        if isinstance(data, BinaryCapsule):
            return self._write_output(data.data, request, content_type, options)

        request.setHeader("content-type", content_type)

        self._log_stats(request, options)

        request.write(data)

    def _log_stats(self, request, options):

        msg = {
            "path": request.path,
            "rendertime": time.time() - request.starttime,
            "maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "load": os.getloadavg(),
            "fds": get_num_fds(),
            "active": len(self.pool.active),
            "qsize": len(self.pool.queue.pending),
            "_id": id(request),
            "method": request.method,
            "timestamp": int(time.time()),
            "user-agent": request.getHeader("user-agent"),
            "args": options
        }
        log.msg(json.dumps(msg), system="events")

    def _on_timeout_error(self, failure, request, timeout=None):
        failure.trap(defer.CancelledError)
        ex = GlobalTimeoutError({'timeout': timeout})
        return self._write_error(request, 504, ex)

    def _on_render_error(self, failure, request):
        failure.trap(RenderError)
        return self._write_error(request, 502, failure.value)

    def _on_internal_error(self, failure, request):
        log.err()
        sentry.capture(failure)
        # only propagate str value to avoid exposing internal details
        ex = InternalError(str(failure.value))
        return self._write_error(request, 500, ex)

    def _on_bad_request(self, failure, request):
        failure.trap(BadOption)
        return self._write_error(request, 400, failure.value)

    def _finish_request(self, _, request):
        if not request._disconnected:
            request.finish()
        #log.msg("_finishRequest: %s" % id(request))

    def _get_render(self, request, options):
        raise NotImplementedError()


class RenderHtmlResource(BaseRenderResource):
    content_type = "text/html; charset=utf-8"

    def _get_render(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        return self.pool.render(HtmlRender, options, **params)


class ExecuteLuaScriptResource(BaseRenderResource):
    content_type = "text/plain; charset=utf-8"

    def __init__(self, pool, is_proxy_request, sandboxed,
                 lua_package_path,
                 lua_sandbox_allowed_modules,
                 max_timeout):
        BaseRenderResource.__init__(self, pool, max_timeout, is_proxy_request)
        self.sandboxed = sandboxed
        self.lua_package_path = lua_package_path
        self.lua_sandbox_allowed_modules = lua_sandbox_allowed_modules

    def _get_render(self, request, options):
        params = dict(
            proxy = options.get_proxy(),
            lua_source = options.get_lua_source(),
            sandboxed = self.sandboxed,
            lua_package_path = self.lua_package_path,
            lua_sandbox_allowed_modules = self.lua_sandbox_allowed_modules,
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
        return self.pool.render(JsonRender, options, **params)


class RenderHarResource(BaseRenderResource):

    content_type = "application/json"

    def _get_render(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        return self.pool.render(HarRender, options, **params)


class DebugResource(Resource):

    isLeaf = True

    def __init__(self, pool, warn=False):
        Resource.__init__(self)
        self.pool = pool
        self.warn = warn

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        info = {
            "leaks": get_leaks(),
            "active": [self.get_repr(r) for r in self.pool.active],
            "qsize": len(self.pool.queue.pending),
            "maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "fds": get_num_fds(),
        }
        if self.warn:
            info['WARNING'] = "/debug endpoint is deprecated. " \
                              "Please use /_debug instead."
            # info['leaks'] = get_leaks()

        return json.dumps(info)

    def get_repr(self, render):
        if hasattr(render, 'url'):
            return render.url
        return render.tab.url


class ClearCachesResource(Resource):
    isLeaf = True
    content_type = "application/json"

    def render_POST(self, request):
        clear_caches()
        unreachable = gc.collect()
        return json.dumps({
            "status": "ok",
            "pyobjects_collected": unreachable
        })


BOOTSTRAP_THEME = 'simplex'
CODEMIRROR_OPTIONS = """{
    mode: 'lua',
    lineNumbers: true,
    autofocus: true,
    tabSize: 2,
    matchBrackets: false,  // doesn't look good in mbo theme
    autoCloseBrackets: true,
    extraKeys: {
        "Ctrl-Space": "autocomplete",
        "Esc": "autocomplete",
    },
    hint: CodeMirror.hint.anyword,
    theme: 'mbo',
}
"""

CODEMIRROR_RESOURCES = """
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/codemirror.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/theme/mbo.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/theme/monokai.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/theme/midnight.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/addon/hint/show-hint.css" rel="stylesheet">

<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/codemirror.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/mode/lua/lua.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/addon/hint/show-hint.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/addon/hint/anyword-hint.min.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/addon/edit/matchbrackets.min.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/codemirror/4.6.0/addon/edit/closebrackets.min.js"></script>

"""

class DemoUI(_ValidatingResource):
    isLeaf = True
    content_type = "text/html; charset=utf-8"

    PATH = 'info'

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
            'timeout': options.get_timeout(),
            'har': 1,
            'png': 1,
            'html': 1,
        })
        if self.lua_enabled:
            params.update({
                'lua_source': options.get_lua_source(),
            })
        return params

    def render_GET(self, request):
        params = self._validate_params(request)
        url = params['url']
        if not url.lower().startswith('http'):
            url = 'http://' + url
        url = url.encode('utf8')
        params = {k: v for k, v in params.items() if v is not None}

        # disable "phases" HAR Viewer feature
        request.addCookie('phaseInterval', 120000)

        LUA_EDITOR = """
          <a href="#" class="btn btn-default dropdown-toggle" data-toggle="dropdown">Script&nbsp;<b class="caret"></b></a>
          <div class="dropdown-menu panel panel-default" id="lua-code-editor-panel">
            <div class="panel-body2">
              <textarea id="lua-code-editor" name='lua_source'></textarea>
            </div>
          </div>
        """

        return """<html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>Splash %(version)s | %(url)s</title>
            <link rel="stylesheet" href="_harviewer/css/harViewer.css" type="text/css"/>

            <link href="//maxcdn.bootstrapcdn.com/bootswatch/3.2.0/%(theme)s/bootstrap.min.css" rel="stylesheet">
            <script src="https://code.jquery.com/jquery-1.11.1.min.js"></script>
            <script src="https://code.jquery.com/jquery-migrate-1.2.1.js"></script>

            <script src="//maxcdn.bootstrapcdn.com/bootstrap/3.2.0/js/bootstrap.min.js"></script>

            %(cm_resources)s

            <style>
                /* fix bootstrap + harviewer compatibility issues */
                .label { color: #000; font-weight: normal; font-size: 100%%; }
                table { border-collapse: inherit; }
                #content pre {
                    border: 0;
                    padding: 1px;
                    font-family: Menlo,Monaco,Consolas,"Courier New",monospace;
                    font-size: 13px;
                }
                .netInfoParamName { font-size: 13px; }
                #content * { box-sizing: content-box; }
                .netInfoHeadersText { font-size: 13px; }
                .tab {font-weight: inherit}  /* nicer Headers tabs */
                .netInfoHeadersGroup, .netInfoCookiesGroup { font-weight: normal; }
                .harBody { margin-bottom: 2em; }
                .tabBodies {overflow: hidden;}  /* fix an issue with extra horizontal scrollbar */

                /* remove unsupported buttons */
                .netCol.netOptionsCol {display: none;}

                /* styles for custom events */
                .netPageTimingBar {opacity: 0.3; width: 2px; }
                .timeInfoTip { width: 250px !important; }
                .customEventBar { background-color: gray; }
                ._onStarted { background-color: marine; }
                ._onPrepareStart { background-color: green; }
                ._onCustomJsExecuted { background-color: green; }
                ._onScreenshotPrepared { background-color: magenta; }
                ._onPngRendered { background-color: magenta; }
                ._onIframesRendered { background-color: black; }

                /* editor styling */
                #lua-code-editor-panel {padding: 0}
            </style>
        </head>
        <body class="harBody" style="color:#000">
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

                      <div class="btn-group" id="render-form">
                          <input class="form-control col-lg-8" type="text" placeholder="Paste an URL" type="text" name="url" value="%(url)s">
                          %(lua_editor)s
                      </div>
                      <button class="btn btn-success" type="submit">Render!</button>
                    </form>

                    <ul class="nav navbar-nav navbar-right">
                      <li><a id="status">Initializing...</a></li>
                    </ul>

                  </div>
                </div>

                <div class="pagePreview" style="display:none">
                    <img class='center-block'>
                    <br>
                    <h3>Network Activity</h3>
                </div>

                <div id="content" version="Splash %(version)s"></div>

                <div class="pagePreview" style="display:none">
                    <h3>HTML</h3>
                    <textarea style="width: 100%%;" rows=15 id="renderedHTML"></textarea>
                    <br>
                </div>

                <div id="errorMessage" style="display:none">
                    <h4>HTTP Error <span id='errorStatus'></span></h4>
                    <h4>Type: <span id='errorType'></span></h4>
                    <p id='errorDescription' class="errorMessage"></p>
                    <p id='errorMessageText' class="errorMessage"></p>
                    <pre id='errorData'></pre>
                </div>
            </div>

            <script data-main="_harviewer/scripts/harViewer" src="_harviewer/scripts/require.js"></script>

            <script>
            var params = %(params)s;

            /* Create editor */
            var editor = null;
            var textarea = document.getElementById('lua-code-editor');
            if (textarea) {
                textarea.value = params["lua_source"] || "";

                $('#render-form').on("shown.bs.dropdown", function(e){
                    if (editor === null) {
                        editor = CodeMirror.fromTextArea(textarea, %(cm_options)s);
                        editor.setSize(600, 464);
                    }
                });
                $('#lua-code-editor-panel').click(function(e){e.stopPropagation();});
            }

            /* Initialize HAR viewer & send AJAX requests */
            $("#content").bind("onViewerPreInit", function(event){
                // Get application object
                var viewer = event.target.repObject;

                // Remove unnecessary/unsupported tabs
                viewer.removeTab("Home");
                viewer.removeTab("DOM");
                viewer.removeTab("About");
                viewer.removeTab("Schema");
                // Hide the tab bar
                viewer.showTabBar(false);

                // Remove toolbar buttons
                var preview = viewer.getTab("Preview");
                preview.toolbar.removeButton("download");
                preview.toolbar.removeButton("clear");
                preview.toolbar.removeButton("showTimeline");

                var events = [
                    {name: "_onStarted", description: "Page processing is started"},
                    {name: "_onPrepareStart", description: "Rendering begins"},
                    {name: "_onFullViewportSet", description: "Viewport is changed to full"},
                    {name: "_onCustomJsExecuted", description: "Custom JavaScript is executed"},
                    {name: "_onScreenshotPrepared", description: "Screenshot is taken"},
                    {name: "_onPngRendered", description: "Screenshot is encoded"},
                    {name: "_onHtmlRendered", description: "HTML is rendered"},
                    {name: "_onIframesRendered", description: "Iframes info is calculated"},
                ];

                for (var i=0; i<events.length; i++){
                    var obj = events[i];
                    obj["classes"] = "customEventBar " + obj["name"];
                    preview.addPageTiming(obj);
                }

                // preview.toolbar.removeButton("showStats");

                // Make sure stats are visible to the user by default
                preview.showStats(true);

            });

            $("#content").bind("onViewerHARLoaded", function(event){
                $("#status").hide();
            });

            $("#content").bind("onViewerInit", function(event){
                var viewer = event.target.repObject;
                $("#status").text("Rendering, please wait..");

                $.ajax("/%(endpoint)s", {
                    "contentType": "application/json",
                    "dataType": "json",
                    "type": "POST",
                    "data": JSON.stringify(params)
                }).done(function(data){
                    if (!data){
                        $("#status").text("Empty result");
                        return;
                    }

                    var har = data['har'];
                    var png = data['png'];
                    var jpeg = data['jpeg'];
                    var html = data['html'];

                    if (har){
                        viewer.appendPreview(har);
                    }
                    $("#status").text("Building UI..");
                    if (png) {
                        $(".pagePreview img").attr("src", "data:image/png;base64," + png);
                    }
                    if (jpeg) {
                        $(".pagePreview img").attr("src", "data:image/jpeg;base64," + jpeg);
                    }
                    $("#renderedHTML").val(html);
                    $(".pagePreview").show();
                    $("#status").text("Success");
                }).fail(function(xhr, status, err){
                    $("#errorStatus").text(xhr.status + " (" + err + ")");
                    var err = xhr.responseJSON;
                    var resp = JSON.stringify(err, null, 4);
                    $("#errorData").text(resp);
                    $("#errorMessage").show();
                    $("#status").text("Error occured");
                    $("#errorMessageText").text(err['info']['message']);
                    $("#errorDescription").text(err['description']);

                    var errType = err['type'];
                    if (err['info']['type']){
                        errType += ' -> ' + err['info']['type'];
                    }
                    $("#errorType").text(errType);
                });
            });
            </script>
        </body>
        </html>
        """ % dict(
            version=splash.__version__,
            params=json.dumps(params),
            url=url,
            theme=BOOTSTRAP_THEME,
            cm_options=CODEMIRROR_OPTIONS,
            cm_resources=CODEMIRROR_RESOURCES if self.lua_enabled else "",
            endpoint="execute" if self.lua_enabled else "render.json",
            lua_editor=LUA_EDITOR if self.lua_enabled else "",
        )


class Root(Resource):
    HARVIEWER_PATH = os.path.join(
        os.path.dirname(__file__),
        'vendor',
        'harviewer',
        'webapp',
    )

    def __init__(self, pool, ui_enabled, lua_enabled, lua_sandbox_enabled,
                 lua_package_path,
                 lua_sandbox_allowed_modules,
                 max_timeout):
        Resource.__init__(self)
        self.ui_enabled = ui_enabled
        self.lua_enabled = lua_enabled
        self.putChild("render.html", RenderHtmlResource(pool, max_timeout))
        self.putChild("render.png", RenderPngResource(pool, max_timeout))
        self.putChild("render.jpeg", RenderJpegResource(pool, max_timeout))
        self.putChild("render.json", RenderJsonResource(pool, max_timeout))
        self.putChild("render.har", RenderHarResource(pool, max_timeout))

        self.putChild("_debug", DebugResource(pool))
        self.putChild("_gc", ClearCachesResource())

        # backwards compatibility
        self.putChild("debug", DebugResource(pool, warn=True))

        if self.lua_enabled and ExecuteLuaScriptResource is not None:
            self.putChild("execute", ExecuteLuaScriptResource(
                pool=pool,
                is_proxy_request=False,
                sandboxed=lua_sandbox_enabled,
                lua_package_path=lua_package_path,
                lua_sandbox_allowed_modules=lua_sandbox_allowed_modules,
                max_timeout=max_timeout
            ))

        if self.ui_enabled:
            self.putChild("_harviewer", File(self.HARVIEWER_PATH))
            self.putChild(DemoUI.PATH, DemoUI(
                pool=pool,
                lua_enabled=self.lua_enabled,
                max_timeout=max_timeout
            ))

    def getChild(self, name, request):
        if name == "" and self.ui_enabled:
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
        LUA_EDITOR = """
        <div class="input-group col-lg-10">
          <textarea id='lua-code-editor' name='lua_source'>%(lua_script)s</textarea>
        </div>
        """ % dict(
            lua_script = self.get_example_script(),
        )

        result = """<html>
        <head>
            <title>Splash %(version)s</title>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <link href="//maxcdn.bootstrapcdn.com/bootswatch/3.2.0/%(theme)s/bootstrap.min.css" rel="stylesheet">

            <script src="https://code.jquery.com/jquery-1.11.1.min.js"></script>

            %(cm_resources)s

            <script>
               $(document).ready(function(){
                    /* Create editor */
                    var textarea = document.getElementById('lua-code-editor');
                    var editor = CodeMirror.fromTextArea(textarea, %(cm_options)s);
                    editor.setSize(464, 464);
               });
            </script>

        </head>
        <body>
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
                            <li>Turn OFF images or use <a href="https://adblockplus.org">Adblock Plus</a>
                                rules to make rendering faster</li>
                            <li>Execute custom JavaScript in page context</li>
                            <li>Write Lua browsing scripts;</li>
                            <li>Get detailed rendering info in <a href="http://www.softwareishard.com/blog/har-12-spec/">HAR</a> format</li>
                        </ul>

                        <p class="lead">
                            Splash is free & open source.
                            Commercial support is also available by
                            <a href="http://scrapinghub.com/">Scrapinghub</a>.
                        </p>
                        <p>
                            <a class="btn btn-info" href="http://splash.readthedocs.org/">Documentation</a>
                            <a class="btn btn-info" href="https://github.com/scrapinghub/splash">Source code</a>
                        </p>

                    </div>
                    <div class="col-lg-6">
                        <form class="form-horizontal" method="GET" action="/info">
                          <input type="hidden" name="wait" value="0.5">
                          <input type="hidden" name="images" value="1">
                          <input type="hidden" name="expand" value="1"> <!-- for HAR viewer -->

                          <fieldset>
                            <div class="">
                              <div class="input-group col-lg-10">
                                <input class="form-control" type="text" placeholder="Paste an URL" value="http://google.com" name="url">
                                <span class="input-group-btn">
                                  <button class="btn btn-success" type="submit">Render me!</button>
                                </span>
                              </div>
                              %(lua_editor)s
                            </div>
                          </fieldset>
                        </form>
                    </div>
                </div>
            </div>
        </body>
        </html>""" % dict(
            version=splash.__version__,
            theme=BOOTSTRAP_THEME,
            cm_options=CODEMIRROR_OPTIONS,
            cm_resources=CODEMIRROR_RESOURCES,
            lua_editor=LUA_EDITOR if self.lua_enabled else "",
        )
        return result.encode('utf8')
