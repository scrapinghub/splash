#!/usr/bin/env sh

URL="http://download.qt.io/official_releases/qt/$QT_SHORT_VERSION/$QT_FULL_VERSION/qt-opensource-linux-x64-$QT_FULL_VERSION.run"

curl --fail -L -o "$1" ${URL}
