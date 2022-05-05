#!/usr/bin/env bash
py.test --cov=splash --doctest-modules --durations=50 "$@"
