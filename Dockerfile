FROM ubuntu:16.04
ENV DEBIAN_FRONTEND noninteractive

#RUN /tmp/provision.sh prepare_install
RUN sed 's/main$/main universe/' -i /etc/apt/sources.list && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        curl \
        software-properties-common \
        python3-software-properties


#RUN /tmp/provision.sh install_msfonts

#RUN /tmp/provision.sh install_builddeps
RUN add-apt-repository -y ppa:pi-rho/security && \
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


RUN apt-get install -y --no-install-recommends \
        wget \
        netbase \
        ca-certificates \
        xvfb \
        pkg-config \
        python3 \
        zlib1g \
        libfontconfig1-dev \
        libicu-dev \
        libpng12-dev \
        libxslt1-dev \
        libxml2-dev \
        libhyphen-dev

RUN mkdir -p /downloads && \
    mkdir -p /builds && \
    chmod a+rw /downloads && \
    chmod a+rw /builds

#RUN wget http://download.qt.io/official_releases/online_installers/qt-unified-linux-x64-online.run
RUN cd downloads && wget http://download.qt.io/official_releases/qt/5.8/5.8.0/qt-opensource-linux-x64-5.8.0.run
RUN chmod +x /downloads/qt-opensource-linux-x64-5.8.0.run

RUN apt-get install -y libxcomposite-dev libxrender-dev libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

ADD dockerfiles/splash/qt-installer-noninteractive.qs /tmp/script.qs
RUN xvfb-run /downloads/qt-opensource-linux-x64-5.8.0.run \
    --script /tmp/script.qs \
    | egrep -v '\[[0-9]+\] Warning: (Unsupported screen format)|((QPainter|QWidget))'

#RUN /tmp/provision.sh install_deps
#RUN apt-add-repository -y ppa:beineri/opt-qt58-xenial && \
#    apt-get update -q && \
#    apt-get install -y --no-install-recommends \
#        netbase \
#        ca-certificates \
#        xvfb \
#        pkg-config \
#        python3 \
#        qt58base \
#        qt58svg \
#        zlib1g

ENV PATH="/opt/qt58/5.8/gcc_64/bin:${PATH}"

RUN ls -lh /opt/qt58
RUN ls -lh /opt/qt58/5.8/gcc_64/bin
RUN qmake -query QT_INSTALL_PREFIX
#RUN cat /opt/qt58/InstallationLog.txt

#RUN mkdir -p /downloads && \
#    mkdir -p /builds && \
#    chmod a+rw /downloads && \
#    chmod a+rw /builds

RUN curl -L -o /downloads/qtwebkit.tar.xz https://github.com/annulen/webkit/releases/download/qtwebkit-tp5/qtwebkit-tp5-qt58-linux-x64.tar.xz && \
    ls -lh /downloads && \
    cd /builds && \
    tar xvfJ /downloads/qtwebkit.tar.xz --keep-newer-files
RUN ls -lh /builds/qtwebkit-tp5-qt58-linux-x64/
RUN apt-get install -y rsync
RUN rsync -aP /builds/qtwebkit-tp5-qt58-linux-x64/* `qmake -query QT_INSTALL_PREFIX`

RUN ls -lh `qmake -query QT_INSTALL_PREFIX`

#RUN apt install build-essential perl python ruby flex gperf bison cmake \
#    ninja-build libfontconfig1-dev libicu-dev libsqlite3-dev zlib1g-dev libpng12-dev \
#    libjpeg-dev libxslt1-dev libxml2-dev libhyphen-dev

#RUN apt-get install -y libfontconfig1-dev libicu-dev libicu55 \
#    libpng12-dev libxslt1-dev libxml2-dev libhyphen-dev

# Install, use dev tools, and then clean up in one RUN transaction
# to minimize image size.
ADD dockerfiles/splash/provision.sh /tmp/provision.sh

#RUN /tmp/provision.sh install_extra_fonts
RUN /tmp/provision.sh install_qtwebkit
RUN /tmp/provision.sh install_pyqt5
RUN /tmp/provision.sh install_python_deps
#RUN /tmp/provision.sh install_flash
#RUN /tmp/provision.sh remove_builddeps

RUN apt-get install -y libgbm1 libxcb-image0 libxcb-icccm4 libxcb-keysyms1 libxcb-render-util0 libxi6
RUN ls -lh `qmake -query QT_INSTALL_PREFIX`/lib
RUN ldd `qmake -query QT_INSTALL_PREFIX`/lib/libQt5XcbQpa.so.5.8.0
#RUN echo `qmake -query QT_INSTALL_PREFIX`/lib > /etc/ld.so.conf.d/qt-5.8.conf

#RUN /tmp/provision.sh \
#    prepare_install \
#    install_msfonts \
#    install_builddeps \
#    install_deps \
#    install_extra_fonts \
#    install_pyqt5 \
#    install_python_deps \
#    install_flash \
#    remove_builddeps && \
#    rm /tmp/provision.sh

ADD . /app
RUN pip3 install /app
ENV PYTHONPATH $PYTHONPATH:/app

VOLUME [ \
    "/etc/splash/proxy-profiles", \
    "/etc/splash/js-profiles", \
    "/etc/splash/filters", \
    "/etc/splash/lua_modules" \
]

EXPOSE 8050 5023

ENTRYPOINT [ \
    "python3", \
    "/app/bin/splash", \
    "--proxy-profiles-path", "/etc/splash/proxy-profiles", \
    "--js-profiles-path", "/etc/splash/js-profiles", \
    "--filters-path", "/etc/splash/filters", \
    "--lua-package-path", "/etc/splash/lua_modules/?.lua" \
]