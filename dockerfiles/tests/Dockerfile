# Docker file for running Splash tests.
# It needs a base image named "splash";
# build it by running ``docker build -t splash .`` from Splash
# source checkout.
#
# XXX: in future it should be possible to base this image on
# scrapinghub/splash:master.
FROM splash

USER root:root
RUN apt-get update -q && \
    apt-get install --no-install-recommends -y \
        libzmq3-dev \
        libsqlite3-0 \
        libssl1.0-dev \
        python3-dev \
        build-essential \
        python3-cryptography \
        python3-openssl \
        libsqlite3-dev \
        git

# ADD . /app
RUN pip3 install -r /app/requirements-dev.txt
RUN pip3 install -U pytest-cov coverage codecov pytest-xdist

ADD . /app
RUN pip3 install /app

WORKDIR /app
RUN find . -name \*.pyc -delete

RUN chown -R splash:splash /app
USER splash:splash
ENTRYPOINT ["/app/dockerfiles/tests/runtests.sh"]
CMD ["splash"]