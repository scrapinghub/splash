FROM ubuntu:12.04
ENV DEBIAN_FRONTEND noninteractive

# software-properties-common contains "add-apt-repository" command for PPA conf
RUN apt-get update && apt-get install -y software-properties-common python-software-properties

# add a repo for libre2
RUN add-apt-repository -y ppa:pi-rho/security

RUN sed 's/main$/main universe/' -i /etc/apt/sources.list && \
    apt-get update -q && \
    apt-get install -y netbase ca-certificates python \
        python-dev build-essential \
        xvfb libqt4-webkit python-qt4 libre2-dev \
        git-core python-pip libicu48 liblua5.2-dev

RUN pip install -U pip

# temporary, until lupa is released
RUN pip install 'cython > 0.21'

RUN pip install \
            Twisted==14.0.2 \
            qt4reactor==1.6 \
            psutil==2.1.3 \
            adblockparser==0.3 \
            git+https://github.com/axiak/pyre2.git@382bb743f16722b582cc2bac8fc08ff121dec20e#egg=re2 \
            xvfbwrapper==0.2.4 \
            git+https://github.com/scoder/lupa.git@7a19cda9be9c7df9ab21be88ff9540cb3d2c702c#egg=lupa

ADD . /app
RUN pip install /app

VOLUME ["/etc/splash/proxy-profiles", "/etc/splash/js-profiles", "/etc/splash/filters"]

EXPOSE 8050 8051 5023
ENTRYPOINT [ \
    "/app/bin/splash", \
    "--proxy-profiles-path",  "/etc/splash/proxy-profiles", \
    "--js-profiles-path", "/etc/splash/js-profiles", \
    "--filters-path", "/etc/splash/filters" \
]
