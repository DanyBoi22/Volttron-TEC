"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
import paho.mqtt.client as mqtt
import csv
import gevent
from datetime import datetime, timedelta, timezone
import uuid

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def tester(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Tester
    :rtype: Tester
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Tester(config, **kwargs)


class Tester(Agent):
    """
    Document agent constructor here.
    """
    #def __init__(self, setting1=1, setting2="some/random/topic", broker_name="localhost", broker_port=1883, topic="some/random/topic", csv_name="tester_logs.scv", **kwargs):
    def __init__(self, config, **kwargs):
        super(Tester, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        self.config = config
        self._agent_manager = config.get("agent_manager_identity")
        self._target_identity = config.get("target_agent_identity")
        self._scheduler = config.get("scheduler_identity")
        self._experiment_manager = config.get("exepriment_manager_identity")
        self._logger = config.get("logger_identity")

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        gevent.sleep(2)
        self.test_duration()
        self.core.stop()
    
    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        _log.info(f"Tester Agent over and out.")

    def test_logger(self):
        exp_id = "testexp"
        topic = "testtopic"
        topic_list = [topic]
        
        _log.info(f"Attempting to log topics ...")
        result = self.vip.rpc.call(self._logger, "start_logging_topics", exp_id, topic_list).get(timeout=3)
        _log.info(f"Topics are being logged: {result}")

        self.vip.pubsub.publish("pubsub", topic, message="payload")
        gevent.sleep(5)
        self.vip.pubsub.publish("pubsub", topic, message="payload")
        gevent.sleep(5)
        self.vip.pubsub.publish("pubsub", topic, message="payload")
        gevent.sleep(5)

        result = self.vip.rpc.call(self._logger, "stop_logging_topics", exp_id).get(timeout=3)

    def test_mqtt_interface_pipeline(self):
        # send couple of time message on topic "validated/testcommand" on internal bus
        topic = "validated/testcommand"
        headers = {"source":"tester",
                   "target":"mqttinterface",
                   "timestamp": datetime.now().isoformat()}
        payload = "Testi"
        self.vip.pubsub.publish("pubsub", topic, headers=headers, message=payload)
        gevent.sleep(5)
        self.vip.pubsub.publish("pubsub", topic, headers=headers, message=payload)
        gevent.sleep(5)
        self.vip.pubsub.publish("pubsub", topic, headers=headers, message=payload)
        

    def test_agent_manager(self):
        try:
            _log.info(f"Attempting to start agent {self._target_identity}")
            result = self.vip.rpc.call(self._agent_manager, "start_agent", self._target_identity).get(timeout=10)
            _log.info(f"Start result: {result}")
        except Exception as e:
            _log.error(f"Failed to start agent: {e}")

        gevent.sleep(10)

        try:
            _log.info(f"Attempting to stop agent {self._target_identity}")
            result = self.vip.rpc.call(self._agent_manager, "stop_agent", self._target_identity).get(timeout=10)
            _log.info(f"Stop result: {result}")
        except Exception as e:
            _log.error(f"Failed to stop agent: {e}")

    def test_schedule(self):
        """
        Schedule a test experiment with two agents.
        """
        
        now = datetime.now(timezone.utc)
        start_time = now + timedelta(seconds=20)
        stop_time = now + timedelta(seconds=80)
        expid = str(uuid.uuid1())
        experimenter = "Dany"
        description = "Integration test"
        plants = ["Test"]
        supervisor_name = "Super cool supervisor"
        agents_for_experiment = ["exptest1agent-0.1_1", "exptest1agent-0.1_2"]
        topics_to_log = ["raw/testcommand1","raw/testcommand2"]
        experiment = {
            "experiment_id": expid,
            "start_time": start_time.isoformat(),
            "stop_time": stop_time.isoformat(),
            "experimenter": experimenter,
            "description": description,
            "plants": plants
        }
        
        try:
            # Submit
            _log.info(f"Test trying to submit experiment {expid}...")
            result = self.vip.rpc.call(self._experiment_manager, "submit_experiment_data", experiment).get(timeout=3)
            if result == expid:
                _log.info(f"Test schedule experiment {result} is successfull") 
            else:
                _log. error(f"Test schedule experiment is failed")
                return

            # Authorise
            _log.info(f"Test trying to authorise experiment {expid}...")
            result = self.vip.rpc.call(self._experiment_manager, "authorise_experiment", expid, supervisor_name).get(timeout=3)
            if result:
                _log.info(f"Test authorise experiment {expid} is successfull") 
            else:
                _log. error(f"Test authorise experiment is failed")
                return

            # Finalize
            _log.info(f"Test trying to finalize experiment {expid}...")
            result = self.vip.rpc.call(self._experiment_manager, "finalize_experiment", expid, agents_for_experiment, topics_to_log).get(timeout=3)
            if result:
                _log.info(f"Test finalize experiment {expid} is successfull") 
            else:
                _log. error(f"Test finalize experiment is failed")
                return
            
        except Exception as e:
            _log.error(f"Error while running integration test: {e}")


    def test_duration(self):
        """
        Schedule a duration test experiment with single agents.
        """
        
        now = datetime.now(timezone.utc)
        start_time = now + timedelta(seconds=20)
        stop_time = now + timedelta(hours=5)
        expid = str(uuid.uuid1())
        experimenter = "Dany"
        description = "Impulsbeladung test"
        plants = ["BHKW"]
        supervisor_name = "Super cool supervisor"
        agents_for_experiment = ["impulsetestagent-0.1_1"]
        topics_to_log = ["command/bhkw/einschaltpunkt", "command/bhkw/ausschaltpunkt", "bhkw/einschaltpunkt","bhkw/ausschaltpunkt","bhkw/bereit","bhkw/laeuft","bhkw/error","bhkw/warning","bhkw/temperatur/ruecklauf","bhkw/temperatur/vorlauf","bhkw/leistung/elektrisch/ist","bhkw/leistung/thermisch/ist"]

        experiment = {
            "experiment_id": expid,
            "start_time": start_time.isoformat(),
            "stop_time": stop_time.isoformat(),
            "experimenter": experimenter,
            "description": description,
            "plants": plants
        }

        
        try:
            # Submit
            _log.info(f"Test trying to submit experiment {expid}...")
            result = self.vip.rpc.call(self._experiment_manager, "submit_experiment_data", experiment).get(timeout=3)
            if result == expid:
                _log.info(f"Test schedule experiment {result} is successfull") 
            else:
                _log. error(f"Test schedule experiment is failed")
                return

            # Authorise
            _log.info(f"Test trying to authorise experiment {expid}...")
            result = self.vip.rpc.call(self._experiment_manager, "authorise_experiment", expid, supervisor_name).get(timeout=3)
            if result:
                _log.info(f"Test authorise experiment {expid} is successfull") 
            else:
                _log. error(f"Test authorise experiment is failed")
                return

            # Finalize
            _log.info(f"Test trying to finalize experiment {expid}...")
            result = self.vip.rpc.call(self._experiment_manager, "finalize_experiment", expid, agents_for_experiment, topics_to_log).get(timeout=3)
            if result:
                _log.info(f"Test finalize experiment {expid} is successfull") 
            else:
                _log. error(f"Test finalize experiment is failed")
                return
            
        except Exception as e:
            _log.error(f"Error while running integration test: {e}")


    def test_cancel(self):
        expid = "df8326f0-c3e3-11f0-be46-00155df10b63"
        try:
            # Submit
            _log.info(f"Test trying to cancel experiment {expid}...")
            result = self.vip.rpc.call(self._experiment_manager, "cancel_experiment", expid).get(timeout=3)
            if result == True:
                _log.info(f"Test cancel experiment success") 
            else:
                _log. error(f"Test cancel experiment is failed")
                return
            
        except Exception as e:
            _log.error(f"Error while running integration test: {e}")

    
    def test_impulse_naive(self):
        exp_id = "testimpulse_" + str(uuid.uuid1())
        topic_list = ["command/bhkw/ausschaltpunkt", "command/bhkw/einschaltpunkt"]
        test_agent = "impulsetestagent-0.1_1"
        test_time = 15*60 # 15 mins 
        
        # start logging topics
        result = self.vip.rpc.call(self._logger, "start_logging_topics", exp_id, topic_list).get(timeout=3)
        # start impulsetest
        result = self.vip.rpc.call(self._agent_manager, "start_agent", test_agent).get(timeout=3)
        
        gevent.sleep(test_time)

        result = self.vip.rpc.call(self._agent_manager, "stop_agent", test_agent).get(timeout=3)
        
        result = self.vip.rpc.call(self._logger, "stop_logging_topics", exp_id).get(timeout=3)
        

def main():
    """Main method called to start the agent."""
    utils.vip_main(tester, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
