"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from datetime import datetime, timezone
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import Dict, List, Any
import pytz
import json
import importlib
import gevent

from metadata.metadata_mixin import MetadataMixin

from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.jobstores.base import JobLookupError


_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

class ScheduledExperiment(BaseModel):
    experiment_id: str
    start_time: str
    stop_time: str
    agents: List[str]
    
    started: bool = False
    stopped: bool = False

    @model_validator(mode='after')
    def validate_time_order(self) -> 'ScheduledExperiment':
        if self.stop_time <= self.start_time:
            raise ValueError("stop_time must be after start_time")
        return self
    
DEFAULT_SCHEDULES_PATH = "/home/volttron/.volttron/AgentPackages/SchedulerAgent/scheduler/schedules.json"
DEFAULT_AGENT_MANAGER_IDENTITY = "agentmanageragent-0.1_1"
DEFAULT_EXPERIMENT_MANAGER_IDENTITY = "expmanageragent-0.1_1"
TIMEZONE = pytz.utc

def scheduler(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Scheduler
    :rtype: Scheduler
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Scheduler(config, **kwargs)


class Scheduler(Agent, MetadataMixin):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Scheduler, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)

        self._config = config
        self._scheduled_experiments_filepath = self._config.get("schedules_path", DEFAULT_SCHEDULES_PATH)
        # TODO: Later can be replaced with a call to Agent Registry
        self._agent_manager = self._config.get("agent_manager_identity", DEFAULT_AGENT_MANAGER_IDENTITY)
        self._experiment_manager = self._config.get("experiment_manager_identity", DEFAULT_EXPERIMENT_MANAGER_IDENTITY)

        self._scheduler = GeventScheduler(timezone=TIMEZONE)
      
        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
 

    def _configure(self, config_name, action, contents):
        self._config = contents
        self._scheduled_experiments_filepath = contents.get("schedules_path", self._scheduled_experiments_filepath)
        # TODO: Later can be replaced with a call to Agent Registry
        self._agent_manager = self._config.get("agent_manager_identity", self._agent_manager)
        self._experiment_manager = self._config.get("experiment_manager_identity", self._experiment_manager)

        self._start_scheduler()
        # TODO persistence check
        #self._load_scheduled_experiments()

# ----------------- RPC exposed functions ----------------- 

    @RPC.export
    def submit_experiment_schedule(self, experiment_data: Dict) -> bool:
        """
        Accepts an experiment schedule and registers it.
        
        Params:
            Dict of the experiment data to schedule 
            Expected format:
            {
                "experiment_id": "exp_001",
                "start_time": "2025-07-10T14:00:00+00:00",
                "stop_time": "2025-07-10T16:30:00+00:00",
                "agents": ["agent1.identity", "agent2.identity", ...]
            }
        Returns:
            True on success
        Raises:
            Exception on failure to schedule
        """
        
        try:
            experiment = ScheduledExperiment(**experiment_data)

            start_job_id: str = 'start_'+experiment.experiment_id
            stop_job_id: str = 'stop_'+experiment.experiment_id
            self._scheduler.add_job(self._start_agents, trigger='date', run_date=experiment.start_time, args=[experiment.agents, experiment.experiment_id], id=start_job_id, misfire_grace_time=60)
            self._scheduler.add_job(self._stop_agents, trigger='date', run_date=experiment.stop_time, args=[experiment.agents, experiment.experiment_id], id=stop_job_id, misfire_grace_time=60)

            _log.info(f"Experiment \"{experiment.experiment_id}\" scheduled from {experiment.start_time} to {experiment.stop_time}")
            return True

        except Exception as e:
            _log.error(f"Exception occured while scheduling experiment: {e}")
            raise RuntimeError(f"Failed to schedule: {e}")

    @RPC.export
    def remove_experiment_schedule(self, experiment_data: Dict) -> bool:
        """
        Removes scheduled experiment and stops it if it is already running
        
        Params:
            Dict of data for the experiment to remove from schedules 
            Expected format:
            {
                "experiment_id": "exp_001",
                "agents": ["agent1.identity", "agent2.identity", ...]
            }
        Returns:
            True on success
        Raises:
            Exception on failure to remove
        """
        # Note the agents to stop can also be extracted from job arguments

        result: bool = True
        experiment_id: str = experiment_data.get("experiment_id")
        agents: List[str] = experiment_data.get("agents")
        
        if not experiment_id or not agents:
            _log.error(f"Could not remove schedule for starting experiment \"{experiment_id}\": experiment ID or agents are not specified")
            raise RuntimeError(f"Failed to remove schedule, specify experiment ID and agents")

        start_job_id: str = 'start_'+experiment_id
        stop_job_id: str = 'stop_'+experiment_id
        
        # Remove start schedule
        try:    
            self._scheduler.remove_job(start_job_id)
        except JobLookupError as e:
            # If Experiment already started the job is removed automatically (alternatively maybe scheduling failed and there are no start schedule)
            _log.warning(f"Could not remove schedule for starting experiment \"{experiment_id}\": {e}")
            # Stop agents 
            if not self._stop_agents(agents, experiment_id):
                _log.warning(f"Could not stop agents for running experiment \"{experiment_id}\": {e}")
                result = False
        # Remove stop schedule
        try:    
            self._scheduler.remove_job(stop_job_id)
        except JobLookupError as e:        
            _log.warning(f"Could not remove schedule for stopping experiment \"{experiment_id}\": {e}")
            result = False
        
        if result: 
            _log.info(f"Successfully removed schedules for experiment \"{experiment_id}\".")
            return result
        else:
            _log.error(f"Exception occured while removing schedule for experiment \"{experiment_id}\"")
            raise RuntimeError(f"Failed to remove schedule")
    
