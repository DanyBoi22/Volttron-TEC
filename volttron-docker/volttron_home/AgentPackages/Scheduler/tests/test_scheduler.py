import pytest
import json
import os 
from scheduler.agent import ScheduledExperiment, Scheduler
from pydantic import BaseModel, ValidationError
from datetime import datetime, timedelta
import tests.conftest as con
from apscheduler.schedulers.base import STATE_STOPPED
from unittest.mock import patch, MagicMock

#------------------- Initialisation --------------------
class TestInit:
    def test_agent_initialise(self):
        scheduler_agent = Scheduler({})
        jobs = scheduler_agent._scheduler.get_jobs()
        assert len(jobs) == 0
        # the configure function is not called. the state is stopped. need to manually start the scheduler instance
        scheduler_agent._start_scheduler()
        assert scheduler_agent._scheduler.state != STATE_STOPPED

#------------------- Submiting Schedules --------------------
class TestSubmitSchedule:
    def test_submit_experiment_schedule_success(self, scheduler: Scheduler, experiment_data: dict):

        assert scheduler._scheduler.state != STATE_STOPPED

        result = scheduler.submit_experiment_schedule(experiment_data)
        assert result
        jobs = scheduler._scheduler.get_jobs()
        assert len(jobs) > 0

#------------------- Removing Schedules --------------------
class TestRemoveSchedule:
    def test_remove_experiment_schedule_success(self, scheduler: Scheduler, experiment_data: dict):

        assert scheduler._scheduler.state != STATE_STOPPED
    
        result = scheduler.submit_experiment_schedule(experiment_data)
        assert result
        jobs = scheduler._scheduler.get_jobs()
        assert len(jobs) > 0

        result = scheduler.remove_experiment_schedule(experiment_data)
        assert result
        jobs = scheduler._scheduler.get_jobs()
        assert len(jobs) == 0

#------------------- Starting Agents --------------------
class TestStartAgents:
    def test_start_agents_success(self, scheduler: Scheduler):
        agents = ["agent1", "agent2"]
        exp_id = "testexp"

        # Mock _start_agent to always succeed
        with patch.object(scheduler, "_start_agent", return_value=True) as mock_start, \
            patch.object(scheduler, "notify_experiment_is_running") as mock_running, \
            patch.object(scheduler, "notify_experiment_is_failed") as mock_failed:
            
            result = scheduler._start_agents(agents, exp_id)

            assert result is True
            assert mock_start.call_count == 2
            mock_running.assert_called_with(exp_id)
            mock_failed.assert_not_called()

    def test_start_agents_partial_failure(self, scheduler: Scheduler):
        agents = ["agent1", "agent2"]
        exp_id = "testexp"

        # Mock: first succeeds, second fails
        def mock_start(agent):
            return agent == "agent1"
        
        with patch.object(scheduler, "_start_agent", side_effect=mock_start) as mock_start, \
            patch.object(scheduler, "notify_experiment_is_running") as mock_running, \
            patch.object(scheduler, "notify_experiment_is_failed") as mock_failed:
            
            result = scheduler._start_agents(agents, exp_id)

            assert result is False
            assert mock_start.call_count == 2
            mock_running.assert_not_called()
            mock_failed.assert_called_once_with(exp_id)
        
            # TODO: assert started agents get stop call
    
    def test_start_agents_with_exception(self, scheduler: Scheduler):
        agents = ["agent1"]
        exp_id = "testexp"

        with patch.object(scheduler, "_start_agent", side_effect=Exception("oh nooooo")) as mock_start, \
            patch.object(scheduler, "notify_experiment_is_running") as mock_running, \
            patch.object(scheduler, "notify_experiment_is_failed") as mock_failed:
            
            result = scheduler._start_agents(agents, exp_id)

            assert result is False
            mock_running.assert_not_called()
            mock_failed.assert_called_once_with(exp_id)

#------------------- Stopping Agents --------------------
class TestStopAgents:
    def test_stop_agents_success(self, scheduler: Scheduler):
        agents = ["agent1", "agent2"]
        exp_id = "testexp"

        # Mock _stop_agent to always succeed
        with patch.object(scheduler, "_stop_agent", return_value=True) as mock_stop, \
            patch.object(scheduler, "notify_experiment_is_finished") as mock_finished:
            
            result = scheduler._stop_agents(agents, exp_id)

            assert result is True
            assert mock_stop.call_count == 2
            mock_finished.assert_called_with(exp_id)

    def test_stop_agents_partial_failure(self, scheduler: Scheduler):
        agents = ["agent1", "agent2"]
        exp_id = "testexp"

        # Mock: first succeeds, second fails
        def mock_stop(agent):
            return agent == "agent1"
        
        with patch.object(scheduler, "_stop_agent", side_effect=mock_stop) as mock_stop, \
            patch.object(scheduler, "notify_experiment_is_finished") as mock_finished:
            
            result = scheduler._stop_agents(agents, exp_id)

            # assert both call functions are called but no finish flag is set
            assert result is False
            assert mock_stop.call_count == 2
            mock_finished.assert_not_called()
    
    def test_stop_agents_with_exception(self, scheduler: Scheduler):
        agents = ["agent1"]
        exp_id = "testexp"

        with patch.object(scheduler, "_stop_agent", side_effect=Exception("oh nooooo")) as mock_stop, \
            patch.object(scheduler, "notify_experiment_is_finished") as mock_finished, \
            patch.object(scheduler, "notify_experiment_is_failed") as mock_failed:
            
            result = scheduler._stop_agents(agents, exp_id)

            # assert no finish flag is set
            assert result is False
            mock_finished.assert_not_called()
            mock_failed.assert_not_called()

