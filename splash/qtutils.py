# -*- coding: utf-8 -*-
""" Utils for working with QWebKit objects.
"""
from __future__ import absolute_import

import array
import functools
import itertools
import struct
import sys
import time
from abc import ABCMeta, abstractmethod, abstractproperty
from cStringIO import StringIO
from math import ceil, floor

from twisted.python import log
from PIL import Image
from PyQt4.QtGui import QApplication, QImage, QPainter, QRegion, QTransform, QPolygonF
from PyQt4.QtCore import (
    QAbstractEventDispatcher, QVariant, QString, QObject,
    QDateTime, QRegExp, QSize, QRect, QPoint, QRectF, QBuffer, Qt
)
from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkReply

from splash import defaults
from splash.utils import truncated


OPERATION_NAMES = {
    QNetworkAccessManager.HeadOperation: 'HEAD',
    QNetworkAccessManager.GetOperation: 'GET',
    QNetworkAccessManager.PostOperation: 'POST',
    QNetworkAccessManager.PutOperation: 'PUT',
    QNetworkAccessManager.DeleteOperation: 'DELETE',
}
OPERATION_QT_CONSTANTS = {v:k for k,v in OPERATION_NAMES.items()}


# See: http://pyqt.sourceforge.net/Docs/PyQt4/qnetworkreply.html#NetworkError-enum
REQUEST_ERRORS = {
    QNetworkReply.NoError : 'no error condition. Note: When the HTTP protocol returns a redirect no error will be reported. You can check if there is a redirect with the QNetworkRequest::RedirectionTargetAttribute attribute.',
    QNetworkReply.ConnectionRefusedError : 'the remote server refused the connection (the server is not accepting requests)',
    QNetworkReply.RemoteHostClosedError : 'the remote server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.HostNotFoundError : 'the remote host name was not found (invalid hostname)',
    QNetworkReply.TimeoutError : 'the connection to the remote server timed out',
    QNetworkReply.OperationCanceledError : 'the operation was canceled via calls to abort() or close() before it was finished.',
    QNetworkReply.SslHandshakeFailedError : 'the SSL/TLS handshake failed and the encrypted channel could not be established. The sslErrors() signal should have been emitted.',
    QNetworkReply.TemporaryNetworkFailureError : 'the connection was broken due to disconnection from the network, however the system has initiated roaming to another access point. The request should be resubmitted and will be processed as soon as the connection is re-established.',
    QNetworkReply.ProxyConnectionRefusedError : 'the connection to the proxy server was refused (the proxy server is not accepting requests)',
    QNetworkReply.ProxyConnectionClosedError : 'the proxy server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.ProxyNotFoundError : 'the proxy host name was not found (invalid proxy hostname)',
    QNetworkReply.ProxyTimeoutError : 'the connection to the proxy timed out or the proxy did not reply in time to the request sent',
    QNetworkReply.ProxyAuthenticationRequiredError : 'the proxy requires authentication in order to honour the request but did not accept any credentials offered (if any)',
    QNetworkReply.ContentAccessDenied : 'the access to the remote content was denied (similar to HTTP error 401)',
    QNetworkReply.ContentOperationNotPermittedError : 'the operation requested on the remote content is not permitted',
    QNetworkReply.ContentNotFoundError : 'the remote content was not found at the server (similar to HTTP error 404)',
    QNetworkReply.AuthenticationRequiredError : 'the remote server requires authentication to serve the content but the credentials provided were not accepted (if any)',
    QNetworkReply.ContentReSendError : 'the request needed to be sent again, but this failed for example because the upload data could not be read a second time.',
    QNetworkReply.ProtocolUnknownError : 'the Network Access API cannot honor the request because the protocol is not known',
    QNetworkReply.ProtocolInvalidOperationError : 'the requested operation is invalid for this protocol',
    QNetworkReply.UnknownNetworkError : 'an unknown network-related error was detected',
    QNetworkReply.UnknownProxyError : 'an unknown proxy-related error was detected',
    QNetworkReply.UnknownContentError : 'an unknown error related to the remote content was detected',
    QNetworkReply.ProtocolFailure : 'a breakdown in protocol was detected (parsing error, invalid or unexpected responses, etc.)',
}

REQUEST_ERRORS_SHORT = {
    QNetworkReply.NoError: 'OK',
    QNetworkReply.OperationCanceledError: 'cancelled',
    QNetworkReply.ConnectionRefusedError: 'connection_refused',
    QNetworkReply.RemoteHostClosedError : 'connection_closed',
    QNetworkReply.HostNotFoundError : 'invalid_hostname',
    QNetworkReply.TimeoutError : 'timed_out',
    QNetworkReply.SslHandshakeFailedError : 'ssl_error',
    QNetworkReply.TemporaryNetworkFailureError : 'temp_network_failure',
    QNetworkReply.ProxyConnectionRefusedError : 'proxy_connection_refused',
    QNetworkReply.ProxyConnectionClosedError : 'proxy_connection_closed',
    QNetworkReply.ProxyNotFoundError : 'proxy_not_found',
    QNetworkReply.ProxyTimeoutError : 'proxy_timeout',
    QNetworkReply.ProxyAuthenticationRequiredError : 'proxy_auth_required',
    QNetworkReply.ContentAccessDenied : 'access_denied_401',
    QNetworkReply.ContentOperationNotPermittedError : 'operation_not_permitted',
    QNetworkReply.ContentNotFoundError : 'not_found_404',
    QNetworkReply.AuthenticationRequiredError : 'auth_required',
    QNetworkReply.ContentReSendError : 'must_resend',
    QNetworkReply.ProtocolUnknownError : 'unknown_protocol',
    QNetworkReply.ProtocolInvalidOperationError : 'invalid_operation',
    QNetworkReply.UnknownNetworkError : 'unknown_network_error',
    QNetworkReply.UnknownProxyError : 'unknown_proxy_error',
    QNetworkReply.UnknownContentError : 'unknown_remote_content_error',
    QNetworkReply.ProtocolFailure : 'protocol_error',
}



# A global reference must be kept to QApplication, otherwise the process will
# segfault
_qtapp = None


def init_qt_app(verbose):
    """ Initialize Main Qt Application.
    :param verbose:
    :return: QApplication
    """
    global _qtapp
    if _qtapp:
        log.msg("QApplication is already initiated.")
        return _qtapp

    class QApp(QApplication):

        blockedAt = 0

        def __init__(self, *args):
            super(QApp, self).__init__(*args)
            if verbose:
                disp = QAbstractEventDispatcher.instance()
                disp.aboutToBlock.connect(self.aboutToBlock)
                disp.awake.connect(self.awake)

        def aboutToBlock(self):
            self.blockedAt = time.time()
            log.msg("aboutToBlock", system="QAbstractEventDispatcher")

        def awake(self):
            diff = time.time() - self.blockedAt
            log.msg("awake; block time: %0.4f" % diff, system="QAbstractEventDispatcher")
    _qtapp = QApp(sys.argv)
    return _qtapp


def get_qt_app():
    """ Return Main QtApplication. """
    assert _qtapp is not None, "init_qt_app should be called first."
    return _qtapp


def qurl2ascii(url):
    """ Convert QUrl to ASCII text suitable for logging """
    url = unicode(url.toString()).encode('unicode-escape').decode('ascii')
    if url.lower().startswith('data:'):
        return truncated(url, 80, '...[data uri truncated]')
    return url


def drop_request(request):
    """ Drop the request """
    # hack: set invalid URL
    request.setUrl(QUrl(''))


def request_repr(request, operation=None):
    """ Return string representation of QNetworkRequest suitable for logging """
    method = OPERATION_NAMES.get(operation, '?')
    url = qurl2ascii(request.url())
    return "%s %s" % (method, url)


