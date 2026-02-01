import pytest
import os
import tempfile
from scheduler.agent import Scheduler
from datetime import datetime, timedelta, timezone
from volttrontesting.fixtures.volttron_platform_fixtures import volttron_instance_zmq, PlatformWrapper

FILEPATHNAME = "schedules_path"

@pytest.fixture
def experiment_data():
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    stop = start + timedelta(hours=1)
    return {
        "experiment_id": "testexp",
        "start_time": start.isoformat(),
        "stop_time": stop.isoformat(),
        "agents": ["agent1", "agent2"]
    }


@pytest.fixture
def temp_experiments_file():
    """
    Creates a temporary file for experiment persistence.
    """
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_experiments_")
    os.close(fd)  # Close the open file descriptor to avoid file lock issues
    
    with open(path, "w") as f:
        f.write("[]")  # <-- ensures valid JSON structure from the start

    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def scheduler(temp_experiments_file):
    """
    Returns a Scheduler agent that uses a temporary JSON file.
    """
    config = {
        FILEPATHNAME: temp_experiments_file,
    }
    agent = Scheduler(config)
    
    # this step is requiered because by default _configure() want be called
    # to avoid hardcoding this step you could mock the Agent via volttron testing   
    agent._start_scheduler()
    
    yield agent
    # Cleanup internal experiment list and remove file if still there
    #agent._full_data_deletion()

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

@pytest.fixture(autouse=True)
def patch_core_spawn(monkeypatch):
    """
    Replace agent.core.spawn with a synchronous implementation during tests.
    This makes .get() work immediately and avoids greenlet assertion errors.
    """

    def immediate_spawn(self, func, *args, **kwargs):
        class DummyResult:
            def get(self, timeout=None):
                return func(*args, **kwargs)
        return DummyResult()

    monkeypatch.setattr(
        "volttron.platform.vip.agent.core.ZMQCore.spawn",
        immediate_spawn,
        raising=True
    )
