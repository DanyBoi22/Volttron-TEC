import pytest
import json
from typing import List, Dict
from datetime import datetime
from plantregistry.agent import Plantregistry, PlantMetadata, PlantStatus

def test_agent(plant_registry):
    assert isinstance(plant_registry, Plantregistry)
    
#------------------- Persisting Data --------------------
class TestPersisting:
    def test_save_plant_status_to_file(self, plant_registry: Plantregistry, temp_plant_status_filepath):
        """
        Manually add a status to the internal structure
        and tests if the data is saved to the persistent file correctly 
        """
        plant_status_test: PlantStatus = PlantStatus(status="available", updated_at=datetime.now().isoformat())

        # Add one experiment to internal structure
        plant_registry._plants_status["PlantA"] = plant_status_test
        
        # Save to file
        plant_registry._save_plant_status()

        # Read file directly
        with open(temp_plant_status_filepath, "r") as f:
            content = json.load(f)
        
        # Check file content is correct and complete
        assert isinstance(content, Dict)
        assert content["PlantA"] == plant_status_test.model_dump()


    def test_load_plant_status_from_file(self, plant_registry: Plantregistry, temp_plant_status_filepath):
        """
        Manualy writes a json with a single plant status
        and verifies that the loaded data is correct
        """

        plant_status_test: PlantStatus = PlantStatus(status="available", updated_at=datetime.now().isoformat())
        st = {"PlantA": plant_status_test.model_dump()}
        
        # Write valid JSON list with one status manually
        with open(temp_plant_status_filepath, "w") as f:
            json.dump(st, f)
        
        # load the data
        plant_registry._load_plant_status()
        
        # Check agent state
        assert isinstance(plant_registry._plants_status, Dict)
        assert isinstance(plant_registry._plants_status["PlantA"], PlantStatus)
        assert plant_status_test == plant_registry._plants_status["PlantA"]


    def test_status_persistence(self, plant_registry: Plantregistry, temp_plant_status_filepath):
        """
        Test save and load together
        """
        # update and save
        plant_registry._update_status("PlantA", "not available")

        with open(temp_plant_status_filepath, "r") as f:
            data = json.load(f)
        assert "PlantA" in data
        assert data["PlantA"]["status"] == "not available"

        # reload and check
        plant_registry._plants_status = {}
        plant_registry._load_plant_status()
        assert plant_registry._get_status("PlantA") == "not available"


    def test_load_plants_data_from_config_valid(self, sample_config_valid):
        """
        Initiates an agent with valid config with plants data 
        and verifies the correct data in internal data structure 
        """

        # when config is loaded, metadata is correctly parsed
        plant_registry = Plantregistry(sample_config_valid)
        assert len(plant_registry._plants_list) == 2
        assert isinstance(plant_registry._plants_list[0], PlantMetadata)
        assert isinstance(plant_registry._plants_list[1], PlantMetadata)
        assert plant_registry._plants_list[0].plant_name == "PlantA"
        assert plant_registry._plants_list[1].plant_name == "PlantB" 


    def test_load_plants_data_from_config_invalid(self, sample_config_invalid):
        """
        Initiates an agent with invalid config with plants data 
        and verifies the agent is not crashed 
        """

        # infalid config is parsed without crashing the agent
        plant_registry = Plantregistry(sample_config_invalid)
        assert len(plant_registry._plants_list) == 0
        assert plant_registry._plants_list == []
        assert isinstance(plant_registry, Plantregistry)

#------------------- Update, Get, List Data --------------------
class TestList:
    def test_list_plants(self, plant_registry: Plantregistry):
        # populated registry
        plants = plant_registry._list_plants()
        assert plants == ["PlantA", "PlantB"]

        # empty registry
        plant_registry._plants_list = []
        plants = plant_registry._list_plants()
        assert plants == []

        # error in registry
        plant_registry._plants_list = None
        with pytest.raises(ValueError):
            plants = plant_registry._list_plants()

class TestUpdate:
    def test_update_status(self, plant_registry: Plantregistry):
        # valid updates
        assert len(plant_registry._plants_status) == 0

        plant_registry._update_status("PlantA", "available")
        assert len(plant_registry._plants_status) == 1
        assert isinstance(plant_registry._plants_status["PlantA"], PlantStatus)
        assert plant_registry._plants_status["PlantA"].status == "available"

        plant_registry._update_status("PlantA", "not available")
        assert len(plant_registry._plants_status) == 1
        assert isinstance(plant_registry._plants_status["PlantA"], PlantStatus)
        assert plant_registry._plants_status["PlantA"].status == "not available"

        plant_registry._update_status("PlantB", "control seized")
        assert len(plant_registry._plants_status) == 2
        assert plant_registry._plants_status["PlantA"].status == "not available"
        assert isinstance(plant_registry._plants_status["PlantB"], PlantStatus)
        assert plant_registry._plants_status["PlantB"].status == "control seized"

        # invalid update
        with pytest.raises(ValueError):
            plant_registry._update_status("PlantA", "invalid-status")

        # non-existent plant
        with pytest.raises(ValueError):
            plant_registry._update_status("PlantZ", "available")

    def test_update_and_get_status(self, plant_registry: Plantregistry):
        # valid update
        plant_registry._update_status("PlantA", "available")
        status = plant_registry._get_status("PlantA")
        assert status == "available"



class TestGet:
    def test_get_metadata(self, plant_registry: Plantregistry):
        # retrieving information for existing registry entry
        data = plant_registry._get_plant_data("PlantA")
        assert data["model"] == "ModelX"

        # raising error on retrieving information for non existing entry
        with pytest.raises(ValueError):
            plant_registry._get_plant_data("NonExistent")

    def test_get_status(self, plant_registry: Plantregistry):
        # valid plant
        plant_registry._plants_status["PlantA"] = PlantStatus(status="available", updated_at=datetime.now().isoformat())
        status = plant_registry._get_status("PlantA")
        assert status == "available"

        # non-existent plant
        with pytest.raises(ValueError):
            plant_registry._get_status("PlantZ")