def qt2py(obj, max_depth=100):
    """ Convert a QVariant object to a barebone non-PyQT object """

    if max_depth <= 0:
        raise ValueError("Can't convert object: depth limit is reached")

    if isinstance(obj, QVariant):
        obj = obj.toPyObject()

    # print(obj, obj.__class__)

    if isinstance(obj, QString):
        return unicode(obj)

    if isinstance(obj, QDateTime):
        return obj.toPyDateTime()

    if isinstance(obj, QRegExp):
        return {
            "_jstype": "RegExp",
            "pattern": unicode(obj.pattern()),
            "caseSensitive": bool(obj.caseSensitivity()),
        }

    if isinstance(obj, dict):
        return {
            qt2py(key, max_depth-1): qt2py(value, max_depth-1)
            for key, value in obj.items()
        }

    if isinstance(obj, list):
        return [qt2py(v, max_depth-1) for v in obj]

    if isinstance(obj, tuple):
        return tuple([qt2py(v, max_depth-1) for v in obj])

    if isinstance(obj, set):
        return {qt2py(v, max_depth-1) for v in obj}

    assert not isinstance(obj, QObject), (obj, obj.__class__)
    return obj


class WrappedSignal(object):
    """
    A wrapper for QT signals that assigns ids to callbacks,
    passes callback_id to the callback (as a keyword argument)
    and allows to disconnect callbacks by their ids.

    Its main purpose is to provide a way to disconnect a slot
    when callback is fired.
    """
    def __init__(self, signal):
        self.ids = itertools.count()
        self.callbacks = {}
        self.signal = signal

    def connect(self, func, **kwargs):
        callback_id = next(self.ids)
        cb = functools.partial(func, callback_id=callback_id, **kwargs)
        self.callbacks[callback_id] = cb
        self.signal.connect(cb)
        return callback_id

    def disconnect(self, callback_id):
        cb = self.callbacks.pop(callback_id)
        self.signal.disconnect(cb)


# Brain-dead simple endianness detection needed because QImage stores
# bytes in host-native order.
#
# XXX: do we care about big endian hosts?
# XXX: is there a better way?
_is_little_endian = struct.pack('<i', 0x1122) == struct.pack('=i', 0x1122)


def qimage_to_pil_image(qimage):
    """Convert QImage (in ARGB32 format) to PIL.Image (in RGBA mode)."""
    # In our case QImage uses 0xAARRGGBB format stored in host endian order,
    # we must convert it to [0xRR, 0xGG, 0xBB, 0xAA] sequences used by pillow.
    buf = qimage.bits().asstring(qimage.numBytes())
    if not _is_little_endian:
        buf = swap_byte_order_i32(buf)
    # QImage's 0xARGB in little-endian becomes [0xB, 0xG, 0xR, 0xA] for pillow,
    # hence the 'BGRA' decoder argument.
    return Image.frombytes(
        'RGBA', _qsize_to_tuple(qimage.size()), buf, 'raw', 'BGRA')


def swap_byte_order_i32(buf):
    """Swap order of bytes in each 32-bit word of given byte sequence."""
    arr = array.array('I')
    arr.fromstring(buf)
    arr.byteswap()
    return arr.tostring()


def render_qwebpage(web_page, logger=None, width=None, height=None,
                    scale_method=None):
    """
    Render QWebPage into a WrappedImage.

    :type web_page: PyQt4.QtWebKit.QWebPage
    :type logger: splash.browser_tab._BrowserTabLogger
    :type width: int
    :type height: int
    :type scale_method: str {'raster', 'vector'}
    :rtype: WrappedImage

    """
    # Overall rendering pipeline looks as follows:
    # 1. render_qwebpage
    # 2. render_qwebpage_raster/-vector
    # 3. render_qwebpage_impl
    # 4. render_qwebpage_full/-tiled
    if logger is None:
        logger = _DummyLogger()
    if scale_method is None:
        scale_method = defaults.PNG_SCALE_METHOD

    web_viewport = QRect(QPoint(0, 0), web_page.viewportSize())
    img_viewport, img_size = _calculate_image_parameters(
        web_viewport, width, height)
    logger.log("png render: output size=%s, viewport=%s" %
               (img_size, img_viewport), min_level=2)

    if scale_method == 'vector':
        return _render_qwebpage_vector(
            web_page, logger,
            in_viewport=web_viewport, out_viewport=img_viewport,
            image_size=img_size)
    elif scale_method == 'raster':
        return _render_qwebpage_raster(
            web_page, logger,
            in_viewport=web_viewport, out_viewport=img_viewport,
            image_size=img_size)
    else:
        raise ValueError(
            "Invalid scale method (must be 'vector' or 'raster'): %s" %
            str(scale_method))


