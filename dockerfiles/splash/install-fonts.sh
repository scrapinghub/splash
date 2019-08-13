#!/usr/bin/env bash

install_msfonts() {
    # Agree with EULA and install Microsoft fonts
#    apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu xenial multiverse" && \
#    apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu xenial-updates multiverse" && \
#    apt-get update && \
    echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections && \
    apt-get install --no-install-recommends -y ttf-mscorefonts-installer
}

install_extra_fonts() {
    # Install extra fonts (Chinese and other)
    apt-get install --no-install-recommends -y \
        fonts-liberation \
        ttf-wqy-zenhei \
        fonts-arphic-gbsn00lp \
        fonts-arphic-bsmi00lp \
        fonts-arphic-gkai00mp \
        fonts-arphic-bkai00mp \
        fonts-beng
}
apt-get update -q && \
install_msfonts && install_extra_fonts