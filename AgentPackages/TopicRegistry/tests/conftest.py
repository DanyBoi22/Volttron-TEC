import pytest
from topicregistry.agent import TopicRegistry
from volttrontesting.fixtures.volttron_platform_fixtures import volttron_instance_zmq, PlatformWrapper

@pytest.fixture
def sample_registry():
    return {
        "Plants topics data": {
            "PlantA": {
                "internal/command/one": {
                    "type": "command",
                    "topics": {
                        "validated": "internal/command/true1",
                        "external": "external/topic/one",
                        "feedback": "command/feedback/one"
                    },
                    "meta": {
                        "description": "Pump status"
                        },
                    "validation": []
                },
                "internal/status/two": {
                    "type": "status",
                    "topics": {
                        "external": "external/topic/two" 
                    },
                    "meta": {}
                },
                #"external/topic/skip": {
                #    "type": "status",
                #    "topics": {
                #        # Missing "internal"
                #    },
                #    "meta": {}
                #}
            },
            "PlantB": {
                "internal/command/three": {
                    "type": "command",
                    "topics": {
                        "validated": "internal/command/false1",
                        "external": "external/topic/three",
                        "feedback": "command/feedback/three"
                    },
                    "meta": {},
                    "validation": []
                },
                "internal/sensor/four": {
                    "type": "sensor",
                    "topics": {
                        "external": "external/topic/four"
                    },
                    "meta": {}
                }
            }
        }
    }

@pytest.fixture
def topic_registry(sample_registry):
    """
    Returns an Expmanager agent that uses a temporary JSON file.
    """
    agent = TopicRegistry(sample_registry)

    # this step is requiered because by default _configure() will not be called
    # to avoid hardcoding this step you could mock the Agent via volttron testing    
    agent._load_plants_topics_data()
    agent._flatten_dict()
    
    yield agent
    # Cleanup afterwards if needed
    #agent._clean_up()

@pytest.fixture(scope="module")
def vinst(volttron_instance_zmq) -> PlatformWrapper:
    # starts a clean Volttron instance for test modules
    return volttron_instance_zmq

# Here we create a really simple agent which has only the core functionality, which we can use for Pub/Sub
# or JSON/RPC
@pytest.fixture(scope="module")
def simple_agent(request, vinst: PlatformWrapper):
    # Create the simple agent
    agent = vinst.build_agent()

    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent