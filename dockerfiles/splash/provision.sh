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
install_python_deps -- install python-level dependencies
install_msfonts - agree with EULA and install Microsoft fonts
install_extra_fonts - install extra fonts
remove_builddeps -- remove build-dependencies
remove_extra -- remove files that are unnecessary to run Splash

EOF
}

prepare_install () {
    # Prepare docker image for installation of packages, docker images are
    # usually stripped and aptitude doesn't work immediately.
    #
    # python-software-properties contains "add-apt-repository" command for PPA conf
    sed 's/main$/main universe/' -i /etc/apt/sources.list && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        curl \
        software-properties-common \
        python-software-properties
}

install_deps () {
    # Install package dependencies.
    apt-add-repository -y ppa:beineri/opt-qt541-trusty && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        netbase \
        ca-certificates \
        xvfb \
        pkg-config \
        python3 \
        qt54base \
        qt54declarative \
        qt54webkit \
        python3-pyqt5 \
        python3-pyqt5.qtwebkit \
        libre2 \
        libicu52 \
        liblua5.2-0 \
        zlib1g && \
    # Install more recent version of sip.
    curl -L -o sip.tar.gz http://sourceforge.net/projects/pyqt/files/sip/sip-4.16.7/sip-4.16.7.tar.gz && \
    echo '32abc003980599d33ffd789734de4c36  sip.tar.gz' | md5sum -c - \
    tar xzf sip.tar.gz && \
    pushd sip-4.16.7 && \
    python3 configure.py && \
    make && \
    make install && \
    popd && \
    rm -rf sip-4.16.7 sip.tar.gz
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
        zlib1g-dev
}

install_python_deps () {
    # Install python-level dependencies.
    pip3 install -U pip && \
    pip3 install -U https://github.com/twisted/twisted/archive/trunk.zip#egg=twisted && \
    pip3 install \
        qt5reactor-fork==0.2 \
        psutil==3.1.1 \
        adblockparser==0.4 \
        xvfbwrapper==0.2.4 \
        lupa==1.1 \
        funcparserlib==0.3.6 \
        Pillow==2.9.0 && \
    pip3 install https://github.com/sunu/pyre2/archive/master.zip#egg=pyre2
}

install_msfonts() {
    # Agree with EULA and install Microsoft fonts
    apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu trusty multiverse" && \
    apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu trusty-updates multiverse" && \
    apt-get update && \
    echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections && \
    apt-get install -y ttf-mscorefonts-installer
}

install_extra_fonts() {
    # Install extra fonts (Chinese)
    apt-get install -y ttf-wqy-zenhei
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
        gcc cpp binutils perl && \
    apt-get autoremove -y && \
    apt-get clean -y
}

remove_extra () {
    # Remove unnecessary files.
    rm -rf \
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
