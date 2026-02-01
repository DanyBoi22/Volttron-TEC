import gevent
import os
import subprocess
from pathlib import Path

VOLTTRON_HOME = Path("/home/volttron/.volttron")
AGENT_PACKAGES = VOLTTRON_HOME / "AgentPackages"

AGENTS = {
    "agent_manager": (AGENT_PACKAGES / "AgentManager", AGENT_PACKAGES / "AgentManager" / "config"),

    "agent_registry": (AGENT_PACKAGES / "AgentRegistry", AGENT_PACKAGES / "AgentRegistry" / "config"),
    "plant_registry": (AGENT_PACKAGES / "PlantRegistry", AGENT_PACKAGES / "PlantRegistry" / "config"),
    "topic_registry": (AGENT_PACKAGES / "TopicRegistryAgent", AGENT_PACKAGES / "TopicRegistryAgent" / "config"),
    
    "mqtt_bridge": (AGENT_PACKAGES / "MQTTInterface", AGENT_PACKAGES / "MQTTInterface" / "config"),
    
    "experiment_manager": (AGENT_PACKAGES / "ExperimentManager", AGENT_PACKAGES / "ExperimentManager" / "config"),
    "scheduler": (AGENT_PACKAGES / "Scheduler", AGENT_PACKAGES / "Scheduler" / "config"),
    
    "logger": (AGENT_PACKAGES / "Logger", AGENT_PACKAGES / "Logger" / "config"),
    "backend_server": (AGENT_PACKAGES / "BackendAgent", AGENT_PACKAGES / "BackendAgent" / "config"),
    
    "bhkw": (AGENT_PACKAGES / "ControlBHKW", AGENT_PACKAGES / "ControlBHKW" / "config"),
    "speicher": (AGENT_PACKAGES / "ControlSpeicher", AGENT_PACKAGES / "ControlSpeicher" / "config"),
    
    "tester": (AGENT_PACKAGES / "testingAgents" / "TestAgent", AGENT_PACKAGES / "testingAgents" / "TestAgent" / "config"),
    "impulsetest": (AGENT_PACKAGES / "testingAgents" / "ImpulseTest", AGENT_PACKAGES / "testingAgents" / "ImpulseTest" / "config"),
}

def install_agent(base_dir: str, config_file_path: str, tag: str):
    try:
        print(f"\n--- Installing agent: {tag} ---")

        # Absolute paths
        base_dir = os.path.abspath(base_dir)
        config_file_path = os.path.abspath(config_file_path)

        if not os.path.exists(config_file_path):
            raise FileNotFoundError(f"Config file not found: {config_file_path}")

        command = [
            "python3", "/volttron/scripts/install_agent.py",
            "-s", base_dir,
            "-c", config_file_path,
            "-t", tag
        ]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Agent '{tag}' installed successfully.")
        else:
            print(f"Failed to install agent '{tag}', code: {result} .")

        return result.returncode
    except Exception as e:
        print(f"Error installing agent '{tag}': {e}")
        return 1

if __name__ == '__main__':
    print("Starting automatic Volttron agent installation...\n")

    for tag, (base_dir, config_file) in AGENTS.items():
        code = install_agent(base_dir, config_file, tag)
        gevent.sleep(1)  # avoid overwhelming Volttron core

    print("\nAll agents processed.")