import pytest
import mock
import json
import os 
from mqttinterface.agent import Mqttinterface
from volttrontesting.fixtures.volttron_platform_fixtures import PlatformWrapper

def _install_agents_in_volttron_env(vinst:PlatformWrapper, install_mqtt_inteface, install_topic_registry):
    """
    Tests that two agents are installed and running on the platfrom instance
    """
    assert install_mqtt_inteface
    assert vinst.is_agent_running(install_mqtt_inteface)
    assert install_topic_registry
    assert vinst.is_agent_running(install_topic_registry)

def _installed_agents_can_communicate_in_volttron_env(vinst:PlatformWrapper, simple_agent):
    """
    Tests that two agents can communicate using RPC.
    """
    # Call an RPC method on the topic_registry agent
    response = simple_agent.vip.rpc.call(
        "topic_registry",  # identity of installed topic_registry
        "get_external_to_validated_commands_map"  # method exposed by topic_registry
    ).get(timeout=1)
    assert isinstance(response, dict)

    # Call an RPC method on the mqtt agent
    response = simple_agent.vip.rpc.call(
        "mqtt_interface",  # identity of installed mqtt agent
        "test_comms"  # method exposed by mqtt_interface
    ).get(timeout=1)
    assert response == True
    
    # PlatformWrapper.install_agent() runs the agent in a separate process from pytest code.
    # There is no way to get the agent object to call an rpc directly from it