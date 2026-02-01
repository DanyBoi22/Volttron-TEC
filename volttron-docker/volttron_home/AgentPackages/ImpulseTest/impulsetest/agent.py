"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import gevent
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

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
        self.topic_bhkw_vorlauf = "io/cybus/energie-campus/heizung/bhkw/vorlauf/temperatur"
        self.topic_bhkw_ruecklauf = "io/cybus/energie-campus/heizung/bhkw/ruecklauf/temperatur"
        self.command_topic_bhkw_ausschaltpunkt = ""
        self.command_topic_bhkw_einschaltpunkt = ""


        self._config = config
        self.vip.config.set_default("config", self._config)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.topic_runs, callback=self._l)
        #self.vip.pubsub.subscribe(peer="pubsub", prefix=self.topic_bhkw_ruecklauf, callback=self._log)
        #self.vip.pubsub.subscribe(peer="pubsub", prefix=self.topic_bhkw_vorlauf, callback=self._log)
        
        self.run_test()


    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        pass


    def run_test(self):
        while True:
            gevent.sleep(self.time_intervall)
            if self.bhkw_runs:
                self.turn_on()
            else:
                self.turn_off()


    def turn_off(self):
        self.bhkw_runs = False
        #self.vip.pubsub.publish("pubsub", topic, message="payload")
        

    def turn_on(self):
        self.bhkw_runs = True
        #self.vip.pubsub.publish("pubsub", topic, message="payload")
        


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
