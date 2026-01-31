__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

import gevent
import os
import subprocess
from pydantic import BaseModel
from typing import List, Dict

from gevent.pywsgi import WSGIServer
from flask import Flask, jsonify, request
from flask_cors import CORS


from metadata.metadata_mixin import MetadataMixin

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

LOG_PATH = "/home/user/volttron/volttron.log"
TIMEOUT_TIME = 3

class InstallAgentRequest(BaseModel):
            base_dir: str
            config_file: str
            tag: str

class ConfigStoreRequest(BaseModel):
            config_name: str
            config_path: str

def backend(config_path, **kwargs):

    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return Backend(config, **kwargs)


class Backend(Agent, MetadataMixin):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Backend, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)

        self.app = Flask(__name__)
        CORS(self.app)

        self.config = config
        self.service_id: str = ""
        self.expmanager_id: str = ""
        self.topic_registry: str = ""
        self._http_host: str = ""
        self._http_port: int = 0

        self._server = None

        self.vip.config.set_default("config", self.config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        self.config = contents
        self.service_id = self.config.get("service_agent_identity", "serviceagentagent-0.1_1")
        self.expmanager_id = self.config.get("experiment_manager_identity", "expmanageragent-0.1_1")
        self.topic_registry = self.config.get("topic_registry_identity", "topicregistryagent-0.1_1")
        self._http_host = self.config.get("host", "0.0.0.0")
        self._http_port = int(self.config.get("port", 8000))

        try:
            self._register_routes()
            if self._server:
                self._restart_http_server()
            if not self._server:
                self._start_http_server()
        except Exception as e:
            _log.error(f"Could not start the server. Cause: {e}")
            self.core.stop()


    def _register_routes(self):
    # --------------------- Logs --------------------- #

        @self.app.route("/log", methods=["GET"])
        def get_log():
            if not os.path.exists(LOG_PATH):
                return jsonify({"log": "Log file not found."})
                
            try:
                with open(LOG_PATH, "r") as f:
                    log = f.read()
                return jsonify({"log": log})

            except Exception as e:
                return jsonify({"log": f"Error reading log: {str(e)}"}), 500


    # --------------------- Agent Management --------------------- #

        @self.app.route("/agents", methods=["GET"])
        def get_agents():
            """
            Fetches the list of installed agents and their identities.
            """
            try:
                raw_agents_data = self.vip.rpc.call(self.service_id, "list_agents").get(timeout=TIMEOUT_TIME) 
                
                # raw_agents is now a list of dicts like:
                # [{'name': 'backendagent-0.1', 'uuid': '…', 'tag': 'backend', 'priority': None, 'identity': '…'}, …]

                if not isinstance(raw_agents_data, list):
                    _log.error(f"Unexpected format from rpc list_agents: {raw_agents_data!r}")
                    return jsonify({"agents": []})

                agents = [
                    {
                        "id": agent["uuid"],
                        "type": agent.get("tag"),
                        "identity": agent["identity"]
                    }
                    for agent in raw_agents_data
                ]
                _log.debug(f"Fetched agent list: {agents}")
                return jsonify({"agents": agents})

            except Exception as e:
                _log.error(f"Error fetching agent list: {e}")
                return jsonify({"error": str(e)}), 500
        

        @self.app.route("/agent_statuses", methods=["GET"])
        def get_agent_statuses():
            """
            RPC Call to service agent to retrieve statuses
            """
            try:
                statuses = self.vip.rpc.call(self.service_id, "agent_statuses").get(timeout=TIMEOUT_TIME)
                _log.debug(f"Fetched agent statuses: {statuses}")
                return jsonify({"statuses": statuses})
                
            except Exception as e:
                _log.error(f"Error fetching agent statuses: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/agents/<string:agent_id>/start", methods=["POST"])
        def start_agent(agent_id: str):
            """
            Start a specified agent via RPC
            """
            try:
                result = self.vip.rpc.call(self.service_id, "start_agent", agent_id).get(timeout=TIMEOUT_TIME)
                return jsonify({"message": f"Starting Agent {agent_id}, {result}"})

            except Exception as e:
                _log.error(f"Error starting agent: {e}")
                return jsonify({"error": str(e)}), 500
            
        
        @self.app.route("/agents/<string:agent_id>/stop", methods=["POST"])
        def stop_agent(agent_id: str):
            """"
            Stop a specified agent via rpc
            """
            try:
                result = self.vip.rpc.call(self.service_id, "stop_agent", agent_id).get(timeout=TIMEOUT_TIME)
                _log.debug(f"Stoped agent: {agent_id}, rc = {result}")
                return jsonify({"message": f"Agent {agent_id} stoped"})
            
            except Exception as e:
                _log.error(f"Error stoping agent: {e}")
                return jsonify({"error": str(e)}), 500

        
        @self.app.route("/agents/<string:agent_id>/remove", methods=["DELETE"])
        def remove_agent(agent_id: str):
            """
            Remove a specified agent via rpc
            """
            try:
                result = self.vip.rpc.call(self.service_id, "remove_agent", agent_id).get(timeout=TIMEOUT_TIME)
                if result == 0:
                    _log.debug(f"Removed agent: {agent_id}, result = 0")
                    return jsonify({"message": f"Agent {agent_id} Removed"})
                else:
                    _log.debug(f"Remove agent {agent_id} failed, rc = {result}")
                    return jsonify({"message": f"Agent {agent_id} Remove Failed, rc = {result}"})
                
            except Exception as e:
                _log.error(f"Error stoping agent: {e}")
                return jsonify({"error": str(e)}), 500

        
        @self.app.route("/install-agent", methods=["POST"])
        def install_agent():
            """
            Run the installation script for an agent
            """
            
            try:
                # TODO: test it more doesnt seem to work yet with pydantic
                request: InstallAgentRequest = InstallAgentRequest(request.get_json(force=True))
                command = [
                    "python", "scripts/install-agent.py",
                    "-s", request.base_dir,
                    "-c", request.config_file,
                    "-t", request.tag
                ]
                result = subprocess.run(command, capture_output=True, text=True)

                if result.returncode == 0:
                    return jsonify({"message": "Agent installed successfully", "result": result.stdout})
                else:
                    return jsonify({"message": "Agent installation failed", "returncode": result.returncode})
            except Exception as e:
                return jsonify({"error": str(e)}), 500


    # --------------------- Agent Configuration Store --------------------- #
      
        @self.app.route("/agents/<agent_identity>/configs", methods=["GET"])
        def get_configs(agent_identity: str):
            try:
                result = self.vip.rpc.call(self.service_id, "list_agent_configs", agent_identity).get(timeout=TIMEOUT_TIME)
                return jsonify({"configs": result})
            except Exception as e:
                _log.error(f"Failed to get configs: {e}")
                return jsonify({"error": str(e)}), 500
            

        @self.app.route("/agents/<agent_identity>/configs/<config_name>", methods=["GET"])
        def get_config_content(agent_identity: str, config_name: str):
            try:
                content = self.vip.rpc.call(self.service_id, "get_config", agent_identity, config_name).get(timeout=TIMEOUT_TIME)
                return jsonify({"config_name": config_name, "content": content})
            except Exception as e:
                _log.error(f"Failed to get config content: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/agents/<agent_identity>/configs/<config_name>", methods=["POST"])
        def update_config(agent_identity: str, config_name: str):
            config_data: dict = request.get_json(force=True)
            content = config_data.get("content", "")
            try:
                self.vip.rpc.call(self.service_id, "store_config_content", agent_identity, config_name, content).get(timeout=TIMEOUT_TIME)
                return jsonify({"message": f"Updated config {config_name} for {agent_identity}."})
            except Exception as e:
                _log.error(f"Failed to update config: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/agents/<agent_identity>/configs/<config_name>", methods=["DELETE"])
        def delete_config(agent_identity: str, config_name: str):
            try:
                self.vip.rpc.call(self.service_id, "delete_config", agent_identity, config_name).get(timeout=TIMEOUT_TIME)
                return jsonify({"message": f"Deleted config {config_name} from {agent_identity}."})
            except Exception as e:
                _log.error(f"Failed to delete config: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/agents/<agent_identity>/configs", methods=["POST"])
        def store_config(agent_identity: str):
            try:
                # TODO: test it more doesnt seem to work yet with pydantic
                request: ConfigStoreRequest = ConfigStoreRequest(request.get_json(force=True))
                self.vip.rpc.call(self.service_id, "store_config_file", agent_identity, request.config_name, request.config_path).get(timeout=TIMEOUT_TIME)
                return jsonify({"message": f"Stored config {request.config_name} for {agent_identity} from {request.config_path}."})
            except Exception as e:
                _log.error(f"Failed to store config file: {e}")
                return jsonify({"error": str(e)}), 500


    # --------------------- Experiment Management ---------------------
        
        @self.app.route("/experiments/submit", methods=["POST"])
        def submit_experiment_data():
            try:
                experiment_data: dict = request.get_json(force=True)

                experiment_id = self.vip.rpc.call(self.expmanager_id, "submit_experiment_data", experiment_data).get(timeout=TIMEOUT_TIME)
                return jsonify({"message": "Experiment submited successfully","experiment_id": experiment_id})
            except Exception as e:
                _log.error(f"Error submiting experiment data: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/experiments/<experiment_id>/authorise", methods=["POST"])
        def authorise_experiment(experiment_id: str):
            try:
                request_data = request.get_json(force=True)
                supervisor_name = request_data.get("supervisor_name", "")
                
                result = self.vip.rpc.call(self.expmanager_id, "authorise_experiment", experiment_id, supervisor_name).get(timeout=TIMEOUT_TIME)
                return jsonify({"message": "Experiment authorised", "status": result})
            except Exception as e:
                _log.error(f"Error authorising experiment: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/experiments/<experiment_id>/finalize", methods=["POST"])
        def finalize_experiment(experiment_id: str):
            try:
                request_data = request.get_json(force=True)
                agents_for_experiment: List[str] = request_data.get("agents_for_experiment", [])
                topics_to_log: List[str] = request_data.get("topics_to_log", [])
                
                result = self.vip.rpc.call(self.expmanager_id, "experiment_is_ready", experiment_id, agents_for_experiment, topics_to_log).get(timeout=TIMEOUT_TIME)
                return jsonify({"message": "Experiment finalized", "status": result})
            except Exception as e:
                _log.error(f"Error finalizing experiment: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/experiments/<experiment_id>/data", methods=["GET"])
        def get_experiment_data(experiment_id: str):
            try:
                result = self.vip.rpc.call(self.expmanager_id, "get_dict_experiment_data", experiment_id).get(timeout=TIMEOUT_TIME)
                _log.debug(f"Fetched data for experiment \"{experiment_id}\": {result}")
                return jsonify({"data": result})
            except Exception as e:
                _log.error(f"Error fetching experiment data: {e}")
                return jsonify({"error": str(e)}), 500
        
        
        @self.app.route("/experiments/all/data", methods=["GET"])
        def get_experiments_list():
            try:
                result = self.vip.rpc.call(self.expmanager_id, "get_list_all_experiments_data").get(timeout=TIMEOUT_TIME)
                _log.debug(f"Fetched data for all experiments: {result}")
                return jsonify({"list": result})
            except Exception as e:
                _log.error(f"Error fetching experiments data: {e}")
                return jsonify({"error": str(e)}), 500
        

    # --------------------- Topic Management ---------------------
        @self.app.route("/topics/all/data", methods=["GET"])
        def get_topics_data():
            try:
                result = self.vip.rpc.call(self.topic_registry, "search_topics").get(timeout=TIMEOUT_TIME)
                _log.debug(f"Fetched data for all topics: {result}")
                return jsonify({"data": result})
            except Exception as e:
                _log.error(f"Error fetching topcis data: {e}")
                return jsonify({"error": str(e)}), 500


        @self.app.route("/topics/plantfilter/data", methods=["GET"])
        def get_plant_topics():
            request_data =  request.get_json(force=True)
            plants: List[str] = request_data.get("plants", [])
            try:
                result = self.vip.rpc.call(self.topic_registry, "search_topics", plant_name_list_match=plants).get(timeout=TIMEOUT_TIME)
                _log.debug(f"Fetched data for topics filtered by plant names {plants}: {result}")
                return jsonify({"data": result})
            except Exception as e:
                _log.error(f"Error fetching topcis data filtered by plant names: {e}")
                return jsonify({"error": str(e)}), 500


    # --------------------- Plant Management ---------------------
        # TODO get plant list
        # TODO get plant status


# --------------------- Server functions ---------------------
    
    def _start_http_server(self):
        """
        Start the backend server.
        """
        _log.info("Starting HTTP server…")
        self._server = WSGIServer((self._http_host, self._http_port), self.app, log=None)
        self.core.spawn(self._server.serve_forever)  # runs inside Volttron greenlet hub
        _log.info(f"HTTP server started at {self._http_host}:{self._http_port}")


    def _stop_http_server(self):
        """
        Stop the backend server.
        """
        _log.info("Shutting down HTTP server…")
        if self._server:
            self._server.stop()
            _log.info("HTTP server stopped.")
        else:
            _log.warning("HTTP server was not initiated")


    def _restart_http_server(self):
        """
        Stop & then start again with the latest host/port.
        """
        self._stop_http_server()
        self._start_http_server()


    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        try:
            result = self.vip.rpc.call(self.service_id, "enable_agent_autostart", self.core.identity, "50").get(timeout=TIMEOUT_TIME)
            _log.debug(f"Enabling autostart for {self.core.identity}: {result}")
        except gevent.Timeout as to:
            _log.error(f"RPC enable_agent_autostart time out: {to}.")


    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        self._stop_http_server()


def main():
    """Main method called to start the agent."""
    utils.vip_main(backend, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
