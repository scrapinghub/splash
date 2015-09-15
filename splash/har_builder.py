# -*- coding: utf-8 -*-
from __future__ import absolute_import
import copy
from datetime import datetime

from splash.har.log import HarLog
from splash.har.utils import format_datetime, get_duration, cleaned_har_entry
from splash.har.qt import request2har, reply2har


class HarBuilder(object):
    """
    Splash-specific HAR builder class.
    It knows how to update timings based on events available in QT.
    Also it maintains a history of browser URL changes.
    """
    REQUEST_CREATED = "created"
    REQUEST_FINISHED = "finished"
    REQUEST_HEADERS_RECEIVED = "headers_received"

    def __init__(self):
        self.log = HarLog()
        self.history = []

    def todict(self):
        """ Return HAR log as a Python dict. """
        return self.log.todict()

    def get_history(self):
        """ Get a history of browser URL changes """
        return copy.deepcopy(self.history)

    def reset(self):
        """ Start building a new HAR log """
        self.log = HarLog()

    def get_last_http_status(self):
        """
        Return HTTP status code of the currently loaded webpage
        or None if it is not available.
        """
        if not self.history:
            return
        try:
            return self.history[-1]["response"]["status"]
        except KeyError:
            return

    def get_entry(self, req_id):
        """ Return HAR entry for a given req_id """
        if not self.log.has_entry(req_id):
            return
        entry = self.log.get_mutable_entry(req_id)
        return copy.deepcopy(entry)

    def _initial_entry_data(self, start_time, operation, request, outgoingData):
        """
        Return initial values for a new HAR entry.
        """
        return {
            # custom fields
            '_tmp': {
                'start_time': start_time,
                'request_start_sending_time': start_time,
                'request_sent_time': start_time,
                'response_start_time': start_time,
                # 'outgoingData': outgoingData,
            },
            '_splash_processing_state': self.REQUEST_CREATED,

            # standard fields
            "startedDateTime": format_datetime(start_time),
            "request": request2har(request, operation, outgoingData),
            "response": {
                "bodySize": -1,
            },
            "cache": {},
            "timings": {
                "blocked": -1,
                "dns": -1,
                "connect": -1,
                "ssl": -1,

                "send": 0,
                "wait": 0,
                "receive": 0,
            },
            "time": 0,
        }

    def store_title(self, title):
        self.log.store_title(title)

    def store_url(self, url):
        if hasattr(url, 'toString'):
            url = url.toString()
        self.log.store_url(url)

    def store_timing(self, name):
        self.log.store_timing(name)

    def store_new_request(self, req_id, start_time, operation, request, outgoingData):
        """
        Store information about a new QNetworkRequest.
        """
        entry = self.log.get_mutable_entry(req_id, create=True)
        entry.update(self._initial_entry_data(
            start_time=start_time,
            operation=operation,
            request=request,
            outgoingData=outgoingData
        ))

    def store_new_reply(self, req_id, reply):
        """
        Store initial reply information.
        """
        if not self.log.has_entry(req_id):
            return
        entry = self.log.get_mutable_entry(req_id)
        entry["response"].update(reply2har(reply))

    def store_reply_finished(self, req_id, reply):
        """
        Store information about a finished reply.
        """
        if not self.log.has_entry(req_id):
            return
        entry = self.log.get_mutable_entry(req_id)
        entry["_splash_processing_state"] = self.REQUEST_FINISHED

        # update timings
        now = datetime.utcnow()
        start_time = entry['_tmp']['start_time']
        response_start_time = entry['_tmp']['response_start_time']

        receive_time = get_duration(response_start_time, now)
        total_time = get_duration(start_time, now)

        entry["timings"]["receive"] = receive_time
        entry["time"] = total_time

        if not entry["timings"]["send"]:
            wait_time = entry["timings"]["wait"]
            entry["timings"]["send"] = total_time - receive_time - wait_time
            if entry["timings"]["send"] < 1e-6:
                entry["timings"]["send"] = 0

        # update other reply information
        entry["response"].update(reply2har(reply))

    def store_reply_headers_received(self, req_id, reply):
        """
        Update reply information when HTTP headers are received.
        """
        if not self.log.has_entry(req_id):
            return
        entry = self.log.get_mutable_entry(req_id)
        if entry["_splash_processing_state"] == self.REQUEST_FINISHED:
            # self.log("Headers received for {url}; ignoring", reply,
            #           min_level=3)
            return

        entry["_splash_processing_state"] = self.REQUEST_HEADERS_RECEIVED
        entry["response"].update(reply2har(reply))

        now = datetime.utcnow()
        request_sent = entry["_tmp"]["request_sent_time"]
        entry["_tmp"]["response_start_time"] = now
        entry["timings"]["wait"] = get_duration(request_sent, now)

    def store_reply_download_progress(self, req_id, received, total):
        """
        Update reply information when new data is available
        """
        if not self.log.has_entry(req_id):
            return
        entry = self.log.get_mutable_entry(req_id)
        entry["response"]["bodySize"] = int(received)

    def store_request_upload_progress(self, req_id, sent, total):
        """
        Update request information when outgoing data is sent.
        """
        if not self.log.has_entry(req_id):
            return
        entry = self.log.get_mutable_entry(req_id)
        entry["request"]["bodySize"] = int(sent)

        now = datetime.utcnow()
        if sent == 0:
            # it is a moment the sending is started
            start_time = entry["_tmp"]["request_start_time"]
            entry["_tmp"]["request_start_sending_time"] = now
            entry["timings"]["blocked"] = get_duration(start_time, now)

        entry["_tmp"]["request_sent_time"] = now

        if sent == total:
            entry["_tmp"]["response_start_time"] = now
            start_sending_time = entry["_tmp"]["request_start_sending_time"]
            entry["timings"]["send"] = get_duration(start_sending_time, now)

    def store_redirect(self, url):
        """ Update history when redirect happens """
        cause_ev = self.log._prev_entry(url, last_idx=-1)
        if cause_ev:
            self.history.append(cleaned_har_entry(cause_ev.data))

