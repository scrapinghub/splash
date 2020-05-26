#!/usr/bin/env sh
# XXX: these URLs needs to be replaced with sourceforge in future,
# because riverbank tend to remove old releases.
SIP="https://www.riverbankcomputing.com/static/Downloads/sip/4.19.19/sip-4.19.19.tar.gz"
PYQT="https://www.riverbankcomputing.com/static/Downloads/PyQt${QT_MAJOR_VERSION}/${QT_FULL_VERSION}/PyQt${QT_MAJOR_VERSION}_gpl-${QT_FULL_VERSION}.tar.gz"
WEBENGINE="https://www.riverbankcomputing.com/static/Downloads/PyQtWebEngine/${QT_FULL_VERSION}/PyQtWebEngine_gpl-${QT_FULL_VERSION}.tar.gz"

curl -L -o "$1" ${SIP} && \
curl -L -o "$2" ${PYQT} && \
curl -L -o "$3" ${WEBENGINE}
