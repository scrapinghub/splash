# -*- coding: utf-8 -*-
from __future__ import absolute_import
from collections import namedtuple
from datetime import datetime

import splash
from PyQt4.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt4.QtWebKit import qWebKitVersion

from .utils import get_duration, format_datetime, cleaned_har_entry


HarEvent = namedtuple('HarEvent', 'type data')

HAR_ENTRY = 'entry'
HAR_TIMING = 'timing'
HAR_URL_CHANGED = 'urlChanged'
HAR_TITLE_CHANGED = 'titleChanged'


class HarLog(object):
    """
    Helper class for building HAR data.
    """

    def __init__(self):
        self.created_at = datetime.utcnow()
        self.network_entries_map = {}  # key => network entry
        self.events = []  # all entries in order, including the events
        self.pages = None

    def get_mutable_entry(self, req_id, create=False):
        """
        Return a dict with HAR entry data. The dict is not a copy;
        caller can modify the result and the changes will be kept.
        """
        if create:
            assert req_id not in self.network_entries_map
            entry = {"_idx": req_id}
            self.network_entries_map[req_id] = entry
            self.events.append(HarEvent(HAR_ENTRY, entry))
        return self.network_entries_map[req_id]

    def has_entry(self, req_id):
        """ Return True if entry exists for this request """
        return req_id in self.network_entries_map

    def store_url(self, url):
        """ Call this method when URL is changed. """
        self.events.append(HarEvent(HAR_URL_CHANGED, unicode(url)))

    def store_title(self, title):
        """ Call this method when page title is changed. """
        self.events.append(HarEvent(HAR_TITLE_CHANGED, unicode(title)))

    def store_timing(self, name):
        """
        Call this method when an event you want to store timing for happened.
        """
        self.events.append(
            HarEvent(HAR_TIMING, {"name": name, "time": datetime.utcnow()})
        )

    def todict(self):
        """ Return HAR log as a Python dict. """

        # import pprint
        # pprint.pprint(self.events)

        self._fill_pages()

        return {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "Splash",
                    "version": splash.__version__,
                },
                "browser": self._get_browser(),
                "entries": self._get_har_entries(),
                "pages": self.pages,
            }
        }

    def _get_browser(self):
        return {
            "name": "QWebKit",
            "version": unicode(qWebKitVersion()),
            "comment": "PyQt %s, Qt %s" % (PYQT_VERSION_STR, QT_VERSION_STR),
        }

    def _empty_page(self, page_id, started_dt):
        if not isinstance(started_dt, basestring):
            started_dt = format_datetime(started_dt)

        return {
            "id": str(page_id),
            "title": "[no title]",
            "startedDateTime": started_dt,
            "pageTimings": {
                "onContentLoad": -1,
                "onLoad": -1,
            }
        }

    def _fill_pages(self):
        page_id = 1
        started_dt = self.created_at
        current_page = self._empty_page(page_id, started_dt)
        first_page = True

        self.pages = [current_page]

        for idx, ev in enumerate(self.events):
            if ev.type == HAR_TIMING:
                name = ev.data["name"]
                time = get_duration(started_dt, ev.data["time"])
                current_page["pageTimings"][name] = time

            elif ev.type == HAR_TITLE_CHANGED:
                current_page["title"] = ev.data

            elif ev.type == HAR_ENTRY:
                ev.data["pageref"] = str(page_id)

            elif ev.type == HAR_URL_CHANGED:
                # We need to find a network entry which caused URL
                # to change - it belongs to this new page.
                cause_ev = self._prev_entry(ev.data, idx)
                if first_page:
                    first_page = False
                else:
                    # Start a new page.
                    page_id += 1
                    if cause_ev is None:
                        # XXX: is it a right thing to do?
                        started_dt = self.created_at
                    else:
                        # FIXME: this requires non-standard _tmp data
                        started_dt = cause_ev.data['_tmp']['start_time']
                    current_page = self._empty_page(page_id, started_dt)
                    self.pages.append(current_page)

                if cause_ev is not None:
                    cause_ev.data["pageref"] = str(page_id)

    def _prev_entry(self, url, last_idx):
        for ev in reversed(self.events[:last_idx]):
            if ev.type != HAR_ENTRY:
                continue
            if ev.data["request"]["url"] == url:
                return ev

    def _get_har_entries(self):
        return [
            cleaned_har_entry(e.data)
            for e in self.events
            if e.type == HAR_ENTRY
        ]
