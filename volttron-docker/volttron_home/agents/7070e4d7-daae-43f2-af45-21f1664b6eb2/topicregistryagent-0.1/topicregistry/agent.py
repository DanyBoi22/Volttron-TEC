"""
Topic Registry Agent

This agent provides a centralized registry for mapping internal to external topics
and serves as a discovery interface for agents and users. Topic mappings are stored
in a config file and exposed via RPC.

"""

__docformat__ = "reStructuredText"

import logging
import sys
import json
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, model_validator
from validators.validators import ValidationRule, ValidationType
import jmespath
import gevent

from metadata.metadata_mixin import MetadataMixin

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

class TopicDefinition(BaseModel):
    type: str
    topics: Dict[str, str]
    meta: Optional[Dict[str, Any]] = None
    validation: Optional[List[ValidationRule]] = None

    @model_validator(mode="before")
    def validate_topic_dict(cls, values):
        topic_type = values.get("type")
        topics = values.get("topics", {})
        validation = values.get("validation", None)
        
        if "external" not in topics:
            raise KeyError("Topics require 'external' topic")

        if topic_type == "command" and "validated" not in topics:
            raise KeyError("Command topics require 'validated' topic")
        if topic_type == "command" and "feedback" not in topics:
            raise KeyError("Command topics require 'feedback' topic")
        if topic_type == "command" and validation is None:
            raise KeyError("Command topics require list of validation rules. If non needed, pass an empty list.")
        
        return values

def topicregistry(config_path, **kwargs):
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return TopicRegistry(config, **kwargs)

class TopicRegistry(Agent, MetadataMixin):

    def __init__(self, config, **kwargs):
        super(TopicRegistry, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)

        self._config = config
        self._plants_topics_data: Dict[str, Dict[str, TopicDefinition]] = {}
        # flattened dict for easier search with jmespath
        self._flattened_topics_data: List[Dict[str, Any]] = []

        self._agent_manager = config.get("agent_manager_identity", "agentmanageragent-0.1_1")

        # Support dynamic reloading
        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        

    def _configure(self, config_name, action, contents):
        _log.info(f"Registry config updated ({action})")
        self._config = contents
        self._load_plants_topics_data()
        self._flatten_dict()


