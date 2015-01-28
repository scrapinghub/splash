# -*- coding: utf-8 -*-
""" Utils for working with QWebKit objects.
"""
from __future__ import absolute_import
import sys
import time
import itertools
import functools
import struct
import array
from math import floor, ceil

from twisted.python import log
from PIL import Image
from PyQt4.QtGui import QApplication, QImage, QPainter, QRegion
from PyQt4.QtCore import (
    QAbstractEventDispatcher, QVariant, QString, QObject,
    QDateTime, QRegExp, QSize, QRect, QPoint
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


def _render_qwebpage_impl(web_page, logger, render_geometry):
    rg = render_geometry
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
    tiled_render = rg.horizontal_tile_count > 1 or rg.vertical_tile_count > 1
    if tiled_render:
        logger.log("png render: draw region too large, rendering tile-by-tile",
                   min_level=2)
        out_image = Image.new(mode='RGBA',
                              size=_qsize_to_tuple(rg.render_viewport.size()))
    else:
        assert rg.render_viewport.size() == rg.render_device_size
        # If tiled rendering is not used, out_image will be created from
        # render_device after the first (and the only) rendering operation.
        # Not preallocating out_image will save some memory.
        logger.log("png render: rendering webpage in one step", min_level=2)
        out_image = None

    render_device = QImage(rg.render_device_size, QImage.Format_ARGB32)
    render_device.fill(0)
    painter = QPainter(render_device)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setWindow(rg.web_clip_rect)
        painter.setClipRect(rg.web_clip_rect)
        painter_viewport = rg.render_viewport
        for i in xrange(rg.horizontal_tile_count):
            left = i * render_device.width()
            for j in xrange(rg.vertical_tile_count):
                top = j * render_device.height()
                painter.setViewport(painter_viewport.translated(-left, -top))
                logger.log("Rendering with viewport=%s"
                           % painter.viewport(), min_level=2)

                web_page.mainFrame().render(painter)
                pil_tile_image = qimage_to_pil_image(render_device)
                if not tiled_render:
                    out_image = pil_tile_image
                    break

                # If this is the bottommost tile, its bottom may have stuff
                # left over from rendering the previous tile.  Make sure these
                # leftovers don't garble the resulting image which may be
                # taller than render_viewport because of "height=" option.
                rendered_vsize = min(rg.render_viewport.height() - top,
                                     render_device.height())
                if rendered_vsize < render_device.height():
                    box = (0, 0, render_device.width(), rendered_vsize)
                    pil_tile_image = pil_tile_image.crop(box)

                logger.log("Pasting rendered tile to coords: %s" %
                           ((left, top),), min_level=2)
                out_image.paste(pil_tile_image, (left, top))
    finally:
        # It is important to end painter explicitly in python code, because
        # Python finalizer invocation order, unlike C++ destructors, is not
        # deterministic and there is a possibility of image's finalizer running
        # before painter's which may break tests and kill your cat.
        painter.end()

    if out_image.size != _qsize_to_tuple(rg.image_viewport_size):
        logger.log("Scaling render viewport (%s) to image viewport (%s)" %
                   (rg.render_viewport.size(), rg.image_viewport_size),
                   min_level=2)
        out_image = out_image.resize(_qsize_to_tuple(rg.image_viewport_size),
                                     Image.BILINEAR)
    if out_image.size != _qsize_to_tuple(rg.image_size):
        logger.log("Cropping image viewport (%s) to image size (%s)" %
                   (rg.image_viewport_size, rg.image_size),
                   min_level=2)
        out_image = out_image.crop((0, 0) + _qsize_to_tuple(rg.image_size))
    return out_image


def render_qwebpage(web_page, logger=None, width=None, height=None,
                    scale_method=None):
    """
    Render QWebPage into PIL.Image.

    This function works around bugs in QPaintEngine that occur when the
    resulting image is larger than 32k pixels in either dimension.

    :type web_page: PyQt4.QtWebKit.QWebPage
    :type logger: splash.browser_tab._BrowserTabLogger
    :type width: int
    :type height: int
    :rtype: PIL.Image.Image

    """
    if logger is None:
        logger = _DummyLogger()
    rg = _calculate_render_geometry(
        web_page.viewportSize(), img_width=width, img_height=height,
        scale_method=scale_method)
    for k, v in rg.__dict__.iteritems():
        logger.log("png render: %s=%s" % (k, v), min_level=2)
    return _render_qwebpage_impl(web_page, logger, render_geometry=rg)


class RenderGeometry(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)


def _calculate_render_geometry(web_viewport_size, img_width, img_height,
                               scale_method=None):
    # This function calculates geometry parameters for rendering pipeline that
    # looks like this:
    # - webpage viewport -> (un-)cropping -> webpage cliprect
    # - webpage cliprect -> vector resizing -> render viewport
    # - render viewport -> raster resizing -> image viewport
    # - image viewport -> (un-)cropping -> image size
    if img_width is None:
        img_width = web_viewport_size.width()
        ratio = 1.0
    else:
        if img_width == 0 or web_viewport_size.width() == 0:
            ratio = 1.0
        else:
            ratio = img_width / float(web_viewport_size.width())
    if img_height is None:
        img_height = int(web_viewport_size.height() * ratio)

    if img_height < web_viewport_size.height() * ratio:
        # Output image will be clipped by height, let's propagate this clipping
        # to the input region.
        web_clip_size = QSize(web_viewport_size.width(),
                              img_height / ratio)
    else:
        web_clip_size = web_viewport_size

    img_viewport_size = web_clip_size * ratio
    if scale_method is None:
        scale_method = defaults.PNG_SCALE_METHOD
    if scale_method == 'vector':
        render_viewport_size = img_viewport_size
    elif scale_method == 'raster':
        render_viewport_size = web_clip_size
    else:
        raise ValueError(
            "Invalid scale method (must be 'vector' or 'raster'): %s" %
            str(scale_method))

    tile_maxsize = defaults.TILE_MAXSIZE
    tile_hsize = min(tile_maxsize, render_viewport_size.width())
    tile_vsize = min(tile_maxsize, render_viewport_size.height())
    htiles = 1 + (render_viewport_size.width() - 1) // tile_hsize
    vtiles = 1 + (render_viewport_size.height() - 1) // tile_vsize
    return RenderGeometry(
        # This reads more or less as a rendering pipeline.
        web_viewport_size=web_viewport_size,
        web_clip_rect=QRect(QPoint(0, 0), web_clip_size),
        render_viewport=QRect(QPoint(0, 0), render_viewport_size),
        image_viewport_size=img_viewport_size,
        image_size=QSize(img_width, img_height),

        # Tiling configuration.
        render_device_size=QSize(tile_hsize, tile_vsize),
        horizontal_tile_count=htiles,
        vertical_tile_count=vtiles)


class _DummyLogger(object):
    """Logger to use when no logger is passed into rendering functions."""
    def log(self, *args, **kwargs):
        pass


def _qsize_to_tuple(sz):
    return sz.width(), sz.height()
