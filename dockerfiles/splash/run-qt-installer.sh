#!/usr/bin/env bash
# XXX: if qt version is changed, Dockerfile should be updated,
# as well as qt-installer-noninteractive.qs script.

chmod +x "$1" && \
xvfb-run "$1" --script "$2" \
    | egrep -v '\[[0-9]+\] Warning: (Unsupported screen format)|((QPainter|QWidget))' && \
ls /opt/qt-5.13/ && \
#    cat /opt/qt-5.13/InstallationLog.txt && \
cat /opt/qt-5.13/components.xml