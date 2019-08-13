#!/usr/bin/env bash
apt-get update -q && \
apt-get install -y --no-install-recommends \
    libssl1.0-dev \
    libjpeg-turbo8-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    mesa-common-dev \
    libfontconfig1-dev \
    libicu-dev \
    libpng-dev \
    libxslt1-dev \
    libxml2-dev \
    libhyphen-dev \
    libgbm1 \
    libxcb-image0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxkbcommon-x11-0 \
    libxi6 \
    libxcomposite-dev \
    libxrender-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    gstreamer1.0-plugins-good \
    gstreamer1.0-x \
    gstreamer1.0-libav \
    webp \
    rsync
