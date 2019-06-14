# -*- coding: utf-8 -*-
import math

import attr
from PyQt5.QtCore import QRect, QSize, QPoint
from PyQt5.QtGui import QPainter, QRegion

from splash import defaults
from splash.qtrender_image import (
    BaseQtScreenshotRenderer, WrappedImage,
    WrappedQImage,
    WrappedPillowImage,
)


@attr.s
class _TilingOptions:
    horizontal_count = attr.ib()  # type: int
    vertical_count = attr.ib()  # type: int
    tile_size = attr.ib()  # type: QSize


class QtWebkitScreenshotRenderer(BaseQtScreenshotRenderer):

    def __init__(self, web_page, logger=None, image_format=None,
                 width=None, height=None, scale_method=None, region=None):
        """ Initialize renderer.

        :type web_page: PyQt5.QtWebKit.QWebPage
        :type logger: splash.log.SplashLogger
        :type image_format: str {'PNG', 'JPEG'}
        :type width: int
        :type height: int
        :type scale_method: str {'raster', 'vector'}
        :type region: (int, int, int, int)
        """
        super().__init__(web_page=web_page, logger=logger,
                         image_format=image_format, width=width,
                         height=height, scale_method=scale_method,
                         region=region)

    def get_web_viewport_size(self):
        """ Return size of the current viewport """
        return self.web_page.viewportSize()

    def _render_qwebpage_full(self,
                              web_rect: QRect,
                              render_rect: QRect,
                              canvas_size: QSize,
                              ) -> 'WrappedImage':
        """ Render web page in one step. """
        if self._qpainter_needs_tiling(render_rect, canvas_size):
            # If this condition is true, this function may get stuck.
            raise ValueError("Rendering region is too large to be drawn"
                             " in one step, use tile-by-tile renderer instead")
        canvas = self.img_converter.new_qimage(canvas_size)
        painter = QPainter(canvas)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.setWindow(web_rect)
            painter.setViewport(render_rect)
            painter.setClipRect(web_rect)
            self.web_page.mainFrame().render(painter)
        finally:
            painter.end()
        return WrappedQImage(canvas)

    def _render_qwebpage_tiled(self,
                               web_rect: QRect,
                               render_rect: QRect,
                               canvas_size: QSize,
                               ) -> 'WrappedImage':
        """ Render web page tile-by-tile.

        This function works around bugs in QPaintEngine that occur when
        render_rect is larger than 32k pixels in either dimension.

        """
        # One bug is worked around by rendering the page one tile at a time
        # onto a small-ish temporary image.  The magic happens in
        # viewport-window transformation: painter viewport is moved
        # appropriately so that rendering region is overlayed onto a temporary
        # "render" image which is then pasted into the resulting one.
        #
        # The other bug manifests itself when you do painter.drawImage when
        # pasting the rendered tiles.  Once you reach 32'768 along either
        # dimension all of a sudden drawImage simply stops drawing anything.
        # This is a known limitation of Qt painting system where coordinates
        # are signed short ints. The simplest workaround that comes to mind
        # is to use pillow for pasting.
        tile_conf = self._calculate_tiling(
            to_paint=render_rect.intersected(QRect(QPoint(0, 0), canvas_size)))

        canvas = self.img_converter.new_pillow_image(canvas_size)
        ratio = render_rect.width() / float(web_rect.width())
        tile_qimage = self.img_converter.new_qimage(tile_conf.tile_size, fill=False)
        painter = QPainter(tile_qimage)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.setWindow(web_rect)
            # painter.setViewport here seems superfluous (actual viewport is
            # being set inside the loop below), but it is not. For some
            # reason, if viewport is reset after setClipRect,
            # clipping rectangle is adjusted, which is not what we want.
            painter.setViewport(render_rect)
            # painter.setClipRect(web_rect)
            self.logger.log(
                "Tiled rendering. tile_conf=%s; web_rect=%s, render_rect=%s, "
                "canvas_size=%s" % (tile_conf, web_rect, render_rect, canvas_size),
                min_level=2)
            for i in range(tile_conf.horizontal_count):
                left = i * tile_qimage.width()
                for j in range(tile_conf.vertical_count):
                    top = j * tile_qimage.height()
                    painter.setViewport(render_rect.translated(-left, -top))
                    self.logger.log("Rendering with viewport=%s"
                               % painter.viewport(), min_level=2)

                    clip_rect = QRect(
                        QPoint(math.floor(left / ratio),
                               math.floor(top / ratio)),
                        QPoint(math.ceil((left + tile_qimage.width()) / ratio),
                               math.ceil((top + tile_qimage.height()) / ratio)))
                    self.web_page.mainFrame().render(painter, QRegion(clip_rect))
                    tile_image = self.img_converter.qimage_to_pil(tile_qimage)

                    # If this is the bottommost tile, its bottom may have stuff
                    # left over from rendering the previous tile.  Make sure
                    # these leftovers don't garble the bottom of the canvas
                    # which can be larger than render_rect because of
                    # "height=" option.
                    rendered_vsize = min(render_rect.height() - top,
                                         tile_qimage.height())
                    if rendered_vsize < tile_qimage.height():
                        box = (0, 0, tile_qimage.width(), rendered_vsize)
                        tile_image = tile_image.crop(box)

                    self.logger.log("Pasting rendered tile to coords: %s" %
                                    ((left, top),), min_level=2)
                    canvas.paste(tile_image, (left, top))
        finally:
            # It is important to end painter explicitly in python code, because
            # Python finalizer invocation order, unlike C++ destructors, is not
            # deterministic and there is a possibility of image's finalizer
            # running before painter's which may break tests and kill your cat.
            painter.end()
        return WrappedPillowImage(canvas)

    def _calculate_tiling(self, to_paint: QRect) -> _TilingOptions:
        tile_maxsize = defaults.TILE_MAXSIZE
        tile_hsize = min(tile_maxsize, to_paint.width())
        tile_vsize = min(tile_maxsize, to_paint.height())
        htiles = 1 + (to_paint.width() - 1) // tile_hsize
        vtiles = 1 + (to_paint.height() - 1) // tile_vsize
        tile_size = QSize(tile_hsize, tile_vsize)
        return _TilingOptions(
            horizontal_count=htiles,
            vertical_count=vtiles,
            tile_size=tile_size
        )
