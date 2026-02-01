import os
import pytest
from volttron.platform.jsonrpc import RemoteError
from volttrontesting.fixtures.volttron_platform_fixtures import PlatformWrapper
from volttron.platform.vip.agent import Agent

TOPIC_DIR = os.path.abspath("/home/user/volttron/agents/TopicRegistryAgent/")

    
def _topic_registry_integration(vinst: PlatformWrapper):
    assert vinst.is_running()

    # install topic_registry
    topic_registry_uuid = vinst.install_agent(
        agent_dir=TOPIC_DIR,
        start=True,
        vip_identity="topic_registry"
    )

    # now agent is running and can talk over VIP
    assert topic_registry_uuid
    assert vinst.is_agent_running(topic_registry_uuid)

    # create a generic agent to call rpcs
    generic_agent: Agent = vinst.build_agent(identity="generic")

    result = generic_agent.vip.rpc.call("topic_registry", "get_list_of_internal_topics", topic_type_list_match=["command"]).get(timeout=1)
    assert result
    print(result)

    # search_topics(plant_name_list_match=[""], topic_type_list_match=[""], internal_topics_list_match=[""], external_topics_list_match=[""], feedback_topics_list_match=[""], text_info_match="", )
    #, topic_type_list_match=["command"], internal_topics_list_match=["raw/testcommand"]
    result = generic_agent.vip.rpc.call("topic_registry", "search_topics", None, None, None, None, None, None).get(timeout=1)
    assert result
    print(result)