# ------------------ RPC exposed functions ------------------
    @RPC.export
    def search_topics(self, plant_name_list_match: Optional[List[str]] = None, topic_type_list_match: Optional[List[str]] = None, external_topics_list_match: Optional[List[str]] = None, internal_topics_list_match: Optional[List[str]] = None, feedback_topics_list_match: Optional[List[str]] = None, text_info_match: Optional[str] = None) -> Dict[str, Any]:
        """
        Generic function to filter topics based on matches using jmespath lib.

        Params:
            external_topics_list_match: Explicit external topics to match.
            internal_topics_list_match: Explicit internal topics to match.
            plant_name_list_match: List of plant name filters (case-insensitive).
            topic_type_list_match: List of topic types to match.
            feedback_topics_list_match: List of feedback topics to match.
            text_info_match: Free-text filter across external topic, internal topic, and metadata.

        Returns:
            Dict mapping. Output format:
                {
                    internal_topic: {
                        "plant_name": plant name,
                        "type": topic type,
                        "external_topic": topic internal,
                        "meta": topic metadata,

                            if the topic is a command topic the return includes these fields aswell:
                        "validated_topic": topic for validated commands 
                        "feedback_topic": topic for feedback on commands
                        "validation": lsit of valdiation rules
                    },
                    ...
                }
        """
        # Check the inout params can be reinforced with beartype or something similar
        if plant_name_list_match and not isinstance(plant_name_list_match, List):
            raise KeyError(f"Key \"plant_name_list_match\" must be a List, got {plant_name_list_match.__class__.__name__}")
        if topic_type_list_match and not isinstance(topic_type_list_match, List):
            raise KeyError(f"Key \"topic_type_list_match\" must be a List, got {topic_type_list_match.__class__.__name__}")
        if external_topics_list_match and not isinstance(external_topics_list_match, List):
            raise KeyError(f"Key \"external_topics_list_match\" must be a List, got {external_topics_list_match.__class__.__name__}")
        if internal_topics_list_match and not isinstance(internal_topics_list_match, List):
            raise KeyError(f"Key \"internal_topics_list_match\" must be a List, got {internal_topics_list_match.__class__.__name__}")
        if feedback_topics_list_match and not isinstance(feedback_topics_list_match, List):
            raise KeyError(f"Key \"feedback_topics_list_match\" must be a List, got {feedback_topics_list_match.__class__.__name__}")
        if text_info_match and not isinstance(text_info_match, str):
            raise KeyError(f"Key \"text_info_match\" must be a String, got {text_info_match.__class__.__name__}")


        # Build a query string dynamically
        query_parts = []

        # Plant name matching
        if plant_name_list_match:
            query_parts.append(
                "(" + " || ".join([f"plant_name=='{p}'" for p in plant_name_list_match]) + ")"
            )

        # Topic type matching
        if topic_type_list_match:
            query_parts.append(
                "(" + " || ".join([f"type=='{t}'" for t in topic_type_list_match]) + ")"
            )

        # External topics matching
        if external_topics_list_match:
            query_parts.append(
                "(" + " || ".join([f"external=='{e}'" for e in external_topics_list_match]) + ")"
            )

        # Internal topics matching
        if internal_topics_list_match:
            query_parts.append(
                "(" + " || ".join([f"internal=='{i}'" for i in internal_topics_list_match]) + ")"
            )

        # Feedback topics matching
        if feedback_topics_list_match:
            query_parts.append(
                "(" + " || ".join([f"feedback=='{f}'" for f in feedback_topics_list_match]) + ")"
            )

        # Text matching in meta and topic names
        if text_info_match:
            # simplistic: search external, internal, and meta values
            query_parts.append("("
                f"contains(external, '{text_info_match}') || "
                f"contains(internal, '{text_info_match}') || "
                f"contains(to_string(meta), '{text_info_match}')"
            ")")

        query = "[?" + " && ".join(query_parts) + "]" if query_parts else "[]"

        # run the query
        try:
            results = jmespath.search(query, self._flattened_topics_data)
        except Exception as e:
            _log.error(f"An error occured while searching topics in the JSON file: {e}")

        dict_results = {}
        for entry in results:
            if (entry.get("type") == "command"):
                dict_results[entry.get("internal")] = {
                    "plant_name": entry.get("plant_name"),
                    "type": entry.get("type"),
                    "external_topic": entry.get("external"),
                    "meta": entry.get("meta"),
                    "validated_topic": entry.get("validated"),
                    "feedback_topic": entry.get("feedback"),
                    "validation": [rule.model_dump() for rule in entry.get("validation")] if entry.get("validation") else None # TODO: make it serialisable: the validation rule type is not json serialisable on its own, this can cause problem if rpc called directly. 
                }
            else:
                dict_results[entry.get("internal")] = {
                    "plant_name": entry.get("plant_name"),
                    "type": entry.get("type"),
                    "external_topic": entry.get("external"),
                    "meta": entry.get("meta")
                }
        return dict_results

