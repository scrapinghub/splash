#!/usr/bin/env bash

# Install system dependencies for Qt
apt-get update -q && \
apt-get install -y --no-install-recommends \
    xvfb \
    build-essential \
    libsqlite3-dev \
    zlib1g \
    zlib1g-dev \
    netbase \
    ca-certificates \
    pkg-config