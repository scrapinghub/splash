# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import sys
import time
from IPython.utils import py3compat
from IPython.utils.jsonutil import json_clean

import lupa
from IPython.kernel.zmq.kernelapp import IPKernelApp
from IPython.kernel.zmq.eventloops import loop_qt4
from twisted.internet import defer

import splash
from splash.lua import lua2python, get_version, get_main_sandboxed, get_main
from splash.browser_tab import BrowserTab
from splash.lua_runtime import SplashLuaRuntime
from splash.qtrender_lua import Splash, SplashScriptRunner
from splash.qtutils import init_qt_app
from splash.render_options import RenderOptions
from splash import network_manager
from splash import defaults
from splash.kernel.kernelbase import Kernel
from splash.utils import BinaryCapsule


def init_browser():
    # TODO: support the same command-line options as HTTP server.
    manager = network_manager.create_default()
    proxy_factory = None  # TODO

    data = {}
    data['uid'] = id(data)

    tab = BrowserTab(
        network_manager=manager,
        splash_proxy_factory=proxy_factory,
        verbosity=2,  # TODO
        render_options=RenderOptions(data, defaults.MAX_TIMEOUT),  # TODO: timeout
        visible=True,
    )
    return tab


class DeferredSplashRunner(object):

    def __init__(self, tab, lua, sandboxed):
        self.tab = tab
        self.lua = lua
        self.sandboxed = sandboxed

    def run(self, main_coro, render_options=None):
        """
        Run main_coro Lua coroutine, passing it a Splash
        instance as an argument. Return a Deferred.
        """
        d = defer.Deferred()

        def return_result(result):
            d.callback(result)

        def return_error(err):
            d.errback(err)

        runner = SplashScriptRunner(
            lua=self.lua,
            log=self.tab.logger.log,
            sandboxed=self.sandboxed,
            return_result=return_result,
            return_error=return_error,
        )
        splash = Splash(
            lua=self.lua,
            tab=self.tab,
            return_func=runner.dispatch,
            render_options=render_options,
        )
        self.lua.add_allowed_object(splash, splash.attr_whitelist)

        runner.start(main_coro, splash)
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
        'codemirror_mode': 'Lua',
        'file_extension': '.lua',
        'pygments_lexer': 'lua'
    }
    banner = "Splash kernel - write browser automation scripts interactively"
    help_links = [
        {
            'text': "Splash Help",
            'url': 'http://splash.readthedocs.org/en/latest/scripting-ref.html'
        },
    ]

    sandboxed = False

    def __init__(self, **kwargs):
        super(SplashKernel, self).__init__(**kwargs)
        self.lua = SplashLuaRuntime(self.sandboxed, "", ())
        self.lua_repr = self.lua.eval("tostring")
        self.tab = init_browser()
        self.runner = DeferredSplashRunner(self.tab, self.lua, self.sandboxed)
        # try:
        #     sys.stdout.write = self._print
        # except:
        #     pass # Can't change stdout

    def _print(self, message):
        stream_content = {'name': 'stdout', 'text': message, 'metadata': dict()}
        self.log.debug('Write: %s' % message)
        self.send_response(self.iopub_socket, 'stream', stream_content)

    def get_main(self, lua_source):
        if self.sandboxed:
            main, env = get_main_sandboxed(self.lua, lua_source)
        else:
            main, env = get_main(self.lua, lua_source)
        return self.lua.create_coroutine(main)

    def _publish_execute_result(self, parent, data, metadata, execution_count):
        msg = {
            u'data': data,
            u'metadata': metadata,
            u'execution_count': execution_count
        }
        self.session.send(self.iopub_socket, u'execute_result', msg,
                          parent=parent, ident=self._topic('execute_result')
        )

    def send_execute_reply(self, stream, ident, parent, md, reply_content):
        def done(result):
            reply, result, ct = result
            # self._print(str(reply))
            # self._print(repr(result)+"\n")
            # self._print(ct)
            super(SplashKernel, self).send_execute_reply(stream, ident, parent, md, reply)

            if result:
                data = {
                    'text/plain': repr(result),
                }
                # if isinstance(result, BinaryCapsule):
                #     data["image/png"] = result.data
                self._publish_execute_result(parent, data, {}, self.execution_count)

        assert isinstance(reply_content, defer.Deferred)
        reply_content.addCallback(done)

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):

        def success(result):
            result, content_type = result
            reply = {
                'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
            }
            return reply, result, content_type or 'text/plain'

        def error(failure):
            text = str(failure)
            reply = {
                'status': 'error',
                'execution_count': self.execution_count,
                'ename': '',
                'evalue': text,
                'traceback': []
            }
            return reply, failure, 'text/plain'

        try:
            try:
                lua_source = """
                function main(splash)
                    return %s
                end
                """ % code
                main_coro = self.get_main(lua_source)
            except lupa.LuaSyntaxError:
                lua_source = """
                function main(splash)
                    %s
                end
                """ % code
                main_coro = self.get_main(lua_source)
        except Exception:
            d = defer.Deferred()
            d.addCallbacks(success, error)
            d.errback()
            return d

        d = self.runner.run(main_coro)
        d.addCallbacks(success, error)
        return d


def start():
    # FIXME: logs go to nowhere
    init_qt_app(verbose=False)
    kernel = IPKernelApp.instance(kernel_class=SplashKernel)
    kernel.initialize()
    kernel.kernel.eventloop = loop_qt4
    kernel.start()
