import pytest
import json
from typing import List, Dict
from datetime import datetime
from controlbhkw.agent import Controlbhkw
from unittest.mock import MagicMock, patch
from typing import Optional

def test_agent(control_agent):
    assert isinstance(control_agent, Controlbhkw)

def test_configure_calls_load_and_subscribe(mock_agent):
    """Ensure configure() loads mappings and subscribes to topics."""
    with patch.object(mock_agent, "_load_topic_mappings") as load_mock, \
         patch.object(mock_agent, "_subscribe_topics") as subscribe_mock:
        
        mock_agent.configure("config", "NEW", {})

        load_mock.assert_called_once()
        subscribe_mock.assert_called_once()


def test_load_topic_mappings_sets_correct_data(mock_agent, mock_rpc_responses):
    """Test that _load_topic_mappings retrieves and stores data correctly."""

    def side_effect(peer, method, plant_name_list_match: Optional[list]=None, topic_type_list_match: Optional[list]=None):
        #assert plant_name_list_match == ["Test"] or topic_type_list_match == ["status"] or topic_type_list_match == ["error"]
        #assert peer == "topicregistry"  # optional sanity check
        if topic_type_list_match == ["status"]:
            method = method + "_status"
        elif topic_type_list_match == ["error"]:
            method = method + "_error"
        else:
            method = method
        return MagicMock(get=lambda timeout: mock_rpc_responses[method])

    mock_agent.vip.rpc.call.side_effect = side_effect

    mock_agent._load_topic_mappings()

    assert mock_agent._unvalidated_to_validated_topic_map == mock_rpc_responses["get_unvalidated_to_validated_commands_map"]
    assert mock_agent._unvalidated_to_feedback_topic_map == mock_rpc_responses["get_unvalidated_to_feedback_map"]
    assert mock_agent._unvalidated_topic_to_validation_rule_map == mock_rpc_responses["get_unvalidated_to_validation_rule_map"]
    assert mock_agent._status_topic_list == mock_rpc_responses["get_list_of_internal_topics_status"]
    assert mock_agent._error_topic_list == mock_rpc_responses["get_list_of_internal_topics_error"]


def test_subscribe_topics_registers_all(mock_agent):
    """Verify that _subscribe_topics subscribes to all topics."""
    mock_agent._unvalidated_to_validated_topic_map = {"t1": "v1", "t2": "v2"}
    mock_agent._status_topic_list = ["status1"]
    mock_agent._error_topic_list = ["error1"]

    mock_agent._subscribe_topics()

    # Two command topics + one status + one error
    assert mock_agent.vip.pubsub.subscribe.call_count == 4


def test_on_command_message_validates_and_publishes(mock_agent):
    """Ensure _on_command_message validates payload and republishes."""
    mock_agent._unvalidated_to_validated_topic_map = {"topic1": "validated/topic1"}
    mock_agent._unvalidated_to_feedback_topic_map = {"topic1": "feedback/topic1"}
    mock_agent._unvalidated_topic_to_validation_rule_map = {"topic1": {"rule_type": "range"}}

    # Patch validate_command
    with patch("controlbhkw.agent.validate_command", return_value=42):

        mock_agent._on_command_message("peer", "sender", "bus", "topic1", {}, 100)

        assert mock_agent.vip.pubsub.publish.call_count == 2
        
        first_call_args, first_call_kwargs = mock_agent.vip.pubsub.publish.call_args_list[0]
        second_call_args, second_call_kwargs = mock_agent.vip.pubsub.publish.call_args_list[1]

        # Now check them individually
        assert first_call_kwargs["topic"] == "validated/topic1"
        assert first_call_kwargs["message"] == 42

        assert second_call_kwargs["topic"] == "feedback/topic1"
        assert second_call_kwargs["message"] == "Validation successfull"


def test_on_command_message_validation_fails(mock_agent, caplog):
    """If validation fails, ensure warning is logged."""
    mock_agent._unvalidated_to_validated_topic_map = {"topic1": "validated/topic1"}
    mock_agent._unvalidated_to_feedback_topic_map = {"topic1": "feedback/topic1"}
    mock_agent._unvalidated_topic_to_validation_rule_map = {"topic1": {"rule_type": "range"}}

    with patch("controlbhkw.agent.validate_command", side_effect=ValueError("Invalid")):
        mock_agent._on_command_message("peer", "sender", "bus", "topic1", {}, 100)

    assert "Validation failed for topic1" in caplog.text

    assert mock_agent.vip.pubsub.publish.call_count == 1
    call_args, call_kwargs = mock_agent.vip.pubsub.publish.call_args_list[0]
    assert call_kwargs["topic"] == "feedback/topic1"
    assert  "Validation failed for topic1" in call_kwargs["message"]


def test_on_status_message_logs_info(mock_agent, caplog):
    """Ensure status messages are handled gracefully."""
    mock_agent._on_status_message("peer", "sender", "bus", "status/topic", {}, {"status": "ok"})
    assert "Received status message" in caplog.text


def test_on_error_message_logs_info(mock_agent, caplog):
    """Ensure error messages are handled gracefully."""
    mock_agent._on_error_message("peer", "sender", "bus", "error/topic", {}, {"error": "fail"})
    assert "Received error message" in caplog.text