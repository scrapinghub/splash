#!/usr/bin/env bash
# XXX: if qt version is changed, Dockerfile should be updated,
# as well as qt-installer-noninteractive.qs script.

if [ -z ${DISPLAY+x} ]; then
	command="xvfb-run $1"
else
	command="$1"
fi

chmod +x "$1" && \
http_proxy="http://localhost:8080" https_proxy="http://localhost:8080" $command --script $2 \
    | egrep -v '\[[0-9]+\] Warning: (Unsupported screen format)|((QPainter|QWidget))' && \
ls /opt/qt-5.14/ && \
#    cat /opt/qt-5.14/InstallationLog.txt && \
cat /opt/qt-5.14/components.xml