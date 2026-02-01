"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import gevent
from datetime import datetime, timezone
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from metadata.metadata_mixin import MetadataMixin
from persistence import pydantic_io

from pydantic import BaseModel, Field, model_validator, ValidationError, field_validator
from typing import List, Dict, Optional
from copy import deepcopy

from transitions import Machine, MachineError

class ExperimentDataModel(BaseModel):
    experiment_id: str
    experimenter: str
    description: str
    start_time: str
    stop_time: str
    plants: List[str]
    external_control: bool = False
    # TODO: functioning simulation
    simulation_flag: bool = True
    state: Optional[str] = None # possible states ['submited', 'authorised', 'finalized', 'running', 'finished', 'canceled', 'failed']

    authorised_name: Optional[str] = None
    authorised_time: Optional[str] = None

    agents: Optional[List[str]] = None
    topics: Optional[List[str]] = None

    # TODO: other validation like not empty plant string for non simulative runs, etc
    
    # Validate individual fields: ensure timezone-aware allowed datetime.fromisoformat('2011-11-04 00:05:23.283+00:00')
    @field_validator("start_time", "stop_time", mode="before")
    def parse_and_validate_datetime(cls, value):
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except Exception as e:
                raise ValueError(f"Invalid datetime format. Use ISO 8601: {e}")
        elif isinstance(value, datetime):
            dt = value
            value = value.isoformat()
        else:
            raise ValueError("Must be a datetime or ISO 8601 string.")

        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError("Datetime must include timezone information.")
        
        return value
    
    # validate stop time after start time
    @model_validator(mode='after')
    def validate_time_order(self) -> 'ExperimentDataModel':
        if datetime.fromisoformat(self.stop_time) <= datetime.fromisoformat(self.start_time):
            raise ValueError("Start time must be before stop time.")
        return self


class ExperimentState(object):
    # statemachine for each experiment: look up exp lifecycle state diagramm
    states = ['submited', 'authorised', 'finalized', 'running', 'finished', 'canceled', 'failed']

    transitions = [
        # transitions from submited state
        { 'trigger': 'authorise', 'source': 'submited', 'dest': 'authorised'},
        { 'trigger': 'cancel', 'source': 'submited', 'dest': 'canceled'},

        # transitions from authorised state
        { 'trigger': 'finalize', 'source': 'authorised', 'dest': 'finalized'},
        { 'trigger': 'cancel', 'source': 'authorised', 'dest': 'canceled'},

        # transitions from finalized state
        { 'trigger': 'run', 'source': 'finalized', 'dest': 'running'},
        { 'trigger': 'cancel', 'source': 'finalized', 'dest': 'canceled'},
  
        # transitions from running state
        { 'trigger': 'finish', 'source': 'running', 'dest': 'finished'},
        { 'trigger': 'cancel', 'source': 'running', 'dest': 'canceled'},
        { 'trigger': 'fail', 'source': 'running', 'dest': 'failed'},
    ]

    def __init__(self, experiment_id: str, initial_state: str="submited"):
        # Check for non existing states
        if initial_state not in ExperimentState.states:
            raise MachineError(f"Invalid initial state: {initial_state}")
        # Initialize the state machine
        self.experiment_id = experiment_id
        self.machine = Machine(model=self, states=ExperimentState.states, transitions=ExperimentState.transitions, initial=initial_state)

    # easter egg
    def update_journal(self):
        """ Dear Diary, today I saved Mr. Whiskers. Again. """
        self.kitten_rescued = True
    
_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

DEFAULT_EXPERIMENTS_DATA_PATH = "/home/volttron/.volttron/AgentPackages/ExperimentManager/expmanager/experimentsdata.json"
DEFAULT_AGENT_MANAGER_IDENTITY = "agentmanageragent-0.1_1"
DEFAULT_SCHEDULER_IDENTITY = "scheduleragent-0.1_1"
DEFAULT_LOGGER_IDENTITY = "loggeragent-0.1_1"
DEFAULT_TOPIC_REGISTRY_IDENTITY = "topicregistryagent-0.1_1" 