# ----------------- Helper functions ----------------- 

# -------- Data peristence --------

    def _load_scheduled_experiments(self):
        """
        Load persisted schedules data from file into agent
        """
        # Note the last compatible versions of apscheduler for volttron 9.0.1 is 3.x and they do not support export_jobs() or import_jobs()
        #self._scheduler.import_jobs(self._scheduled_experiments_filepath)

        return
        # TODO: Raises error due to some objects inside trigger not json serializable like timezone
        with open(self._scheduled_experiments_filepath, "r") as f:
            jobs_data = json.load(f)

        for job_data in jobs_data:
            # resolve function reference
            module_name, func_name = job_data["func"].split(":")
            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name)

            # restore trigger from state
            trigger_class = self._scheduler._create_trigger(job_data["trigger_args"])
            self._scheduler.add_job(
                func,
                trigger=trigger_class,
                args=job_data["args"],
                kwargs=job_data["kwargs"],
                id=job_data["id"],
                replace_existing=True,
            )

    def _save_scheduled_experiments(self):
        """
        Persist the temporarly cached schedules data to file
        """
        # Note the last compatible versions of apscheduler for volttron 9.0.1 is 3.x and they do not support export_jobs() or import_jobs()
        #self._scheduler.export_jobs(self._scheduled_experiments_filepath)

        return
        # TODO: Raises error due to some objects inside trigger not json serializable like timezone
        jobs_data = []
        for job in self._scheduler.get_jobs():
            jobs_data.append({
                "id": job.id,
                "func": f"{job.func.__module__}:{job.func.__qualname__}",  # reference
                "trigger": str(job.trigger),  # for logging/debug
                "trigger_args": job.trigger.__getstate__(),  # APScheduler trigger state
                "args": job.args,
                "kwargs": job.kwargs,
            })

        with open(self._scheduled_experiments_filepath, "w") as file:
            json.dump(jobs_data, file, indent=2)


    def _full_data_deletions(self):
        """
        Remove all data from internal structure and persistant file
        """

        self._scheduler.remove_all_jobs()
        self._save_scheduled_experiments()


    def _get_schedules(self) -> List:
        """
        Returns a list of scheduelr jobs
        """

        return self._scheduler.get_jobs()

