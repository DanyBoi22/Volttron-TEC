import pytest
import tempfile
import os
from plantregistry.agent import Plantregistry

CONFIG_NAME_PLANT_STATUS_FILEPATH = "plant_status_filepath"


@pytest.fixture
def temp_plant_status_filepath():
    """
    Creates a temporary file for experiment persistence.
    """
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_plant_statuses_")
    os.close(fd)  # Close the open file descriptor to avoid file lock issues
    
    with open(path, "w") as f:
        f.write("{}")  # ensure valid JSON structure from the start

    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def sample_config_valid(temp_plant_status_filepath):
    return {
        CONFIG_NAME_PLANT_STATUS_FILEPATH: temp_plant_status_filepath,
        "plants": [
            {"plant_name": "PlantA", "model": "ModelX"},
            {"plant_name": "PlantB", "model": "ModelY", "location": "Lab1"},
        ]
    }

@pytest.fixture
def sample_config_invalid():
    return {
        "plants": [
            {"plant_id": 1234, "model": "ModelX"},
            {"plant_name": "PlantB", "model": "ModelY", "location": []},
        ]
    }

@pytest.fixture
def plant_registry(sample_config_valid):
    """
    Returns a Plant Registry agent.
    """
    agent = Plantregistry(sample_config_valid)
    yield agent
    # Cleanup afterwards if needed
    #agent._clean_up()