#!/usr/bin/env bash

_PYTHON=python3
SPLASH_BUILD_PARALLEL_JOBS=4

mkdir -p /tmp/builds/sip && \
mkdir -p /tmp/builds/pyqt5 && \
mkdir -p /tmp/builds/webengine && \
pushd /tmp/builds && \
# sip
tar xzf "$1" --keep-newer-files -C sip --strip-components 1 && \
pushd sip && \
${_PYTHON} configure.py && \
make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
make install  && \
popd  && \

# PyQt5
tar xzf "$2" --keep-newer-files -C pyqt5 --strip-components 1 && \
pushd pyqt5 && \
${_PYTHON} configure.py -c \
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
#    -e QtWebEngine \
#    -e QtWebEngineCore \
#    -e QtWebEngineWidgets \
    -e QtWebChannel \
    -e QtSvg \
    -e QtPrintSupport && \
make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
make install && \
popd  && \

# PyQtWebEngine
tar xzf "$3" --keep-newer-files -C webengine --strip-components 1 && \
pushd webengine && \
${_PYTHON} configure.py && \
make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
make install  && \
popd  && \

# Builds Complete
popd
