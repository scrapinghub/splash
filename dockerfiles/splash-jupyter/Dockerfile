FROM scrapinghub/splash:master
# XXX: after each release a new branch named X.Y should be created,
# and FROM should be changed to FROM scrapinghub/splash:X.Y

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
        libsqlite3-dev

# ADD . /app
RUN pip3 install -r /app/requirements-jupyter.txt
# RUN pip3 freeze
RUN mkdir /notebooks & chown splash:splash /notebooks
USER splash:splash

RUN python3 -m splash.kernel install && \
    echo '#!/bin/bash\nSPLASH_ARGS="$@" jupyter notebook --allow-root --no-browser --NotebookApp.iopub_data_rate_limit=10000000000 --port=8888 --ip=0.0.0.0' > /app/start-notebook.sh && \
    chmod +x /app/start-notebook.sh

VOLUME /notebooks
WORKDIR /notebooks

EXPOSE 8888
ENTRYPOINT ["/app/start-notebook.sh"]
