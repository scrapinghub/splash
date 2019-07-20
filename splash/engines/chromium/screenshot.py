# -*- coding: utf-8 -*-
from PyQt5.QtCore import QSize, QRect
from PyQt5.QtGui import QPainter

from splash.qtrender_image import (
    BaseQtScreenshotRenderer, WrappedImage,
    WrappedQImage,
)


class QtChromiumScreenshotRenderer(BaseQtScreenshotRenderer):

    def __init__(self, web_page, logger=None, image_format=None,
                 width=None, height=None, scale_method=None, region=None):
        """ Initialize renderer.

        :type web_page: PyQt5.QtWebEngineWidgets.QWebEnginePage
        :type logger: splash.log.SplashLogger
        :type image_format: str {'PNG', 'JPEG'}
        :type width: int
        :type height: int
        :type scale_method: str {'raster', 'vector'}
        :type region: (int, int, int, int)
        """
        if region is not None:
            raise ValueError("region argument is not supported yet")

        super().__init__(web_page=web_page, logger=logger,
                         image_format=image_format, width=width,
                         height=height, scale_method=scale_method,
                         region=region)

    def get_web_viewport_size(self) -> QSize:
        """ Return size of the current viewport """
        return self.web_page.view().size()

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
            # self.web_page.mainFrame().render(painter)
            self.web_page.view().render(painter)
        finally:
            painter.end()
        return WrappedQImage(canvas)

    def _render_qwebpage_tiled(self,
                               web_rect: QRect,
                               render_rect: QRect,
                               canvas_size: QSize,
                               ) -> 'WrappedImage':
        raise ValueError("tiling is required, but it is not implemented")

