# -*- coding: utf-8 -*-
from __future__ import absolute_import
from PyQt4.QtNetwork import QNetworkRequest, QNetworkCookie, QNetworkCookieJar


class SplashCookieJar(QNetworkCookieJar):

    def update_cookie_header(self, request):
        """ Use this cookiejar to set Cookie: request header """
        if not _should_send_cookies(request):
            return

        cookies = self.cookiesForUrl(request.url())
        if not cookies:
            return

        request.setRawHeader(b"Cookie", _cookies_to_raw(cookies))

    def fill_from_reply(self, reply):
        """ Add cookies from the reply to the cookiejar """
        # based on QNetworkReplyImplPrivate::metaDataChanged C++ code
        if not _should_save_cookies(reply.request()):
            return
        cookies = reply.header(QNetworkRequest.SetCookieHeader).toPyObject()
        if not cookies:
            return
        self.setCookiesFromUrl(cookies, reply.url())

    def clear(self):
        self.setAllCookies([])


def _should_send_cookies(request):
    """ Return True if cookies should be sent for a request """
    # based on QNetworkAccessManager::createRequest() C++ code
    attr, ok = request.attribute(
        QNetworkRequest.CookieLoadControlAttribute,
        QNetworkRequest.Automatic
    ).toInt()
    return attr == QNetworkRequest.Automatic


def _should_save_cookies(request):
    """ Return True if cookies should be saved for a request """
    # based on QNetworkReplyImplPrivate::metaDataChanged() C++ code
    attr, ok = request.attribute(
        QNetworkRequest.CookieSaveControlAttribute,
        QNetworkRequest.Automatic
    ).toInt()
    return attr == QNetworkRequest.Automatic


def _cookies_to_raw(cookies):
    """ Build raw Cookie: header value from a list of QNetworkCookie instances """
    # based on QNetworkRequest::fromheaderValue() C++ code
    return b"; ".join(
        bytes(cookie.toRawForm(QNetworkCookie.NameAndValueOnly))
        for cookie in cookies
    )