def expmanager(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Expmanager
    :rtype: Expmanager
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Expmanager(config, **kwargs)

class Expmanager(Agent, MetadataMixin):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Expmanager, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)

        self._config = config
        self._experiments_data_filepath = config.get("experiments_data_path", DEFAULT_EXPERIMENTS_DATA_PATH)
        
        # TODO: Later can be replaced with a call to Agent Registry
        self._agent_manager = config.get("agent_manager_identity", DEFAULT_AGENT_MANAGER_IDENTITY)
        self._scheduler = config.get("scheduler_identity", DEFAULT_SCHEDULER_IDENTITY) 
        self._logger = config.get("logger_identity", DEFAULT_LOGGER_IDENTITY) 
        self._topic_registry = config.get("topic_registry_identity", DEFAULT_TOPIC_REGISTRY_IDENTITY) 

        self._experiments_data_list: List[ExperimentDataModel] = [] # list of the experiment
        self._experiments_sm_dict: Dict[str, ExperimentState] = {} # dict of state machines for experiment keyed by experiment id
        
        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        

    def _configure(self, config_name, action, contents):
        self._config = contents
        self._experiments_data_filepath = contents.get("experiments_data_path", self._experiments_data_filepath)

        # TODO: Later can be replaced with a call to Agent Registry
        self._agent_manager = contents.get("agent_manager_identity", self._agent_manager)
        self._scheduler = contents.get("scheduler_identity", self._scheduler) 
        self._logger = contents.get("logger_identity", self._logger) 
        self._topic_registry = contents.get("topic_registry_identity", self._topic_registry) 

        self._load_experiments_data()
        self._reinitialise_state_machines()

