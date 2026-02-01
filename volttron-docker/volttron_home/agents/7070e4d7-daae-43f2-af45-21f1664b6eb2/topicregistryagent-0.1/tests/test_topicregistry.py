import pytest
from topicregistry.agent import TopicRegistry, TopicDefinition

# ---------------- Config load ----------------
class TestPersistenceAndConfig:
    def test_load_plants_topics_data_valid(self, sample_registry):
        # Initialize agent with sample config
        agent = TopicRegistry(sample_registry)
        # this step is requiered because by default _configure() want be called
        # to avoid hardcoding this step you could mock the Agent via volttron testing    
        agent._load_plants_topics_data()

        sample_plant_a_topics = sample_registry["Plants topics data"]["PlantA"]
        sample_plant_b_topics = sample_registry["Plants topics data"]["PlantB"]
        
        # Check Plant A
        plant_a_topics = agent._plants_topics_data.get("PlantA")
        assert plant_a_topics is not None
        assert isinstance(plant_a_topics, dict)
        
        for internal, int_topic_data in plant_a_topics.items():
            assert internal in sample_plant_a_topics
            assert internal not in sample_plant_b_topics



        #assert "external/topic/one" in plant_a_topics
        #assert isinstance(plant_a_topics["external/topic/one"], TopicDefinition)
        # external skip should not be in the data 
        #assert "external/topic/skip" not in plant_a_topics

        # Check Plant B
        #plant_b_topics = agent._plants_topics_data.get("PlantB")
        #assert plant_b_topics is not None
        # external/topic/three and external/topic/four should exist
        #assert set(plant_b_topics.keys()) == {"external/topic/three", "external/topic/four"}
        #for topic in plant_b_topics.values():
        #    assert isinstance(topic, TopicDefinition)


    def test_load_plants_topics_data_empty_config(self):
        # Agent with empty config should produce empty dict
        agent = TopicRegistry(config={"Plants topics data": {}})
        # this step is requiered because by default _configure() want be called
        # to avoid hardcoding this step you could mock the Agent via volttron testing    
        agent._load_plants_topics_data()

        agent._plants_topics_data = {}
        agent._load_plants_topics_data()
        assert agent._plants_topics_data == {}


    def test_load_plants_topics_data_missing_plants_key(self):
        # Agent with config missing "Plants topics data" key
        agent = TopicRegistry(config={})
        # this step is requiered because by default _configure() want be called
        # to avoid hardcoding this step you could mock the Agent via volttron testing    
        agent._load_plants_topics_data()

        agent._plants_topics_data = {}
        agent._load_plants_topics_data()
        # Should not fail, just empty dict
        assert agent._plants_topics_data == {}


