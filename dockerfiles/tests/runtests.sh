#!/usr/bin/env bash
py.test --cov=splash --doctest-modules --durations=50 "$@" && \
if [ -n "${TRAVIS}" ]; then
    codecov
fi;