# ------------------ RPC exposed Functions ------------------

    @RPC.export
    def submit_experiment_data(self, experiment_data: Dict[str, Dict]) -> str:
        """
        Submit experiment data after validation and persist it.

        Params:
            experiment_data: Dictionary containing initial metadata for the experiment
        Returns:
            Experiment ID as a string
        Raises:
            ValueError or RuntimeError: If the data is invalid or submition fails
        """
        
        try:
            # Parse and validate using Pydantic
            experiment = ExperimentDataModel(**experiment_data)
        except ValidationError as e:
            _log.warning(f"Experiment validation failed: {e}")
            raise ValueError(f"Could not submit the experiment. Experiment data validation failed: {e}")

        # check for duplicates
        if self._find_experiment_index_by_id(experiment.experiment_id) is not None:
            _log.warning(f"Could not submit the experiment. An experiment with ID: {experiment.experiment_id} already exists.")
            raise ValueError(f"Experiment with this ID already exists: {experiment.experiment_id}")

        # Check plant availability
        if not self._plants_are_available(experiment_id=experiment.experiment_id, plants=experiment.plants, start_time=experiment.start_time, stop_time=experiment.stop_time):
            _log.warning(f"Could not submit the experiment. Some plants are not available for the selected time slot.")
            raise RuntimeError("Some plants are not available for the selected time slot.")

        self._init_experiment(experiment)

        _log.info(f"An Experiment with ID: {experiment.experiment_id} was successfully submited.")
        return experiment.experiment_id


    @RPC.export
    def authorise_experiment(self, experiment_id: str, supervisor_name: str) -> bool:
        # TODO: params as dict?
        """
        Mark an experiment as authorised by a supervisor.

        Params:
            experiment_id: String ID of the experiment to authorise
            supervisor_name: Name of the supervisor authorising the experiment
        Returns:
            True on success
        Raises:
            ValueError: If the experiment cannot be authorised
        """

        # Check input params
        if experiment_id is None:
            _log.warning(f"Could not autthorise the experiment, ID not provided.")
            raise ValueError("ID not provided.")
        
        if supervisor_name is None:
            _log.warning(f"Could not authorise the experiment. Supervisor Name not provided.")
            raise ValueError("Supervisor Name not provided.")

        if not isinstance(supervisor_name, str):
            _log.warning(f"Could not authorise the experiment. Supervisor Name must be a string.")
            raise ValueError("Supervisor Name must be a string.")
        
        self._update_experiment(experiment_id, "authorise", authorised_name=supervisor_name, authorised_time=datetime.now(timezone.utc).isoformat())

        _log.info(f"An Experiment with ID: {experiment_id} was successfully authorised.")
        return True


    @RPC.export
    def finalize_experiment(self, experiment_id: str, agents_for_experiment: List[str], topics_to_log: List[str]) -> bool:
        # TODO: params as dict?
        """
        Finalise the experiment with the needed info. 
        
        Params:
            experiment_id: String ID or name of experiment to finalize
            agents_for_experiment: List of agents identities requeired for the experiment
            topics_to_log: List of topics to log by the logger agent 
        Returns: 
            True on success
        Raises: 
            Exception: If the experiment can not be finalized
        """

        # Check input params
        if experiment_id is None or not isinstance(experiment_id, str):
            _log.warning(f"Could not finalize the experiment, ID not provided or is not string.")
            raise ValueError("ID not provided.")
        
        if agents_for_experiment is None or not isinstance(agents_for_experiment, list) or len(agents_for_experiment) == 0:
            _log.warning(f"Could not finalize the experiment \"{experiment_id}\". The agents should be in a list of string identeties and the list can not be empty.")
            raise ValueError("No agents are listed.")
        
        if topics_to_log is None or not isinstance(topics_to_log, list) or len(topics_to_log) == 0:
            # Do not raise exception hence you dont always want to log, probably
            _log.warning(f"No topics to log are provided for experiment \"{experiment_id}\". Topics should be in a list.")
 
        experiment_index = self._find_experiment_index_by_id(experiment_id)
        if experiment_index is None:
            _log.warning(f"Could not finalize the experiment \"{experiment_id}\". Experiment ID not found.")
            raise ValueError("Experiment ID not found.")
    
        # find the experiment
        experiment: ExperimentDataModel = self._experiments_data_list[experiment_index]
        
        # append the plant specific topics to log (right now not needed hence you can simply write what topics you want to log)
        #plant_topics = self._get_plant_topics(experiment.plants)
        #extended_topics_to_log = topics_to_log + plant_topics

        # check whether logged topics contain command messages and append the feedback topics to the list of topics to log
        feedback_topics = self._get_feedback_topics(topics_to_log)
        # Add only missing topics
        extended_topics_to_log = topics_to_log + [t for t in feedback_topics if t not in topics_to_log]

        # verify all needed agents are isntalled on the platform 
        if not self._agents_are_installed(agents_for_experiment):
            _log.warning(f"Could not finalize the experiment \"{experiment_id}\". Not all agents are installed.")
            raise RuntimeError("Not all agents are installed.")

        # Notify external systems
        try:
            # try logging topics, if it fails: the experiment will be discarded immediately
            self._start_logging_topics(experiment_id, extended_topics_to_log)
            # try sending data to scheduler, if it fails: stop logging topics and the discard the experiment
            try:
                self._submit_experiment_to_scheduler(experiment_id, agents_for_experiment, experiment.start_time, experiment.stop_time)
            except Exception as e:
                self._stop_logging_topics(experiment_id)
                raise
        except Exception as e:
            _log.warning(f"Could not finalize the experiment \"{experiment_id}\". RPC Call failed with: {e}")
            raise RuntimeError("RPC Call failed")
        
        self._update_experiment(experiment_id, "finalize", topics=extended_topics_to_log, agents=agents_for_experiment)

        _log.info(f"An Experiment \"{experiment_id}\" was finalized and is ready to start.")
        return True


    @RPC.export
    def cancel_experiment(self, experiment_id: str) -> bool:
        """
        Cancel an experiment that is in progress or scheduled.

        Params:
            experiment_id: String ID of the experiment to cancel
        Returns:
            True on success
        Raises:
            Exception: If the experiment cannot be cancelled
        """

        if experiment_id is None:
            _log.warning(f"Could not cancel the experiment, ID not provided.")
            raise ValueError("ID not provided.")
        
        experiment_index = self._find_experiment_index_by_id(experiment_id)
        if experiment_index is None:
            _log.warning(f"Could not cancel the experiment with ID: {experiment_id}. Experiment ID not found.")
            raise ValueError("Experiment ID not found.")
        
        # get experiment data
        experiment: ExperimentDataModel = self._experiments_data_list[experiment_index]

        # TODO: if state finalized or running it needs custom cancelation
        # stop logging topics
        # remove experiment from scheduler

        self._update_experiment(experiment_id, "cancel")

        _log.info(f"Successfully canceled the Experiment \"{experiment_id}\".")
        return True


    @RPC.export
    def remove_experiment(self, experiment_id: str) -> bool:
        """
        Remove an experiment and all its data.
        Can remove only experiments that were canceled, finished or failed.

        Params:
            experiment_id: String ID of the experiment to remove
        Returns:
            True on success
        Raises:
            Exception: If the experiment cannot be removed
        """
        if experiment_id is None:
            _log.warning(f"Could not remove the experiment, ID not provided.")
            raise ValueError("ID not provided.")
        
        # get state
        experiment_index = self._find_experiment_index_by_id(experiment_id)
        if experiment_index is None:
            _log.warning(f"Experiment ID \"{experiment_id}\" not found.")
            raise ValueError("Experiment ID not found.")
        experiment: ExperimentDataModel = self._experiments_data_list[experiment_index]
        state = experiment.state

        if state not in ["canceled", "finished", "failed"]:
            _log.warning(f"Could not remove experiment with \"{experiment_id}\". Can not remove experiment, its state should be \"canceled\", \"finished\" or \"failed\", current state: \"{state}\".")
            raise RuntimeError("Can not remove experiment, its state should be \"canceled\", \"finished\" or \"failed\"")

        removed_experiment = self._delete_experiment(experiment_id)

        _log.info(f"Successfully removed the Experiment \"{removed_experiment.experiment_id}\".")
        return True


    @RPC.export
    def get_list_experiment_ids(self) -> List[str]:
        """
        Retrieve a list of all experiment IDs.

        Returns:
            List of experiment IDs as strings
        """

        exp_dict = deepcopy(self._experiments_data_list)
        return [exp.experiment_id for exp in exp_dict]
    

    @RPC.export
    def get_list_all_experiments_data(self) -> List[Dict]:
        """
        Retrieve metadata and state for all experiments.

        Returns:
            List of dictionaries containing experiment data
        """
        exp_dict = deepcopy(self._experiments_data_list)
        return [exp.model_dump() for exp in exp_dict]
    

    @RPC.export
    def get_dict_experiment_data(self, experiment_id: str) -> Dict[str, Dict]:
        """
        Retrieve metadata and state for a single experiment.

        Params:
            experiment_id: String ID of the experiment
        Returns:
            Dictionary containing experiment data or empty dict if experiment does not exist
        """

        exp_dict = deepcopy(self._experiments_data_list)
        for exp in exp_dict:
            if exp.experiment_id == experiment_id:
                return exp.model_dump()

        return {}
        

    @RPC.export
    def experiment_is_running(self, experiment_id: str) -> bool:
        """
        WARNING: This method is allowed to be invoked only by scheduler agent.
        Mark the finalized experiment as running.

        Params:
            experiment_id: String ID of the experiment that started
        Returns:
            True on success
        Raises:
            ValueError: If the experiment cannot be marked as started
        """
        
        # Check input params
        if experiment_id is None:
            _log.warning(f"Could not start the experiment, ID not provided.")
            raise ValueError("ID not provided.")
        
        self._update_experiment(experiment_id, "run")

        _log.info(f"An Experiment \"{experiment_id}\" was started.")
        return True


    @RPC.export
    def experiment_is_finished(self, experiment_id: str) -> bool:
        """
        WARNING: This method is allowed to be invoked only by scheduler agent.
        Mark the running experiment as finished.

        Params:
            experiment_id: String ID of the experiment that finished
        Returns:
            True on success
        Raises:
            ValueError: If the experiment cannot be marked as finished
        """

        if experiment_id is None:
            _log.warning(f"Could not finish the experiment, ID not provided.")
            raise ValueError("ID not provided.")
        
        self._update_experiment(experiment_id, "finish")

        # stop logging topics
        try:
            self._stop_logging_topics(experiment_id)
        except Exception as e:
            _log.warning(f"Could not stop logging topics for experiment \"{experiment_id}\". RPC Call failed with: {e}")

        _log.info(f"Successfully finished the Experiment \"{experiment_id}\".")
        return True    


    @RPC.export
    def experiment_is_failed(self, experiment_id: str) -> bool:
        """
        WARNING: This method is allowed to be invoked only by scheduler agent.
        Mark the running experiment as failed.

        Params:
            experiment_id: String ID of the experiment that failed
        Returns:
            True on success
        Raises:
            Exception: If the experiment cannot be marked as failed
        """

        if experiment_id is None:
            _log.warning(f"Could not fail the experiment, ID not provided.")
            raise ValueError("ID not provided.")

        self._update_experiment(experiment_id, "fail")

        # stop logging topics
        try:
            self._stop_logging_topics(experiment_id)
        except Exception as e:
            _log.warning(f"Could not stop logging topics for experiment \"{experiment_id}\". RPC Call failed with: {e}")
        
        # TODO: notify user the experiment failed
        return True

