"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import os
import csv
import gevent
from typing import Dict, List
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

from metadata.metadata_mixin import MetadataMixin

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

DEFAULT_LOG_DIR = "/home/volttron/.volttron/AgentPackages/Logger/loggs/"
DEFAULT_AGENT_MANAGER = "agentmanageragent-0.1_1"

def logger(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Testlog
    :rtype: Testlog
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Logger(config, **kwargs)


class Logger(Agent, MetadataMixin):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Logger, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)
        
        self._config = config
        self._agent_manager = config.get("agent_manager_identity", DEFAULT_AGENT_MANAGER)
        self._log_dir = self._config.get("logger_directory", DEFAULT_LOG_DIR)

        self._subscriptions: Dict[str, List[str]] = {}  # experiment_id -> topics list
        self._file_handles: Dict[str, str] = {}  # experiment_id -> file path

        self.vip.config.set_default("config", self._config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        self._config = contents
        self._log_dir = self._config.get("logger_directory", self._log_dir)
        self._agent_manager = self._config.get("agent_manager_identity", self._agent_manager)

    @RPC.export
    def start_logging_topics(self, experiment_id: str, topics_to_log: List[str]) -> bool:
        """
        Subscribe to the given topics and log messages to CSV per experiment.
        """
        if not experiment_id or not topics_to_log:
            _log.error("Invalid parameters for log_topics.")
            return False
        
        if experiment_id in self._file_handles:
            _log.warning(f"Experiment {experiment_id} is already being logged")
            return False
        
        file_path = self._create_new_logfile(experiment_id)
        self._file_handles[experiment_id] = file_path
        self._subscribe_to_topics(experiment_id, topics_to_log)
        return True
    
    @RPC.export
    def stop_logging_topics(self, experiment_id: str) -> bool:
        """
        Subscribe to the given topics and log messages to CSV per experiment.
        """
        if not experiment_id:
            _log.error("Invalid parameters for stop_log_topics.")
            return False
        
        if not experiment_id in self._file_handles:
            _log.warning(f"Experiment {experiment_id} is not being logged")
            return False
        
        self._unsubscribe_from_topics(experiment_id)
        del self._file_handles[experiment_id]

        return True
    
    def _create_new_logfile(self, experiment_id: str) -> str:
        """
        Create a new log file for the experiment
        """
        # Prepare file for this experiment
        file_path = os.path.join(self._log_dir, f"topiclogs_{experiment_id}.csv")

        if not os.path.exists(file_path):
            # Create file and write header if new
            with open(file_path, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "topic", "message"])
        
        return file_path 

    def _subscribe_to_topics(self, experiment_id:str, topics: List[str]):
        """
        Subscribe to the provided list of topics on the internal bus
        """
        for topic in topics:
            self.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=self._on_message)
        
        self._subscriptions[experiment_id] = topics
        _log.info(f"Subscribed to topics to logg for experiment {experiment_id}: {topics}")

    def _unsubscribe_from_topics(self, experiment_id:str):
        """
        Unsubscribe from the provided list of topics on the internal bus
        """

        if experiment_id not in self._subscriptions:
            _log.warning(f"No subscriptions found for experiment {experiment_id}.")
            return
        
        topics: List[str] = self._subscriptions[experiment_id]
        
        # TODO: if the logger logs same topics for multiple experiments do not unsubscribe from it
        for topic in topics:
            try:
                self.vip.pubsub.unsubscribe(peer='pubsub', prefix=topic, callback=self._on_message)
                _log.debug(f"Unsubscribed from topic {topic} for experiment {experiment_id}")
            except Exception as e:
                _log.error(f"Failed to unsubscribe from {topic}: {e}")

        del self._subscriptions[experiment_id]
        _log.info(f"Unsubscribed from topics for experiment {experiment_id}: {topics}")
    
    def _on_message(self, peer, sender, bus, topic, headers, message):
        """
        Callback for handling incoming messages and logging them to the right file.
        """
        #_log.debug(f"Received message on topic {topic}")
        # extract timestamp
        timestamp = headers.get("timestamp") or "unknown"
        # Find which experiment this topic belongs to
        # TODO: to optimise the agent make reverse dict for subscriptions: topic -> List[exp_id]
        for exp_id, topics in self._subscriptions.items():
            if topic in topics:
                file_path = self._file_handles[exp_id]
                with open(file_path, "a", newline="") as file: # Append mode for csv
                    writer = csv.writer(file)
                    writer.writerow([timestamp, topic, message])
                break

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
    utils.vip_main(logger, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
