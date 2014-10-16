"""
This module contains Splash twisted.web Resources (HTTP API endpoints
exposed to the user).
"""
from __future__ import absolute_import
import os
import time
import resource
import json

from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.internet import reactor, defer
from twisted.python import log

import splash
from splash.qtrender import (
    HtmlRender, PngRender, JsonRender, HarRender, RenderError
)
from splash.utils import get_num_fds, get_leaks
from splash import sentry
from splash.render_options import RenderOptions, BadOption


class _ValidatingResource(Resource):
    def render(self, request):
        try:
            return Resource.render(self, request)
        except BadOption as e:
            request.setResponseCode(400)
            return str(e) + "\n"


class RenderBase(_ValidatingResource):

    isLeaf = True
    content_type = "text/html; charset=utf-8"

    def __init__(self, pool, is_proxy_request=False):
        Resource.__init__(self)
        self.pool = pool
        self.js_profiles_path = self.pool.js_profiles_path
        self.is_proxy_request = is_proxy_request

    def render_GET(self, request):
        #log.msg("%s %s %s %s" % (id(request), request.method, request.path, request.args))

        # _check_filters(self.pool, request)
        render_options = RenderOptions.fromrequest(request)
        render_options.get_filters(self.pool)  # check filters earlier

        pool_d = self._getRender(request, render_options)

        timeout = render_options.get_timeout()
        wait_time = render_options.get_wait()

        timer = reactor.callLater(timeout+wait_time, pool_d.cancel)
        pool_d.addCallback(self._cancelTimer, timer)
        pool_d.addCallback(self._writeOutput, request)
        pool_d.addErrback(self._timeoutError, request)
        pool_d.addErrback(self._renderError, request)
        pool_d.addErrback(self._badRequest, request)
        pool_d.addErrback(self._internalError, request)
        pool_d.addBoth(self._finishRequest, request)
        request.starttime = time.time()
        return NOT_DONE_YET

    def render_POST(self, request):
        if self.is_proxy_request:
            # If request comes from splash proxy service don't handle
            # special content-types.
            # TODO: pass http method to WebpageRender explicitly.
            return self.render_GET(request)

        content_type = request.getHeader('content-type')
        if not any(ct in content_type for ct in ['application/javascript', 'application/json']):
            request.setResponseCode(415)
            request.write("Request content-type not supported\n")
            return

        return self.render_GET(request)

    def _cancelTimer(self, _, timer):
        #log.msg("_cancelTimer")
        timer.cancel()
        return _

    def _writeOutput(self, html, request):
        # log.msg("_writeOutput: %s" % id(request))
        stats = {
            "path": request.path,
            "args": request.args,
            "rendertime": time.time() - request.starttime,
            "maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "load": os.getloadavg(),
            "fds": get_num_fds(),
            "active": len(self.pool.active),
            "qsize": len(self.pool.queue.pending),
            "_id": id(request),
        }
        log.msg(json.dumps(stats), system="stats")
        request.setHeader("content-type", self.content_type)
        request.write(html)

    def _timeoutError(self, failure, request):
        failure.trap(defer.CancelledError)
        request.setResponseCode(504)
        request.write("Timeout exceeded rendering page\n")
        #log.msg("_timeoutError: %s" % id(request))

    def _renderError(self, failure, request):
        failure.trap(RenderError)
        request.setResponseCode(502)
        request.write("Error rendering page\n")
        #log.msg("_renderError: %s" % id(request))

    def _internalError(self, failure, request):
        request.setResponseCode(500)
        request.write(failure.getErrorMessage())
        log.err()
        sentry.capture(failure)

    def _badRequest(self, failure, request):
        failure.trap(BadOption)
        request.setResponseCode(400)
        request.write(str(failure.value) + "\n")

    def _finishRequest(self, _, request):
        if not request._disconnected:
            request.finish()
        #log.msg("_finishRequest: %s" % id(request))

    def _getRender(self, request, options):
        raise NotImplementedError()


