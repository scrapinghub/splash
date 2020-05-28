#!/usr/bin/env bash
_PYTHON=python3

install_python_deps () {
    # Install python-level dependencies.
    ${_PYTHON} -m pip install -U pip setuptools six && \
    ${_PYTHON} -m pip install \
        qt5reactor==0.5 \
        psutil==5.0.0 \
        "Twisted[http2]==19.7.0" \
        adblockparser==0.7 \
        xvfbwrapper==0.2.9 \
        funcparserlib==0.3.6 \
        Pillow==5.4.1 \
        attrs==18.2.0 \
        lupa==1.3 && \
    ${_PYTHON} -m pip install https://github.com/sunu/pyre2/archive/c610be52c3b5379b257d56fc0669d022fd70082a.zip#egg=re2
}

install_python_deps
