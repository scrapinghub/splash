import os, time, resource, json
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor, defer
from twisted.python import log
try:
    from plop.collector import Collector
except ImportError:
    Collector = None

from splash.qtrender import HtmlRender, PngRender, JsonRender, RenderError
from splash.utils import getarg, BadRequest, get_num_fds, get_leaks
from splash import sentry
from splash import defaults


class RenderBase(Resource):

    isLeaf = True
    content_type = "text/html; charset=utf-8"

    def __init__(self, pool, is_proxy_request=False):
        Resource.__init__(self)
        self.pool = pool
        self.js_profiles_path = self.pool.js_profiles_path
        self.is_proxy_request = is_proxy_request

    def render_GET(self, request):
        #log.msg("%s %s %s %s" % (id(request), request.method, request.path, request.args))
        pool_d = self._getRender(request)
        timeout = getarg(request, "timeout", defaults.TIMEOUT, type=float, range=(0, defaults.MAX_TIMEOUT))
        wait_time = getarg(request, "wait", defaults.WAIT_TIME, type=float, range=(0, defaults.MAX_WAIT_TIME))

        timer = reactor.callLater(timeout+wait_time, pool_d.cancel)
        pool_d.addCallback(self._cancelTimer, timer)
        pool_d.addCallback(self._writeOutput, request)
        pool_d.addErrback(self._timeoutError, request)
        pool_d.addErrback(self._renderError, request)
        pool_d.addErrback(self._internalError, request)
        pool_d.addBoth(self._finishRequest, request)
        request.starttime = time.time()
        return NOT_DONE_YET

    def render_POST(self, request):
        # this check is required only in request not coming from the splash proxy service.
        if not self.is_proxy_request:
            content_type = request.getHeader('content-type')
            if content_type != 'application/javascript':
                request.setResponseCode(415)
                request.write("Request content-type not supported\n")
                return

        return self.render_GET(request)

    def render(self, request):
        try:
            return Resource.render(self, request)
        except BadRequest as e:
            request.setResponseCode(400)
            return str(e) + "\n"

    def _cancelTimer(self, _, timer):
        #log.msg("_cancelTimer")
        timer.cancel()
        return _

    def _writeOutput(self, html, request):
        #log.msg("_writeOutput: %s" % id(request))
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

    def _finishRequest(self, _, request):
        if not request._disconnected:
            request.finish()
        #log.msg("_finishRequest: %s" % id(request))

    def _getRender(self, request):
        raise NotImplementedError()


def _check_viewport(viewport, wait, max_width, max_heigth, max_area):
    if viewport is None:
        return

    if viewport == 'full':
        if wait == 0:
            raise BadRequest("Pass non-zero 'wait' to render full webpage")
        return

    try:
        w, h = map(int, viewport.split('x'))
        if (0 < w <= max_width) and (0 < h <= max_heigth) and (w*h < max_area):
            return
        raise BadRequest("Viewport is out of range (%dx%d, area=%d)" % (max_width, max_heigth, max_area))
    except (ValueError):
        raise BadRequest("Invalid viewport format: %s" % viewport)


def _get_javascript_params(request, js_profiles_path):
    js_profile = _check_js_profile(request, js_profiles_path, getarg(request, 'js', None))
    js_source = getarg(request, 'js_source', None)
    if js_source is not None:
        return js_source, js_profile

    if request.method == 'POST':
        return request.content.getvalue(), js_profile
    else:
        return None, js_profile


def _check_js_profile(request, js_profiles_path, js_profile):
    if js_profile:
        if js_profiles_path is None:
            raise BadRequest('Javascript profiles are not enabled')
        profile_dir = os.path.join(js_profiles_path, js_profile)
        if not profile_dir.startswith(js_profiles_path + os.path.sep):
            # security check fails
            raise BadRequest('Javascript profile does not exist')
        if not os.path.isdir(profile_dir):
            raise BadRequest('Javascript profile does not exist')
        return profile_dir


def _get_png_params(request, js_profiles_path):
    url, baseurl, wait_time, viewport, js_source, js_profile = _get_common_params(request, js_profiles_path)
    width = getarg(request, "width", None, type=int, range=(1, defaults.MAX_WIDTH))
    height = getarg(request, "height", None, type=int, range=(1, defaults.MAX_HEIGTH))
    return url, baseurl, wait_time, viewport, js_source, js_profile, width, height