# -------- Schedule managment --------

    def _start_scheduler(self):
        """
        """
        # Satrt scheduler to process jobs
        self._scheduler.start()

    def _stop_scheduler(self):
        """
        """
        # Stop scheduler without waiting
        self._scheduler.shutdown(wait=False)

    def _start_agents(self, agents: List[str], experiment_id: str) -> bool:
        """
        Loops trough the list of agents and starts them via RPC.
        
        Params:
            agents: List of agents to start
            experiment_id: Corresponding experiment ID 
        Returns: 
            True on success, False otherwise
        """
        start_successfull = True
        for agent in agents:
            result = False
            try:
                result = self._start_agent(agent)
            except Exception as e:
                _log.error(f"Error while trying to start agent {agent}: {e}")
            
            if result:
                _log.debug(f"Started agent \"{agent}\" for experiment \"{experiment_id}\"")
            else:
                start_successfull = False
                _log.debug(f"Failed to start agent \"{agent}\" for experiment \"{experiment_id}\", rc: {result}")

        if start_successfull:
            self.notify_experiment_is_running(experiment_id)
        # TODO: stop those agents that not failed from this list
        else:
            self.notify_experiment_is_failed(experiment_id)

        return start_successfull
    
    def _stop_agents(self, agents: List[str], experiment_id: str) -> bool:
        """
        Loops trough the list of agents and stops them via RPC

        Params:
            agents: List of agents to stop
            experiment_id: Corresponding experiment ID
        Returns: 
            True on success, False otherwise
        """
        stop_successfull = True
        for agent in agents:
            result = False
            try:
                result = self._stop_agent(agent)
            except Exception as e:
                _log.error(f"Error while trying to stop agent {agent}: {e}")
            
            if result:
                _log.debug(f"Stoped agent \"{agent}\" for experiment \"{experiment_id}\"")
            else:
                _log.debug(f"Failed to stop agent \"{agent}\" for experiment \"{experiment_id}\"")
                stop_successfull = False

        # TODO: notify user if stoping failed?
        if stop_successfull:
            self.notify_experiment_is_finished(experiment_id)

        return stop_successfull

# -------- external calls --------

    def _start_agent(self, agent: str):
        """
        """
        try:
            return self.core.spawn(self.vip.rpc.call, self._agent_manager, "start_agent", agent).get(timeout=2)
        except:
            raise

    def _stop_agent(self, agent: str):
        """
        """
        try:
            return self.core.spawn(self.vip.rpc.call, self._agent_manager, "stop_agent", agent).get(timeout=2)
        except:
            raise

    def notify_experiment_is_running(self, experiment_id: str) -> bool:
        """
        Notify the experiment manager that the experiment is running

        Params:
            experiment_id: Experiment ID string
        Returns:
            True on success, False on fail
        """
        
        try:
            return self.core.spawn(self.vip.rpc.call, self._experiment_manager, "experiment_is_running", experiment_id).get(timeout=2)
        except Exception as e:
            _log.warning(f"Failed to notify on start, with error: {e}")
            return False

    def notify_experiment_is_finished(self, experiment_id: str) -> bool:
        """
        Notify the experiment manager that the experiment is finished

        Params:
            experiment_id: Experiment ID string
        Returns:
            True on success, False on fail
        """

        try:
            return self.core.spawn(self.vip.rpc.call, self._experiment_manager, "experiment_is_finished", experiment_id).get(timeout=2)
        except Exception as e:
            _log.warning(f"Failed to notify on finish, with error: {e}")
            return False

    def notify_experiment_is_failed(self, experiment_id: str) -> bool:
        """
        Notify the experiment manager that the experiment is failed

        Params:
            experiment_id: Experiment ID string
        Returns:
            True on success, False on fail
        """

        try:
            return self.core.spawn(self.vip.rpc.call, self._experiment_manager, "experiment_is_failed", experiment_id).get(timeout=2)
        except Exception as e:
            _log.warning(f"Failed to notify on fail, with error: {e}")
            return False
        
    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        try:
            result = self.vip.rpc.call(self._agent_manager, "enable_agent_autostart", self.core.identity, "60").get(timeout=2)
            _log.debug(f"Enabling autostart for {self.core.identity}: {result}")
        except gevent.Timeout as to:
            _log.error(f"RPC enable_agent_autostart time out: {to}.")

    
    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        pass

def main():
    """Main method called to start the agent."""
    utils.vip_main(scheduler, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