# ------------------ Helper Functions ------------------

# ------ data persitence ------

    def _reinitialise_state_machines(self):
        """
        Recreate state machines for each experiment based on state from persisted data 
        """
        for experiment in self._experiments_data_list:
            try:
                machine = ExperimentState(experiment.experiment_id, experiment.state)
                self._experiments_sm_dict[experiment.experiment_id] = machine
            except MachineError as e:
                # TODO: currently: on fail initiate state machine as failed. maybe implement other fail safe
                _log.warning(f"Could not reinstate experiment with id \"{experiment.experiment_id}\" to state \"{experiment.state}\", reason: {e}. The experiment will be initiated as failed.")
                machine = ExperimentState(experiment.experiment_id, "failed")
                self._experiments_sm_dict[experiment.experiment_id] = machine

    def _load_experiments_data(self):
        """
        Load persisted data from file
        """

        experiments_copy = self._experiments_data_list.copy()
        try:
            self._experiments_data_list = pydantic_io.load_model_list(self._experiments_data_filepath, ExperimentDataModel)
        except Exception as e:
            _log.error(f"Failed to load experiments data file: {e}.")
            self._experiments_data_list = experiments_copy


    def _save_experiments_data(self):
        """
        Persist the temporaly cashed data to the file
        """

        try:
            pydantic_io.save_model_list(self._experiments_data_filepath, self._experiments_data_list)
        except Exception as e:
            _log.error(f"Failed to save experiments to the file: {e}. The experiments data will not be persisted.")
    

    def _full_data_deletion(self):
        """
        WARNING: do not use except in testing
        """
        self._experiments_sm_dict = {}
        self._experiments_data_list = []
        self._save_experiments_data()
    