def _get_common_params(request, js_profiles_path):
    url = getarg(request, "url")
    baseurl = getarg(request, "baseurl", None)
    wait_time = getarg(request, "wait", defaults.WAIT_TIME, type=float, range=(0, defaults.MAX_WAIT_TIME))
    js_source, js_profile = _get_javascript_params(request, js_profiles_path)

    viewport = getarg(request, "viewport", defaults.VIEWPORT)
    _check_viewport(viewport, wait_time, defaults.VIEWPORT_MAX_WIDTH,
                    defaults.VIEWPORT_MAX_HEIGTH, defaults.VIEWPORT_MAX_AREA)

    return url, baseurl, wait_time, viewport, js_source, js_profile


class RenderHtml(RenderBase):

    content_type = "text/html; charset=utf-8"

    def _getRender(self, request):
        return self.pool.render(HtmlRender, request, *_get_common_params(request, self.js_profiles_path))


class RenderPng(RenderBase):

    content_type = "image/png"

    def _getRender(self, request):
        return self.pool.render(PngRender, request, *_get_png_params(request, self.js_profiles_path))


class RenderJson(RenderBase):

    content_type = "application/json"

    def _getRender(self, request):
        url, baseurl, wait_time, viewport, js_source, js_profile, width, height = _get_png_params(request, self.js_profiles_path)

        html = getarg(request, "html", defaults.DO_HTML, type=int, range=(0, 1))
        iframes = getarg(request, "iframes", defaults.DO_IFRAMES, type=int, range=(0, 1))
        png = getarg(request, "png", defaults.DO_PNG, type=int, range=(0, 1))
        script = getarg(request, "script", defaults.SHOW_SCRIPT, type=int, range=(0, 1))
        console = getarg(request, "console", defaults.SHOW_CONSOLE, type=int, range=(0, 1))

        return self.pool.render(JsonRender, request,
                                url, baseurl, wait_time, viewport, js_source, js_profile,
                                html, iframes, png, script, console,
                                width, height)


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


class Profile(Resource):
    isLeaf = True

    def __init__(self, auth_token):
        Resource.__init__(self)
        self.auth_token = auth_token

    def render_GET(self, request):
        timeout = getarg(request, "timeout", default=30, type=int, range=(0, 120))
        auth_token = getarg(request, "auth", default=None)
        if auth_token != self.auth_token:
            request.setResponseCode(403)
            return 'auth token is incorrect'

        collector = Collector()
        collector.start()
        d = reactor.callLater(timeout, self.finishProfile, request, collector)

        def onFailure(failure):
            d.cancel()
            collector.stop()

        request.notifyFinish().addErrback(onFailure)
        return NOT_DONE_YET

    def finishProfile(self, request, collector):
        collector.stop()
        result = self.stats_to_json(collector.stack_counts)
        request.setHeader("content-type", "application/json")
        request.write(result)
        request.finish()

    @classmethod
    def stats_to_json(cls, stack_counts):
        values = sorted(stack_counts.items(), key=lambda item: item[1], reverse=True)
        return json.dumps([
            (["%s:%s:%s" % frame for frame in frames], count)
            for frames, count in values
        ])


class Root(Resource):

    def __init__(self, pool, profiling_auth_token=None):
        Resource.__init__(self)
        self.putChild("render.html", RenderHtml(pool))
        self.putChild("render.png", RenderPng(pool))
        self.putChild("render.json", RenderJson(pool))
        self.putChild("debug", Debug(pool))

        if Collector is None:
            log.msg("/profile endoint is disabled; "
                    "install 'plop' python package to enable profiling support")
        elif not profiling_auth_token:
            log.msg("/profile endpoint is disabled; start splash with non-empty "
                    "--profiling-auth-token option to enable profiling support")
        else:
            log.msg("/profile endpoint is enabled")
            self.putChild("profile", Profile(profiling_auth_token))

    def getChild(self, name, request):
        if name == "":
            return self
        return Resource.getChild(self, name, request)

    def render_GET(self, request):
        return ""
