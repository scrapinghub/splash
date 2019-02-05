FROM scrapinghub/splash:3.3

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

# ADD . /app
RUN pip3 install -r /app/requirements-jupyter.txt
# RUN pip3 freeze

RUN python3 -m splash.kernel install && \
    echo '#!/bin/bash\nSPLASH_ARGS="$@" jupyter notebook --allow-root --no-browser --NotebookApp.iopub_data_rate_limit=10000000000 --port=8888 --ip=0.0.0.0' > start-notebook.sh && \
    chmod +x start-notebook.sh

VOLUME /notebooks
WORKDIR /notebooks

EXPOSE 8888
ENTRYPOINT ["/start-notebook.sh"]
