import pytest
import os
import tempfile
from expmanager.agent import Expmanager
from datetime import datetime, timedelta, timezone


@pytest.fixture
def experiment_data_correct():
    start = datetime.now(timezone.utc)
    stop = start + timedelta(hours=1)
    return {
        "experiment_id": "testexp",
        "experimenter": "Tester",
        "description": "Unit test experiment",
        "start_time": start.isoformat(),
        "stop_time": stop.isoformat(),
        "plants": ["plant1", "plant2"],
        #"agents": ["agent1", "agent2"],
        #"topics": ["topic1", "topic2"]
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
def exp_manager(temp_experiments_file):
    """
    Returns an Expmanager agent that uses a temporary JSON file.
    """
    config = {
        "experiments_data_path": temp_experiments_file,
    }
    agent = Expmanager(config)
    yield agent
    # Cleanup internal experiment list and remove file if still there
    agent._full_data_deletion()

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