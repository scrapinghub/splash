#!/usr/bin/env bash

_PYTHON=python3

mkdir -p /tmp/builds/webengine && \
pushd /tmp/builds && \
# PyQtWebEngine
tar xzf "$1" --keep-newer-files -C webengine --strip-components 1 && \
pushd webengine && \
${_PYTHON} configure.py -c -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
make install && \
popd  && \
popd
