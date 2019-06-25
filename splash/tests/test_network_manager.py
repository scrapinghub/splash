from itertools import permutations, product

from PyQt5.QtNetwork import QNetworkReply

from splash.network_manager import (
    _get_content_length, _size_warrants_abort, _InvalidContentLength)

from pytest import mark, raises


class MockReply(QNetworkReply):

    def __init__(self, headers=None):
        super().__init__()
        if headers is not None:
            for header, value in headers:
                self.setRawHeader(header, value)


CONTENT_LENGHT_HEADER_VARIANTS = (
    b'Content-Length',
    b'content-length',
    b'CONTENT-LENGTH',
    b'cOntent-length',
)


@mark.parametrize(
    'headers,result',
    (
        (
            (),
            None
        ),
        *(
            (
                (
                    (header, value),
                ),
                result
            )
            for (header, (value, result)) in product(
                CONTENT_LENGHT_HEADER_VARIANTS,
                (
                    (b'', _InvalidContentLength),
                    (b'1', 1),
                    (b'-1', _InvalidContentLength),
                    (b'1.0', _InvalidContentLength),
                    (b'a', _InvalidContentLength),
                    ('á'.encode('utf-8'), _InvalidContentLength),
                )
            )
        ),
        *(
            (
                (
                    (header, b'1,2'),
                ),
                1
            )
            for header in CONTENT_LENGHT_HEADER_VARIANTS
        ),
    )
)
def test_get_content_length(headers, result):
    if result is None or isinstance(result, int):
        assert _get_content_length(MockReply(headers)) == result
    else:
        assert issubclass(result, Exception)
        with raises(result):
            _get_content_length(MockReply(headers))


# TODO: Switch to an actual RenderOptions instance.
@mark.parametrize(
    'kwargs,result',
    (
        (
            {
                'sizes_and_sources': (),
                'render_options': None,
                'log': lambda *args, **kwargs: None,
                'reply': MockReply(),
            },
            False,
        ),
        (
            {
                'sizes_and_sources': (),
                'render_options': {},
                'log': lambda *args, **kwargs: None,
                'reply': MockReply(),
            },
            False,
        ),
    )
)
def test_size_warrants_abort(kwargs, result):
    assert _size_warrants_abort(**kwargs) == result