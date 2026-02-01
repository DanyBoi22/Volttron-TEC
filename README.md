# VOLTTRON-TEC
Prototype of a VOLTTRON-based experimentation platform. Developed for use at TEC as part of a bachelor's thesis.

## Content
This repository has three different subfolders.

- The AgentPackages folder contains the packages with the agent code that are ready to be installed in VOLTTRON.
You can find the installation guide in the Readme inside the subfolder.

- volttron-docker contains everything you need to install and run a Docker image on the platform.
You can find the installation guide in the Readme inside the subfolder.

- volttron-gui contains files for the user interface.
You can find more information and installation guides in the subfolder.

## VOLTTRON Installation
The experimentation platform is implemented as system of agents in the VOLTTRON platform, therefore VOLTTRON is essential. 
There are 2 ways to install VOLTTRON. For both you will need Linux System or WSL 2 on Windows. 

- Local installation: Follow the official guide https://volttron.readthedocs.io/en/develop/introduction/platform-install.html.

- Docker Image: Follow the guide provided in the volttron-docker subfolder.

## General Tipps and Quick Start (For Localy Installed VOLTTRON)
- VOLTTRON official documentation is a must read to use the platform: https://volttron.readthedocs.io/en/main/ 

- After Installation you need to activate the environment and start the VOLTTRON.
Start the volttron: 
    1.	Source ./volttron/env/bin/activate (to start the volttron environment)
    2.	./start-volttron

- On the first platform Installation the Agents will not be installed so you need to install them manually.    
Install an agent:
    1. Copy the AgentPackages subfolder into the VOLTTRON base directory
    2. In the volttron environment: python scripts/install-agent.py -s <Base directory of the agent> -c <Path to the config file> -t <Tag of the agent> 

    Example: python scripts/install-agent.py -s AgentPackages/TestAgent/ -c AgentPackages/TestAgent/config -t testagent

    or use the install_script.py provided in the subfolder, but make sure to use correct VOLTTRON_HOME Path in the script.
    
    3. Each agent has config file in the agent base directory. Make sure that if the config contains any variables with path, that this path matches your installed system path.

- On the first platform installation the Agents will not start automatically, so you need to start them manually first.
Start/stop the agent:
	In the volttron environment
    1.	Vctl list / status: list with all installed agents
    2.	for each instaleld agent: vctl start <uuid> / --name <name> / --tag <tag> : start the chosen agent
    3.	vctl stop -…- : stop the chosen agent 

## Developing new agents ##  
All you need to start can be found in the official documentation: https://volttron.readthedocs.io/en/main/developing-volttron/developing-agents/agent-development.html

## Installing New Dependencies ##
If you want to use your own libraries you will need to install them as packages in the VOLTTRON env.
Let’s say your .py code lives in AgentPackages/shared/metadata_mixin.py. You want to install this into an agent as a dependency.
1.	Restructure it into a pip-installable package:
shared/ 
└──  metadata/
├── setup.py
├── README.nd
    └──  metadata/
            ├── __init__.py 
            └──  metadata_mixin.py 
2.	Fill setup.py:
from setuptools import setup, find_packages
setup(
    name='volttron-metadata',
    version='0.1',
    packages=find_packages(),
    description='Shared metadata mixin and tools for Volttron agents',
    author=My Name',
    install_requires=[],
)
3.	Install the new package in the environment:
pip install -e ./agents/shared/metadata
4.	Your agent will now be able to import the new package:
from metadata.metadata_mixin import MetadataMixin

## Testing ## 
Unit tests are very useful to test the agent's functions, because they do not require an agent's installation and start. The communication with paltform or other agents can be mocked. 

To test communication of multiple agents, you can run integration tests with simulated environment. For more information see https://volttron.readthedocs.io/en/main/developing-volttron/developing-agents/writing-agent-tests.html#writing-agent-tests or see the examples in the infrastructure agents.

1.	Create a folder for tests inside your agent like Example with ExperimentManager Agent:
ExperimentManager/ 
├── expmanager/
 │    ├── __init__.py 
 │     └──  agent.py 
├── tests/
 │    ├── __init__.py
 │    ├── conftest.py
 │     └──  test_expmanager.py
 └── [Other files]
2.	Run “pytest” in the agent folder

## Connect to TEC MQTT Brocker ##

To be able to get sensor data from the plants and send the control commands you need to connect to the Cybus middleware. You can communicate with sybus via paho MQTT Client (or any other MQTT Client). 
You must have an MQTT user profile authorised by TEC.
Within HAW Net: As long as you are connected to eduroam or use HAW VPN you can access the MQTT Broker on its server address and 1883 port. 
If you try to access the broker from outside HAW Net you need to use port 8883 and have TSL configured.
