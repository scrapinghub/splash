# Docker file for running Splash tests.
# It needs a base image named "splash";
# build it by running ``docker build -t splash .`` from Splash
# source checkout.
#
# XXX: in future it should be possible to base this image on
# scrapinghub/splash:master.
FROM splash

RUN apt-get update -q && \
    apt-get install --no-install-recommends -y \
        libzmq-dev \
        libsqlite3-0 \
        libssl-dev \
        python3-dev \
        build-essential \
        python3-cryptography \
        python3-openssl \
        libsqlite3-dev

RUN pip install -r /app/requirements-dev.txt
RUN pip install -U pytest-cov coverage codecov pytest-xdist

ADD . /app
RUN pip3 install /app

WORKDIR /app
RUN find . -name \*.pyc -delete
ENTRYPOINT py.test --cov=splash --doctest-modules --duration=50 -v splash