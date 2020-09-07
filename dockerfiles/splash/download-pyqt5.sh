#!/usr/bin/env sh
# XXX: these URLs needs to be replaced with sourceforge in future,
# because riverbank tend to remove old releases.
SIP="https://distfiles.macports.org/py-sip/sip-4.19.19.tar.gz"
PYQT="https://sources.voidlinux.org/python-PyQt5-5.13.2/PyQt5-5.13.2.tar.gz"
WEBENGINE="https://sources.voidlinux-ppc.org/python-PyQt5-webengine-5.13.2/PyQtWebEngine-5.13.2.tar.gz"

curl --fail -L -o "$1" ${SIP} && \
curl --fail -L -o "$2" ${PYQT} && \
curl --fail -L -o "$3" ${WEBENGINE}
