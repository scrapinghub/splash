"""This module handles rendering QWebPage into PNG and JPEG images."""
import sys
from abc import ABCMeta, abstractmethod, abstractproperty
from io import BytesIO
from math import ceil
from typing import Optional, Tuple

from PIL import Image
from PyQt5.QtCore import QBuffer, QPoint, QRect, QSize, Qt, QSizeF
from PyQt5.QtGui import QImage

from splash import defaults
from splash.log import DummyLogger
from splash.qtutils import qsize_to_tuple
from splash.utils import swap_byte_order_i32


class QImagePillowConverter:
    """ Object for managing Pillow and QImages """
    def __init__(self, tagret_format: str) -> None:
        self.target_format = tagret_format.upper()
        if self.target_format not in ('JPEG', 'PNG'):
            raise ValueError('Invalid image format %s, must be PNG or JPEG' %
                             self.target_format)

        # QImage's 0xARGB in little-endian becomes [0xB, 0xG, 0xR, 0xA] for
        # Pillow, hence the 'BGRA' decoder argument. Same for 'RGB' - 'BGRX'.
        # mapping for self.pillow_image_decoder is taken from
        # https://github.com/python-pillow/Pillow/blob/2.9.0/libImaging/Pack.c#L526
        if self.target_format == 'JPEG':
            self.qt_image_format = QImage.Format_ARGB32
            self.pillow_image_format = "RGB"
            self.pillow_decoder_format = "BGRX"
        else:
            self.qt_image_format = QImage.Format_ARGB32
            self.pillow_image_format = "RGBA"
            self.pillow_decoder_format = "BGRA"

    def qimage_to_pil(self, qimage: QImage) -> Image:
        """ Convert QImage (in ARGB32 format) to PIL.Image (in RGBA mode). """
        # In our case QImage uses 0xAARRGGBB format stored in host endian
        # order, we must convert it to [0xRR, 0xGG, 0xBB, 0xAA] sequences
        # used by Pillow.
        buf = qimage.bits().asstring(qimage.byteCount())
        if sys.byteorder != "little":
            buf = swap_byte_order_i32(buf)
        return Image.frombytes(
            self.pillow_image_format,
            qsize_to_tuple(qimage.size()),
            buf, 'raw', self.pillow_decoder_format)

    def new_pillow_image(self, size) -> Image:
        """ Return a new blank Pillow image """
        if isinstance(size, (QSize, QSizeF)):
            size = qsize_to_tuple(size)
        return Image.new(self.pillow_image_format, size=size)

    def new_qimage(self, size, fill=True) -> QImage:
        img = QImage(size, self.qt_image_format)
        if fill:
            if self.target_format == "JPEG":
                # White background for JPEG images, same as in all browsers.
                img.fill(Qt.white)
            else:
                # Preserve old behaviour for PNG format.
                img.fill(0)
        return img


