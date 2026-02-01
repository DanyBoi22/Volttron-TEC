# out of all tested 3.10s "3.10.18-bookworm" is the only working
# python:3.8.18-bullseye is also compatible but too old
FROM python:3.10.18-bookworm

# system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential python3-dev python3-venv openssl libssl-dev libevent-dev git && \
    rm -rf /var/lib/apt/lists/*

# Clone VOLTTRON code
RUN git clone https://github.com/VOLTTRON/volttron --branch main

# Create a dedicated volttron user with UID 1000 and group with GID 1000.
# home /home/volttron, in that group and shell
# becuase bootstraping refuses to run in root mode and also to be able to mount external directory 
RUN groupadd -g 1000 volttron && \
    useradd  -u 1000 -g 1000 -m -d /home/volttron -s /bin/bash volttron && \
    chown -R volttron:volttron /volttron

# Copy the entrypoint helper script into the image
# The script runs installation of custom modules in the volttron env
COPY entrypoint.sh /volttron/entrypoint.sh
RUN chown volttron:volttron /volttron/entrypoint.sh

# Switch to the volttron user and make the working directory
USER volttron
WORKDIR /volttron

# Setup virtual environment for ZMQ
RUN python3 bootstrap.py --testing
RUN . env/bin/activate
# Install deps for Backend
RUN env/bin/pip install flask jmespath paho-mqtt transitions pytest pytest-cov mock APScheduler==3.6.3 pytz
#volttrontesting 

# Put Volttron commands on PATH
ENV PATH="/volttron/env/bin:${PATH}"

# Set up a persistent VOLTTRON_HOME (mount this from the host)
USER root
ENV VOLTTRON_HOME=/home/volttron/.volttron
RUN mkdir -p $VOLTTRON_HOME && \
    chown -R volttron:volttron $VOLTTRON_HOME
USER volttron

# Expose Ports
# VIP port
EXPOSE 22916
# Web port  
EXPOSE 8000

# give explicit rights to the entrypoint script
RUN chmod +x /volttron/entrypoint.sh
# Start params "/home/volttron/.volttron/volttron.log" to save logs in the mounted folder
ENTRYPOINT ["/volttron/entrypoint.sh", "-vv", "-l", "$VOLTTRON_HOME/volttron.log"]