# ---------------- The most import function ----------------
class TestSearchTopics:
    def test_filter_no_filter(self, topic_registry):
        result = topic_registry.search_topics()
        
        for key, value in result.items():
            #{"external/topic/one","external/topic/two","external/topic/three","external/topic/four"}
            #{"internal/command/one","internal/status/two","internal/command/three","internal/sensor/four"}
            assert key in {"internal/command/one","internal/status/two","internal/command/three","internal/sensor/four"}
            assert value.get("type") in {"command", "sensor", "status"}
            assert value.get("plant_name") in {"PlantA", "PlantB"}


    def test_filter_internal_topics(self, topic_registry):
        
        # single topic
        result = topic_registry.search_topics(internal_topics_list_match=["internal/status/two"])
        for key, value in result.items():
            assert key in {"internal/status/two"}

        # topic with no external topic
        result2 = topic_registry.search_topics(internal_topics_list_match=["internal/command/false1"])
        assert set(result2.keys()) == set()

        # multiple topics
        result = topic_registry.search_topics(internal_topics_list_match=["internal/command/one", "internal/status/two"])
        for key, value in result.items():
            assert key in {"internal/command/one", "internal/status/two"}

        # multiple topics with one faulty
        result = topic_registry.search_topics(internal_topics_list_match=["internal/command/false1", "internal/command/one"])
        for key, value in result.items():
            assert key in {"internal/command/one"}


    def test_filter_external_topics(self, topic_registry):
        
        # single topic
        result = topic_registry.search_topics(external_topics_list_match=["external/topic/one"])
        for key, value in result.items():
            assert value.get("external_topic") in {"external/topic/one"}

        # no external topic
        result2 = topic_registry.search_topics(external_topics_list_match=["external/topic/hagrid"])
        assert set(result2.keys()) == set()

        # multiple topics
        result = topic_registry.search_topics(external_topics_list_match=["external/topic/two", "external/topic/three"])
        for key, value in result.items():
            assert value.get("external_topic") in {"external/topic/two","external/topic/three"}

        # multiple topics with one faulty
        result = topic_registry.search_topics(external_topics_list_match=["external/topic/four", "external/topic/golum"])
        for key, value in result.items():
            assert value.get("external_topic") in {"external/topic/four"}


    def test_filter_feedback_topics(self, topic_registry):
        
        # single topic
        result = topic_registry.search_topics(feedback_topics_list_match=["command/feedback/one"])
        for key, value in result.items():
            assert value.get("feedback_topic") in {"command/feedback/one"}

        # no external topic
        result2 = topic_registry.search_topics(feedback_topics_list_match=["command/feedback/bruderlion"])
        assert set(result2.keys()) == set()

        # multiple topics
        result = topic_registry.search_topics(feedback_topics_list_match=["command/feedback/one", "command/feedback/three"])
        for key, value in result.items():
            assert value.get("feedback_topic") in {"command/feedback/one", "command/feedback/three"}

        # multiple topics with one faulty
        result = topic_registry.search_topics(feedback_topics_list_match=["command/feedback/one", "DonutOperator/he/knows/the/location/of/JimboJames"])
        for key, value in result.items():
            assert value.get("feedback_topic") in {"command/feedback/one"}

    
    def test_filter_plant_name(self, topic_registry):

        # single plant
        result = topic_registry.search_topics(plant_name_list_match=["PlantA"])
        for key, value in result.items():
            assert value.get("plant_name") in {"PlantA"}

        # plant not present
        result2 = topic_registry.search_topics(plant_name_list_match=["PopcornMachine"])
        assert set(result2.keys()) == set()

        # multiple plants
        result = topic_registry.search_topics(plant_name_list_match=["PlantA", "PlantB"])
        for key, value in result.items():
            assert value.get("plant_name") in {"PlantA", "PlantB"}
        
        # multiple plants with one not present
        result = topic_registry.search_topics(plant_name_list_match=["PlantA", "Multikocher"])
        for key, value in result.items():
            assert value.get("plant_name") in {"PlantA"}


    def test_filter_topic_type(self, topic_registry):
        
        # single type
        result = topic_registry.search_topics(topic_type_list_match=["sensor"])
        for key, value in result.items():
            assert value.get("type") in {"sensor"}

        # type not present
        result2 = topic_registry.search_topics(topic_type_list_match=["problemo"])
        assert set(result2.keys()) == set()

        # multiple types
        result = topic_registry.search_topics(topic_type_list_match=["sensor", "status"])
        for key, value in result.items():
            assert value.get("type") in {"sensor", "status"}
            
        # multiple types with one not present
        result = topic_registry.search_topics(topic_type_list_match=["sensor", "problemka"])
        for key, value in result.items():
            assert value.get("type") in {"sensor"}

        # more multiple types
        result = topic_registry.search_topics(topic_type_list_match=["sensor", "status", "command"])
        for key, value in result.items():
            assert value.get("type") in {"command", "sensor", "status"}


    def test_str_match(self, topic_registry):
        
        # simple case 1
        result = topic_registry.search_topics(text_info_match="Pump status")
        for key, value in result.items():
            assert value.get("meta") == {"description": "Pump status"}

        # simple case 2
        result = topic_registry.search_topics(text_info_match="description")
        for key, value in result.items():
            assert value.get("meta").get("description") is not None

        # little more interesting
        result = topic_registry.search_topics(text_info_match="sensor")
        for key, value in result.items():
            assert "sensor" in key \
                or "sensor" in value.get("internal_topic") \
                or "sensor" in str(value.get("meta"))
    

    def test_multiple_match_cases(self, topic_registry):

        # little more interesting
        result = topic_registry.search_topics(external_topics_list_match=["external/topic/four"], plant_name_list_match=["PlantB"], text_info_match="status") 
        for key, value in result.items():
            assert key in {"external/topic/four"}
            assert value.get("plant_name") in {"PlantB"}
            assert "status" in key \
                or "status" in value.get("internal_topic") \
                or "status" in str(value.get("meta"))
                    
        result = topic_registry.search_topics(plant_name_list_match=["PlantB"], text_info_match="status") 
        for key, value in result.items():
            assert value.get("plant_name") in {"PlantB"}
            assert "status" in key \
                or "status" in value.get("internal_topic") \
                or "status" in str(value.get("meta"))

        result = topic_registry.search_topics(topic_type_list_match=["status"], text_info_match="command") 
        assert set(result.keys()) == set()

        result = topic_registry.search_topics(topic_type_list_match=["status"], feedback_topics_list_match=["command/feedback/three"]) 
        assert set(result.keys()) == set()


