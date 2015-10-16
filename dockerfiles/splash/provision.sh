#!/bin/bash

usage() {
    cat <<EOF
Splash docker image provisioner.

Usage: $0 COMMAND [ COMMAND ... ]

Available commands:
usage -- print this message
prepare_install -- prepare image for installation
install_deps -- install system-level dependencies
install_builddeps -- install system-level build-dependencies
install_pyqt5 -- install PyQT5 from sources
install_python_deps -- install python-level dependencies
install_msfonts -- agree with EULA and install Microsoft fonts
install_extra_fonts -- install extra fonts
remove_builddeps -- remove build-dependencies
remove_extra -- remove files that are unnecessary to run Splash

EOF
}

SIP_VERSION='4.16.9'
PYQT_VERSION='5.5'
QT_PATH='/opt/qt55'


prepare_install () {
    # Prepare docker image for installation of packages, docker images are
    # usually stripped and apt-get doesn't work immediately.
    #
    # python-software-properties contains "add-apt-repository" command for PPA conf
    sed 's/main$/main universe/' -i /etc/apt/sources.list && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        curl \
        software-properties-common \
        python3-software-properties
}

install_deps () {
    # Install package dependencies.
    apt-add-repository -y ppa:beineri/opt-qt551-trusty && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        netbase \
        ca-certificates \
        xvfb \
        pkg-config \
        python3 \
        qt55base \
        qt55webkit \
        libre2 \
        libicu52 \
        liblua5.2-0 \
        zlib1g
}

install_builddeps () {
    # Install build dependencies for package (and its pip dependencies).
    # ppa:pi-rho/security is a repo for libre2-dev
    add-apt-repository -y ppa:pi-rho/security && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        python3-dev \
        python3-pip \
        build-essential \
        libre2-dev \
        liblua5.2-dev \
        libsqlite3-dev \
        zlib1g-dev \
        libjpeg-turbo8-dev \
        libgl1-mesa-dev-lts-utopic
}

install_pyqt5 () {
    mkdir -p /downloads && \
    chmod a+rw /downloads && \
    curl -L -o /downloads/sip.tar.gz http://sourceforge.net/projects/pyqt/files/sip/sip-${SIP_VERSION}/sip-${SIP_VERSION}.tar.gz && \
    curl -L -o /downloads/pyqt5.tar.gz http://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-${PYQT_VERSION}/PyQt-gpl-${PYQT_VERSION}.tar.gz && \
    # TODO: check downloads
    mkdir -p /builds && \
    chmod a+rw /builds && \
    pushd /builds && \
    # SIP
    tar xzf /downloads/sip.tar.gz --keep-newer-files  && \
    pushd sip-${SIP_VERSION}  && \
    python3 configure.py  && \
    make  && \
    make install  && \
    popd  && \
    # PyQt5
    tar xzf /downloads/pyqt5.tar.gz --keep-newer-files  && \
    pushd PyQt-gpl-${PYQT_VERSION}  && \
    python3 configure.py -c --qmake "${QT_PATH}/bin/qmake" --verbose \
        --confirm-license \
        --no-designer-plugin \
        -e QtCore \
        -e QtGui \
        -e QtWidgets \
        -e QtNetwork \
        -e QtWebKit \
        -e QtWebKitWidgets \
        -e QtPrintSupport && \
    make  && \
    make install && \
    popd  && \
    # Builds Complete
    popd
}

install_python_deps () {
    # Install python-level dependencies.
    pip3 install -U pip && \
    pip3 install \
        qt5reactor-fork==0.2 \
        psutil==3.2.2 \
        Twisted==15.4.0 \
        adblockparser==0.4 \
        xvfbwrapper==0.2.5 \
        lupa==1.2 \
        funcparserlib==0.3.6 \
        Pillow==2.9.0 && \
    pip3 install https://github.com/sunu/pyre2/archive/c610be52c3b5379b257d56fc0669d022fd70082a.zip#egg=pyre2
}

install_msfonts() {
    # Agree with EULA and install Microsoft fonts
    apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu trusty multiverse" && \
    apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu trusty-updates multiverse" && \
    apt-get update && \
    echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections && \
    apt-get install --no-install-recommends -y ttf-mscorefonts-installer
}

install_extra_fonts() {
    # Install extra fonts (Chinese)
    apt-get install --no-install-recommends -y \
        ttf-wqy-zenhei \
        fonts-arphic-gbsn00lp \
        fonts-arphic-bsmi00lp \
        fonts-arphic-gkai00mp \
        fonts-arphic-bkai00mp
}

remove_builddeps () {
    # Uninstall build dependencies.
    apt-get remove -y --purge \
        python3-dev \
        build-essential \
        libre2-dev \
        liblua5.2-dev \
        zlib1g-dev \
        libc-dev \
        libjpeg-turbo8-dev \
        libcurl3 \
        gcc cpp binutils perl && \
    apt-get autoremove -y && \
    apt-get clean -y
}

remove_extra () {
    # Remove unnecessary files.
    rm -rf \
        /builds \
        /downloads \
        ${QT_PATH}/examples \
        ${QT_PATH}/include \
        ${QT_PATH}/mkspecs \
        ${QT_PATH}/bin \
        ${QT_PATH}/doc \
        /usr/share/perl \
        /usr/share/perl5 \
        /usr/share/man \
        /usr/share/info \
        /usr/share/doc \
        /var/lib/apt/lists/*
}

if [ \( $# -eq 0 \) -o \( "$1" = "-h" \) -o \( "$1" = "--help" \) ]; then
    usage
    exit 1
fi

UNKNOWN=0
for cmd in "$@"; do
    if [ "$(type -t -- "$cmd")" != "function" ]; then
        echo "Unknown command: $cmd"
        UNKNOWN=1
    fi
done

if [ $UNKNOWN -eq 1 ]; then
    echo "Unknown commands encountered, exiting..."
    exit 1
fi

while [ $# -gt 0 ]; do
    echo "Executing command: $1"
    "$1" || { echo "Command failed (exitcode: $?), exiting..."; exit 1; }
    shift
done
