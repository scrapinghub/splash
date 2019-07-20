#!/usr/bin/env bash

mkdir -p /tmp/builds/qtwebkit && \
cd /tmp/builds && \
tar xvfJ "$1" --keep-newer-files -C qtwebkit --strip-components 1 && \
rsync -aP /tmp/builds/qtwebkit/* `qmake -query QT_INSTALL_PREFIX`