# ------ experiment managment ------

    def _init_experiment(self, experiment_data: ExperimentDataModel):
        """
        Initiate the experiment with submited data and create the state machine for the experiment.
        Persist the newly created experiment 

        Params:
            experiment_data: pydantic model with submited data for the experiment to initiate
        """

        # Create state machine for the experiment
        state_machine = ExperimentState(experiment_data.experiment_id)
        self._experiments_sm_dict[experiment_data.experiment_id] = state_machine
        
        # Store experiment data internaly and persist it
        experiment_data.state = state_machine.state
        self._experiments_data_list.append(experiment_data)
        self._save_experiments_data()
    

    def _update_experiment(self, experiment_id: str, sm_trigger: str, **extra_fields) -> None:
        """
        Update an experiment's data model and state machine, then persist changes.
        
        Params:
            experiment_id: ID of the experiment to update.
            sm_trigger: State machine method to call (e.g. "authorise", "finalize", "run", "fail" etc).
            extra_fields: Additional ExperimentDataModel fields to override.
        Raises:
            ValueError: If ID not found
            MachineError: If state machine fails
        """

        # Find experiment by ID
        experiment_index = self._find_experiment_index_by_id(experiment_id)
        if experiment_index is None:
            _log.error(f"Experiment ID \"{experiment_id}\" not found.")
            raise ValueError("Experiment ID not found.")
        
        experiment: ExperimentDataModel = self._experiments_data_list[experiment_index]

        # Update state machine
        try:
            state_machine = self._experiments_sm_dict[experiment.experiment_id]
            # dynamically call state machine trigger
            getattr(state_machine, sm_trigger)()  
        except Exception as e:
            _log.error(f"Failed to update experiment state for experiment \"{experiment_id}\": {e}")
            raise RuntimeError(f"Failed to update experiment state: {e}")

        # Copy experiment data and update
        updated_experiment: ExperimentDataModel = experiment.model_copy()
        updated_experiment.state = state_machine.state
        # dynamically update fields in experiment data model
        for field, value in extra_fields.items():
            setattr(updated_experiment, field, value)

        # Store and persist
        self._experiments_data_list[experiment_index] = updated_experiment
        self._save_experiments_data()


    def _delete_experiment(self, experiment_id: str) -> ExperimentDataModel:
        """
        Update an experiment's data model and state machine, then persist changes.
        
        Params:
            experiment_id: ID of the experiment to delete.
        Raises:
            ValueError: if ID not found
        Returns:
            ID of removed experiment
        """

        index = self._find_experiment_index_by_id(experiment_id)
        if index is None:
            _log.warning(f"Could not delete experiment with ID \"{experiment_id}\". ID not found.")
            raise ValueError("ID not found.")

        # remove state machine
        del self._experiments_sm_dict[experiment_id]

        # remove experiment data entry and persist the change
        removed_experiment = self._experiments_data_list.pop(index)
        self._save_experiments_data()

        return removed_experiment


    def _find_experiment_index_by_id(self, experiment_id: str) -> int:
        """
        Find the experiments index in the internal list by the ID
        
        Params:
            experiment_id: ID of the experiment.
        Returns:
            Int index of the experiment in the list if it exists
            None if the experiment could not be find
        """

        for id, exp in enumerate(self._experiments_data_list):
            if exp.experiment_id == experiment_id:
                return id
        return None
    

    def _plants_are_available(self, experiment_id: str, plants: List[str], start_time: str, stop_time: str):
        """
        Check if plants are available for scheduling in the given time window.

        Params:
            experiment_id: String ID of the experiment
            plants: List of plant identifiers to check
            start_time: ISO 8601 start time of the experiment
            stop_time: ISO 8601 stop time of the experiment
        Returns:
            True if plants are available, False otherwise
        Raises:
            Exception: On failure to check availability
        """
        plants_are_available = True

        for exp in self._experiments_data_list:
            # check any plants overlap in experiments
            if any(p in exp.plants for p in plants):            
                if datetime.fromisoformat(start_time) <= datetime.fromisoformat(exp.stop_time) and datetime.fromisoformat(exp.start_time) <= datetime.fromisoformat(stop_time):
                    # check if overlap is in finished, canceled or failed experiments
                    if exp.state in ['finished', 'canceled', 'failed']:
                        continue
                    else:
                        _log.warning(f"Overlaping time window with another experiment using same plants: \"{exp.experiment_id}\" from {exp.start_time} to {exp.stop_time}")
                        plants_are_available = False
                        break

        return plants_are_available

