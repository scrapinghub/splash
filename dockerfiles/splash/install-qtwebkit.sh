#!/usr/bin/env bash
apt-get update -q && \
apt-get install -y p7zip-full && \
mkdir -p /tmp/builds/qtwebkit && \
cd /tmp/builds/qtwebkit && \
cp "$1" ./webkit.7z && \
7z x ./webkit.7z -xr!*.debug && \
rm webkit.7z && \
rsync \
  -aP /tmp/builds/qtwebkit/* \
  $(qmake -query QT_INSTALL_PREFIX)
