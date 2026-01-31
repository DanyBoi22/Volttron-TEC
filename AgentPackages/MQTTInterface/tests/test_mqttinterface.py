import pytest
import mock
from volttron.platform.vip.agent import Agent
from volttrontesting.utils.utils import AgentMock
import json
import os 
from mqttinterface.agent import Mqttinterface
from unittest.mock import MagicMock

def test_agent(mqtt_interface):
    assert isinstance(mqtt_interface, Mqttinterface)

def mock_metadata_rpc():
    pass

@mock.patch.object(Mqttinterface, '_on_metadata_config_update', mock_metadata_rpc)
def test_mock_agent():
    Mqttinterface.__bases__ = (AgentMock.imitate(Agent, Agent()),)
    agent = Mqttinterface({})
    assert isinstance(agent, Mqttinterface)

def mock_command_mappings():
    return {"ext/command/topic": "int/command/topic"}

def mock_status_mappings():
    return {"ext/status/topic": "int/status/topic"}

def test_mock_retrieve_mappings_success(mqtt_interface: Mqttinterface):
    # Patch the RPC call chain
    mqtt_interface.vip = mock.MagicMock()
    mqtt_interface.vip.rpc.call.side_effect = [
        mock.MagicMock(get=mock.MagicMock(return_value=mock_command_mappings())),
        mock.MagicMock(get=mock.MagicMock(return_value=mock_status_mappings()))
    ]
    mqtt_interface._retrieve_mappings()

    assert "ext/command/topic" in mqtt_interface._external_to_internal_commands_map.keys()
    assert "int/command/topic" in mqtt_interface._external_to_internal_commands_map.values()
    assert "ext/status/topic" in mqtt_interface._external_to_internal_status_map.keys()
    assert "int/status/topic" in mqtt_interface._external_to_internal_status_map.values()

def test_internal_to_mqtt_publishes_message(mqtt_interface: Mqttinterface):
    # Arrange
    mqtt_interface._mqtt_client = MagicMock()
    external_topic = "external/topic"
    callback = mqtt_interface._republish_internal_to_external(external_topic)
    
    # Simulate internal Volttron message
    message = {"key": "value"}
    headers = {"target": "me", "source": "OTHER_AGENT", "timestamp": "today"}  # Not loopback
    callback(peer="peer", sender="sender", bus="pubsub", topic="internal/topic", headers=headers, message=message)
    
    # Assert MQTT publish was called with correct args
    payload = json.dumps(message)
    mqtt_interface._mqtt_client.publish.assert_called_once_with(external_topic, payload)

class FakeMsg:
    topic = "external/status"
    payload = b'{"status":"ok"}'

def test_on_message_publishes_to_internal(mqtt_interface: Mqttinterface):
    mqtt_interface.vip = MagicMock()
    mqtt_interface._external_to_internal_status_map = {"external/status": "internal/status"}
    
    # Simulate getting a message from mqtt broker, this message is pushed to the message queue
    msg = FakeMsg()
    mqtt_interface._on_message(client=None, userdata=None, msg=msg)
    
    # retrieve the message from  the queue and republish it
    ret_msg = mqtt_interface._incoming_message_queue.get() 
    mqtt_interface._republish_external_to_internal(ret_msg)

    # Assert pubsub.publish was called correctly
    args, kwargs = mqtt_interface.vip.pubsub.publish.call_args
    #print(f"kwargs: {kwargs}")
    assert args[0] == "pubsub"
    assert args[1] == "internal/status"
    assert "source" in args[2]
    assert '{"status":"ok"}' in args[3]

def test_on_message_ignores_unmapped_topics(mqtt_interface: Mqttinterface):
    mqtt_interface.vip = MagicMock()
    mqtt_interface._external_to_internal_status_map = {}  # no mapping
    
    msg = type("FakeMsg", (), {"topic": "unknown/topic", "payload": b"data"})
    mqtt_interface._on_message(client=None, userdata=None, msg=msg)
    
    mqtt_interface.vip.pubsub.publish.assert_not_called()