class RenderHtml(RenderBase):

    content_type = "text/html; charset=utf-8"

    def _getRender(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        return self.pool.render(HtmlRender, options, **params)


class RenderPng(RenderBase):

    content_type = "image/png"

    def _getRender(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        params.update(options.get_png_params())
        return self.pool.render(PngRender, options, **params)


class RenderJson(RenderBase):

    content_type = "application/json"

    def _getRender(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        params.update(options.get_png_params())
        params.update(options.get_include_params())
        return self.pool.render(JsonRender, options, **params)


class RenderHar(RenderBase):

    content_type = "application/json"

    def _getRender(self, request, options):
        params = options.get_common_params(self.js_profiles_path)
        return self.pool.render(HarRender, options, **params)


class Debug(Resource):

    isLeaf = True

    def __init__(self, pool):
        Resource.__init__(self)
        self.pool = pool

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps({
            "leaks": get_leaks(),
            "active": [x.url for x in self.pool.active],
            "qsize": len(self.pool.queue.pending),
            "maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "fds": get_num_fds(),
        })


class HarViewer(_ValidatingResource):
    isLeaf = True
    content_type = "text/html; charset=utf-8"

    PATH = 'info'

    def __init__(self, pool):
        Resource.__init__(self)
        self.pool = pool

    def _validate_params(self, request):
        options = RenderOptions.fromrequest(request)
        options.get_filters(self.pool)  # check
        params = options.get_common_params(self.pool.js_profiles_path)
        params.update({
            'timeout': options.get_timeout(),
            'har': 1,
            'png': 1,
            'html': 1,
        })
        return params


    def render_GET(self, request):
        params = self._validate_params(request)
        url = params['url']
        if not url.lower().startswith('http'):
            url = 'http://' + url

        params = {k:v for k,v in params.items() if v is not None}

        request.addCookie('phaseInterval', 120000)  # disable "phases" HAR Viewer feature

        return """<html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>Splash %(version)s | %(url)s</title>
            <link rel="stylesheet" href="_harviewer/css/harViewer.css" type="text/css"/>
            <link href="//maxcdn.bootstrapcdn.com/bootswatch/3.2.0/simplex/bootstrap.min.css" rel="stylesheet">
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
                      <input class="form-control col-lg-8" type="text" placeholder="Paste an URL" type="text" name="url" value="%(url)s">
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
            </div>

            <script src="_harviewer/scripts/jquery.js"></script>
            <script data-main="_harviewer/scripts/harViewer" src="_harviewer/scripts/require.js"></script>

            <script>
            var params = %(params)s;
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

                $.ajax("/render.json", {
                    "contentType": "application/json",
                    "dataType": "json",
                    "type": "POST",
                    "data": JSON.stringify(params)
                }).done(function(data){
                    var har = data['har'];
                    var png = data['png'];
                    var html = data['html'];

                    viewer.appendPreview(har);
                    $("#status").text("Building UI..");

                    $(".pagePreview img").attr("src", "data:image/png;base64,"+png);

                    $("#renderedHTML").val(html);
                    $(".pagePreview").show();
                }).fail(function(data){
                    $("#status").text("Error occured");
                });
            });
            </script>
        </body>
        </html>
        """ % dict(version=splash.__version__, params=json.dumps(params), url=url)


class Root(Resource):
    HARVIEWER_PATH = os.path.join(
        os.path.dirname(__file__),
        'vendor',
        'harviewer',
        'webapp',
    )

    def __init__(self, pool, ui_enabled):
        Resource.__init__(self)
        self.ui_enabled = ui_enabled
        self.putChild("render.html", RenderHtml(pool))
        self.putChild("render.png", RenderPng(pool))
        self.putChild("render.json", RenderJson(pool))
        self.putChild("render.har", RenderHar(pool))
        self.putChild("debug", Debug(pool))

        if self.ui_enabled:
            self.putChild("_harviewer", File(self.HARVIEWER_PATH))
            self.putChild(HarViewer.PATH, HarViewer(pool))

    def getChild(self, name, request):
        if name == "" and self.ui_enabled:
            return self
        return Resource.getChild(self, name, request)

    def render_GET(self, request):
        return """<html>
        <head>
            <title>Splash %(version)s</title>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <link href="//maxcdn.bootstrapcdn.com/bootswatch/3.2.0/simplex/bootstrap.min.css" rel="stylesheet">
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
                            <li>Transparently plug into existing software using Proxy interface</li>
                            <li>Get detailed rendering info in <a href="http://www.softwareishard.com/blog/har-12-spec/">HAR</a> format</li>
                        </ul>

                        <p class="lead">
                            Splash is free & open source.
                            Commercial support is also available by
                            <a href="http://scrapinghub.com/">Scrapinghub</a>.
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
                                <input class="form-control" type="text" placeholder="Paste an URL" value="http://google.com" type="text" name="url">
                                <span class="input-group-btn">
                                  <button class="btn btn-success" type="submit">Render me!</button>
                                </span>
                              </div>
                            </div>
                          </fieldset>
                        </form>
                        <p>
                            <a class="btn btn-default" href="http://splash.readthedocs.org/">Documentation</a>
                            <a class="btn btn-default" href="https://github.com/scrapinghub/splash">Source code</a>
                        </p>

                    </div>
                </div>
            </div>
        </body>
        </html>""" % dict(version=splash.__version__)
