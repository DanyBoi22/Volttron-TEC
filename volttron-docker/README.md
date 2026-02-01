# User Guide for Dockerised version of the Platform # 

## Content ## 
This folder contains:
- volttron_home: Full copy of a home folder used in the volltron instance at TEC. The agents and dependencies are preinstalled.
- Dockerfile: code to create an image and run the container.
- entrypoint.sh: script to install the agent's dependencies after the volttron is installed. Used by Dockerfile. 
- this Readme

## For Windows
1. Install Ubuntu LTS (I use 24.04.1 LTS)
2. Follow the installation instructions for Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/

For better user experience with VS on Windows (in case used) connect it: https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-vscode

## Creating Container
1. For creating volttron image run in the ubuntu:
```docker build -t volttronimage .```
2. For Running the container in the background mode with mounted directory:
```docker run -d --name volttrondocker -v ~/volttron-docker/volttron_home:/home/volttron/.volttron -p 22916:22916 -p 8080:8080 volttronimage```
3. For entering the containers bash directly:
```sudo docker exec -it volttrondocker /bin/bash```

## Tipps for VOLTTRON-DOCKER
Some essential commands and tipps to use the container and docker in general:
- Show logs of the container: ```docker logs volttrondocker```
- Show all Images isntalled: ```docker images```
- Remove an image: ```docker rmi volttronimage```
- Show all Containers: ```docker ps -a```
- Remove a container: ```docker rm volttrondocker```
- The mounted directory is at ```/home/volttron/.volttron```
- The actual volttron directory that runs in the container is at ```/volttron```
- The volttron.log is saved into the mounted directory
- The packages with agents are in the mounted directory at ```AgentPackages/```
- The platform data for installed agents are in the mounted directory at ```agents/```
- The useful Scripts are at ```/volttron/scripts```
- To run the commands like packaging an agent etc you have to be in the mounted directory aka: ```$VOLTTRON_HOME```.
For Example:
  1. ```cd $VOLTTRON_HOME```
  2. ```vpkg init AgentPackages/TestAgent test```
- To run the scripts you have to use the full path for example:
```python3 /volttron/scripts/install-agent.py -s /home/volttron/.volttron/AgentPackages/TestAgent/ c /home/volttron/.volttron/AgentPackages/TestAgent/config/ -t test```
- To be able to utilise IDEs properly i would recommend to install a local copy of volttron and select its python env (volttron/env/bin/python) as an interpretor

- IMPORTANT:
For some reason dockerised Volttron does not run like its local instance. For example Errors in VIP are being passed as Strings and not Int. You will encounter this problem if you try to rpc an agent that is not installed yet. Tt will kill the intire VIP

## Common errors:
The container exists as soon as started with code 127: most likely the entrypoint helper script is broken due to Windows encoding. This happens especially if the folder is copied from Windows to WSL.
Inside the host system, run:
 1. ```sudo apt install dos2unix```
 2. Then use dos2unix on the folder
 3. Create new image
