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
install_flash -- install flash plugin
remove_builddeps -- remove build-dependencies
remove_extra -- remove files that are unnecessary to run Splash

EOF
}

env | grep SPLASH

SPLASH_SIP_VERSION=${SPLASH_SIP_VERSION:-"4.17"}
SPLASH_PYQT_VERSION=${SPLASH_PYQT_VERSION:-"5.5.1"}
SPLASH_QT_PATH=${SPLASH_QT_PATH:-"/opt/qt55"}
SPLASH_BUILD_PARALLEL_JOBS=${SPLASH_BUILD_PARALLEL_JOBS:-"1"}

# '2' is not fully supported by this script!
SPLASH_PYTHON_VERSION=${SPLASH_PYTHON_VERSION:-"3"}

if [[ ${SPLASH_PYTHON_VERSION} == "venv" ]]; then
    _PYTHON=python
else
    _PYTHON=python${SPLASH_PYTHON_VERSION}
fi

_activate_venv () {
    if [[ ${SPLASH_PYTHON_VERSION} == "venv" ]]; then
        source ${VIRTUAL_ENV}/bin/activate
    fi
}

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
        libgl1-mesa-dri \
        pkg-config \
        python3 \
        qt55base \
        qt55webkit \
        qt55svg \
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
        libgl1-mesa-dev \
        libglu1-mesa-dev \
        mesa-common-dev
}

install_pyqt5 () {
    _activate_venv && \
    ${_PYTHON} --version && \
    mkdir -p /downloads && \
    chmod a+rw /downloads && \
    curl -L -o /downloads/sip.tar.gz http://sourceforge.net/projects/pyqt/files/sip/sip-${SPLASH_SIP_VERSION}/sip-${SPLASH_SIP_VERSION}.tar.gz && \
    curl -L -o /downloads/pyqt5.tar.gz http://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-${SPLASH_PYQT_VERSION}/PyQt-gpl-${SPLASH_PYQT_VERSION}.tar.gz && \
    # TODO: check downloads
    mkdir -p /builds && \
    chmod a+rw /builds && \
    pushd /builds && \
    # SIP
    tar xzf /downloads/sip.tar.gz --keep-newer-files  && \
    pushd sip-${SPLASH_SIP_VERSION}  && \
    ${_PYTHON} configure.py  && \
    make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
    make install  && \
    popd  && \
    # PyQt5
    tar xzf /downloads/pyqt5.tar.gz --keep-newer-files  && \
    pushd PyQt-gpl-${SPLASH_PYQT_VERSION}  && \
    ${_PYTHON} configure.py -c --qmake "${SPLASH_QT_PATH}/bin/qmake" --verbose \
        --confirm-license \
        --no-designer-plugin \
        -e QtCore \
        -e QtGui \
        -e QtWidgets \
        -e QtNetwork \
        -e QtWebKit \
        -e QtWebKitWidgets \
        -e QtSvg \
        -e QtPrintSupport && \
    make -j ${SPLASH_BUILD_PARALLEL_JOBS} && \
    make install && \
    popd  && \
    # Builds Complete
    popd
}

install_python_deps () {
    # Install python-level dependencies.
    _activate_venv && \
    ${_PYTHON} -m pip install -U pip && \
    ${_PYTHON} -m pip install \
        qt5reactor==0.3 \
        psutil==5.0.0 \
        Twisted==16.1.1 \
        adblockparser==0.7 \
        xvfbwrapper==0.2.8 \
        funcparserlib==0.3.6 \
        Pillow==3.4.2 \
        lupa==1.3 && \
    ${_PYTHON} -m pip install https://github.com/sunu/pyre2/archive/c610be52c3b5379b257d56fc0669d022fd70082a.zip#egg=re2
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

install_flash () {
    apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu trusty multiverse" && \
    apt-get update && \
    apt-get install -y flashplugin-installer
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
        ${SPLASH_QT_PATH}/examples \
        ${SPLASH_QT_PATH}/include \
        ${SPLASH_QT_PATH}/mkspecs \
        ${SPLASH_QT_PATH}/bin \
        ${SPLASH_QT_PATH}/doc \
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
