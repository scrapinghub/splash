#!/usr/bin/env bash

# Lists are from https://wiki.qt.io/QtWebEngine/How_to_Try,
# but non-development versions, and with some packages removed
apt-get update -q && \
apt-get install -y --no-install-recommends \
    libasound2 \
    libbz2-dev \
    libcap-dev \
    libcups2 \
    libdrm-dev \
    libegl1-mesa \
    libgcrypt11-dev \
    libnss3 \
    libpci-dev \
    libpulse-dev \
    libudev-dev \
    libxtst-dev  && \

apt-get install -y --no-install-recommends \
    openssl1.0 \
    libssl1.0-dev \
    libxcursor-dev \
    libxcomposite-dev \
    libxdamage-dev \
    libxrandr-dev \
    libfontconfig1 \
    libxss-dev \
    libsrtp0 \
    libwebp-dev \
    libjsoncpp-dev \
    libopus-dev \
    libminizip-dev \
    libavutil-dev \
    libavformat-dev \
    libavcodec-dev \
    libevent-dev
