import pytest
import tempfile
import os
from controlbhkw.agent import Controlbhkw
from unittest.mock import MagicMock


@pytest.fixture
def control_agent():
    """
    Returns an agent ._.
    """
    agent = Controlbhkw({})
    yield agent
    # Cleanup afterwards if needed
    #agent._clean_up()

@pytest.fixture
def mock_agent():
    """Fixture to create a Controlbhkw instance with mocked dependencies."""
    config = {}
    agent = Controlbhkw(config)

    # Mock vip attributes
    agent.vip = MagicMock()
    agent.vip.config.set_default = MagicMock()
    agent.vip.config.subscribe = MagicMock()
    agent.vip.rpc.call = MagicMock()
    agent.vip.pubsub.subscribe = MagicMock()
    agent.vip.pubsub.publish = MagicMock()

    return agent


@pytest.fixture
def mock_rpc_responses():
    """Default fake RPC responses for topicregistry methods."""
    return {
        "get_unvalidated_to_validated_commands_map": {"unvalidated/topic": "validated/topic"},
        "get_unvalidated_to_feedback_map": {"unvalidated/topic": "feedback/topic"},
        "get_unvalidated_to_validation_rule_map": {"unvalidated/topic": [{"rule": "number"}]},
        "get_list_of_internal_topics_status": ["status/topic"],
        "get_list_of_internal_topics_error": ["error/topic"]
    }