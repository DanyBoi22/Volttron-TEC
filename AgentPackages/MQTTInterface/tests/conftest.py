import pytest
import os
from mqttinterface.agent import Mqttinterface
from volttrontesting.fixtures.volttron_platform_fixtures import volttron_instance_zmq, PlatformWrapper

@pytest.fixture
def sample_config():
    return {
        "mqtt": {
            "broker_adress": "localhost",
            "broker_port": 1883,
            "username": "user",
            "password": "pass"
        },
        "topic_registry_identity": "registry"
    }

@pytest.fixture
def mqtt_interface(sample_config):
    """
    Returns an Mqttinterface agent.
    """
    agent = Mqttinterface(sample_config)
    yield agent
    # Cleanup if needed
    #agent._clean_up()

@pytest.fixture(scope="module")
def vinst(volttron_instance_zmq):
    # starts a clean Volttron instance for test modules
    return volttron_instance_zmq

# Here we create a really simple agent which has only the core functionality, which we can use for Pub/Sub
# or JSON/RPC
@pytest.fixture(scope="module")
def simple_agent(request, vinst:PlatformWrapper):
    # Create the simple agent
    agent = vinst.build_agent()

    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent

@pytest.fixture(scope="module")
def install_mqtt_inteface(vinst:PlatformWrapper, config=None):
    mqtt_interface = os.path.abspath("/home/user/volttron/agents/MQTTInterfaceAgent/")

    # install mqtt interface
    mqtt_interface_uuid = vinst.install_agent(
        agent_dir=mqtt_interface,
        start=True, #volttron_instance.start_agent(agent)
        vip_identity="mqtt_interface",
        config_file=config)

    yield mqtt_interface_uuid
    
@pytest.fixture(scope="module")
def install_topic_registry(vinst:PlatformWrapper):
    topic_registry = os.path.abspath("/home/user/volttron/agents/TopicRegistryAgent/")

    # install topic registry
    topic_registry_uuid = vinst.install_agent(
        agent_dir=topic_registry,
        start=True,
        vip_identity="topic_registry")

    yield topic_registry_uuid