def _render_qwebpage_vector(web_page, logger,
                            in_viewport, out_viewport, image_size):
    """
    Render a webpage using vector rescale method.

    :param in_viewport: region of the webpage to render from
    :param out_viewport: region of the image to render to
    :param image_size: size of the resulting image

    :type in_viewport: QRect
    :type out_viewport: QRect
    :type image_size: QSize

    """
    web_rect = QRect(in_viewport)
    render_rect = QRect(out_viewport)
    canvas_size = QSize(image_size)

    logger.log("png render: rendering %s of the web page" % web_rect,
               min_level=2)
    logger.log("png render: rendering into %s of the canvas" % render_rect,
               min_level=2)
    logger.log("png render: canvas size=%s" % canvas_size, min_level=2)

    to_paint = render_rect.intersected(QRect(QPoint(0, 0), canvas_size))
    # QPainter has several issues when its rendering area is more than 2**15 in
    # any dimension.
    need_tiling = max(to_paint.width(), to_paint.height()) >= (1 << 15)
    if need_tiling:
        logger.log("png render: draw region too large, rendering tile-by-tile",
                   min_level=2)
        return _render_qwebpage_tiled(web_page, logger,
                                      web_rect, render_rect, canvas_size)
    else:
        logger.log("png render: rendering webpage in one step", min_level=2)
        return _render_qwebpage_full(web_page, logger,
                                     web_rect, render_rect, canvas_size)


def _render_qwebpage_raster(web_page, logger,
                            in_viewport, out_viewport, image_size):
    """
    Render a webpage rescaling pixel-wise if necessary.

    :param in_viewport: region of the webpage to render from
    :param out_viewport: region of the image to render to
    :param image_size: size of the resulting image

    :type in_viewport: QRect
    :type out_viewport: QRect
    :type image_size: QSize

    """
    render_rect = QRect(in_viewport)
    if in_viewport.size() == out_viewport.size():
        # If no resizing is requested, we can make canvas of the size of the
        # output image to avoid the final cropping step.
        canvas_size = QSize(image_size)
    else:
        canvas_size = QSize(in_viewport.size())

    if image_size.height() < out_viewport.height():
        logger.log("png render: image is trimmed vertically")
        hcut = image_size.height()
        if in_viewport.size() == out_viewport.size():
            # If no resizing then we need to render exactly the requested
            # number of pixels vertically.
            hrender = hcut
        else:
            # If there's a resize, there will be interpolation.  We must ensure
            # that both pixels that contribute to the color of the last row of
            # the resulting image are rendered.
            h0 = in_viewport.height()
            h1 = out_viewport.height()
            hrender = min(ceil(h0 * (hcut - 0.5) / float(h1) + 0.5), h0)
        render_rect = QRect(QPoint(0, 0),
                            QSize(in_viewport.width(), hrender))
        logger.log("png render: image is trimmed vertically,"
                   " need to render %s pixel(-s)" % hrender, min_level=2)

    # To perform pixel-wise rescaling, we first render the image without
    # rescaling via vector-based method and resize/crop afterwards.
    canvas = _render_qwebpage_vector(
        web_page, logger,
        in_viewport=render_rect, out_viewport=render_rect,
        image_size=canvas_size)
    if in_viewport.size() != out_viewport.size():
        logger.log("Scaling canvas (%s) to image viewport (%s)" %
                   (canvas.size, out_viewport.size()), min_level=2)
        canvas.resize(out_viewport.size())
    if canvas.size != image_size:
        logger.log("Cropping canvas (%s) to image size (%s)" %
                   (canvas.size, image_size), min_level=2)
        canvas.crop(QRect(QPoint(0, 0), image_size))
    return canvas


