"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import gevent
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from datetime import datetime, timezone

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def impulsetest(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Impulsetest
    :rtype: Impulsetest
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Impulsetest(config, **kwargs)


class Impulsetest(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Impulsetest, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        self.time_intervall = 15*60 # 15 mins in seconds
        self.bhkw_runs = False
        self.bhkw_runtime = 0
        self.bhkw_vorlauf = 0
        self.bhkw_ruecklauf = 0
        self.topic_runs = "bhkw/laeuft"
        self.topic_runtime = "bhkw/laufzeit/aktuell"
        self.topic_bhkw_vorlauf = "bhkw/temperatur/vorlauf"
        self.topic_bhkw_ruecklauf = "bhkw/temperatur/ruecklauf"
        self.command_topic_bhkw_ausschaltpunkt = "command/bhkw/ausschaltpunkt"
        self.command_topic_bhkw_einschaltpunkt = "command/bhkw/einschaltpunkt"


        self._config = config
        self.vip.config.set_default("config", self._config)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        _log.info(f"Impulse Test is running")
        
        self.run_test()


    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        _log.info(f"Impulse Test is finished")


    def run_test(self):
        self.bhkw_runs = True
        while True:
            if self.bhkw_runs:
                self.turn_off()
            else:
                self.turn_on()
            gevent.sleep(self.time_intervall)

    def turn_off(self):
        einschalttemp = 60
        ausschalttemp = 30
        self.bhkw_runs = False

        self.vip.pubsub.publish("pubsub", self.command_topic_bhkw_einschaltpunkt, message=einschalttemp)
        self.vip.pubsub.publish("pubsub", self.command_topic_bhkw_ausschaltpunkt, message=ausschalttemp)
        

    def turn_on(self):
        einschalttemp = 30
        ausschalttemp = 60
        self.bhkw_runs = True

        self.vip.pubsub.publish("pubsub", self.command_topic_bhkw_einschaltpunkt, message=einschalttemp)
        self.vip.pubsub.publish("pubsub", self.command_topic_bhkw_ausschaltpunkt, message=ausschalttemp)
        
        


def main():
    """Main method called to start the agent."""
    utils.vip_main(impulsetest, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
