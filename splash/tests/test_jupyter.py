# -*- coding: utf-8 -*-
from __future__ import absolute_import

import pytest
jupyter_kernel_test = pytest.importorskip("jupyter_kernel_test")
lupa = pytest.importorskip("lupa")


class SplashKernelTest(jupyter_kernel_test.KernelTests):

    @classmethod
    def setUpClass(cls):
        # XXX: this installs kernel spec to global user environment,
        # not to a virtualenv.
        from splash.kernel import kernel
        kernel.install()

        super(SplashKernelTest, cls).setUpClass()

    # The name identifying an installed kernel to run the tests against
    kernel_name = "splash"

    # language_info.name in a kernel_info_reply should match this
    language_name = "Splash"

    # Optional --------------------------------------
    # Code in the kernel's language to write "hello, world" to stdout
    # code_hello_world = "print 'hello, world'"

    # Tab completions: in each dictionary, text is the input, which it will
    # try to complete from the end of. matches is the collection of results
    # it should expect.
    completion_samples = [
        {
            'text': 'spl',
            'matches': {'splash'},
        },
        {
            'text': 'splash:eva',
            'matches': {'evaljs'},
        },
        {
            'text': 'splash.ar',
            'matches': {'args'},
        },
    ]

    # Code completeness: samples grouped by expected result
    # complete_code_samples = ['x=2']
    # incomplete_code_samples = ['function foo(', '"""in a string']
    # invalid_code_samples = ['x=2a']

    # # Pager: code that should display something (anything) in the pager
    # code_page_something = "help('foldl')"
