#!/usr/bin/env sh
# XXX: these URLs needs to be replaced with sourceforge in future,
# because riverbank tend to remove old releases.
SIP="${SIP_URL:-https://www.riverbankcomputing.com/static/Downloads/sip/4.19.24/sip-4.19.24.tar.gz}"
PYQT="${PYQT_URL:-https://files.pythonhosted.org/packages/4d/81/b9a66a28fb9a7bbeb60e266f06ebc4703e7e42b99e3609bf1b58ddd232b9/PyQt5-5.14.2.tar.gz}"
WEBENGINE="${WEBENGINE:-https://files.pythonhosted.org/packages/47/9f/60e630711fd1dd14ef3bd95c86c733c86b8c0853749c7a03691f681f13fd/PyQtWebEngine-5.14.0.tar.gz}"

curl --fail -L -o "$1" ${SIP} && \
curl --fail -L -o "$2" ${PYQT} && \
curl --fail -L -o "$3" ${WEBENGINE}
