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

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def durtest(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Durtest
    :rtype: Durtest
    """
    return Durtest(**kwargs)


class Durtest(Agent):
    """
    Docstring for Durtest
    WARNING: AGENT DEPRECATED. DONT USE IN RUNNING SYSTEM
    This agent was used to test conenction to extern mqtt Broker and over long duration 
    """


    def __init__(self, **kwargs):
        super(Durtest, self).__init__(**kwargs)
        _log.info("Duration experiment agent startet with identity: " + self.core.identity)
        
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
 
    def _configure(self, config_name, action, contents):
        pass
        # subscribe to feedback
        
    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        gevent.sleep(2)
        self.test_passive()

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        _log.info(f"Agent {self.core.identity} over and out.")

    def test_passive(self):
        while True:
            gevent.sleep(900)
        #self.topic = "bhkw/laeuft"
        #self.vip.pubsub.subscribe(peer="pubsub", prefix=self.topic, callback=self._log)

    def test_active(self):
        command_topic1 = "command/bhkw/einschaltpunkt"
        feedback_topic1 = "feedback/bhkw/einschaltpunkt"
        command_topic2 = "command/bhkw/ausschaltpunkt"
        feedback_topic2 = "feedback/bhkw/ausschaltpunkt"
        sensor_topic = "bhkw/sollwert"
        self.vip.pubsub.subscribe(peer="pubsub", prefix=feedback_topic1, callback=self._on_feedback)
        self.vip.pubsub.subscribe(peer="pubsub", prefix=feedback_topic2, callback=self._on_feedback)
        self.vip.pubsub.subscribe(peer="pubsub", prefix=sensor_topic, callback=self._log)

        ein = 0
        aus = 0 
        count = 0
        while True:
            
            if(count%2==0):
                ein = 40
                aus = 80
            else:
                ein = 80
                aus = 40
                
            header = {"source":"test", "target":"mqtt", "timestamp": datetime.now(timezone.utc).isoformat()}
            self.vip.pubsub.publish("pubsub", command_topic1, header, ein)
            _log.debug(f"Sending message, topic: {command_topic1}, header:{header}, payload: {ein}")
            self.vip.pubsub.publish("pubsub", command_topic2, header, aus)
            _log.debug(f"Sending message, topic: {command_topic2}, header:{header}, payload: {aus}")
            count += 1
            gevent.sleep(60)

    def _on_feedback(self, peer, sender, bus, topic, headers, message):
        _log.debug(f"Feedback to the message: \"{message}\"")

    def _log(self, peer, sender, bus, topic, headers, message):
        _log.debug(f"Message logged. \"{topic}\": \"{message}\"")



def main():
    """Main method called to start the agent."""
    utils.vip_main(durtest, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