# ------------------ Topic mappings and lists needed for infrastructure ------------------
    @RPC.export
    def get_list_of_internal_topics(self, topic_type_list_match: Optional[List[str]] = None, plant_name_list_match: Optional[List[str]] = None) -> List[str]:
        """
        Returns a list of internal topics. Optionally filtered by provided topic type and or plant name

        Params:
            topic_type_list_match: list of topic types to filter for
            plant_name_list_match: list of plant names to filter for
        Returns:
            List with internal topics
        """

        topic_list: List[str] = []
        topics = self.search_topics(topic_type_list_match=topic_type_list_match, plant_name_list_match=plant_name_list_match)
        for internal, details in topics.items():
            if internal:
                topic_list.append(internal)

        return topic_list
    
    @RPC.export
    def get_external_to_internal_noncommand_map(self, plant_name_list_match: Optional[List[str]] = None) -> Dict[str, str]:
        """ 
        Returns a mapping of external status topic to internal non command topic. For status, sensor, error and warning messages from plants.
        For MQTT interface.

        
        Params:
            plant_name_list_match: list of plant names to filter for
        Returns:
            Dict with topic mappings. Output format:
            {
                external status topic: internal status topic,
                ...
            }
        """

        mapping: Dict[str, str] = {}
        topics = self.search_topics(topic_type_list_match=["sensor", "status", "error", "warning"], plant_name_list_match=plant_name_list_match)
        for internal, details in topics.items():
            external = details.get("external_topic")
            if internal:
                mapping[external] = internal
        return mapping


    @RPC.export
    def get_external_to_validated_commands_map(self, plant_name_list_match: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Returns mapping of external command topic to internal validated command topic.
        For MQTT interface.
        
        Params:
            plant_name_list_match: list of plant names to filter for
        Returns:
            Dict with topic mappings. Output format:
            {
                external command topic: validated internal command topic,
                ...
            }
        """

        mapping: Dict[str, str] = {}
        topics = self.search_topics(topic_type_list_match=["command"], plant_name_list_match=plant_name_list_match)
        for internal, details in topics.items():
            validated = details.get("validated_topic")
            external = details.get("external_topic")
            if validated:
                mapping[external] = validated
        return mapping

    @RPC.export
    def get_unvalidated_to_validated_commands_map(self, plant_name_list_match: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Returns a mapping of internal unvalidated command topic to internal validated command topic
        For plant control agents.
        
        Params:
            plant_name_list_match: list of plants to filter for
        Returns:
            Dict with topic mappings. Output format:
            {
                internal unvalidated command topic: internal validated command topic,
                ...
            }
        """

        mapping: Dict[str, str] = {}
        topics = self.search_topics(topic_type_list_match=["command"], plant_name_list_match=plant_name_list_match)
        for unvalidated, details in topics.items():
            validated = details.get("validated_topic")
            if validated and unvalidated:
                mapping[unvalidated] = validated
        return mapping
    

    @RPC.export
    def get_unvalidated_to_validation_rule_map(self, plant_name_list_match: Optional[List[str]] = None) -> Dict[str, List]:
        """
        Returns mapping: internal unvalidated command topic -> list of valdiation rules for the topic
        For plant control agents.
        
        Params:
            plant_name_list_match: list of plants to filter for
        Returns:
            Dict with topic mappings. Output format:
            {
                internal unvalidated command topic: List of validation rules,
                ...
            }
        """

        mapping: Dict[str, str] = {}
        topics = self.search_topics(topic_type_list_match=["command"], plant_name_list_match=plant_name_list_match)
        for unvalidated, details in topics.items():
            validation = details.get("validation")
            if validation and unvalidated:
                mapping[unvalidated] = validation
        return mapping
    

    @RPC.export
    def get_unvalidated_to_feedback_map(self, plant_name_list_match: Optional[List[str]] = None) -> Dict[str, List]:
        """
        Returns mapping: internal unvalidated command topic -> feedback command topic
        For plant control agents.
        
        Params:
            plant_name_list_match: list of plants to filter for
        Returns:
            Dict with topic mappings. Output format:
            {
                internal unvalidated command topic: command topic,
                ...
            }
        """

        mapping: Dict[str, str] = {}
        topics = self.search_topics(topic_type_list_match=["command"], plant_name_list_match=plant_name_list_match)
        for unvalidated, details in topics.items():
            feedback = details.get("feedback_topic")
            if feedback and unvalidated:
                mapping[unvalidated] = feedback
        return mapping

# ------------------ Helper functions ------------------

    def _load_plants_topics_data(self):
        """
        Parse and validate data from config
        On fail or validation errors logs the error and loads empty values
        """
        self._plants_topics_data: Dict[str, Dict[str, TopicDefinition]] = {}
        raw_data = self._config.get("Plants topics data", {})

        for plant_name, external_topics_dict in raw_data.items():
            self._plants_topics_data[plant_name] = {}
            for external_topic, topic_data_dict in external_topics_dict.items():
                try:
                    self._plants_topics_data[plant_name][external_topic] = TopicDefinition(**topic_data_dict)
                except Exception as e:
                    _log.error(f"Invalid topic definition {external_topic} for plant {plant_name}: {e}")


    def _flatten_dict(self):
        # flatten the nested dict for easier machine querry

        self._flattened_topics_data = []
        for plant, internal_topics in self._plants_topics_data.items():
            for internal, topic_def in internal_topics.items():
                data_dict = {}
                if topic_def.type == "command":
                    data_dict={
                        "plant_name": plant,
                        "type": topic_def.type,
                        "external": topic_def.topics.get("external"),
                        "internal": internal,
                        "validated": topic_def.topics.get("validated"),
                        "feedback":topic_def.topics.get("feedback"),
                        "meta": topic_def.meta,
                        "validation": topic_def.validation
                    }
                else:
                    data_dict={
                        "plant_name": plant,
                        "type": topic_def.type,
                        "external": topic_def.topics.get("external"),
                        "internal": internal,
                        "meta": topic_def.meta,
                    }
                self._flattened_topics_data.append(data_dict)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        try:
            result = self.vip.rpc.call(self._agent_manager, "enable_agent_autostart", self.core.identity, "50").get(timeout=2)
            _log.debug(f"Enabling autostart for {self.core.identity}: {result}")
        except gevent.Timeout as to:
            _log.error(f"RPC enable_agent_autostart time out: {to}.")


    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        pass

def main():
    utils.vip_main(topicregistry, version=__version__)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass