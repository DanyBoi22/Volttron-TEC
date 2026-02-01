import logging
import gevent
from volttron.platform.vip.agent import RPC

_log = logging.getLogger(__name__)

DEFAULT_AGENT_METADATA = {
        "identity": "unknown",
        "role":[],
        "description": "unknown",
        "version": "unknown",
        "author": "unknown"
    }
DEFAULT_AGENT_REGISTRY_IDENTITY = "agentregistryagent-0.1_1"

class MetadataMixin:
    """
    A mixin class that provides standardized agent metadata and an RPC method for metadata discovery.
    Usage:
        class MyAgent(Agent, MetadataMixin):
            def __init__(self, config, **kwargs):
                Agent.__init__(self, **kwargs)
                MetadataMixin.__init__(self, config)
    
    To allow a dynamical update of metadata from config file configure the config store in the agent init:
        class MyAgent(Agent, MetadataMixin):
            def __init__(self, config, **kwargs):    
                self.vip.config.subscribe(self._on_metadata_config_update, actions=["NEW", "UPDATE"], pattern="config")
        
    """

    def __init__(self, config, identity):

        # subscribe to config store changes for metadata
        self.vip.config.subscribe(self._on_metadata_config_update, actions=["NEW", "UPDATE"], pattern="config")

        self.agent_registry_identity = config.get("agent_registry_identity", DEFAULT_AGENT_REGISTRY_IDENTITY)
        self.agent_metadata = DEFAULT_AGENT_METADATA.copy()

        # Update fields if provided
        metadata_cfg = config.get("metadata", {})
        for key in DEFAULT_AGENT_METADATA:
            self.agent_metadata[key] = metadata_cfg.get(key, DEFAULT_AGENT_METADATA[key])

        self.agent_metadata["identity"] = identity

    def _update_metadata(self, contents):
        """
        Update metadata fields from config store contents.
        """
        metadata_update = contents.get("metadata", {})
        for key in self.agent_metadata:
            if key in metadata_update:
                self.agent_metadata[key] = metadata_update[key]
        self.agent_metadata["identity"] = self.core.identity
        _log.debug(f"Updated agent metadata: {self.agent_metadata}")

    def _register_at_agent_registry(self):
        """
        Attempt to register at the Agent Registry Agent.
        """
        if not self.agent_registry_identity:
            _log.warning("Agent registry identity is not set.")
            return False
        
        if (self.agent_registry_identity == self.core.identity):
            _log.info("The Agents identity is agent registy identity")
            return True    
        
        if ("Agent Manager" in self.agent_metadata["role"]):
            _log.info("Ignoring agent manager")
            return True    

        self.agent_metadata["identity"] = self.core.identity
        rpc_future = self.vip.rpc.call(self.agent_registry_identity, "register_agent", self.agent_metadata["identity"], self.agent_metadata)

        def handle_future(rpc_future):
            try:
                result = rpc_future.get(timeout=3)
                if result:
                    _log.info(f"Successfully registered at agent registry")
                else: 
                    _log.warning(f"Failed to register at agent registry")
                return result
            except Exception as e:
                _log.warning(f"Failed to register at agent registry: {e}")
                return False
            except gevent.Timeout as to:
                _log.warning(f"Failed to register at agent registry, rpc time out: {to}")
                return False

        self.core.spawn(handle_future, rpc_future)

    def _on_metadata_config_update(self, config_name, action, contents):
        """
        Callback for config store updates to reload metadata.
        """
        _log.info(f"Metadata config updated via config store: {action}")
        self._update_metadata(contents)
        self._register_at_agent_registry()

    @RPC.export
    def get_agent_data(self):
        """
        Expose this agents metadata for registry lookup.
        This should be called by the AgentRegistryAgent to auto-register agents.
        """
        return self.agent_metadata