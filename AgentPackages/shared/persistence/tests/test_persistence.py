import pytest
import json
import os 
from persistence import json_io, pydantic_io
from pydantic import BaseModel, ValidationError
from tests.conftest import ModelTest

# ------------------- Basic JSON --------------------

def test_json_load(temp_json_file_path, test_dict: dict):

    # manually write test data in the temp file 
    with open(temp_json_file_path, "w") as file:
        json.dump(test_dict, file)
    
    data = json_io.load_json(temp_json_file_path)

    # Check file content is correct and complete
    assert isinstance(data, dict)
    for key in data.keys():
        assert data.get(key) == test_dict.get(key)

def test_json_save(temp_json_file_path, test_dict: dict):

    json_io.save_json(temp_json_file_path, test_dict)

    # manually load data from the temp file
    with open(temp_json_file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Check file content is correct and complete
    assert isinstance(data, dict)
    for key in data.keys():
        assert data.get(key) == test_dict.get(key)

# ------------------- Pydantic Lists ------------------- #

def test_save_and_load_model_list(temp_json_file_path, model_list):

    pydantic_io.save_model_list(temp_json_file_path, model_list)
    loaded_models = pydantic_io.load_model_list(temp_json_file_path, ModelTest)

    assert loaded_models == model_list
    assert all(isinstance(m, ModelTest) for m in loaded_models)

def test_save_empty_model_list(temp_json_file_path):

    pydantic_io.save_model_list(temp_json_file_path, [])
    loaded_models = pydantic_io.load_model_list(temp_json_file_path, ModelTest)

    assert loaded_models == []

def test_load_model_list_with_invalid_data(temp_json_file_path):

    invalid_data = [{"id": 1}, {"name": "Missing ID"}]  # Missing fields
    
    # manually load data from the temp file
    with open(temp_json_file_path, "w") as file:
        json.dump(invalid_data, file)

    with pytest.raises(Exception):
        pydantic_io.load_model_list(temp_json_file_path, ModelTest)

# ------------------- Pydantic Dicts ------------------- #

def test_save_and_load_model_dict(temp_json_file_path, model_dict):

    pydantic_io.save_model_dict(temp_json_file_path, model_dict)
    loaded_models = pydantic_io.load_model_dict(temp_json_file_path, ModelTest)

    assert loaded_models == model_dict
    assert all(isinstance(v, ModelTest) for v in loaded_models.values())

def test_save_empty_model_dict(temp_json_file_path):

    pydantic_io.save_model_dict(temp_json_file_path, {})
    loaded_models = pydantic_io.load_model_dict(temp_json_file_path, ModelTest)

    assert loaded_models == {}

def test_load_model_dict_with_invalid_data(temp_json_file_path):
    
    invalid_data = {"Alice": {"id": 1}, "Bob": {"name": "Missing ID"}}

    # manually load data from the temp file
    with open(temp_json_file_path, "w") as file:
        json.dump(invalid_data, file)

    with pytest.raises(Exception):
        pydantic_io.load_model_dict(temp_json_file_path, ModelTest)