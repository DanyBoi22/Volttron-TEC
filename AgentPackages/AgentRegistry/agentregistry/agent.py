__docformat__ = 'reStructuredText'

import logging
import sys
import gevent
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from gevent import Timeout
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from metadata.metadata_mixin import MetadataMixin
from persistence import pydantic_io

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

class AgentDataModel(BaseModel):
    identity: str
    #uuid: Optional[str] = None
    #name: Optional[str] = None
    #tag: Optional[str] = None
    role: List[str] = Field(default=[])
    description: str = Field(default="Unknown")
    version: str = Field(default="Unknown")
    author: str = Field(default="Unknown")
    authorised: bool = Field(default=False)

DEFAULT_REGISTRY_PATH = "/home/user/volttron/agents/RegistryAgent/_registry.json"

def agentregistry(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Agentregistry
    :rtype: Agentregistry
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Agentregistry(config, **kwargs)


class Agentregistry(Agent, MetadataMixin):

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)
        self._config = config
        
        self._service = self._config.get("service_agent_identity", "serviceagentagent-0.1_1")
        self._registry_filepath = self._config.get("registry_filepath", DEFAULT_REGISTRY_PATH)
        self._registry: Dict[str, AgentDataModel] = {}

        self._agent_manager = config.get("service_agent_identity", "serviceagentagent-0.1_1")

        self.vip.config.set_default("config", self._config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")


    def _configure(self, config_name, action, contents):
        _log.info(f"Agent registry config updated: {action}")
        self._config = contents
        
        self._registry_filepath = self._config.get("registry_filepath", self._registry_filepath)
        self._load_registry_from_file()


    @RPC.export
    def register_agent(self, identity: str, data: dict) -> bool:
        """
        Register an agent with metadata (e.g., role, description, tag)
        """
        agent_data = AgentDataModel(**data, authorised=True)
        self._registry[identity] = agent_data
        self._save_registry_to_file()
        _log.info(f"Registered agent {identity} with data: {agent_data.model_dump()}")
        return True

    @RPC.export
    def unregister_agent(self, identity: str) -> bool:
        """
        Remove an agent from registry
        """
        if identity not in self._registry:
            _log.warning(f"Agent {identity} could not be unregistered: no such agent registered")
            return False
    
        del self._registry[identity]
        self._save_registry_to_file()
        _log.info(f"Agent unregistered: {identity}")
        return True
    
    @RPC.export
    def get_agent_data(self, identity: str) -> Dict[str, Any]:
        """
        Retrieve all data for a given agent
        """
        if identity not in self._registry:
            return None
        
        return self._registry.get(identity).model_dump()

    # TODO: search agents identity
    @RPC.export
    def get_agent_identity(self, agent_uuid: str = None, agent_name: str = None, agent_tag: str = None, agent_role: List[str] = None) -> List[str]:
        """
        Get agent identety based on provided match parameters
        """
        matches = []
        for identity, agent in self._registry.items():
            if agent_uuid and agent.uuid != agent_uuid:
                continue
            if agent_name and agent.name != agent_name:
                continue
            if agent_tag and agent.tag != agent_tag:
                continue
            if agent_role and agent.role != agent_role:
                continue
            matches.append(identity)
        return matches

    @RPC.export
    def list_registered_agents(self) -> List[str]:
        """
        List identities of all registered agents
        """
        return list(self._registry.keys())

    @RPC.export
    def get_full_registry(self) -> Dict[str, Any]:
        """
        Return the entire registry content
        """
        return {identity: agent.model_dump() for identity, agent in self._registry.items()}

    # TODO: make it later thread safe for rpc use
    def _load_registry_from_file(self):
        """
        Load persisted data from file
        """
        registry_copy = self._registry.copy()
        try:
            self._registry = pydantic_io.load_model_dict(self._registry_filepath, AgentDataModel)
        except Exception as e:
            _log.error(f"Failed to load plant status file: {e}")
            self._registry = registry_copy

    # TODO: make it later thread safe for rpc use
    def _save_registry_to_file(self):
        """
        Persist the local data to file
        """
        pydantic_io.save_model_dict(self._registry_filepath, self._registry)

    def _get_installed_agents(self):
        """
        RPC Call to the service agent to retrieve the agent list

        Returns: 
            List of Strings with identities of installed agents
        """
        installed_agent = []
        try:
            raw_list = self.vip.rpc.call(self._service, "list_agents").get(timeout=2)
            for agent_data in raw_list:
                identity = agent_data.get("identity")
                installed_agent.append(identity)
            return installed_agent
        
        except Exception as e:
            _log.error(f"Failed to get installed agents: {e}")
            return installed_agent
        except gevent.Timeout as to:
            _log.error(f"Failed to get installed agents, rpc time out: {to}")
            return installed_agent

    def _scan_and_register_unregistered_agents(self):
        """
        Periodical scans to find unregistered agents
        """
        # TODO: do i really need this?
        installed = self._get_installed_agents()
        for identity in installed:
            if identity == self.core.identity:
                continue # Don't query self
            if identity not in self._registry:
                _log.info(f"Discovered unregistered agent: {identity}")
                self._registry[identity] = AgentDataModel(identity=identity)
                self._get_agent_data(identity)

    def _get_agent_data(self, identity: str):
        """
        Retrieve the agents data via rpc to this agent
        """
        try:
            raw_data = self.vip.rpc.call(identity, "get_agent_data").get(timeout=2)
            agent = AgentDataModel(**raw_data, authorised=True)
        except gevent.Timeout as to:
            _log.warning(f"Timeout while querying agent {identity}: {e}")
            return
        except Exception as e:
            _log.warning(f"Agent {identity} failed to respond: {e}")
            return
        self._registry[identity] = agent
        self._save_registry_to_file()

    @Core.periodic(60)
    def periodic_scan(self):
        self._scan_and_register_unregistered_agents()
        # not needed in this agent
        #self._update_agent_statuses()

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
    """Main method called to start the agent."""
    utils.vip_main(agentregistry, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass