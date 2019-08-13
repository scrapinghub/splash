#!/usr/bin/env bash
apt-get update -q && \
apt-get install -y --no-install-recommends \
    cmake \
    ninja-build \
    bison \
    gperf \
    ruby \
    python
