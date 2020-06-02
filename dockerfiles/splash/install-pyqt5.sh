#!/usr/bin/env bash

_PYTHON=python3

mkdir -p /tmp/builds/sip && \
mkdir -p /tmp/builds/pyqt5 && \
pushd /tmp/builds && \
# sip
tar xzf "$1" --keep-newer-files -C sip --strip-components 1 && \
pushd sip && \
${_PYTHON} configure.py --sip-module PyQt5.sip && \
make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
make install && \
popd && \
# PyQt5
tar xzf "$2" --keep-newer-files -C pyqt5 --strip-components 1 && \
pushd pyqt5 && \
${_PYTHON} configure.py -c -j ${SPLASH_BUILD_PARALLEL_JOBS} \
    --verbose \
    --confirm-license \
    --no-designer-plugin \
    --no-qml-plugin \
    --no-python-dbus \
    -e QtCore \
    -e QtGui \
    -e QtWidgets \
    -e QtNetwork \
    -e QtWebKit \
    -e QtWebKitWidgets \
    -e QtWebChannel \
    -e QtSvg \
    -e QtQuick \
    -e QtPrintSupport && \
make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
make install && \
popd  && \
${_PYTHON} -c "import PyQt5.QtCore; print(PyQt5.QtCore.__file__)"

# Builds Complete
popd
