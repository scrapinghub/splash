# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import six
import sys

import lupa
from ipykernel.kernelapp import IPKernelApp
from ipykernel.eventloops import loop_qt5
from jupyter_client.kernelspec import install_kernel_spec
from twisted.internet import defer

import splash
from splash.lua import get_version, get_main_sandboxed, get_main
from splash.browser_tab import BrowserTab
from splash.lua_runtime import SplashLuaRuntime
from splash.qtrender_lua import (
    Splash, MainCoroutineRunner, StoredExceptions, Extras
)
from splash.qtutils import init_qt_app
from splash.render_options import RenderOptions
from splash import defaults
from splash.kernel.kernelbase import Kernel
from splash.utils import BinaryCapsule
from splash.kernel.completer import Completer
from splash.kernel.inspections import Inspector
from splash.kernel.errors import error_repr
import splash.server as server


def install(user=True):
    """ Install IPython kernel specification """
    name = 'splash-py2' if six.PY2 else 'splash-py3'
    folder = os.path.join(os.path.dirname(__file__), 'kernels', name)
    install_kernel_spec(folder, kernel_name="splash", user=user, replace=True)


def init_browser(network_manager_factory):
    # TODO: support the same command-line options as HTTP server.

    # from splash.server import start_logging
    # class opts(object):
    #    logfile = "./kernel.log"
    # start_logging(opts)

    proxy_factory = None  # TODO

    data = {}
    data['uid'] = id(data)

    tab = BrowserTab(
        network_manager=network_manager_factory(),
        splash_proxy_factory=proxy_factory,
        verbosity=2,  # TODO
        render_options=RenderOptions(data, defaults.MAX_TIMEOUT),  # TODO: timeout
        visible=True,
    )
    return tab


class DeferredSplashRunner(object):

    def __init__(self, lua, splash, sandboxed, log=None, render_options=None):
        self.lua = lua
        self.splash = splash
        self.sandboxed = sandboxed

        if log is None:
            self.log = self.splash.tab.logger.log
        else:
            self.log = log

        self.runner = MainCoroutineRunner(
            lua=self.lua,
            log=self.log,
            splash=splash,
            sandboxed=self.sandboxed,
        )

    def run(self, main_coro):
        """
        Run main_coro Lua coroutine, passing it a Splash
        instance as an argument. Return a Deferred.
        """
        d = defer.Deferred()

        def return_result(result):
            d.callback(result)

        def return_error(err):
            d.errback(err)

        self.runner.start(
            main_coro=main_coro,
            return_result=return_result,
            return_error=return_error,
        )
        return d


