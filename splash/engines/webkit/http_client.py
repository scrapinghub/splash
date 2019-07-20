# -*- coding: utf-8 -*-
import functools

from PyQt5.QtCore import QObject
from PyQt5.QtNetwork import QNetworkRequest

from splash.network_manager import SplashQNetworkAccessManager
from splash.qtutils import to_qurl
from splash.utils import to_bytes
from splash.engines.webkit.webpage import WebkitWebPage


class SplashWebkitHttpClient(QObject):
    """
    Wrapper class for making HTTP requests on behalf of a WebkitWebPage
    """
    def __init__(self, web_page: WebkitWebPage) -> None:
        super(SplashWebkitHttpClient, self).__init__()
        self._replies = set()
        self.web_page = web_page
        self.network_manager = web_page.networkAccessManager()  # type: SplashQNetworkAccessManager

    def set_user_agent(self, value):
        """ Set User-Agent header for future requests """
        self.web_page.custom_user_agent = value

    def request_obj(self, url, headers=None, body=None):
        """ Return a QNetworkRequest object """
        request = QNetworkRequest()
        request.setUrl(to_qurl(url))
        request.setOriginatingObject(self.web_page.mainFrame())

        if headers is not None:
            self.web_page.skip_custom_headers = True
            self._set_request_headers(request, headers)

        if body and not request.hasRawHeader(b"content-type"):
            # There is POST body but no content-type. QT will set this
            # header, but it will complain so better to do this here.
            request.setRawHeader(b"content-type",
                                 b"application/x-www-form-urlencoded")

        return request

    def request(self, url, callback, method='GET', body=None,
                headers=None, follow_redirects=True, max_redirects=5):
        """
        Create a request and return a QNetworkReply object with callback
        connected.
        """
        cb = functools.partial(
            self._on_request_finished,
            callback=callback,
            method=method,
            body=body,
            headers=headers,
            follow_redirects=follow_redirects,
            redirects_remaining=max_redirects,
        )
        return self._send_request(url, cb, method=method, body=body,
                                  headers=headers)

    def get(self, url, callback, headers=None, follow_redirects=True):
        """ Send a GET HTTP request; call the callback with the reply. """
        cb = functools.partial(
            self._return_reply,
            callback=callback,
            url=url,
        )
        self.request(url, cb, headers=headers, follow_redirects=follow_redirects)

    def post(self, url, callback, headers=None, follow_redirects=True, body=None):
        """ Send HTTP POST request;
        """
        cb = functools.partial(self._return_reply, callback=callback, url=url)
        self.request(url, cb, headers=headers,
                     follow_redirects=follow_redirects, body=body,
                     method="POST")

    def _send_request(self, url, callback, method='GET', body=None,
                      headers=None):
        # this is called when request is NOT downloaded via webpage.mainFrame()
        # XXX: The caller must ensure self._delete_reply is called in
        # a callback.
        if method.upper() not in ["POST", "GET"]:
            raise NotImplementedError()

        if body is not None:
            assert isinstance(body, bytes)

        request = self.request_obj(url, headers=headers, body=body)

        # setting UA for request that is not downloaded via
        # webpage.mainFrame().load_to_mainframe()
        ua_from_headers = get_header_value(headers, b'user-agent')
        web_page_ua = self.web_page.userAgentForUrl(to_qurl(url))
        user_agent = ua_from_headers or web_page_ua
        request.setRawHeader(b"user-agent", to_bytes(user_agent))

        if method.upper() == "POST":
            reply = self.network_manager.post(request, body)
        else:
            reply = self.network_manager.get(request)

        reply.finished.connect(callback)
        self._replies.add(reply)
        return reply

    def _on_request_finished(self, callback, method, body, headers,
                             follow_redirects, redirects_remaining):
        """ Handle redirects and call the callback. """
        reply = self.sender()
        try:
            if not follow_redirects:
                callback()
                return
            if not redirects_remaining:
                callback()  # XXX: should it be an error?
                return

            redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
            if redirect_url is None:  # no redirect
                callback()
                return

            # handle redirects after POST request
            if method.upper() == "POST":
                method = "GET"
                body = None

            redirect_url = reply.url().resolved(redirect_url)
            self.request(
                url=redirect_url,
                callback=callback,
                method=method,
                body=body,
                headers=headers,
                follow_redirects=follow_redirects,
                max_redirects=redirects_remaining-1,
            )
        finally:
            self._delete_reply(reply)

    def _return_reply(self, callback, url):
        reply = self.sender()
        callback(reply)

    def _set_request_headers(self, request, headers):
        """ Set HTTP headers for the request. """
        if isinstance(headers, dict):
            headers = headers.items()

        for name, value in headers or []:
            request.setRawHeader(to_bytes(name), to_bytes(value))

    def _delete_reply(self, reply):
        self._replies.remove(reply)
        reply.close()
        reply.deleteLater()


def get_header_value(headers, name, default=None):
    """ Return header value, doing case-insensitive match """
    if not headers:
        return default

    if isinstance(headers, dict):
        headers = headers.items()

    name = to_bytes(name.lower())
    for k, v in headers:
        if name == to_bytes(k.lower()):
            return v
    return default
