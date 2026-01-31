"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
import gevent
from datetime import datetime, timezone

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def exptest1(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Exptest1
    :rtype: Exptest1
    """
    return Exptest1(**kwargs)


class Exptest1(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, **kwargs):
        super(Exptest1, self).__init__(**kwargs)
        _log.info("Experiment test agent 1 startet with identity: " + self.core.identity)
        if self.core.identity == "exptest1agent-0.1_1":
            self.topic = "raw/testcommand1"
            self.feedback_topic = "feedback/testcommand1"
            self.message = 50
        else:
            self.topic = "raw/testcommand2"
            self.feedback_topic = "feedback/testcommand2"
            self.message = 120

        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
 
    def _configure(self, config_name, action, contents):
        # subscribe to feedback
        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.feedback_topic, callback=self._on_feedback)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        gevent.sleep(2)
        self.test1()

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        _log.info(f"Agent {self.core.identity} over and out.")

    def test1(self):
        while True:
            header = {"timestamp": datetime.now(timezone.utc).isoformat()}
            self.vip.pubsub.publish("pubsub", self.topic, header, self.message)
            _log.debug(f"Sending message, topic: {self.topic}, header:{header}, payload: test_payload")
            gevent.sleep(5)

    def _on_feedback(self, peer, sender, bus, topic, headers, message):
        _log.info(f"Feedback to the message: \"{message}\"")
        
def main():
    """Main method called to start the agent."""
    utils.vip_main(exptest1, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
