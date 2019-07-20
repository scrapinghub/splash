#!/usr/bin/env sh
PYQT5="https://sourceforge.net/projects/pyqt/files/sip/sip-4.19.4/sip-4.19.4.tar.gz"
SIP="https://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-5.9.2/PyQt5_gpl-5.9.2.tar.gz"

curl -L -o "$1" ${PYQT5} && \
curl -L -o "$2" ${SIP}
