#!/usr/bin/env bash
docker build -t splash-tests -f dockerfiles/tests/Dockerfile . && \
docker run -it -p8050:8050 --rm --entrypoint "/app/bin/splash" splash-tests "$@"