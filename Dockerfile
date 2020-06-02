ARG QT_MAJOR_VERSION=5
ARG QT_MINOR_VERSION=14
ARG QT_PATCH_VERSION=1
# docker build has arguments but doesn't have variables
# here we use arguments as variables
ARG QT_SHORT_VERSION=${QT_MAJOR_VERSION}.${QT_MINOR_VERSION}
ARG QT_FULL_VERSION=${QT_SHORT_VERSION}.${QT_PATCH_VERSION}

ARG SPLASH_BUILD_PARALLEL_JOBS=8

# =====================

FROM byrnedo/alpine-curl as qt-downloader

ARG QT_SHORT_VERSION
ARG QT_FULL_VERSION
ENV QT_SHORT_VERSION=${QT_SHORT_VERSION}
ENV QT_FULL_VERSION=${QT_FULL_VERSION}

COPY dockerfiles/splash/download-qt-installer.sh /tmp/download-qt-installer.sh
RUN /tmp/download-qt-installer.sh /tmp/qt-installer.run

# =====================
#
#FROM byrnedo/alpine-curl as qtwebkit-source-downloader
#COPY dockerfiles/splash/download-qtwebkit-source.sh /tmp/download-qtwebkit-source.sh
#RUN /tmp/download-qtwebkit-source.sh /tmp/qtwebkit.tar.xz

# =====================

FROM byrnedo/alpine-curl as qtwebkit-downloader
ARG WEBKIT_URL=https://github.com/qtwebkit/qtwebkit/releases/download/qtwebkit-5.212.0-alpha4/qtwebkit-Linux-RHEL_7_6-GCC-Linux-RHEL_7_6-X86_64.7z
ENV WEBKIT_URL=${WEBKIT_URL}
COPY dockerfiles/splash/download-qtwebkit.sh /tmp/download-qtwebkit.sh
RUN /tmp/download-qtwebkit.sh /tmp/qtwebkit.7z

# =====================

FROM byrnedo/alpine-curl as pyqt5-downloader

# need to update URLs here with new version of Qt
COPY dockerfiles/splash/download-pyqt5.sh /tmp/download-pyqt5.sh
RUN /tmp/download-pyqt5.sh /tmp/sip.tar.gz /tmp/pyqt5.tar.gz /tmp/webengine.tar.gz

# =====================

FROM ubuntu:18.04 as qtbase
ENV DEBIAN_FRONTEND noninteractive

COPY dockerfiles/splash/prepare-install.sh /tmp/prepare-install.sh
RUN /tmp/prepare-install.sh

COPY dockerfiles/splash/install-system-deps.sh /tmp/install-system-deps.sh
RUN /tmp/install-system-deps.sh

COPY dockerfiles/splash/install-fonts.sh /tmp/install-fonts.sh
RUN /tmp/install-fonts.sh

COPY dockerfiles/splash/install-flash.sh /tmp/install-flash.sh
RUN /tmp/install-flash.sh

COPY dockerfiles/splash/install-qtwebengine-deps.sh /tmp/install-qtwebengine-deps.sh
RUN /tmp/install-qtwebengine-deps.sh

COPY dockerfiles/splash/install-qtwebkit-deps.sh /tmp/install-qtwebkit-deps.sh
RUN /tmp/install-qtwebkit-deps.sh

# =====================

FROM qtbase as qtbuilder
ENV DEBIAN_FRONTEND noninteractive

COPY --from=qt-downloader /tmp/qt-installer.run /tmp/

ARG DISPLAY

ARG QT_MAJOR_VERSION
ARG QT_MINOR_VERSION
ARG QT_PATCH_VERSION
ARG QT_SHORT_VERSION
ARG QT_FULL_VERSION
ENV QT_MAJOR_VERSION=${QT_MAJOR_VERSION}
ENV QT_MINOR_VERSION=${QT_MINOR_VERSION}
ENV QT_PATCH_VERSION=${QT_PATCH_VERSION}
ENV QT_SHORT_VERSION=${QT_SHORT_VERSION}
ENV QT_FULL_VERSION=${QT_FULL_VERSION}

COPY dockerfiles/splash/qt-installer-noninteractive.qs /tmp/script.qs
COPY dockerfiles/splash/run-qt-installer.sh /tmp/run-qt-installer.sh
RUN /tmp/run-qt-installer.sh /tmp/qt-installer.run /tmp/script.qs

ENV PATH="/opt/qt-${QT_SHORT_VERSION}/${QT_FULL_VERSION}/gcc_64/bin:${PATH}"

# install qtwebkit
COPY --from=qtwebkit-downloader /tmp/qtwebkit.7z /tmp/
COPY dockerfiles/splash/install-qtwebkit.sh /tmp/install-qtwebkit.sh
RUN /tmp/install-qtwebkit.sh /tmp/qtwebkit.7z

# =====================

FROM qtbuilder as qtwebkitbuilder-base

COPY dockerfiles/splash/install-qtwebkit-build-deps.sh /tmp/install-qtwebkit-build-deps.sh
COPY dockerfiles/splash/create-package.sh /tmp/create-package.sh
RUN /tmp/install-qtwebkit-build-deps.sh

# =====================

#FROM qtbuilder as qtwebkitbuilder
#COPY --from=qtwebkit-downloader /tmp/qtwebkit.tar.xz /tmp/
#
#COPY dockerfiles/splash/install-qtwebkit-build-deps.sh /tmp/install-qtwebkit-build-deps.sh
#RUN /tmp/install-qtwebkit-build-deps.sh
#
#COPY dockerfiles/splash/build-qtwebkit.sh /tmp/build-qtwebkit.sh
#RUN /tmp/build-qtwebkit.sh /tmp/qtwebkit.tar.xz

# =====================

FROM qtbase as splash-base

COPY dockerfiles/splash/install-system-splash-deps.sh /tmp/install-system-splash-deps.sh
RUN /tmp/install-system-splash-deps.sh

ARG QT_SHORT_VERSION
ARG QT_FULL_VERSION

COPY --from=qtbuilder \
    /opt/qt-${QT_SHORT_VERSION}/${QT_FULL_VERSION}/gcc_64 \
    /opt/qt-${QT_SHORT_VERSION}/${QT_FULL_VERSION}/gcc_64

#RUN ls -l /opt/qt-${QT_SHORT_VERSION}/${QT_FULL_VERSION}/gcc_64/lib
ENV PATH="/opt/qt-${QT_SHORT_VERSION}/${QT_FULL_VERSION}/gcc_64/bin:${PATH}"
ENV LD_LIBRARY_PATH="/opt/qt-${QT_SHORT_VERSION}/${QT_FULL_VERSION}/gcc_64/lib:$LD_LIBRARY_PATH"

# =====================

FROM splash-base as qt5-builder

ARG SPLASH_BUILD_PARALLEL_JOBS
ENV SPLASH_BUILD_PARALLEL_JOBS=${SPLASH_BUILD_PARALLEL_JOBS}

COPY --from=pyqt5-downloader /tmp/sip.tar.gz /tmp/
COPY --from=pyqt5-downloader /tmp/pyqt5.tar.gz /tmp/
COPY dockerfiles/splash/install-pyqt5.sh /tmp/install-pyqt5.sh
RUN /tmp/install-pyqt5.sh /tmp/sip.tar.gz /tmp/pyqt5.tar.gz

COPY --from=pyqt5-downloader /tmp/webengine.tar.gz /tmp/
COPY dockerfiles/splash/install-pyqtwebengine.sh /tmp/install-pyqtwebengine.sh
RUN /tmp/install-pyqtwebengine.sh /tmp/webengine.tar.gz

# =====================

FROM splash-base as splash

ARG QT_MAJOR_VERSION
ENV QT_MAJOR_VERSION=${QT_MAJOR_VERSION}

COPY dockerfiles/splash/install-python-splash-deps.sh /tmp/install-python-splash-deps.sh
RUN /tmp/install-python-splash-deps.sh

# FIXME: use virtualenv
COPY --from=qt5-builder /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages
COPY --from=qt5-builder /usr/local/lib/python3.6/dist-packages /usr/local/lib/python3.6/dist-packages

COPY . /app
RUN pip3 install /app
ENV PYTHONPATH $PYTHONPATH:/app
#ENV QT_DEBUG_PLUGINS=1

# Chromium refuses to start under root
RUN groupadd -r splash && useradd --no-log-init --create-home -r -g splash splash
RUN chown -R splash:splash /app
USER splash:splash


VOLUME [ \
    "/etc/splash/proxy-profiles", \
    "/etc/splash/js-profiles", \
    "/etc/splash/filters", \
    "/etc/splash/lua_modules" \
]

EXPOSE 8050

ENTRYPOINT [ \
    "python3", \
    "/app/bin/splash", \
    "--proxy-profiles-path", "/etc/splash/proxy-profiles", \
    "--js-profiles-path", "/etc/splash/js-profiles", \
    "--filters-path", "/etc/splash/filters", \
    "--lua-package-path", "/etc/splash/lua_modules/?.lua" \
]
