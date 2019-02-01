FROM ubuntu:16.04
ENV DEBIAN_FRONTEND noninteractive

# XXX: this needs to be updated if Qt is updated in provision.sh
ENV PATH="/opt/qt59/5.9.1/gcc_64/bin:${PATH}"

# Install, use dev tools, and then clean up in one RUN transaction
# to minimize image size.
ADD dockerfiles/splash/provision.sh /tmp/provision.sh
ADD dockerfiles/splash/qt-installer-noninteractive.qs /tmp/script.qs

RUN /tmp/provision.sh \
    prepare_install \
    install_deps \
    install_qtwebkit_deps \
    install_official_qt \
    install_qtwebkit \
    install_pyqt5 \
    install_python_deps \
    install_flash \
    install_msfonts \
    install_extra_fonts \
    remove_builddeps \
    remove_extra && \
    rm /tmp/provision.sh


ADD . /app
RUN pip3 install /app
ENV PYTHONPATH $PYTHONPATH:/app

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