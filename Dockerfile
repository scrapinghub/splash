FROM ubuntu:12.04
ENV DEBIAN_FRONTEND noninteractive

# software-properties-common contains "add-apt-repository" command for PPA conf
# ppa:pi-rho/security is a repo for libre2

RUN sed 's/main$/main universe/' -i /etc/apt/sources.list && \
    apt-get update -q && \
    apt-get install -y \
        software-properties-common \
        python-software-properties && \
    add-apt-repository -y ppa:pi-rho/security && \
    apt-get update -q && \
    apt-get install -y \
        netbase \
        ca-certificates \
        python \
        python-dev \
        build-essential \
        xvfb \
        libqt4-webkit \
        python-qt4 \
        libre2-dev \
        python-pip \
        libicu48 \
        liblua5.2-dev \
        zlib1g-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip install -U pip
RUN pip install \
            Twisted==15.0.0 \
            qt4reactor==1.6 \
            psutil==2.2.1 \
            adblockparser==0.3 \
            https://github.com/axiak/pyre2/archive/master.zip#egg=re2 \
            xvfbwrapper==0.2.4 \
            lupa==1.1 \
            funcparserlib==0.3.6 \
            Pillow==2.7.0 && \
    rm -rf /root/.cache

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
