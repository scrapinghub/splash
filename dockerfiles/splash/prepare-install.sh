#!/usr/bin/env bash
# Prepare docker image for installation of packages, docker images are
# usually stripped and apt-get doesn't work immediately.
#
# python-software-properties contains "add-apt-repository" command for PPA conf
sed 's/main$/main universe/' -i /etc/apt/sources.list && \
apt-get update -q && \
apt-get install -y --no-install-recommends \
    curl \
    software-properties-common \
    apt-transport-https \
    python3-software-properties
