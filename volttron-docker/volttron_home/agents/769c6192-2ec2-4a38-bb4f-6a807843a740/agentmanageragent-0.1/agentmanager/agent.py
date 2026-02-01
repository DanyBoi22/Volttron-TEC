"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import time
import subprocess
import logging
import sys
from typing import List, Dict, Any
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

from metadata.metadata_mixin import MetadataMixin

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

DEFAULT_DEPENDENCY_MAP = {}
RPC_TIMEOUT = 3

def agentmanager(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Agentmanager
    :rtype: Agentmanager
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Agentmanager(config, **kwargs)


class Agentmanager(Agent, MetadataMixin):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Agentmanager, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)

        self._config = config
        self._dependency_map = config.get("dependencies", DEFAULT_DEPENDENCY_MAP)
        self._agent_status_map = {}  # identity -> {"uuid": "2e31b", "status": "running", "last_checked": timestamp}

        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        
        
    def _configure(self, config_name, action, contents):
        self._config = contents
        self._dependency_map = contents.get("dependencies", self._dependency_map)

    def _get_uuid_from_identity(self, agent_identity) -> str:
        uuid = self._agent_status_map.get(agent_identity, {}).get("uuid")
        if not uuid:
            _log.error(f"UUID not found in the map for identity: {agent_identity}")
            ValueError(f"UUID not found in the map for identity: {agent_identity}")
        return uuid

    @Core.receiver("onstart")
    def _enable_own_autostart(self, sender, **kwargs):
        """
        Create an AUTOSTART file,
        so that on next Volttron reboot this agent will be started.
        Hence AUTOSTART file does not exist at the first start up can not use 
            self.vip.rpc.call("control", "prioritize_agent", my_uuid, priority)
        There is no implementef rpc method that fully realises the autostart,
        only wayaround with vctl
        """
        priority = "40"                    # 0–100, lower means start earlier
        self.enable_agent_autostart(self.core.identity, priority)
        
    @RPC.export
    def start_agent(self, agent_identity: str) -> None:
        """
        Start a specified agent via rpc

        Params:
            agent_identity: String identity of the agent to start
        Raises:
            RuntimeError on fail
        """  

        try:
            uuid = self._get_uuid_from_identity(agent_identity)
            self.vip.rpc.call("control", "start_agent", uuid).get(timeout=RPC_TIMEOUT)
            _log.debug(f"RPC start_agent called for {agent_identity}.")
        except Exception as e:
            _log.error(f"Failed to start agent {agent_identity}: {e}")
            raise RuntimeError(f"Failed to start agent {agent_identity}: {e}")

    @RPC.export
    def stop_agent(self, agent_identity: str) -> None:
        """
        Stop a specified agent via rpc
                
        Params:
            agent_identity: String identity of the agent to stop
        Raises:
            RuntimeError on fail
        """  

        try:
            uuid = self._get_uuid_from_identity(agent_identity)
            self.vip.rpc.call("control", "stop_agent", uuid).get(timeout=RPC_TIMEOUT)
            _log.debug(f"RPC stop_agent called for {agent_identity}.")
        except Exception as e:
            _log.error(f"Failed to stop agent {agent_identity}: {e}")
            raise RuntimeError(f"Failed to stop agent {agent_identity}: {e}")
    
    @RPC.export
    def restart_agent(self, agent_identity: str) -> None:
        """
        Restart a specified agent via rpc
           
        Params:
            agent_identity: String identity of the agent to restart
        Raises:
            RuntimeError on fail
        """  

        try:
            uuid = self._get_uuid_from_identity(agent_identity)
            self.vip.rpc.call("control", "restart_agent", uuid).get(timeout=RPC_TIMEOUT)
            _log.debug(f"RPC restart_agent called for {agent_identity}.")
        except Exception as e:
            _log.error(f"Failed to restart agent {agent_identity}: {e}")
            raise RuntimeError(f"Failed to restart agent {agent_identity}: {e}")

    @RPC.export
    def remove_agent(self, agent_identity: str) -> None:
        """
        Restart a specified agent via rpc
           
        Params:
            agent_identity: String identity of the agent to remove
        Raises:
            RuntimeError on fail
        """  

        try:
            uuid = self._get_uuid_from_identity(agent_identity)
            self.vip.rpc.call("control", "remove_agent", uuid).get(timeout=RPC_TIMEOUT)
            _log.debug(f"RPC remove_agent called for {agent_identity}.")
        except Exception as e:
            _log.error(f"Failed to remove agent {agent_identity}: {e}")
            raise RuntimeError(f"Failed to remove agent {agent_identity}: {e}")


    @RPC.export
    def list_agents(self) -> List[Dict]: 
        """
        Get a list of all installed agents on the platform
           
        Returns: 
            The list of  dict with information on installed agents
            Output format:
            [
                {
                    "name": name,
                    "uuid": uuid,
                    "tag": tag,
                    "priority": priority,
                    "identity": identity,
                },...
            ]
        Raises:
            RuntimeError on fail
        """  

        try:
            raw_list = self.vip.rpc.call("control", "list_agents").get(timeout=RPC_TIMEOUT)
            #_log.debug(f"RPC list_agents called, output: {raw_list}")
            return raw_list
        except Exception as e:
            _log.error(f"Failed to fetch list of agents: {e}")
            raise RuntimeError(f"Failed to fetch list of agents: {e}")

    @RPC.export
    def agents_are_installed(self, agents: List[str]) -> bool:
        """
        Checks whether all agents from the list are installed on the platform 
        
        Params:
            List of agent identities as strings
        Returns: 
            True if all agents are installed false otherwise
        Raises:
            RuntimeError on fail
        """
        if not isinstance(agents, list):
            _log.error(f"agents_are_installed failed: Parameter \"agents\" must be a list")
            raise RuntimeError(f"Parameter \"agents\" must be a list")
        if not all(isinstance(i, str) for i in agents):
            _log.error(f"agents_are_installed failed: Parameter \"agents\" must be a list")
            raise RuntimeError("All elements in \"agents\" must be strings.")

        try:
            installed_agents = self.list_agents()
            installed_ids = {d.get("identity") for d in installed_agents}
            return all(agent in installed_ids for agent in agents)
        except:
            raise 

    # TODO
    @RPC.export
    def start_with_dependencies(self, identity):
        """
        Recursively start dependencies before starting the agent
        """
        deps = self._dependency_map.get(identity, [])
        _log.debug(f"RPC start_with_dependencies called for {identity}, deps: {deps}")
        for dep in deps:
            self.start_with_dependencies(dep)
        return self.start_agent(identity)

    # TODO
    @RPC.export
    def stop_with_dependencies(self, identity):
        """
        Recursively stop dependencies before starting the agent
        """
        deps = self._dependency_map.get(identity, [])
        _log.debug(f"RPC stop_with_dependencies called for {identity}, deps: {deps}")
        for dep in deps:
            self.stop_with_dependencies(dep)
        return self.stop_agent(identity)


    @RPC.export
    def agent_statuses(self) -> Dict[str, Dict]:
        """
        Calls RPC, parses vctl status lines,
        and updates self._agent_status_map when done.
        
        Returns: 
            A Dict of agent identities. with uuid, status and last checked timestamp mapped to each agent identity
            Output format:
            {
                agents_identity: 
                { 
                    "uuid": uuid,
                    "status": status[never started | running | stopped | unknown],
                    "last_checked": timestamp
                }
            }
        Raises:
            RuntimeError on fail
        """  

        try:
            list_of_installed_agents = self.list_agents()
            if not list_of_installed_agents:
                raise ValueError("List of Agents is empty")

            list_of_agents_status = self.vip.rpc.call("control", "status_agents").get(timeout=RPC_TIMEOUT)
            #_log.debug(f"List of agents statuses: {list_of_agents_status}")

            new_map = {}
            for list_entry in list_of_installed_agents:
                identity = list_entry["identity"]
                uuid = list_entry["uuid"]
                # default if not found:
                status = "never started"

                # scan the raw list for our identity:
                for status_entry in list_of_agents_status:
                    if len(status_entry) == 4 and status_entry[3] == identity:
                        pid = status_entry[2][0]  # rec[2] is [pid, exitcode]
                        exitcode = status_entry[2][1]
                        if pid is None:
                            status = "never started"
                        elif exitcode is None:
                            status = "running"
                        elif exitcode == 0:
                            status = "stopped"
                        else:
                            status = "unknown"
                        break

                new_map[identity] = {
                    "uuid": uuid,
                    "status": status,
                    "last_checked": time.time()
                }

            self._agent_status_map = new_map
            #_log.debug(f"Refreshed agents statuses: {new_map}")
            return new_map

        except Exception as e:
            _log.error(f"Failed to fetch agents statuses: {e}")

    @RPC.export
    def get_agent_status_map(self):
        """
        Same as agent_statuses() but simply returnes the stored map
        """
        return self._agent_status_map.copy
    
    @RPC.export
    def enable_agent_autostart(self, agent_identity: str, priority: str) -> bool:
        """
        Enable the autostart for the agent at the priority 

        Params:
            agent_identity: String identity of the agent to autostart
            priority: String with prioriy in range from 0 to 100, lower means start earlier
        Returns: 
            True on success, Fail if unable to set the autostart
        Raises:
            RuntimeError on exception
        """

        self.agent_statuses()
        try:
            agent_uuid = self._get_uuid_from_identity(agent_identity)
            # For some reason there is no full rpc implementation for autostart only from within vctl
            # if AUTOSTART file for an agent exists you can use self.vip.rpc.call("control", "prioritize_agent", agent_uuid, priority) 
            result = subprocess.run(["vctl", "enable", agent_uuid, priority], capture_output=True, text=True)
            if result.returncode == 0:
                _log.info(f"Enabled autostart for agent {agent_identity} at priority {priority}")
                return True
            else:
                _log.error(f"Failed to enable autostart for {agent_identity}, {result.stderr.strip()}")
                return False
        except Exception as e:
            _log.error(f"Error while enabling autostart for {agent_identity}: {e}")
            raise RuntimeError(f"Error while enabling autostart for {agent_identity}: {e}")

    @RPC.export
    def disable_agent_autostart(self, agent_identity: str) -> bool:
        """
        Disable the autostart for the agent

        Params:
            agent_identity: String identity of the agent to disable autostart
        Returns: 
            True on success, Fail if unable to disable the autostart
        Raises:
            RuntimeError on exception 
        """

        self.agent_statuses()
        try:
            agent_uuid = self._get_uuid_from_identity(agent_identity)
            # if AUTOSTART file for an agent exists you can use self.vip.rpc.call("control", "prioritize_agent", agent_uuid, "0")
            result = subprocess.run(["vctl", "disable", agent_uuid], capture_output=True, text=True)
            if result.returncode == 0:
                _log.info(f"Disabled autostart for agent {agent_identity}")
                return True
            else:
                _log.error(f"Failed to disable autostart for {agent_identity}, {result.stderr.strip()}")
                return False
        except Exception as e:
            _log.error(f"Error while disabling autostart for {agent_identity}: {e}")
            raise RuntimeError(f"Error while disabling autostart for {agent_identity}: {e}")

    #---------- Config Store ---------- 
    # TODO: Replace vctl with rpc to store agent
    @RPC.export
    def list_agent_configs(self, agent_identity: str):
        """
        List all stored configs in the config store of the agent

        Params:
            agent_identity: String identity of the agent to get configs
        Returns: 
            List of config names stored in the config store
        Raises:
            RuntimeError on exception 
        """
        try:
            rc = self._run_vctl(["config", "list", agent_identity]).splitlines()
            _log.debug(f"Config list called for agent {agent_identity}, output: {rc}")
            return rc
        except Exception as e:
            _log.error(f"Error listing configs for agent{agent_identity}: {e}")
            raise RuntimeError(f"Error listing configs for agent: {e}")
    
    @RPC.export
    def get_config(self, agent_identity: str, config_name: str):
        """
        Get the specified config of the specified agent as dictionary

        Params:
            agent_identity: String identity of the agent to get configs
            config_name: String name of the config
        Returns: 
            Config as dict
        Raises:
            RuntimeError on exception 
        """

        try:
            rc = self._run_vctl(["config", "get", agent_identity, config_name]).strip()
            _log.debug(f"Get config with name {config_name} called for agent {agent_identity}, output: {rc}")
            return rc
        except Exception as e:
            _log.error(f"Error getting config {config_name} for agent {agent_identity}: {e}")
            raise RuntimeError(f"Error getting config: {e}")
    
    @RPC.export
    def store_config_content(self, agent_identity: str, config_name: str, content: str):
        """
        Store the config content with specified config name for the specified agent

        Params:
            agent_identity: String identity of the agent to store config for
            config_name: String name of the config
            content: serialized json to store as a config
        Returns: 
            rc
        Raises:
            RuntimeError on exception 
        """

        try:
            rc = self._run_vctl(["config", "store", agent_identity, config_name, "-"], input=content)
            _log.debug(f"Store config with name {config_name} called for agent {agent_identity} content: {content}, output: {rc}")
            return rc
        except Exception as e:
            _log.error(f"Error storing config {config_name} for agent {agent_identity}: {e}")
            raise RuntimeError(f"Error storing config: {e}")

    @RPC.export
    def delete_config(self, agent_identity: str, config_name: str) -> bool:
        """
        Remove the config with specified name for the specified agent

        Params:
            agent_identity: String identity of the agent
            config_name: String name of the config to remove
        Returns: 
            True on success
        Raises:
            RuntimeError on exception 
        """

        try:
            self._run_vctl(["config", "delete", agent_identity, config_name])
            return True
        except Exception as e:
            _log.error(f"Error deleting config {config_name} for agent {agent_identity}: {e}")
            raise RuntimeError(f"Error deleting config: {e}")

    @RPC.export
    def store_config_file(self, agent_identity: str, config_name: str, config_path: str):
        """
        Store the config file with specified config name for the specified agent

        Params:
            agent_identity: String identity of the agent to store config for
            config_name: String name of the config
            config_path: String Path to the config file
        Returns: 
            rc
        Raises:
            RuntimeError on exception 
        """

        try:
            rc = self._run_vctl(["config", "store", agent_identity, config_name, config_path])
            _log.debug(f"Store config with name {config_name} called for agent {agent_identity}, output: {rc}")
            return rc
        except Exception as e:
            _log.error(f"Error storing config file {config_name} for agent {agent_identity}: {e}")
            raise RuntimeError(f"Error storing config file: {e}")

    def _run_vctl(self, args, input=None):
        """
        Runs a command in volttrons CLI 
        """
        result = subprocess.run(["vctl"] + args, input=input, text=True, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout
    
    # @Core.periodic(60)
    def _periodic_status_scan(self):
        """
        WARNING: Depracated this function was moved to agent registry  
        Every 60s, spawn a worker greenlet to fetch & parse agent statuses.
        Returns immediately, so this greenlet never blocks.
        """
        self.agent_statuses()

def main():
    """Main method called to start the agent."""
    utils.vip_main(agentmanager, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass