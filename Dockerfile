FROM ubuntu:12.04
ENV DEBIAN_FRONTEND noninteractive

# Install, use dev tools, and then clean up in one RUN transaction
# to minimize image size.

# software-properties-common contains "add-apt-repository" command for PPA conf
# ppa:pi-rho/security is a repo for libre2

RUN sed 's/main$/main universe/' -i /etc/apt/sources.list && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        software-properties-common \
        python-software-properties && \
    add-apt-repository -y ppa:pi-rho/security && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends \
        netbase \
        ca-certificates \
        xvfb \
        pkg-config \
        python \
        libqt4-webkit \
        python-qt4 \
        python-pip \
        libre2 \
        libicu48 \
        liblua5.2 \
        zlib1g && \
    pip install -U pip && \

    apt-get install -y --no-install-recommends \
        python-dev \
        build-essential \
        libre2-dev \
        liblua5.2-dev \
        libsqlite3-dev \
        zlib1g-dev && \

    /usr/local/bin/pip install --no-cache-dir \
        Twisted==15.0.0 \
        qt4reactor==1.6 \
        psutil==2.2.1 \
        adblockparser==0.3 \
        https://github.com/axiak/pyre2/archive/master.zip#egg=re2 \
        xvfbwrapper==0.2.4 \
        lupa==1.1 \
        funcparserlib==0.3.6 \
        Pillow==2.7.0 && \

    apt-get remove -y --purge \
        python-dev \
        build-essential \
        libre2-dev \
        liblua5.2-dev \
        zlib1g-dev \
        libc-dev && \
    apt-get remove -y --purge gcc cpp binutils perl && \
    apt-get autoremove -y && \
    apt-get clean -y && \
    rm -rf /usr/share/perl /usr/share/perl5 /usr/share/man /usr/share/info /usr/share/doc && \
    rm -rf /var/lib/apt/lists/*


ADD . /app
RUN pip install /app

VOLUME ["/etc/splash/proxy-profiles", "/etc/splash/js-profiles", "/etc/splash/filters", "/etc/splash/lua_modules"]

EXPOSE 8050 8051 5023

ENTRYPOINT [ \
    "/app/bin/splash", \
    "--proxy-profiles-path",  "/etc/splash/proxy-profiles", \
    "--js-profiles-path", "/etc/splash/js-profiles", \
    "--filters-path", "/etc/splash/filters", \
    "--lua-package-path", "/etc/splash/lua_modules/?.lua" \
]