def _render_qwebpage_full(web_page, logger,
                          web_rect, render_rect, canvas_size):
    """Render web page in one step."""
    if max(render_rect.width(), render_rect.height()) >= (1 << 15):
        # If this condition is true, this function may get stuck.
        raise ValueError("Rendering region is too large to be drawn"
                         " in one step, use tile-by-tile renderer instead")
    canvas = QImage(canvas_size, QImage.Format_ARGB32)
    canvas.fill(0)
    painter = QPainter(canvas)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setWindow(web_rect)
        painter.setViewport(render_rect)
        painter.setClipRect(web_rect)
        web_page.mainFrame().render(painter)
    finally:
        painter.end()
    return WrappedQImage(canvas)


def _render_qwebpage_tiled(web_page, logger,
                           web_rect, render_rect, canvas_size):
    """
    Render web page tile-by-tile.

    This function works around bugs in QPaintEngine that occur when render_rect
    is larger than 32k pixels in either dimension.

    """
    # One bug is worked around by rendering the page one tile at a time onto a
    # small-ish temporary image.  The magic happens in viewport-window
    # transformation: painter viewport is moved appropriately so that rendering
    # region is overlayed onto a temporary "render" image which is then pasted
    # into the resulting one.
    #
    # The other bug manifests itself when you do painter.drawImage when pasting
    # the rendered tiles.  Once you reach 32'768 along either dimension all of
    # a sudden drawImage simply stops drawing anything.  This is a known
    # limitation of Qt painting system where coordinates are signed short ints.
    # The simplest workaround that comes to mind is to use pillow for pasting.
    tile_conf = _calculate_tiling(
        to_paint=render_rect.intersected(QRect(QPoint(0, 0), canvas_size)))

    canvas = Image.new('RGBA', _qsize_to_tuple(canvas_size))

    tile_qimage = QImage(tile_conf['tile_size'], QImage.Format_ARGB32)
    tile_qimage.fill(0)
    painter = QPainter(tile_qimage)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setWindow(web_rect)
        # painter.setViewport here seems superfluous (actual viewport is being
        # set inside the loop below), but it is not.  For some reason, if
        # viewport is reset after setClipRect, clipping rectangle is adjusted,
        # which is not what we want.
        painter.setViewport(render_rect)
        painter.setClipRect(web_rect)
        for i in xrange(tile_conf['horizontal_count']):
            left = i * tile_qimage.width()
            for j in xrange(tile_conf['vertical_count']):
                top = j * tile_qimage.height()
                painter.setViewport(render_rect.translated(-left, -top))
                logger.log("Rendering with viewport=%s"
                           % painter.viewport(), min_level=2)

                web_page.mainFrame().render(painter)
                tile_image = qimage_to_pil_image(tile_qimage)

                # If this is the bottommost tile, its bottom may have stuff
                # left over from rendering the previous tile.  Make sure these
                # leftovers don't garble the bottom of the canvas which can be
                # larger than render_rect because of "height=" option.
                rendered_vsize = min(render_rect.height() - top,
                                     tile_qimage.height())
                if rendered_vsize < tile_qimage.height():
                    box = (0, 0, tile_qimage.width(), rendered_vsize)
                    tile_image = tile_image.crop(box)

                logger.log("Pasting rendered tile to coords: %s" %
                           ((left, top),), min_level=2)
                canvas.paste(tile_image, (left, top))
    finally:
        # It is important to end painter explicitly in python code, because
        # Python finalizer invocation order, unlike C++ destructors, is not
        # deterministic and there is a possibility of image's finalizer running
        # before painter's which may break tests and kill your cat.
        painter.end()
    return WrappedPillowImage(canvas)