# ------ external calls ------

    def _agents_are_installed(self, agents: List[str]) -> bool:
        """
        Verify that all required agents are installed on the platform.

        Params:
            agents: List of agent identifiers to check
        Returns:
            True if all agents are installed, False otherwise
        Raises:
            Exception: If the RPC call to the agent manager fails
        """
        
        try:
            return self.vip.rpc.call(self._agent_manager, "agents_are_installed", agents).get(timeout=2)
        except Exception as e:
            _log.error(f"RPC agents_are_installed failed: {e}.")
            raise
        except gevent.Timeout as to:
            _log.error(f"RPC agents_are_installed timedout: {to}.")
            raise Exception
        

    def _submit_experiment_to_scheduler(self, experiment_id: str, agents: List[str], start_time: str, stop_time: str) -> bool:
        """
        Submit an experiment to the scheduler for execution.

        Params:
            experiment_id: String ID of the experiment
            agents: List of agent identifiers required for the experiment
            start_time: ISO 8601 start time of the experiment
            stop_time: ISO 8601 stop time of the experiment
        Returns:
            True on success
        Raises:
            Exception: If the RPC call to the scheduler fails
        """

        schedule_data = {
            "experiment_id": experiment_id,
            "agents": agents,
            "start_time": start_time,
            "stop_time": stop_time
        }
        try:
            return self.vip.rpc.call(self._scheduler, "submit_experiment_schedule", schedule_data).get(timeout=2)
        except Exception as e:
            _log.error(f"RPC submit_experiment_schedule failed: {e}.")
            raise
        except gevent.Timeout as to:
            _log.error(f"RPC submit_experiment_schedule timedout: {to}.")
            raise Exception


    def _remove_experiment_from_scheduler(self, experiment_id: str, agents: List[str]) -> bool:
        """
        Remove a scheduled experiment from the scheduler.

        Params:
            experiment_id: String ID of the experiment
            agents: List of agent identifiers assigned to the experiment
        Returns:
            True on success
        Raises:
            Exception: If the RPC call to the scheduler fails
        """

        schedule_data = {
            "experiment_id": experiment_id,
            "agents": agents
        }
        try:
            return self.vip.rpc.call(self._scheduler, "remove_experiment_schedule", schedule_data).get(timeout=2)
        except Exception as e:
            _log.error(f"RPC remove_experiment_schedule failed: {e}.")
            raise
        except gevent.Timeout as to:
            _log.error(f"RPC remove_experiment_schedule timedout: {to}.")
            raise Exception


    def _start_logging_topics(self, experiment_id: str, topics_to_log: List[str]) -> bool:
        """
        Start logging topics for an experiment via the logger agent.

        Params:
            experiment_id: String ID of the experiment
            topics_to_log: List of topic strings to log
        Returns:
            True on success
        Raises:
            Exception: If the RPC call to the logger fails
        """

        try:
            return self.vip.rpc.call(self._logger, "start_logging_topics", experiment_id, topics_to_log).get(timeout=2)
        except Exception as e:
            _log.error(f"RPC start_logging_topics failed: {e}.")
            raise
        except gevent.Timeout as to:
            _log.error(f"RPC start_logging_topics timedout: {to}.")
            raise Exception


    def _stop_logging_topics(self, experiment_id: str) -> bool:
        """
        Stop logging topics for an experiment via the logger agent.

        Params:
            experiment_id: String ID of the experiment
        Returns:
            True on success
        Raises:
            Exception: If the RPC call to the logger fails
        """

        try:
            return self.vip.rpc.call(self._logger, "stop_logging_topics", experiment_id).get(timeout=2)
        except Exception as e:
            _log.error(f"RPC stop_logging_topics failed: {e}.")
            raise
        except gevent.Timeout as to:
            _log.error(f"RPC stop_logging_topics timedout: {to}.")
            raise Exception
        
    def _get_plant_topics(self, plants: Optional[List[str]] = None) -> List[str]:
        """
        Retrieve plant specific topics like status and error topics. 
        Via RPC to the topic registry.
        
        Params:
            plants: a list of string plant names for the experiment
        Returns:
            A list of plant topics. Empty list on fail
        """
        if plants and not isinstance(plants, list):
            _log.error(f"_get_plant_topics: Plants have to be a list")
            return []
        elif plants == None:
            _log.error(f"_get_plant_topics: No plants were listed")
            return []

        plant_topics: List[str] = []
        try:
            result = self.vip.rpc.call(self._topic_registry, "get_list_of_internal_topics", topic_type_list_match=["error", "status", "sensor"], plant_name_list_match=plants).get(timeout=2)
            plant_topics = plant_topics + result

        except Exception as e:
            _log.error(f"RPC search_topics for plant topics failed: {e}.")
        except gevent.Timeout as to:
            _log.error(f"RPC search_topics for plant topics timedout: {to}.")

        return plant_topics

    def _get_feedback_topics(self, topics_to_log: List[str]) -> List[str]:
        """
        Find feedback topics for the provided command topics to log for the experiment if any exist. 
        Via RPC to the topic registry.

        Params:
            topics_to_log: a list of topics to log for the experiment
        Returns:
            A list of feedback topics. Empty list on fail
        """
        if topics_to_log and not isinstance(topics_to_log, list):
            _log.error(f"_get_feedback_topics: Topics to log have to be a list.")
            return []
        elif topics_to_log == None:
            _log.error(f"_get_feedback_topics: No topics to log were listed")
            return []

        feedback_topics: List[str] = []
        try:
            result = self.vip.rpc.call(self._topic_registry, "search_topics", topic_type_list_match=["command"], internal_topics_list_match=topics_to_log).get(timeout=2)
            for key, value in result.items():
                feedback_topics.append(value.get("feedback_topic"))
        
        except Exception as e:
            _log.error(f"RPC search_topics for feedback topics failed: {e}.")
        except gevent.Timeout as to:
            _log.error(f"RPC search_topics for feedback topics timedout: {to}.")

        return feedback_topics

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
    utils.vip_main(expmanager, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
