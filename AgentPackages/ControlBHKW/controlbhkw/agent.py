"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import gevent
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

from metadata.metadata_mixin import MetadataMixin
from validators.validators import validate_command

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

DEFAULT_AGENT_MANAGER_IDENTITY = "agentmanageragent-0.1_1"
DEFAULT_TOPIC_REGISTRY_IDENTITY = "topicregistryagent-0.1_1"
DEFAULT_MQTT_INTERFACE_IDENTITY = "mqttinterfaceagent-0.2_1"

def controlbhkw(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Controlbhkw
    :rtype: Controlbhkw
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Controlbhkw(config, **kwargs)

class Controlbhkw(Agent, MetadataMixin):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Controlbhkw, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)

        self._config = config
        self._unvalidated_to_validated_topic_map: Dict[str, str] = {}           # {"unvalidated_topic": "validated_topic", ...}
        self._unvalidated_to_feedback_topic_map: Dict[str, str] = {}            # {"unvalidated_topic": "feedback_topic", ...} 
        self._unvalidated_topic_to_validation_rule_map: Dict[str, List[Any]] = {}     # {"unvalidated_topic": [{"validation_type": "type", ...params...}, ...], ...}
        # TODO: Sensor topics
        self._status_topic_list: List[str] = []              
        self._error_topic_list: List[str] = []
        self._command_messages_last_seen: Dict[str, datetime] = {}

        self._plant_name = self._config.get("plant_name")
        self._topic_registry = config.get("topic_registry_identity", DEFAULT_TOPIC_REGISTRY_IDENTITY)
        self._agent_manager = config.get("agent_manager_identity", DEFAULT_AGENT_MANAGER_IDENTITY)
        self._mqtt_interface = config.get("mqtt_interface_identity", DEFAULT_MQTT_INTERFACE_IDENTITY)

        self.vip.config.set_default("config", self._config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")


    def configure(self, config_name, action, contents):
        self._config = contents
        self._plant_name = self._config.get("plant_name")
        self._topic_registry = self._config.get("topic_registry_identity", self._topic_registry)
        self._agent_manager = self._config.get("agent_manager_identity", self._agent_manager)
        self._mqtt_interface = self._config.get("mqtt_interface_identity", self._mqtt_interface)
        self._load_topic_mappings()
        self._subscribe_topics()


    def _load_topic_mappings(self):
        """
        Retrieve topic lists, mappings and validation rules from TopicRegistry.
        """
        try:
            self._unvalidated_to_validated_topic_map: Dict[str, str] = self._get_command_mapping()
            
            self._unvalidated_to_feedback_topic_map: Dict[str, str] = self._get_command_feedback()

            self._unvalidated_topic_to_validation_rule_map: Dict[str, List[Any]] = self._get_validation_rules()

            self._status_topic_list: List[str] = self._get_status_topics()

            self._error_topic_list: List[str] = self._get_error_topics()

            _log.debug(f"Loaded topic mappings.")
        except Exception as e:
            _log.error(f"Failed loading topic mappings: {e}")
            raise


    def _subscribe_topics(self):
        """
        Subscribes to unvalidated topics for command interception.
        Subscribes to status topics to monitor the plant.
        """
        for unvalidated_topic in self._unvalidated_to_validated_topic_map.keys():
            self.vip.pubsub.subscribe(
                peer="pubsub", # TODO maybe its own peer group for more security
                prefix=unvalidated_topic,
                callback=self._on_command_message
            )
            _log.debug(f"Subscribed to {unvalidated_topic} command topic")

        for status_topic in self._status_topic_list:
            self.vip.pubsub.subscribe(
                peer="pubsub",
                prefix=status_topic,
                callback=self._on_status_message
            )
            _log.debug(f"Subscribed to {status_topic} status topic")
        
        for error_topic in self._error_topic_list:
            self.vip.pubsub.subscribe(
                peer="pubsub",
                prefix=error_topic,
                callback=self._on_error_message
            )
            _log.debug(f"Subscribed to {error_topic} error topic")


    def _on_command_message(self, peer, sender, bus, topic, headers, message):
        """
        Callback function to on receiving unvalidated plant command message then apply validation and republish if valid.
        """

        # get the list of validation rules 
        rules = self._unvalidated_topic_to_validation_rule_map.get(topic)
        validation_message: str = None 
        time_now = datetime.now(timezone.utc)
        
        # TODO: multiple messages in short time are discarded?
        #if not self._topic_is_timed_out(topic, time_now): 
        try:
            # validate the payload
            validated_value = validate_command(message, rules)
            validation_message = "Validation successfull"
        
            # publish validated command
            validated_topic = self._unvalidated_to_validated_topic_map[topic]
            header = {"source": self.core.identity, "target": self._mqtt_interface, "timestamp": time_now.isoformat()}
            self.vip.pubsub.publish(peer="pubsub", topic=validated_topic, headers=header, message=validated_value)
            #_log.debug(f"Validated {topic} -> {validated_topic}: {validated_value}")

        # TODO: match msg id?

        except ValueError as e:
            # TODO: need more data like timestamp and etc. or outload the publishing and message matching to a client
            _log.warning(f"Validation failed for {topic}: {e}")
            validation_message = f"Validation failed for {topic}: {e}"
        
        #else: validation_message = "Message timedout, wait."

        # publish validation feedback
        validated_topic = self._unvalidated_to_feedback_topic_map[topic]
        header = {"source": self.core.identity, "target": "volttron_bus", "timestamp": time_now.isoformat()}
        self.vip.pubsub.publish(peer="pubsub", topic=validated_topic, headers=header, message=validation_message)
        

    def _on_status_message(self, peer, sender, bus, topic, headers, message):
        """
        Callback function on receiving plant status from MQTT interface and update PlantRegistry.
        """
        try:
            # TODO
            #status = message.get("status")
            #self.vip.rpc.call(self.plant_registry, "update_status", plant_name = self.plant_name, status = status)
            #_log.debug(f"Received status message.{topic}: {message}")
            pass
        except Exception as e:
            _log.error(f"Failed to update status: {e}")


    def _on_error_message(self, peer, sender, bus, topic, headers, message):
        """
        Callback function on receiving plant error messages from MQTT interface and update PlantRegistry.
        """
        try:
            # TODO
            #status = message.get("status")
            #self.vip.rpc.call(self.plant_registry, "update_status", plant_name = self.plant_name, status = status)
            #_log.debug(f"Received error message.{topic}: {message}")
            pass
        except Exception as e:
            _log.error(f"Failed to update status: {e}")


    def _topic_is_timed_out(self, topic: str, now: datetime) -> bool:
        """
        Check whether the topic is timed out and should be ignored.

        Params:
            topic: topic as string
            now: datetime object of current time to check against

        Returns:
            bool: True if message should be ignored, False otherwise 
        """
        timeout = self._unvalidated_topic_to_validation_rule_map.get(topic).get("timeout")
        last_time = self._command_messages_last_seen.get(topic)

        # If no timeout is defined, validate
        if not timeout:
            return False

        # If this is the first message, validate
        if not last_time:
            self._command_messages_last_seen[topic] = now
            return False

        # Check if timeout window has passed
        if now - last_time >= timeout:
            self._command_messages_last_seen[topic] = now
            return False

        # Too soon — ignore message
        return True 

    
    # -----------------------
    # for easier unit testing
    def _get_command_mapping(self):
        return self.vip.rpc.call(self._topic_registry, "get_unvalidated_to_validated_commands_map", plant_name_list_match=[self._plant_name]).get(timeout=2)
    
    def _get_command_feedback(self):
        return self.vip.rpc.call(self._topic_registry, "get_unvalidated_to_feedback_map", plant_name_list_match=[self._plant_name]).get(timeout=2)
    
    def _get_validation_rules(self):
        return self.vip.rpc.call(self._topic_registry, "get_unvalidated_to_validation_rule_map", plant_name_list_match=[self._plant_name]).get(timeout=2)
    
    def _get_status_topics(self):
        return self.vip.rpc.call(self._topic_registry, "get_list_of_internal_topics", topic_type_list_match=["status"], plant_name_list_match=[self._plant_name]).get(timeout=2)
    
    def _get_error_topics(self):
        return self.vip.rpc.call(self._topic_registry, "get_list_of_internal_topics", topic_type_list_match=["error"], plant_name_list_match=[self._plant_name]).get(timeout=2)
    # -----------------------

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
    utils.vip_main(controlbhkw, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
