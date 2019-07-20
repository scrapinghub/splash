#!/usr/bin/env sh

# XXX: if qt version is changed, Dockerfile should be updated,
# as well as qt-installer-noninteractive.qs script.
URL="http://download.qt.io/official_releases/qt/5.9/5.9.1/qt-opensource-linux-x64-5.9.1.run"

curl -L -o "$1" ${URL}
