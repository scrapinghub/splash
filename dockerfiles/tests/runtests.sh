#!/usr/bin/env bash
py.test --cov=splash --doctest-modules --duration=50 splash "$@" && \
if [ -n "${TRAVIS}" ]; then
    codecov
fi;