# ---------------- Mappings ----------------
class TestMappings:
    def test_get_external_to_validated_commands_map(self, topic_registry):
        """
        Creates an agent with fake config file 
        and tests the mapping of external to internal validated command topics 
        """
        correct_ext_to_int_mapping = {
            "external/topic/one": "internal/command/true1",
            "external/topic/three": "internal/command/false1"
        }

        result = topic_registry.get_external_to_validated_commands_map()
        assert result == correct_ext_to_int_mapping


    def test_get_external_to_internal_noncommand_map(self, topic_registry):
        """
        Creates an agent with fake config file 
        and tests the mapping of internal to external status topics 
        """
        correct_int_to_ext_mapping = {
            "external/topic/two": "internal/status/two",
            "external/topic/four": "internal/sensor/four"
        }

        result = topic_registry.get_external_to_internal_noncommand_map()
        assert result == correct_int_to_ext_mapping


    def test_get_unvalidated_to_validated_commands_map(self, topic_registry):
        correct_int_to_ext_mapping = {
            "internal/command/one": "internal/command/true1",
            "internal/command/three": "internal/command/false1"
        }

        result = topic_registry.get_unvalidated_to_validated_commands_map()
        assert result == correct_int_to_ext_mapping


    def test_get_unvalidated_to_validated_commands_map_plant_match(self, topic_registry):
        correct_int_to_ext_mapping = {
            "internal/command/one": "internal/command/true1"
        }

        result = topic_registry.get_unvalidated_to_validated_commands_map(plant_name_list_match=["PlantA"])
        assert result == correct_int_to_ext_mapping

        correct_int_to_ext_mapping = {
            "internal/command/three": "internal/command/false1"
        }

        result = topic_registry.get_unvalidated_to_validated_commands_map(plant_name_list_match=["PlantB"])
        assert result == correct_int_to_ext_mapping





# ---------------- Topic Info ---------------- 
class TestTopicInfo:
    def test_get_internal_topic_info_found(self, topic_registry):
        """
        Test search for existing metadata for a given internal topic.
        """
        result = topic_registry.search_topics(internal_topics_list_match=["internal/command/one"])
        for key, value in result.items():
            assert value.get("meta") == {"description": "Pump status"}


    def test_get_internal_topic_info_not_found(self, topic_registry):
        """
        Test search for metadata for non existing internal topic.
        """
        result = topic_registry.search_topics(internal_topics_list_match=["internal/command/x"])
        for key, value in result.items():
            assert value.get("meta") == None


    def test_get_internal_topic_info_on_external_topic(self, topic_registry):
        """
        Test search for metadata for existing external topic.
        """
        result = topic_registry.search_topics(external_topics_list_match=["external/topic/one"])
        for key, value in result.items():
            assert value.get("meta") == {"description": "Pump status"}


    def test_get_external_topic_info_not_found(self, topic_registry):
        """
        Test search for metadata for non existing external topic.
        """
        result = topic_registry.search_topics(external_topics_list_match=["external/command/x"])
        for key, value in result.items():
            assert value.get("meta") == None