#!/usr/bin/env bash

mkdir -p /tmp/builds/qtwebkit && \
cd /tmp/builds && \
tar xvfJ "$1" --keep-newer-files --strip-components 1 && \
mkdir build && \
cd build && \
cmake -G Ninja -DPORT=Qt -DCMAKE_BUILD_TYPE=Release .. && \
ninja && \
ninja install