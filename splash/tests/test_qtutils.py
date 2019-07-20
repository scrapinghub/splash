# -*- coding: utf-8 -*-
from PyQt5.QtCore import QSize, QSizeF

from splash.qtutils import qsize_to_tuple


def test_qsize_to_tuple():
    assert qsize_to_tuple(QSize(2, 3)) == (2, 3)
    assert qsize_to_tuple(QSizeF(2.0, 3.0)) == (2.0, 3.0)
