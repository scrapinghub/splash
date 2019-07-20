# -*- coding: utf-8 -*-
from PyQt5.QtWebEngineWidgets import QWebEnginePage


RenderProcessTerminationStatus = {
    QWebEnginePage.NormalTerminationStatus: "The render process terminated normally.",
    QWebEnginePage.AbnormalTerminationStatus: "The render process terminated with with a non-zero exit status.",
    QWebEnginePage.CrashedTerminationStatus: "The render process crashed, for example because of a segmentation fault.",
    QWebEnginePage.KilledTerminationStatus: "The render process was killed, for example by SIGKILL or task manager kill.",
}
