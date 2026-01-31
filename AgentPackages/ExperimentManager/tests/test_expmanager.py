import pytest
import json
import os 
from expmanager.agent import ExperimentState, ExperimentDataModel, Expmanager
from pydantic import BaseModel, ValidationError
from datetime import datetime
from transitions import MachineError
from unittest.mock import MagicMock, patch

#------------------- Persisting Data --------------------
class TestPersistence:
    def test_initializes_with_empty_file(self, temp_experiments_file):
        """
        If file is empty, experiments list should remain empty.
        """
        with open(temp_experiments_file, "w") as f:
            json.dump("[]", f)

        agent = Expmanager({"experiments_data_path": temp_experiments_file})
        assert agent._experiments_data_list == []
        agent._full_data_deletion()

    def test_corrupted_json_file(self, temp_experiments_file):
        """
        If JSON file is corrupted, manager should handle gracefully.
        """
        with open(temp_experiments_file, "w") as f:
            json.dump("{ invalid json ]", f)

        agent = Expmanager({"experiments_data_path": temp_experiments_file})
        assert agent._experiments_data_list == []
        agent._full_data_deletion()


    def test_save_correct_experiment_to_file(self, temp_experiments_file, experiment_data_correct: dict):
        """
        Manually adds a experiment to the internal structure
        and tests if the data is saved to the persistent file correctly 
        """
        
        # Create agent manually to isolate save logic
        agent = Expmanager({"experiments_data_path": temp_experiments_file})
        
        # Add one experiment to internal list
        agent._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        
        # Save to file
        agent._save_experiments_data()
        
        # Read file directly
        with open(temp_experiments_file, "r") as f:
            content = json.load(f)

        # Check file content is correct and complete
        assert isinstance(content, list)
        assert len(content) == 1
        for key in experiment_data_correct.keys():
            assert key in content[0]
            assert content[0][key] == experiment_data_correct[key]

        agent._full_data_deletion()


    def test_load_experiments_from_file(self, temp_experiments_file, experiment_data_correct: dict):
        """
        Manualy writes a json with a single experiment data
        and verifies that the loaded data at  start up is correct
        """
        
        # Write valid JSON list with one experiment manually
        with open(temp_experiments_file, "w") as f:
            json.dump([experiment_data_correct], f)
        
        # Create agent and load
        agent = Expmanager({"experiments_data_path": temp_experiments_file})
        agent._load_experiments_data()
        
        # Check agent state
        assert len(agent._experiments_data_list) == 1
        exp = agent._experiments_data_list[0]
        assert isinstance(exp, ExperimentDataModel)
        assert agent._experiments_data_list[0].experiment_id == experiment_data_correct["experiment_id"]

        agent._full_data_deletion()
        

    def test_save_and_load_roundtrip(self, experiment_data_correct: dict, temp_experiments_file):
        """
        Ensure experiments are saved and loaded correctly from JSON.
        """
        exp_manager: Expmanager = Expmanager({"experiments_data_path": temp_experiments_file})
        
        # this step is requiered because by default _configure() want be called
        # to avoid hardcoding this step you could mock the Agent via volttron testing   
        exp_manager._configure("config", "NEW", {})
        
        # when correct experiment is submited the experiment is saved
        experiment_id = exp_manager.submit_experiment_data(experiment_data_correct)
        assert experiment_id == experiment_data_correct["experiment_id"]
        
        # Read file directly
        with open(temp_experiments_file, "r") as f:
            content = json.load(f)

        # Check file content is correct and complete
        assert isinstance(content, list)
        assert len(content) == 1
        for key in experiment_data_correct.keys():
            assert key in content[0]
            assert content[0][key] == experiment_data_correct[key]

        # Reload from file
        new_manager: Expmanager = Expmanager({"experiments_data_path": temp_experiments_file})
        new_manager._configure("config", "NEW", {})
        assert new_manager != None

        assert len(new_manager._experiments_data_list) == 1
        assert new_manager._experiments_data_list[0].experiment_id == experiment_id

        new_manager._full_data_deletion()


    def test_initialise_with_existing_file(self, temp_experiments_file, experiment_data_correct: dict):
        """
        Verifies that when an existing experiments file is provided,
        the agent loads experiments correctly from it.
        """

        # Save one experiment manually to the file
        with open(temp_experiments_file, "w") as f:
            json.dump([experiment_data_correct], f)

        # Initialize the agent with the existing file
        agent = Expmanager({
            "experiments_data_path": temp_experiments_file
        })
        
        # this step is requiered because by default _configure() want be called
        # to avoid hardcoding this step you could mock the Agent via volttron testing   
        agent._configure("config", "NEW", {})

        # Assert that the experiment was loaded
        assert len(agent._experiments_data_list) == 1
        assert agent._experiments_data_list[0].experiment_id == experiment_data_correct["experiment_id"]

        # Save again to check _save_experiments works
        agent._save_experiments_data()
        with open(temp_experiments_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["experiment_id"] == experiment_data_correct["experiment_id"]

        agent._full_data_deletion()


    def test_initialise_with_default_path(self, experiment_data_correct: dict):
        """
        Verifies that the agent uses a default file path when none is provided,
        and that save/load still works.
        """
        # Don't pass path in config
        agent = Expmanager({})
        # this step is requiered because by default _configure() want be called
        # to avoid hardcoding this step you could mock the Agent via volttron testing   
        agent._configure("config", "NEW", {})

        default_path = agent._experiments_data_filepath
        # Add and save experiment
        agent.submit_experiment_data(experiment_data_correct)
        agent._save_experiments_data()
        assert os.path.exists(default_path)

        # Recreate agent to verify loading
        new_agent = Expmanager({})
        new_agent._configure("config", "NEW", {})
        assert len(new_agent._experiments_data_list) == 1
        assert new_agent._experiments_data_list[0].experiment_id == experiment_data_correct["experiment_id"]

        agent._full_data_deletion()
        new_agent._full_data_deletion()
        # delete the default file
        os.remove(default_path)

#------------------- Important helpers --------------------
class TestHelpers:
    def test_full_data_deletion(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Verify the clean up function. it should remove all the data from internal list
        and save the empty list to persistant file
        """
        assert exp_manager._experiments_data_list == []
        exp_manager.submit_experiment_data(experiment_data_correct)
        assert len(exp_manager._experiments_data_list) == 1
        exp_manager._full_data_deletion()
        assert exp_manager._experiments_data_list == [] 


    def test_get_list_all_experiments_data(self, exp_manager: Expmanager, experiment_data_correct: dict):
        experiment_data_correct_1 = experiment_data_correct.copy()
        experiment_data_correct_1.update({"experiment_id": "1"})
        
        assert len(exp_manager._experiments_data_list) == 0

        experiment_id = exp_manager.submit_experiment_data(experiment_data_correct_1)
        experiment_list = exp_manager.get_list_all_experiments_data()
        # The experiment with the id is in there
        for exp_field in experiment_data_correct_1:
            assert exp_field in experiment_list[0]
        assert experiment_id in experiment_list[0].get("experiment_id")
        assert len(experiment_list) == 1

        experiment_data_correct_2 = experiment_data_correct.copy()
        experiment_data_correct_2.update({"experiment_id": "2"})
        experiment_data_correct_2.update({"start_time": "2025-11-02T13:00:00+00:00"})
        experiment_data_correct_2.update({"stop_time": "2025-11-02T15:00:00+00:00"})

        experiment_id = exp_manager.submit_experiment_data(experiment_data_correct_2)
        experiment_list = exp_manager.get_list_all_experiments_data()
        # The experiment with the id is in there
        for exp_field in experiment_data_correct_2:
            assert exp_field in experiment_list[1]
        assert experiment_id in experiment_list[1].get("experiment_id")
        assert len(experiment_list) == 2


    def test_get_list_experiment_ids(self, exp_manager: Expmanager, experiment_data_correct: dict):
        assert len(exp_manager._experiments_data_list) == 0
        experiment_data_correct_1 = experiment_data_correct.copy()
        experiment_data_correct_2 = experiment_data_correct.copy()
        experiment_data_correct_1.update({"experiment_id": "1"})
        experiment_data_correct_2.update({"experiment_id": "2"})
        experiment_data_correct_2.update({"start_time": "2025-11-02T13:00:00+00:00"})
        experiment_data_correct_2.update({"stop_time": "2025-11-02T15:00:00+00:00"})

        experiment_id_1 = exp_manager.submit_experiment_data(experiment_data_correct_1)
        experiment_id_2 = exp_manager.submit_experiment_data(experiment_data_correct_2)
        experiment_list = exp_manager.get_list_experiment_ids()
        # The experiment with the id is in there
        assert experiment_id_1 in experiment_list
        assert experiment_id_2 in experiment_list
        assert len(experiment_list) == 2


    def test_get_experiment_data(self, exp_manager: Expmanager, experiment_data_correct: dict):
        assert len(exp_manager._experiments_data_list) == 0
        experiment_data_correct_1 = experiment_data_correct.copy()
        experiment_data_correct_2 = experiment_data_correct.copy()
        experiment_data_correct_1.update({"experiment_id": "1"})
        experiment_data_correct_2.update({"experiment_id": "2"})
        experiment_data_correct_2.update({"start_time": "2025-11-02T13:00:00+00:00"})
        experiment_data_correct_2.update({"stop_time": "2025-11-02T15:00:00+00:00"})

        experiment_id_1 = exp_manager.submit_experiment_data(experiment_data_correct_1)
        experiment_id_2 = exp_manager.submit_experiment_data(experiment_data_correct_2)
        
        experiment_data = exp_manager.get_dict_experiment_data(experiment_id_1)
        for exp_field in experiment_data_correct_1:
            assert exp_field in experiment_data

        experiment_data = exp_manager.get_dict_experiment_data("aloha")
        assert experiment_data == {}


    def test_plants_are_available(self, exp_manager: Expmanager):
        # Load the test data into agent
        experiment_list = [
        ExperimentDataModel(
            experiment_id="exp1",
            experimenter="alice",
            description="Heatpump test",
            start_time="2025-11-02T10:00:00+00:00",
            stop_time="2025-11-02T12:00:00+00:00",
            plants=["heatpump_A"],
        ),
        ExperimentDataModel(
            experiment_id="exp2",
            experimenter="bob",
            description="Solar test",
            start_time="2025-11-02T13:00:00+00:00",
            stop_time="2025-11-02T15:00:00+00:00",
            plants=["solar_1"],
        )]
        exp_manager._experiments_data_list = experiment_list

        # Requesting a plant that's not in use
        assert exp_manager._plants_are_available("exp3", ["heatpump_B"], "2025-11-02T10:00:00+00:00", "2025-11-02T12:00:00+00:00")

        # Overlaps with exp1 (same plant, overlapping time)
        assert not exp_manager._plants_are_available("exp3", ["heatpump_A"], "2025-11-02T11:00:00+00:00", "2025-11-02T12:30:00+00:00")

        # Same time but different plant — should be available
        assert exp_manager._plants_are_available("exp3", ["solar_1"], "2025-11-02T10:00:00+00:00", "2025-11-02T12:00:00+00:00")

        # Starts before exp2 but ends during exp2
        assert not exp_manager._plants_are_available("exp3", ["solar_1"], "2025-11-02T12:30:00+00:00", "2025-11-02T13:30:00+00:00")

        # The new experiment is fully inside exp1's window
        assert not exp_manager._plants_are_available("exp3", ["heatpump_A"], "2025-11-02T10:30:00+00:00", "2025-11-02T11:30:00+00:00")


#------------------- Submiting of experiments data --------------------
class TestSubmitExperiments:
    def test_submit_experiment_valid(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Verifies the adding an experiment with valid data works correctly
        """
        assert len(exp_manager._experiments_data_list) == 0
        experiment_id = exp_manager.submit_experiment_data(experiment_data_correct)
        assert experiment_id == experiment_data_correct["experiment_id"]
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_data_list[0].experiment_id == experiment_id


    def test_submit_experiment_invalid_time(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Verifies the adding of an experiment with invalid time raises error
        """
        experiment_data_correct["stop_time"] = "2000-01-01T00:00:00+00:00"  # invalid (before start)
        with pytest.raises(ValueError, match="Start time must be before stop time"):
            exp_manager.submit_experiment_data(experiment_data_correct)


    def test_submit_experiment_invalid_field(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Verifies the adding of an experiment with a wrong field type raises error
        """
        experiment_data_correct.update({"start_time": 12345})  # Invalid datetime
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct)
    

    def test_submit_experiment_missing_required_field_raises(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Verifies the adding of an experiment with a missing requiered field type raises error
        """
        experiment_data_correct_missing = experiment_data_correct.copy()
        experiment_data_correct_missing.update({"experiment_id": None}) 
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct_missing)

        experiment_data_correct_missing = experiment_data_correct.copy()
        experiment_data_correct_missing.update({"experimenter": None}) 
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct_missing)
        
        experiment_data_correct_missing = experiment_data_correct.copy()
        experiment_data_correct_missing.update({"description": None}) 
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct_missing)

        experiment_data_correct_missing = experiment_data_correct.copy()
        experiment_data_correct_missing.update({"start_time": None}) 
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct_missing)

        experiment_data_correct_missing = experiment_data_correct.copy()
        experiment_data_correct_missing.update({"stop_time": None}) 
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct_missing)

        experiment_data_correct_missing = experiment_data_correct.copy()
        experiment_data_correct_missing.update({"plants": None}) 
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct_missing)


    def test_submit_experiment_duplicate_id_raises(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Verifies the adding of an experiment with a id already existing raises error
        """
        assert len(exp_manager._experiments_data_list) == 0

        # Verify the experiment is submited
        experiment_id =  exp_manager.submit_experiment_data(experiment_data_correct)
        assert experiment_id == experiment_data_correct["experiment_id"]
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_data_list[0].experiment_id == experiment_id

        # Verify there is only one Experiment in  the list
        with pytest.raises(ValueError):
            exp_manager.submit_experiment_data(experiment_data_correct)
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_data_list[0].experiment_id == experiment_id

 
    def test_submit_experiment_invalid_time_format(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Validates the passed time string is in correct format
        """
        assert len(exp_manager._experiments_data_list) == 0
        experiment_data_correct_time = experiment_data_correct.copy()
        exp_manager.submit_experiment_data(experiment_data_correct_time)
        assert len(exp_manager._experiments_data_list) == 1

        # Not ISO Format
        experiment_data_incorrect_time = experiment_data_correct.copy()
        experiment_data_incorrect_time.update({"start_time": "bajajaba"}) 
        with pytest.raises(ValueError, match="Invalid datetime format. Use ISO 8601."):
            exp_manager.submit_experiment_data(experiment_data_incorrect_time)
        assert len(exp_manager._experiments_data_list) == 1

        # No timezone information
        experiment_data_incorrect_time.update({"start_time": datetime.now()}) 
        with pytest.raises(ValueError, match="Datetime must include timezone information"):
            exp_manager.submit_experiment_data(experiment_data_incorrect_time)
        assert len(exp_manager._experiments_data_list) == 1

        # Not time type
        experiment_data_incorrect_time.update({"start_time": []}) 
        with pytest.raises(ValueError, match="Must be a datetime or ISO 8601 string."):
            exp_manager.submit_experiment_data(experiment_data_incorrect_time)
        assert len(exp_manager._experiments_data_list) == 1

        # Not ISO Format
        experiment_data_incorrect_time = experiment_data_correct.copy()
        experiment_data_incorrect_time.update({"stop_time": "bajajaba"}) 
        with pytest.raises(ValueError, match="Invalid datetime format. Use ISO 8601."):
            exp_manager.submit_experiment_data(experiment_data_incorrect_time)
        assert len(exp_manager._experiments_data_list) == 1
        
        # No timezone information
        experiment_data_incorrect_time.update({"stop_time": datetime.now()}) 
        with pytest.raises(ValueError, match="Datetime must include timezone information"):
            exp_manager.submit_experiment_data(experiment_data_incorrect_time)
        assert len(exp_manager._experiments_data_list) == 1

        # Not time type
        experiment_data_incorrect_time.update({"stop_time": []}) 
        with pytest.raises(ValueError, match="Must be a datetime or ISO 8601 string."):
            exp_manager.submit_experiment_data(experiment_data_incorrect_time)
        assert len(exp_manager._experiments_data_list) == 1


#------------------- Authorisation of experiments --------------------
class TestAuthorisation:
    def testauthorise_experiment_success(self, exp_manager: Expmanager, experiment_data_correct: dict):
            #exp_id = exp_manager.submit_experiment_data(experiment_data_correct)#
        # Note to avoid chain reaction if one initial step fails or is being worked on, add expeiment manually with correct state
        # Add manually first
        exp_id = "test1"
        state = "submited"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        # Then authorise
        result = exp_manager.authorise_experiment(experiment_id=exp_id, supervisor_name="Dr. Test")
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "authorised"
        assert exp.authorised_name == "Dr. Test"


    def testauthorise_experiment_missing(self, exp_manager: Expmanager):
        with pytest.raises(ValueError, match="Experiment ID not found."):
            exp_manager.authorise_experiment("non-existent-id", "Dr. Test")


    def testauthorise_experiment_missing_fields(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # Add first
        exp_id = exp_manager.submit_experiment_data(experiment_data_correct)
        # Supervisor name is missing
        with pytest.raises(Exception):
            exp_manager.authorise_experiment(experiment_id=exp_id)
    

    def testauthorise_experiment_wrong_field_type(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # Add first
        exp_id = exp_manager.submit_experiment_data(experiment_data_correct)
        # Supervisor name is not string
        with pytest.raises(ValueError, match="Supervisor Name must be a string."):
            exp_manager.authorise_experiment(experiment_id=exp_id, supervisor_name=[])


#------------------- Finalisation of Experiments --------------------
class TestFinalising:
    def testfinalize_experiment_success(self, exp_manager: Expmanager, experiment_data_correct: dict):
            #exp_id = exp_manager.submit_experiment_data(experiment_data_correct)
            #exp_manager.authorise_experiment(experiment_id=exp_id, supervisor_name="Dr. Test")
        # Note to avoid chain reaction if one initial step fails or is being worked on, add expeiment manually with correct state
        # Add and authorise manually first
        exp_id = "test1"
        state = "authorised"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        # Then finalize
        with patch("expmanager.agent.Expmanager._agents_are_installed", return_value=True), \
            patch("expmanager.agent.Expmanager._start_logging_topics", return_value=True), \
            patch("expmanager.agent.Expmanager._submit_experiment_to_scheduler", return_value=True), \
            patch("expmanager.agent.Expmanager._get_feedback_topics", return_value=["feedback_test"]), \
            patch("expmanager.agent.Expmanager._get_plant_topics", return_value=["plant_test"]):
    
            agents = ["test_agent"]
            topics = ["test_topic"]
            result = exp_manager.finalize_experiment(experiment_id=exp_id, agents_for_experiment=agents, topics_to_log=topics)
            assert result is True
            exp = exp_manager._experiments_data_list[0]
            assert exp.state is "finalized"
            assert exp.agents == agents
            for t in exp.topics: assert t in ["test_topic", "feedback_test", "plant_test"] 


    def testfinalize_experiment_fails(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # Add and authorise manually first
        exp_id = "test1"
        state = "authorised"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        # Then finalize
        with patch("expmanager.agent.Expmanager._agents_are_installed", return_value=True), \
            patch("expmanager.agent.Expmanager._start_logging_topics", return_value=True), \
            patch("expmanager.agent.Expmanager._submit_experiment_to_scheduler", return_value=True):
    
            agents = ["test_agent"]
            topics = ["test_topic"]
            result = exp_manager.finalize_experiment(experiment_id=exp_id, agents_for_experiment=agents, topics_to_log=topics)
            assert result is True
            exp = exp_manager._experiments_data_list[0]
            assert exp.state is "finalized"
            assert exp.agents == agents
            assert exp.topics == topics

#------------------- Starting of Experiments --------------------
class TestStarting:
    def testexperiment_is_running_success(self, exp_manager: Expmanager, experiment_data_correct: dict):
            #exp_id = exp_manager.submit_experiment_data(experiment_data_correct)
            #exp_manager.authorise_experiment(experiment_id=exp_id, supervisor_name="Dr. Test")
            #exp_manager.finalize_experiment(experiment_id=exp_id, ["test_agent"], ["test_topic"])
        # Note to avoid chain reaction if one initial step fails or is being worked on, add expeiment manually with correct state
        # Add, authorise, finalize manually first
        exp_id = "test1"
        state = "finalized"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        # Then run
        result = exp_manager.experiment_is_running(experiment_id=exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "running"


    def testexperiment_is_running_fails(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # Add, authorise, finalize manually first
        exp_id = "test1"
        state = "finished"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        # Then run
        with pytest.raises(RuntimeError, match="Can't trigger event run from state finished"):
            exp_manager.experiment_is_running(experiment_id=exp_id)
        
#------------------- Finishing of experiments --------------------
class TestFinishing:
    def testexperiment_is_finished_success(self, exp_manager: Expmanager, experiment_data_correct: dict):
            #exp_id = exp_manager.submit_experiment_data(experiment_data_correct)
            #exp_manager.authorise_experiment(experiment_id=exp_id, supervisor_name="Dr. Test")
            #exp_manager.finalize_experiment(experiment_id=exp_id, ["test_agent"], ["test_topic"])
            #exp_manager._run_experiment(experiment_id=exp_id)
        # Note to avoid chain reaction if one initial step fails or is being worked on, add expeiment manually with correct state
        # Add, authorise, finalize and run manually first
        exp_id = "test1"
        state = "running"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        # Then finish
        result = exp_manager.experiment_is_finished(exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "finished"
 
    
    def test_finish_fails(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # submit exp 
        exp_id = "test1"
        state = "submited"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Try finish not authorised
        with pytest.raises(RuntimeError, match="Can't trigger event finish from state submited"):
            exp_manager.experiment_is_finished(exp_id)

        # authorise an exp
        state = "authorised"
        exp_manager._experiments_data_list[0].state = state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Try finish when experiment is not finilized
        with pytest.raises(RuntimeError, match="Can't trigger event finish from state authorised"):
            exp_manager.experiment_is_finished(exp_id)

        # finalize an exp
        state = "finalized"
        exp_manager._experiments_data_list[0].state = state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Try finish when experiment is not ready
        with pytest.raises(RuntimeError, match="Can't trigger event finish from state finalized"):
            exp_manager.experiment_is_finished(exp_id)

        # run an exp
        state = "running"
        exp_manager._experiments_data_list[0].state = state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        result = exp_manager.experiment_is_finished(exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "finished"

        # try to finish second time        
        with pytest.raises(RuntimeError, match="Can't trigger event finish from state finished"):
            exp_manager.experiment_is_finished(exp_id)


#------------------- Cancelation of Experiments --------------------
class TestCancel:
    def testcancel_experiment_success(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # submit experiment
        exp_id = "test1"
        state = "submited"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then cancel
        result = exp_manager.cancel_experiment(exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "canceled"

        # authorise an exp
        state = "authorised"
        exp_manager._experiments_data_list[0].state = state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then cancel
        result = exp_manager.cancel_experiment(exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "canceled"

        # finalize an exp
        state = "finalized"
        exp_manager._experiments_data_list[0].state = state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then cancel
        result = exp_manager.cancel_experiment(exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "canceled"

        # run an exp
        state = "running"
        exp_manager._experiments_data_list[0].state = state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then cancel
        result = exp_manager.cancel_experiment(exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "canceled"


#------------------- Failing of Experiments --------------------
class TestFail:
    def testexperiment_is_failed_success(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # run an exp
        exp_id = "test1"
        state = "running"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then fail
        result = exp_manager.experiment_is_failed(exp_id)
        assert result is True
        exp = exp_manager._experiments_data_list[0]
        assert exp.state is "failed"


    def testexperiment_is_failed_fail(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # run an exp
        exp_id = "test1"
        state = "finished"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        
        # fail non existing id
        with pytest.raises(ValueError, match="Experiment ID not found"):
            exp_manager.experiment_is_failed("wrong_id")
        assert exp_manager._experiments_sm_dict[exp_id].state is state

        # fail wrong state
        with pytest.raises(RuntimeError, match="Can't trigger event fail from state finished"):
            exp_manager.experiment_is_failed(exp_id)
        assert exp_manager._experiments_sm_dict[exp_id].state is state


#------------------- Removing of experiments --------------------
class TestRemoveExperiments:
    def testremove_experiment_success(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        The experiment is successfully removed
        """
        # finish an exp
        exp_id = "test1"
        state = "finished"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then remove
        result = exp_manager.remove_experiment(exp_id)
        assert result is True
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 0

        # cancel an exp
        state = "canceled"
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then remove
        result = exp_manager.remove_experiment(exp_id)
        assert result is True
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 0

        # fail an exp
        state = "failed"
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then remove
        result = exp_manager.remove_experiment(exp_id)
        assert result is True
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 0

   
    def test_remove_non_existing_experiment(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        The experiment was not removed because it does not exist
        """
        # fail an exp
        exp_id = "test1"
        state = "failed"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # Then remove
        with pytest.raises(ValueError, match="Experiment ID not found"):
            exp_manager.remove_experiment("wrong_id")


    def testremove_experiment_edge(self, exp_manager: Expmanager, experiment_data_correct: dict):
        """
        Verify some edge cases like remove on empty list and remove the same experiment twice
        """
        # remove on empty list
        assert len(exp_manager._experiments_data_list) == 0
        with pytest.raises(ValueError, match="Experiment ID not found"):
            exp_manager.remove_experiment("experiment_id")


        # double remove
        exp_id = "test1"
        state = "finished"
        experiment_data_correct.update({"experiment_id": exp_id})
        experiment_data_correct.update({"state": state})
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_correct))
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict[exp_id].state is state
        # remove first time
        result = exp_manager.remove_experiment(exp_id)
        assert result is True
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 0
        # remove second time
        with pytest.raises(ValueError, match="Experiment ID not found"):
            exp_manager.remove_experiment(exp_id)
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 0


#------------------- State Machine --------------------
class TestStateMachine:
    def test_intialisation(self):
        # default case
        m = ExperimentState("testexp")
        assert m.state is "submited"
        assert m.is_submited()
        
        # explicit intialisation
        for state in ExperimentState.states:
            m = ExperimentState("testexp", state)
            assert m.state is state
        
    def test_transitions(self):
        # default run
        m = ExperimentState("testexp")
        assert m.is_submited()

        m.authorise()
        assert m.is_authorised()
        
        m.finalize()
        assert m.is_finalized()

        m.run()
        assert m.is_running()

        m.finish()
        assert m.is_finished()

        # cancel
        m = ExperimentState("testexp")
        assert m.is_submited()

        m.cancel()
        assert m.is_canceled()

        # fail
        m = ExperimentState("testexp")
        assert m.is_submited()

        m.authorise()
        assert m.is_authorised()
        
        m.finalize()
        assert m.is_finalized()

        m.run()
        assert m.is_running()

        m.fail()
        assert m.is_failed()


    def test_transitions_raises(self):
        m = ExperimentState("testexp")
        assert m.is_submited()
        with pytest.raises(MachineError, match="Can't trigger event run from state submited!"):
            m.run()


    def test_reinitialise(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # check that there are no experiments and no state machines in the memory
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 0 

        # load data but not machine
        experiment_data_correct.update({"experiment_id": "test1"})
        experiment_data_correct.update({"state": "submited"})
        experiment_data_1 = experiment_data_correct.copy()
        experiment_data_correct.update({"experiment_id": "test2"})
        experiment_data_correct.update({"state": "finished"})
        experiment_data_2= experiment_data_correct.copy()
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_1))
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_2))
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 2 

        # reinitialise machine and check its state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 2
        assert len(exp_manager._experiments_data_list) == 2
        assert exp_manager._experiments_sm_dict["test1"].state is "submited"
        assert exp_manager._experiments_sm_dict["test2"].state is "finished"


    def test_reinitialise_raises(self, exp_manager: Expmanager, experiment_data_correct: dict):
        # check that there are no experiments and no state machines in the memory
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 0 

        # load wringfull data but not machine
        experiment_data_correct.update({"experiment_id": "test1"})
        experiment_data_correct.update({"state": "non existing state"})
        experiment_data_1 = experiment_data_correct.copy()
        exp_manager._experiments_data_list.append(ExperimentDataModel(**experiment_data_1))
        assert len(exp_manager._experiments_sm_dict) == 0
        assert len(exp_manager._experiments_data_list) == 1 

        # reinitialise machine and check its state
        exp_manager._reinitialise_state_machines()
        assert len(exp_manager._experiments_sm_dict) == 1
        assert len(exp_manager._experiments_data_list) == 1
        assert exp_manager._experiments_sm_dict["test1"].state is "failed"