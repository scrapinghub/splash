#!/usr/bin/env bash
docker build -t splash-tests -f dockerfiles/tests/Dockerfile . && \
docker run -it splash-tests "$@"