def _calculate_image_parameters(web_viewport, img_width, img_height):
    """
    :return: (image_viewport, image_size)
    """
    if img_width is None:
        img_width = web_viewport.width()
        ratio = 1.0
    else:
        if img_width == 0 or web_viewport.width() == 0:
            ratio = 1.0
        else:
            ratio = img_width / float(web_viewport.width())
    image_viewport = QRect(
        QPoint(0, 0),
        QSize(img_width, round(web_viewport.height() * ratio)))
    if img_height is None:
        img_height = image_viewport.height()
    image_size = QSize(img_width, img_height)
    return image_viewport, image_size


def _calculate_tiling(to_paint):
    tile_maxsize = defaults.TILE_MAXSIZE
    tile_hsize = min(tile_maxsize, to_paint.width())
    tile_vsize = min(tile_maxsize, to_paint.height())
    htiles = 1 + (to_paint.width() - 1) // tile_hsize
    vtiles = 1 + (to_paint.height() - 1) // tile_vsize
    tile_size = QSize(tile_hsize, tile_vsize)
    return {'horizontal_count': htiles,
            'vertical_count': vtiles,
            'tile_size': tile_size}


class _DummyLogger(object):
    """Logger to use when no logger is passed into rendering functions."""
    def log(self, *args, **kwargs):
        pass


def _qsize_to_tuple(sz):
    return sz.width(), sz.height()


class WrappedImage(object):
    """
    Base interface for operations with images of rendered webpages.

    QImage doesn't work well with large images, but PIL.Image seems
    significantly slower in resizing, so depending on context we may want to
    use one or another.

    """
    __metaclass__ = ABCMeta

    @abstractproperty
    def size(self):
        """
        Size of the image.

        :rtype: QSize

        """

    @abstractmethod
    def resize(self, new_size):
        """
        Resize the image.

        :type new_size: QSize

        """

    @abstractmethod
    def crop(self, rect):
        """
        Crop/extend image to specified rectangle.

        :type rect: QRect
        """

    @abstractmethod
    def to_png(self, complevel):
        """
        Serialize image as PNG and return the result as a byte sequence.

        :param complevel: compression level as defined by zlib (0 being
                          no compression and 9 being maximum compression)

        """


class WrappedQImage(WrappedImage):
    def __init__(self, qimage):
        assert isinstance(qimage, QImage)
        self.img = qimage

    @property
    def size(self):
        return self.img.size()

    def resize(self, new_size):
        assert isinstance(new_size, QSize)
        self.img = self.img.scaled(new_size,
                                   transformMode=Qt.SmoothTransformation)

    def crop(self, rect):
        assert isinstance(rect, QRect)
        self.img = self.img.copy(rect)

    def to_png(self, complevel=defaults.PNG_COMPRESSION_LEVEL):
        quality = 90 - (complevel * 10)
        buf = QBuffer()
        self.img.save(buf, 'png', quality=quality)
        return bytes(buf.data())


class WrappedPillowImage(WrappedImage):
    def __init__(self, image):
        assert isinstance(image, Image.Image)
        self.img = image

    @property
    def size(self):
        return QSize(*self.img.size)

    def resize(self, new_size):
        assert isinstance(new_size, QSize)
        self.img = self.img.resize((new_size.width(), new_size.height()),
                                   Image.BILINEAR)

    def crop(self, rect):
        assert isinstance(rect, QRect)
        left, right = rect.left(), rect.left() + rect.width()
        top, bottom = rect.top(), rect.top() + rect.height()
        self.img = self.img.crop((left, top, right, bottom))

    def to_png(self, complevel=defaults.PNG_COMPRESSION_LEVEL):
        buf = StringIO()
        self.img.save(buf, 'png', compression_level=complevel)
        return buf.getvalue()
