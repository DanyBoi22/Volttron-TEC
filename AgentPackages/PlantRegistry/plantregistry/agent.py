"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import gevent
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Dict, List
from datetime import datetime

from metadata.metadata_mixin import MetadataMixin
from persistence import pydantic_io

DEFAULT_PLANT_STATUS_FILEPATH =  "/home/user/volttron/agents/PlantRegistry/plantstatus.json"

class PlantMetadata(BaseModel):
    plant_name: str
    model: str
    tag: Optional[str] = None
    location: Optional[str] = None
    additional_info: Dict[str, str] = {}

class PlantStatus(BaseModel):
    status: str = Field(..., pattern="^(available|not available|control seized)$")
    updated_at: str # Watch out it should be isoformat

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def plantregistry(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Plantregistry
    :rtype: Plantregistry
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Plantregistry(config, **kwargs)


class Plantregistry(Agent, MetadataMixin):

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)
        _log.info(f"Plant Registry initialised")

        self._config = config
        self._plants_status_filepath = self._config.get("plant_status_filepath", DEFAULT_PLANT_STATUS_FILEPATH)
        self._plants_list: List[PlantMetadata] = []
        self._plants_status: Dict[str, PlantStatus] = {}

        self._agent_manager = config.get("service_agent_identity", "serviceagentagent-0.1_1")

        self._load_plants_data_from_config()
        self._load_plant_status()

        self.vip.config.set_default("config", self._config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        
        
    def _configure(self, config_name, action, contents):
        _log.info(f"Plant Registry config updated ({action})")
        self._config = contents
        self._plants_status_filepath = self._config.get("plant_status_filepath", self._plants_status_filepath)
        self._load_plants_data_from_config()
        self._load_plant_status()

    def _load_plants_data_from_config(self):
        try:
            self._plants_list = [PlantMetadata(**item) for item in self._config.get("plants", [])]
            _log.info(f"Loaded {len(self._plants_list)} plants from config")
        except ValidationError as e:
            _log.error(f"Metadata validation failed: {e}")
            self._plants_list: List[PlantMetadata] = []

    def _load_plant_status(self):
        """
        Load persisted data from file
        """
        plants_status_copy = self._plants_status.copy()
        try:
            self._plants_status = pydantic_io.load_model_dict(self._plants_status_filepath, PlantStatus)
        except Exception as e:
            _log.error(f"Failed to load plant status file: {e}")
            self._plants_status = plants_status_copy

    def _save_plant_status(self):
        """
        Persist the local data to file
        """
        pydantic_io.save_model_dict(self._plants_status_filepath, self._plants_status)
        
    def _update_status(self, plant_name: str, status: str):
        """
        Updates the status of the given plant.
        Returns: True on success
        Raises: ValueError on fail
        """
        if plant_name not in [plant.plant_name for plant in self._plants_list]:
            raise ValueError(f"Plant '{plant_name}' not found in registry")

        try:
            self._plants_status[plant_name] = PlantStatus(
                status=status,
                updated_at=datetime.now().isoformat()
            )
            self._save_plant_status()
            _log.debug(f"Status of '{plant_name}' updated to '{status}'")
            return True
        except ValidationError as e:
            raise ValueError(f"Validatation failed: {e}")

    def _get_status(self, plant_name: str):
        """
        Provides the status of the given plant.
        Returns: Str with status(available | not available | control seized) on success
        Raises: ValueError on fail
        """
        if plant_name not in [plant.plant_name for plant in self._plants_list]:
            raise ValueError(f"Plant '{plant_name}' not found in registry")

        if plant_name not in self._plants_status:
            raise ValueError(f"No data on '{plant_name}' status")
        return self._plants_status[plant_name].status

    def _get_plant_data(self, plant_name: str):
        """
        Provides the saved data of the given plant.
        Returns: Dict[str] with metadata on success
        Raises: ValueError on fail
        """
        for plant in self._plants_list:
            if plant.plant_name == plant_name:
                return plant.model_dump()
        raise ValueError(f"Plant '{plant_name}' not found in registry")
    
    # TODO
    def _plants_are_available(self, plants: List[str], start_time: str, stop_time: str) -> bool:
        return True

    # TODO
    def _lock_plants(self, plants: List[str], start_time: str, stop_time: str) -> bool:
        return True

    # TODO
    def _unlock_plants(self, plants: List[str], start_time: str, stop_time: str) -> bool:
        return True

    def _list_plants(self):
        """
        Provides the list of saved plants.
        Returns: List[Str] with plant names
        Raises: ValueError on error
        """
        if self._plants_list == None:
            raise ValueError("Internal Error. Registry is None")
        return [plant.plant_name for plant in self._plants_list]
    
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
    utils.vip_main(plantregistry, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
