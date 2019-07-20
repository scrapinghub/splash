#!/usr/bin/env bash

# Install system dependencies for Qt, Python packages, etc.
# ppa:pi-rho/security is a repo for libre2-dev
add-apt-repository -y ppa:pi-rho/security && \
apt-get update -q && \
apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    python3-pip \
    libre2-dev \
    liblua5.2-dev \
    libsqlite3-dev \
    zlib1g \
    zlib1g-dev \
    netbase \
    ca-certificates \
    pkg-config
