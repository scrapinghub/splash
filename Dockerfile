FROM ubuntu:precise
ENV DEBIAN_FRONTEND noninteractive    
RUN sed 's/main$/main universe/' -i /etc/apt/sources.list && \        
    apt-get update -q && \        
    apt-get install -y netbase ca-certificates python \
        python-dev build-essential libicu48 \
        xvfb libqt4-webkit python-twisted python-qt4
ADD https://raw.github.com/pypa/pip/master/contrib/get-pip.py /get-pip.py        
RUN python /get-pip.py 
ADD . /app
RUN pip install qt4reactor psutil raven supervisor supervisor-stdout
RUN pip install /app
EXPOSE 8050 8051 5023
CMD ["/usr/local/bin/supervisord", "-c", "/app/supervisord.conf"] 
