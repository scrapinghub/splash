try:
    # try PyQt5
    from PyQt5.QtCore import (
        QEventLoop
    )
except ImportError as e0:
    try:
        # try PySide2
        from PySide2.QtCore import (
            QEventLoop
        )
    except ImportError as e1:
        raise ImportError(
            "Neither PyQt5 nor PySide2 installed.\nPyQt5: {}\nPySide2: {})".format(e0, e1)
        )
from qt5reactor import QtReactor

class PatchedQtReactor(QtReactor):
    def run(self, installSignalHandlers=True):
        if self._ownApp:
            self._blockApp = self.qApp
        else:
            self._blockApp = QEventLoop()
        self.runReturn(installSignalHandlers=installSignalHandlers)
        self._blockApp.exec_()
        if self.running:
            self.stop()
            self.runUntilCurrent()