class SplashKernel(Kernel):
    implementation = 'Splash'
    implementation_version = splash.__version__
    language = 'Lua'
    language_version = get_version()
    language_info = {
        'name': 'Splash',
        'mimetype': 'application/x-lua',
        'display_name': 'Splash',
        'language': 'lua',
        'codemirror_mode': {
            "name": "text/x-lua",
        },
        'file_extension': '.lua',
        'pygments_lexer': 'lua',
        'version': get_version(),
    }
    banner = "Splash kernel - write browser automation scripts interactively"
    help_links = [
        {
            'text': "Splash Tutorial",
            'url': 'http://splash.readthedocs.org/en/latest/scripting-tutorial.html'
        },
        {
            'text': "Splash Reference",
            'url': 'http://splash.readthedocs.org/en/latest/scripting-ref.html'
        },
        {
            'text': "Programming in Lua",
            'url': 'http://www.lua.org/pil/contents.html'
        },
        {
            'text': "Lua 5.2 Manual",
            'url': 'http://www.lua.org/manual/5.2/'
        },
    ]

    sandboxed = False

    def __init__(self, **kwargs):
        super(SplashKernel, self).__init__(**kwargs)
        self.tab = init_browser(SplashKernel.network_manager_factory)

        self.lua = SplashLuaRuntime(self.sandboxed, lua_package_path="",
                                    lua_sandbox_allowed_modules=())
        self.exceptions = StoredExceptions()
        self.splash = Splash(
            lua=self.lua,
            exceptions=self.exceptions,
            tab=self.tab
        )
        self.lua.add_to_globals("splash", self.splash.get_wrapped())
        self.extras = Extras(self.lua, self.exceptions)
        self.extras.inject_to_globals()

        self.runner = DeferredSplashRunner(self.lua, self.splash, self.sandboxed) #, self.log_msg)
        self.completer = Completer(self.lua)
        self.inspector = Inspector(self.lua)
        #
        # try:
        #     sys.stdout.write = self._print
        #     sys.stderr.write = self._print
        # except:
        #     pass # Can't change stdout

    def send_execute_reply(self, stream, ident, parent, md, reply_content):
        def done(result):
            reply, result, ct = result
            if result:
                data = {
                    'text/plain': result if isinstance(result, six.text_type) else str(result),
                }
                if isinstance(result, BinaryCapsule):
                    if result.content_type in {'image/png', 'image/jpeg'}:
                        data[result.content_type] = result.as_b64()
                self._publish_execute_result(parent, data, {}, self.execution_count)

            super(SplashKernel, self).send_execute_reply(stream, ident, parent, md, reply)

        assert isinstance(reply_content, defer.Deferred)
        reply_content.addCallback(done)

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        def success(res):
            result, content_type, headers, status_code = res
            reply = {
                'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
            }
            return reply, result, content_type or 'text/plain'

        def error(failure):
            text = "<unknown error>"
            try:
                failure.raiseException()
            except Exception as e:
                text = error_repr(e)
            reply = {
                'status': 'error',
                'execution_count': self.execution_count,
                'ename': '',
                'evalue': text,
                'traceback': []
            }
            return reply, text, 'text/plain'

        try:
            try:
                # XXX: this ugly formatting is important for exception
                # line numbers to be displayed properly!
                lua_source = 'local repr = require("repr"); function main(splash) return repr(%s) end' % code
                main_coro = self._get_main(lua_source)
            except lupa.LuaSyntaxError:
                try:
                    lines = code.splitlines(False)
                    lua_source = '''local repr = require("repr"); function main(splash) %s
                        return repr(%s)
                    end
                    ''' % ("\n".join(lines[:-1]), lines[-1])
                    main_coro = self._get_main(lua_source)
                except lupa.LuaSyntaxError:
                    lua_source = "function main(splash) %s end" % code
                    main_coro = self._get_main(lua_source)

        except (lupa.LuaSyntaxError, lupa.LuaError) as e:
            d = defer.Deferred()
            d.addCallbacks(success, error)
            d.errback(e)
            return d
        except Exception:
            d = defer.Deferred()
            d.addCallbacks(success, error)
            d.errback()
            return d

        d = self.runner.run(main_coro)
        d.addCallbacks(success, error)
        return d

    def do_complete(self, code, cursor_pos):
        return self.completer.complete(code, cursor_pos)

    def do_inspect(self, code, cursor_pos, detail_level=0):
        return self.inspector.help(code, cursor_pos, detail_level)

    def _publish_execute_result(self, parent, data, metadata, execution_count):
        msg = {
            u'data': data,
            u'metadata': metadata,
            u'execution_count': execution_count
        }
        self.session.send(self.iopub_socket, u'execute_result', msg,
                          parent=parent, ident=self._topic('execute_result')
        )

    def log_msg(self, text, min_level=2):
        self._print(text + "\n")

    def _print(self, message):
        stream_content = {'name': 'stdout', 'text': message, 'metadata': dict()}
        self.log.debug('Write: %s' % message)
        self.send_response(self.iopub_socket, 'stream', stream_content)

    def _get_main(self, lua_source):
        if self.sandboxed:
            main, env = get_main_sandboxed(self.lua, lua_source)
        else:
            main, env = get_main(self.lua, lua_source)
        return self.lua.create_coroutine(main)


def server_factory(network_manager_factory, verbosity, **kwargs):
    init_qt_app(verbose=verbosity >= 5)
    SplashKernel.network_manager_factory = network_manager_factory
    kernel = IPKernelApp.instance(kernel_class=SplashKernel)
    kernel.initialize()
    kernel.kernel.eventloop = loop_qt5
    kernel.start()


def start():
    splash_args = os.environ.get('SPLASH_ARGS', '').split()
    server.main(jupyter=True, argv=splash_args, server_factory=server_factory)
