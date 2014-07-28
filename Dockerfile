FROM ubuntu:14.04
ENV DEBIAN_FRONTEND noninteractive

# software-properties-common contains "add-apt-repository" command for PPA conf
RUN apt-get update && apt-get install -y software-properties-common

RUN add-apt-repository -y ppa:pi-rho/security
RUN sed 's/main$/main universe/' -i /etc/apt/sources.list && \
    apt-get update -q && \
    apt-get install -y netbase ca-certificates python \
        python-dev build-essential \
        xvfb libqt4-webkit python-twisted python-qt4 libre2-dev \
        git-core

ADD https://raw.github.com/pypa/pip/master/contrib/get-pip.py /get-pip.py
RUN python /get-pip.py
RUN pip install \
            qt4reactor==1.0 \
            psutil==2.1.1 \
            adblockparser==0.3 \
            git+https://github.com/axiak/pyre2.git@382bb743f16722b582cc2bac8fc08ff121dec20e#egg=re2 \
            raven==5.0.0 \
            supervisor==3.0 \
            supervisor-stdout==0.1.1
ADD . /app
RUN pip install /app
EXPOSE 8050 8051 5023
CMD ["/usr/local/bin/supervisord", "-c", "/app/supervisord.conf"]
