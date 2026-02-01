import os
import pytest
from volttron.platform.jsonrpc import RemoteError
from volttrontesting.fixtures.volttron_platform_fixtures import PlatformWrapper
from volttron.platform.vip.agent import Agent

EXPMANAGER_DIR = os.path.abspath("/home/user/volttron/agents/ExperimentManager/")
SCHEDULER_DIR = os.path.abspath("/home/user/volttron/agents/SchedulerAgent/")
    
# TODO: integration test of exp manager and scheduler
def _experiment_scheduler_integration(vinst: PlatformWrapper):
    assert vinst.is_running()

    # install ExperimentManager
    exp_manager_uuid = vinst.install_agent(
        agent_dir=EXPMANAGER_DIR,
        start=True,
        vip_identity="experiment_manager"
    )

    # install Scheduler
    scheduler_uuid = vinst.install_agent(
        agent_dir=SCHEDULER_DIR,
        start=True,
        vip_identity="scheduler"
    )

    # now both agents are running and can talk over VIP
    assert exp_manager_uuid
    assert scheduler_uuid
    assert vinst.is_agent_running(exp_manager_uuid)
    assert vinst.is_agent_running(scheduler_uuid)


    # create a generic agent to call rpcs
    generic_agent: Agent = vinst.build_agent(identity="generic")
    generic_agent_uuid = vinst.get_agent_by_identity("generic")
    assert generic_agent_uuid
    assert vinst.is_agent_running(generic_agent_uuid)

    # submit exp
    generic_agent.vip.rpc.call("experiment_manager", "submit_experiment_schedule", {"experiment_id": "exp1", "start": "..."}).get(timeout=1)

    # authorise exp
    # finalize exp





    # stop the agents and assert they are stopped
    vinst.stop_agent(exp_manager_uuid)
    vinst.stop_agent(scheduler_uuid)
    assert not vinst.is_agent_running(exp_manager_uuid)
    assert not vinst.is_agent_running(scheduler_uuid)




def _scheduler_rpc_returns_error(vinst: PlatformWrapper):
    assert vinst.is_running()

    scheduler_uuid = vinst.get_agent_by_identity("scheduler")

    generic_agent: Agent = vinst.build_agent(identity="generic")
    generic_agent_uuid = vinst.get_agent_by_identity("generic")
    # now both agents are running and can talk over VIP
    
    assert scheduler_uuid
    assert generic_agent_uuid
    assert vinst.is_agent_running(scheduler_uuid)
    assert vinst.is_agent_running(generic_agent_uuid)

    with pytest.raises(RemoteError) as excinfo:
        generic_agent.vip.rpc.call("scheduler", 
                                    "submit_experiment_schedule",
                                    {"experiment_id": "exp1", "start": "..."}
                                ).get(timeout=1)

    # optional: check that the remote error actually came from ValueError
    assert "Validation error" in str(excinfo.value)
    assert "ScheduledExperiment" in str(excinfo.value)

    # stop the agents and assert they are stopped
    vinst.stop_agent(scheduler_uuid)
    vinst.stop_agent(generic_agent_uuid)
    assert not vinst.is_agent_running(scheduler_uuid)
    assert not vinst.is_agent_running(generic_agent_uuid)

    # stop the platform
    vinst.stop_platform()
    assert not vinst.is_running()