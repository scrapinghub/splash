FROM ubuntu:14.04
ENV DEBIAN_FRONTEND noninteractive

# Install, use dev tools, and then clean up in one RUN transaction
# to minimize image size.
ADD dockerfiles/splash/provision.sh /tmp/provision.sh


RUN /tmp/provision.sh \
    prepare_install \
    install_msfonts \
    install_builddeps \
    install_deps \
    install_extra_fonts \
    install_pyqt5 \
    install_python_deps \
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

EXPOSE 8050 8051 5023

ENTRYPOINT [ \
    "python3", \
    "/app/bin/splash", \
    "--proxy-profiles-path",  "/etc/splash/proxy-profiles", \
    "--js-profiles-path", "/etc/splash/js-profiles", \
    "--filters-path", "/etc/splash/filters", \
    "--lua-package-path", "/etc/splash/lua_modules/?.lua" \
]
