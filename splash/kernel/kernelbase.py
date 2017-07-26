# -*- coding: utf-8 -*-
"""
Refactored from IPython.kernel.zmq.kernelbase.Kernel with async execution
support. See https://github.com/ipython/ipython/pull/7713.
"""
import functools
import time
import sys

from ipython_genutils import py3compat
from ipykernel.jsonutil import json_clean
from ipykernel.kernelbase import Kernel as _Kernel


if hasattr(_Kernel, "send_execute_reply"):
    # patched IPython version
    raise Exception("Incompatible IPython version")
else:
    # non-patched IPython version
    class Kernel(_Kernel):

        async_msg_types = {'execute_request'}

        def __init__(self, **kwargs):
            super(Kernel, self).__init__(**kwargs)

            # XXX: A HUGE HACK
            # In existing ipykernel implementation
            # `dispatch_control` and `dispatch_shell` methods
            # publish 'idle' state at the end. This is not correct
            # in presence of async handlers. Overriding `dispatch_control` and
            # `dispatch_shell` is problematic because it is a big copy-paste.
            # So all handlers are overridden to set "idle" at the end,
            # and `_publish_status` skips "idle" by default.
            this = self
            def send_idle(meth):
                @functools.wraps(meth)
                def wrapper(self, *args, **kwargs):
                    res = meth(self, *args, **kwargs)
                    this._publish_idle()
                    return res
                return wrapper

            for msg_type in self.shell_handlers:
                if msg_type in self.async_msg_types:
                    continue
                self.shell_handlers[msg_type] = send_idle(self.shell_handlers[msg_type])

            for msg_type in self.control_handlers:
                if msg_type in self.async_msg_types:
                    continue
                self.control_handlers[msg_type] = send_idle(self.control_handlers[msg_type])

        def _publish_status(self, status, parent=None, force=False):
            if status != 'idle' or force:
                super(Kernel, self)._publish_status(status, parent)

        def _publish_idle(self, parent=None):
            self._publish_status("idle", parent, force=True)

        def execute_request(self, stream, ident, parent):
            """handle an execute_request"""
            # This function is mostly a copy-pasted version from ipykernel,
            # but it is split into several functions in order to allow
            # overriding them in subclasses.

            # ============ BEGIN COPY-PASTE =============
            try:
                content = parent[u'content']
                code = py3compat.cast_unicode_py2(content[u'code'])
                silent = content[u'silent']
                store_history = content.get(u'store_history', not silent)
                user_expressions = content.get('user_expressions', {})
                allow_stdin = content.get('allow_stdin', False)
            except:
                self.log.error("Got bad msg: ")
                self.log.error("%s", parent)
                return

            metadata = self.init_metadata(parent)

            # Re-broadcast our input for the benefit of listening clients, and
            # start computing output
            if not silent:
                self.execution_count += 1
                self._publish_execute_input(code, parent, self.execution_count)

            reply_content = self.do_execute(code, silent, store_history,
                                            user_expressions, allow_stdin)

            # ============ END COPY-PASTE =============
            self.send_execute_reply(stream, ident, parent, metadata, reply_content)

        def send_execute_reply(self, stream, ident, parent, metadata, reply_content):
            """ Send a reply to execute_request """

            # This function is mostly copy-pasted from the last part of
            # ipykernel's execute_reply method.
            # It is extracted to allow overriding in subclasses.
            # Splash kernel overrides it for async replies: instead
            # of returning result immediately it only calls the original
            # implementation when async reply is received.

            content = parent[u'content']
            stop_on_error = content.get('stop_on_error', True)
            silent = content[u'silent']

            # ============ BEGIN COPY-PASTE ============

            # Flush output before sending the reply.
            sys.stdout.flush()
            sys.stderr.flush()
            # FIXME: on rare occasions, the flush doesn't seem to make it to the
            # clients... This seems to mitigate the problem, but we definitely need
            # to better understand what's going on.
            if self._execute_sleep:
                time.sleep(self._execute_sleep)

            # Send the reply
            reply_content = json_clean(reply_content)
            metadata = self.finish_metadata(parent, metadata, reply_content)

            reply_msg = self.session.send(stream, u'execute_reply',
                                          reply_content, parent, metadata=metadata,
                                          ident=ident)
            self.log.debug("%s", reply_msg)

            if not silent and reply_msg['content']['status'] == u'error' and stop_on_error:
                self._abort_queues()

            # ============== END COPY-PASTE ==============

            # fix idle signal handling for async replies
            self._publish_idle()
            if hasattr(stream, 'flush'):
                stream.flush()
