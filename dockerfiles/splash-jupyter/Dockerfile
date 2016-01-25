FROM scrapinghub/splash:master
# XXX: after each release a new branch named X.Y should be created,
# and FROM should be changed to FROM scrapinghub/splash:X.Y

# Install, use dev tools, and then clean up in one RUN transaction
# to minimize image size.

RUN apt-get update -q && \
    apt-get install --no-install-recommends -y \
        libzmq3 \
        libsqlite3-0 && \

    apt-get install --no-install-recommends -y \
        python3-dev \
        build-essential \
        libzmq3-dev \
        libsqlite3-dev && \
    pip3 install \
        ipython[notebook]==4.0.3 && \
    apt-get remove -y --purge \
        python3-dev \
        build-essential \
        libzmq3-dev \
        libsqlite3-dev \
        libc-dev && \
    apt-get remove -y --purge gcc cpp binutils perl && \
    apt-get autoremove -y && \
    apt-get clean -y && \
    rm -rf /usr/share/perl /usr/share/perl5 /usr/share/man /usr/share/info /usr/share/doc && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m splash.kernel install && \
    echo 'ipython notebook --no-browser --port=8888 --ip=*' > start-ipython.sh && \
    chmod +x start-ipython.sh

VOLUME /notebooks
WORKDIR /notebooks

EXPOSE 8888
ENTRYPOINT /start-ipython.sh
