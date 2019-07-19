#!/usr/bin/env bash
apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu trusty multiverse" && \
apt-get update && \
apt-get install -y flashplugin-installer
