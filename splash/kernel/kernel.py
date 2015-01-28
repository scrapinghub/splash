# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import sys
from IPython.kernel.zmq.session import default_secure

import lupa
from IPython.kernel.zmq.kernelbase import Kernel
from IPython.kernel.zmq.kernelapp import IPKernelApp
from IPython.kernel.zmq.eventloops import loop_qt4
from IPython.lib.guisupport import get_app_qt4

from splash.lua import get_new_runtime, lua2python, get_version
from splash.browser_tab import BrowserTab
from splash.qtutils import init_qt_app
from splash.render_options import RenderOptions
from splash import network_manager
from splash import defaults


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


class SplashKernel(Kernel):
    implementation = 'Splash'
    implementation_version = '1.0'
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

    def __init__(self, **kwargs):
        super(SplashKernel, self).__init__(**kwargs)
        self.lua = get_new_runtime()
        self.lua_repr = self.lua.eval("tostring")
        self.tab = init_browser()

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        text = ""
        is_error = False

        if code == 'go':
            self.tab.go("http://google.com", lambda *args: None, lambda *args: None)
        else:
            try:
                try:
                    res = self.lua.eval(code)
                    text = self.lua_repr(res)
                except lupa.LuaSyntaxError:
                    self.lua.execute(code)
            except Exception as e:
                text = str(e)
                is_error = True

            if not silent:
                stream_content = {'name': 'stdout', 'text': text}
                self.send_response(self.iopub_socket, 'stream', stream_content)

        if is_error:
            return {
                'status': 'error',
                'execution_count': self.execution_count,
                'ename': '',
                'evalue': text,
                'traceback': []
            }
        else:
            return {
                'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
            }


def start():
    # FIXME: logs go to nowhere
    init_qt_app(verbose=False)
    kernel = IPKernelApp.instance(kernel_class=SplashKernel)
    kernel.initialize()
    kernel.kernel.eventloop = loop_qt4
    kernel.start()
