import pytest
import os
import tempfile
from pydantic import BaseModel, ValidationError
from typing import List, Dict

# A simple model for testing
class ModelTest(BaseModel):
    id: int
    name: str

@pytest.fixture
def model_list() -> List[ModelTest]:
    return [
        ModelTest(id=1, name="Alice"),
        ModelTest(id=2, name="Bob"),
    ]

@pytest.fixture
def model_dict(model_list) -> Dict[str, ModelTest]:
    return {model.name: model for model in model_list}


@pytest.fixture
def test_dict():
    return {
        "string": "abc123",
        "list": ["1", "2"],
        "dict": {
            "string": "abc123"
        }
    }

@pytest.fixture
def temp_json_file_path():
    """
    Creates a temporary file for experiment persistence.
    """
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_")
    os.close(fd)  # Close the open file descriptor to avoid file lock issues

    yield path
    if os.path.exists(path):
        os.remove(path)