#------------------- Persisting Data --------------------
# TODO: export and import of scheduled jobs
class TestPersisting:

    def test_persistence_roundtrip(self, scheduler: Scheduler):
        
        tmp_filepath: str = scheduler._scheduled_experiments_filepath

        # Add a dummy job
        scheduler._scheduler.add_job(lambda: None, 'interval', seconds=60, id="job1")

        # Save jobs
        scheduler._save_scheduled_experiments()
        assert os.path.exists(tmp_filepath)

        # Clear jobs and reload
        scheduler._scheduler.remove_all_jobs()
        scheduler._load_scheduled_experiments()

        jobs = scheduler._scheduler.get_jobs()
        assert any(job.id == "job1" for job in jobs)

def _save_experiments_to_file(temp_experiments_file, experiment_data: dict):
    """
    Manually adds a experiment to the internal structure
    and tests if the data is saved to the persistent file correctly 
    """
    
    return

    # Create agent manually to isolate save logic
    agent = Scheduler({con.FILEPATHNAME: temp_experiments_file})
    
    # Add one experiment to internal list
    agent._scheduled_experiments_list.append(ScheduledExperiment(**experiment_data))
    
    # Save to file
    agent._save_scheduled_experiments()
    
    # Read file directly
    with open(temp_experiments_file, "r") as f:
        content = json.load(f)
    
    # Check file content is correct and complete
    assert isinstance(content, list)
    assert len(content) == 1
    assert content[0]["experiment_id"] == experiment_data["experiment_id"]
    assert content[0]["start_time"] == experiment_data["start_time"]
    assert content[0]["stop_time"] == experiment_data["stop_time"]
    assert content[0]["agents"] == experiment_data["agents"]
    assert content[0]["experiment_id"] != experiment_data["agents"]
    assert content[0]["start_time"] != experiment_data["stop_time"]
    assert content[0]["agents"] != experiment_data["stop_time"]

def _load_experiments_from_file(temp_experiments_file, experiment_data: dict):
    """
    Manualy writes a json with a single experiment data
    and verifies that the loaded data at  start up is correct
    """

    return

    # Write valid JSON list with one experiment manually
    with open(temp_experiments_file, "w") as f:
        json.dump([experiment_data], f)
    
    # Create agent, loading happens automatically at startup
    # TODO: find out why even with wron filepath the test still works
    agent = Scheduler({con.FILEPATHNAME: temp_experiments_file})
    
    # Check agent state
    assert len(agent._scheduled_experiments_list) == 1
    exp = agent._scheduled_experiments_list[0]
    assert isinstance(exp, ScheduledExperiment)

    # Write valid JSON list with 2 experiments manually and load the file again
    with open(temp_experiments_file, "w") as f:
        json.dump([experiment_data, experiment_data], f)
    agent._load_scheduled_experiments()
    
    # Check agent state
    assert len(agent._scheduled_experiments_list) == 2
    exp = agent._scheduled_experiments_list[0]
    assert isinstance(exp, ScheduledExperiment)
    exp = agent._scheduled_experiments_list[1]
    assert isinstance(exp, ScheduledExperiment)

def _initialise_with_existing_file(temp_experiments_file, experiment_data: dict):
    """
    Verifies that when an existing experiments file is provided,
    the agent loads experiments correctly from it.
    """

    return

    # Save one experiment manually to the file
    with open(temp_experiments_file, "w") as f:
        json.dump([experiment_data], f)

    # Initialize the agent with the existing file
    agent = Scheduler({con.FILEPATHNAME: temp_experiments_file})

    # Assert that the experiment was loaded
    assert len(agent._scheduled_experiments_list) == 1
    assert agent._scheduled_experiments_list[0].experiment_id == experiment_data["experiment_id"]

    # Save again to check _save_experiments works
    agent._save_scheduled_experiments()
    with open(temp_experiments_file) as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["experiment_id"] == experiment_data["experiment_id"]

    agent._clean_up()

def _initialise_with_default_path(experiment_data: dict):
    """
    Verifies that the agent uses a default file path when none is provided,
    and that save/load still works.
    """
    
    return

    # Don't pass path in config
    agent = Scheduler({})

    default_path = agent._scheduled_experiments_filepath

    # Initially, file should not exist 
    # If exists check the contents before deleting
    assert not os.path.exists(default_path)

    # Add and save experiment
    agent._scheduled_experiments_list.append(ScheduledExperiment(**experiment_data))
    agent._save_scheduled_experiments()
    assert os.path.exists(default_path)

    # Recreate agent to verify loading
    new_agent = Scheduler({})
    assert len(new_agent._scheduled_experiments_list) == 1
    assert new_agent._scheduled_experiments_list[0].experiment_id == experiment_data["experiment_id"]

    agent._clean_up()
    new_agent._clean_up()
    # delete the default file
    os.remove(default_path)

def test_stop_time_before_start_time_raises():
    now = datetime.now()
    with pytest.raises(ValidationError):
        ScheduledExperiment(
            experiment_id="failcase",
            start_time=now,
            stop_time=now - timedelta(minutes=5),
            agents=["x"]
        )