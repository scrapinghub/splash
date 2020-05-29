#!/usr/bin/env sh
URL="https://github.com/qtwebkit/qtwebkit/releases/download/qtwebkit-5.212.0-alpha3/qtwebkit-5.212.0-alpha3.tar.xz"
curl --fail -L -o "$1" ${URL}