class BaseQtScreenshotRenderer(metaclass=ABCMeta):
    """ Base class for rendering web page (or its parts) as an image.

    It doesn't render anything by itself: subclasses must define
    ``_render_qwebpage_tiled`` and ``_render_qwebpage_full`` methods
    with implementations.
    """

    # QPainter cannot render a region with any dimension greater than
    # this value.
    QPAINTER_MAXSIZE = 32766

    def __init__(self, web_page, logger=DummyLogger(), image_format=None,
                 width=None, height=None, scale_method=None, region=None):
        self.web_page = web_page  # BaseQtScreenshotRenderer shouldn't use it
        self.logger = logger
        self.width = width
        self.height = height
        self.img_converter = QImagePillowConverter(image_format)

        if scale_method is None:
            scale_method = defaults.IMAGE_SCALE_METHOD
        self.scale_method = scale_method
        if self.scale_method not in ('vector', 'raster'):
            raise ValueError(
                "Invalid scale method (must be 'vector' or 'raster'): %s" %
                str(self.scale_method))

        self.region = region
        if self.region is not None and self.height:
            raise ValueError("'height' argument is not supported when "
                             "'region' is argument is passed")

    @abstractmethod
    def get_web_viewport_size(self) -> QSize:
        """ Return size of the current viewport """
        raise NotImplementedError()

    @abstractmethod
    def _render_qwebpage_full(self,
                              web_rect: QRect,
                              render_rect: QRect,
                              canvas_size: QSize,
                              ) -> 'WrappedImage':
        """ Render web page in one step. """
        raise NotImplementedError()

    @abstractmethod
    def _render_qwebpage_tiled(self,
                               web_rect: QRect,
                               render_rect: QRect,
                               canvas_size: QSize,
                               ) -> 'WrappedImage':
        """ Render web page tile-by-tile.

        This function should work around bugs in QPaintEngine that occur when
        render_rect is larger than 32k pixels in either dimension.
        """
        raise NotImplementedError()

    def render_qwebpage(self) -> 'WrappedImage':
        """ Render QWebPage into a WrappedImage. """
        # Overall rendering pipeline looks as follows:
        # 1. render_qwebpage
        # 2. render_qwebpage_raster/-vector
        # 3. render_qwebpage_full/-tiled
        web_viewport = self._region_to_web_viewport(self.region)
        img_viewport, img_size = self._calculate_output_image_parameters(
            web_viewport=web_viewport,
            img_width=self.width,
            img_height=self.height)

        if img_viewport.isEmpty() or img_size.isEmpty():
            self.logger.log("requested image is empty", min_level=1)
            return EmptyImage()

        self.logger.log("image render: output size=%s, viewport=%s" %
                        (img_size, img_viewport), min_level=2)

        if self.scale_method == 'vector':
            return self._render_qwebpage_vector(
                in_viewport=web_viewport,
                out_viewport=img_viewport,
                image_size=img_size)
        elif self.scale_method == 'raster':
            return self._render_qwebpage_raster(
                in_viewport=web_viewport,
                out_viewport=img_viewport,
                image_size=img_size)

    def _region_to_web_viewport(self, region: Optional[Tuple]) -> QRect:
        """ Return QRect from region parameter. By default, current viewport
        is used. """
        if region is None:
            sz = self.get_web_viewport_size()
            left, top, right, bottom = 0, 0, sz.width(), sz.height()
            # return QRect(QPoint(0, 0), self.get_web_viewport_size())
        else:
            left, top, right, bottom = region
        return QRect(QPoint(left, top), QPoint(right - 1, bottom - 1))

    def _render_qwebpage_vector(self,
                                in_viewport: QRect,
                                out_viewport: QRect,
                                image_size: QSize) -> 'WrappedImage':
        """
        Render a webpage using vector rescale method.

        :param in_viewport: region of the webpage to render from
        :param out_viewport: region of the image to render to
        :param image_size: size of the resulting image
        """
        web_rect = QRect(in_viewport)
        render_rect = QRect(out_viewport)
        canvas_size = QSize(image_size)

        self.logger.log("image render: rendering %s of the web page" % web_rect,
                        min_level=2)
        self.logger.log("image render: rendering into %s of the canvas" % render_rect,
                        min_level=2)
        self.logger.log("image render: canvas size=%s" % canvas_size,
                        min_level=2)

        if self._qpainter_needs_tiling(render_rect, canvas_size):
            self.logger.log(
                "image render: draw region too large, rendering tile-by-tile",
                min_level=2)
            return self._render_qwebpage_tiled(web_rect, render_rect, canvas_size)
        else:
            self.logger.log("image render: rendering webpage in one step",
                            min_level=2)
            return self._render_qwebpage_full(web_rect, render_rect, canvas_size)

    def _render_qwebpage_raster(self,
                                in_viewport: QRect,
                                out_viewport: QRect,
                                image_size: QSize) -> 'WrappedImage':
        """ Render a webpage rescaling pixel-wise if necessary.

        :param in_viewport: region of the webpage to render from
        :param out_viewport: region of the image to render to
        :param image_size: size of the resulting image
        """
        self.logger.log("image render (raster): rendering %s of the web page" %
                        in_viewport, min_level=2)
        self.logger.log("image render (raster): rendering into %s of the canvas" %
                        out_viewport, min_level=2)
        self.logger.log("image render (raster): canvas size=%s" % image_size,
                        min_level=2)

        render_rect = QRect(in_viewport)
        if in_viewport.size() == out_viewport.size():
            # If no resizing is requested, we can make canvas of the size
            # of the output image to avoid the final cropping step.
            canvas_size = QSize(image_size)
        else:
            canvas_size = QSize(in_viewport.size())

        if image_size.height() < out_viewport.height():
            self.logger.log("image render: image is trimmed vertically",
                            min_level=2)
            hcut = image_size.height()
            if in_viewport.size() == out_viewport.size():
                # If no resizing then we need to render exactly the requested
                # number of pixels vertically.
                hrender = hcut
            else:
                # If there's a resize, there will be interpolation.  We must
                # ensure that both pixels that contribute to the color of the
                # last row of the resulting image are rendered.
                h0 = in_viewport.height()
                h1 = out_viewport.height()
                hrender = min(ceil(h0 * (hcut - 0.5) / float(h1) + 0.5), h0)
            render_rect = QRect(QPoint(0, 0),
                                QSize(in_viewport.width(), hrender))
            self.logger.log("image render: image is trimmed vertically, "
                            "need to render %s pixel(-s)" % hrender,
                            min_level=2)

        # To perform pixel-wise rescaling, we first render the image without
        # rescaling via vector-based method and resize/crop afterwards.
        canvas = self._render_qwebpage_vector(
            in_viewport=render_rect,
            out_viewport=QRect(QPoint(0, 0), render_rect.size()),
            image_size=canvas_size)
        if in_viewport.size() != out_viewport.size():
            self.logger.log("Scaling canvas (%s) to image viewport (%s)" %
                            (canvas.size, out_viewport.size()), min_level=2)
            canvas.resize(out_viewport.size())
        if canvas.size != image_size:
            self.logger.log("Cropping canvas (%s) to image size (%s)" %
                            (canvas.size, image_size), min_level=2)
            canvas.crop(QRect(QPoint(0, 0), image_size))
        return canvas

    def _qpainter_needs_tiling(self, render_rect: QRect,
                               canvas_size: QSize) -> bool:
        """ Return True if QPainter cannot perform given render
        without tiling. """
        to_paint = render_rect.intersected(QRect(QPoint(0, 0), canvas_size))
        return max(to_paint.width(), to_paint.height()) > self.QPAINTER_MAXSIZE

    def _calculate_output_image_parameters(self,
                                           web_viewport: QRect,
                                           img_width: Optional[int],
                                           img_height: Optional[int]
                                           ) -> Tuple[QRect, QSize]:
        """
        Calculate parameters of the resulting image to render - coordinates
        and size of rescaled and truncated image. Return
        ``(image_viewport, image_size)`` tuple.

        ``web_viewport`` is a QRect to render, in webpage coordinates.

        FIXME: add tests for it, to make the behavior clear.
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


class WrappedImage(metaclass=ABCMeta):
    """
    Base interface for operations with images of rendered webpages.

    QImage doesn't work well with large images, but PIL.Image seems
    significantly slower in resizing, so depending on context we may want to
    use one or another.
    """
    @abstractproperty
    def size(self) -> QSize:
        """ Size of the image. """

    @abstractmethod
    def resize(self, new_size: QSize) -> None:
        """ Resize the image. """

    @abstractmethod
    def crop(self, rect: QRect) -> None:
        """ Crop/extend image to specified rectangle. """

    @abstractmethod
    def to_png(self, complevel: int = defaults.PNG_COMPRESSION_LEVEL) -> bytes:
        """
        Serialize image as PNG and return the result as a byte sequence.

        :param complevel: compression level as defined by zlib (0 being
                          no compression and 9 being maximum compression)
        """

    @abstractmethod
    def to_jpeg(self, quality: float) -> bytes:
        """
        Serialize image as JPEG and return the result as a byte sequence.

        :param quality: quality level for JPEG images (0 being the worst quality and
            100 being large files with no compression)
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
        self.img.save(buf, 'png', quality)
        return bytes(buf.data())

    def to_jpeg(self, quality=None):
        if quality is None:
            quality = defaults.JPEG_QUALITY
        buf = QBuffer()
        self.img.save(buf, 'jpeg', quality)
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
        buf = BytesIO()
        self.img.save(buf, 'png', compress_level=complevel)
        return buf.getvalue()

    def to_jpeg(self, quality=None):
        if quality is None:
            quality = defaults.JPEG_QUALITY
        buf = BytesIO()
        self.img.save(buf, 'jpeg', quality=quality)
        return buf.getvalue()


class EmptyImage(WrappedImage):
    @property
    def size(self):
        return QSize()

    def resize(self, new_size):
        pass

    def crop(self, rect):
        pass

    def to_png(self, complevel=defaults.PNG_COMPRESSION_LEVEL):
        return b''

    def to_jpeg(self, quality=None):
        return b''
