// import React, { useState, useEffect } from "react";
import React, { useState, useEffect} from "react";
import axios from "axios";

//BACKEND_IP = "http://172.23.68.187:8000"

const App = () => {

  const appStyle = {
    backgroundImage: "url('/cc4e_logo3.png')",
    backgroundSize: "cover",
    backgroundPosition: "center",
    backgroundRepeat: "no-repeat",   // Prevents image from repeating
    backgroundAttachment: "fixed",   // locks paralax
    //filter: "brightness(0.7)",
    height: "100vh",
  };

  // Agents
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [agentStatuses, setStatuses] = useState({});
  // Agent Installation
  const [showInstallForm, setShowInstallForm] = useState(false);
  const [installBaseDir, setInstallBaseDir] = useState("");
  const [installConfigFile, setInstallConfigFile] = useState("");
  const [installTag, setInstallTag] = useState("");
  // Configurations
  const [showConfigEditor, setShowConfigEditor] = useState(false);
  const [configs, setConfigs] = useState([]);
  const [selectedConfig, setSelectedConfig] = useState("");
  const [configContent, setConfigContent] = useState("");
  const [showAddConfig, setShowAddConfig] = useState(false);
  const [newConfigName, setNewConfigName] = useState("");
  const [newConfigPath, setNewConfigPath] = useState("");
  // Experiment Manager States
  const [experimentId, setExperimentId] = useState("");
  const [experimenter, setExperimenter] = useState("");
  const [description, setDescription] = useState("");
  const [startTime, setStartTime] = useState("");
  const [stopTime, setStopTime] = useState("");
  const [plantList, setAgentsList] = useState("");

  const [authExperimentId, setAuthExperimentId] = useState("");
  const [supervisorName, setSupervisorName] = useState("");

  const [readyExperimentId, setReadyExperimentId] = useState("");
  const [readyAgents, setReadyAgents] = useState("");
  const [topicsToLog, setTopicsToLog] = useState("");

  // Logs
  const [logContent, setLogContent] = useState("");
  const highlightLogLine = (line) => {
    // Extract the timestamp at the start (and keep it separate)
    const timestampMatch = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})/);
    let timestamp = "";
    if (timestampMatch) {
      timestamp = `<span style="color: green;">${timestampMatch[1]}</span>`;
      line = line.slice(timestampMatch[1].length); // Remove the timestamp from the line
    }

    // Highlight strings in double or single quotes
    line = line.replace(/(["'])(?:(?=(\\?))\2.)*?\1/g, (match) => {
      return `<span style="color: red;">${match}</span>`;
    });

    // Highlight numbers (excluding those in tags)
    line = line.replace(/(?<![>\d])\b\d+(\.\d+)?\b(?![^<]*>)/g, (match) => {
      return `<span style="color: blue;">${match}</span>`;
    });

    // Highlight log levels: ERROR, WARNING, INFO, DEBUG
    line = line.replace(
      /\b(ERROR|WARNING|INFO|DEBUG)\b/g,
      (match) => {
        const colors = {
          "ERROR": "red",
          "WARNING": "orange",
          "INFO": "green",
          "DEBUG": "blue"
        };
        return `<span style="color: ${colors[match]}; font-weight: bold;">${match}</span>`;
      }
    );

    // Combine timestamp + rest of line
    return `${timestamp}${line}`;
  };

  // Fetch Logs every couple of seconds
  // WARNING bad implementation, clogs up cash if used more than couple of minutes 
  /* 
  useEffect(() => {
    const interval = setInterval(() => {
      axios.get("http://172.23.68.187:8000/log")  // use your actual IP if needed
        .then(response => {
          setLogContent(response.data.log);
        })
        .catch(error => console.error("Error fetching logs:", error));
    }, 10000);  // 1000 ms = 1 seconds

    return () => clearInterval(interval);  // Clean up when component unmounts
  }, []);
  */

  // single update logs
  useEffect(() => {
    axios.get(`http://172.23.68.187:8000/log`)  // use your actual IP if needed
      .then(response => {
        setLogContent(response.data.log);
      })
      .catch(error => console.error("Error fetching logs:", error));
  }, []);

  // Auto fetch the agent list on page load
  useEffect(() => {
    fetchAgents();
  }, []); 

  // Fetch config list when an agent is selected
  useEffect(() => {
    if (selectedAgent && showConfigEditor) {
      axios.get(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/configs`)
        .then((response) => setConfigs(response.data.configs))
        .catch((error) => console.error("Error fetching configs:", error));
    } else {
      setConfigs([]);
      setSelectedConfig("");
      setConfigContent("");
    }
  }, [selectedAgent, showConfigEditor]);

  // Fetch config content when a config file is selected
  useEffect(() => {
    if (selectedAgent && selectedConfig) {
      axios.get(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/configs/${selectedConfig}`)
        .then((response) => setConfigContent(response.data.content))
        .catch((error) => console.error("Error fetching config content:", error));
    } else {
      setConfigContent("");
    }
  }, [selectedAgent, selectedConfig]);

  // Fetch the agent list
  const fetchAgents = () => {
    axios.get(`http://172.23.68.187:8000/agents`)
      .then(response => setAgents(response.data.agents))
      .catch(error => console.error("Error fetching agents:", error));
  };

  // Fetch Agent Statuses
  const fetchStatuses = () => {
    axios.get(`http://172.23.68.187:8000/agent_statuses`)
      .then(res => setStatuses(res.data.statuses))
      .catch(err => console.error("Error fetching statuses:", err));
  };

  // Start agent
  const handleStartAgent = () => {
    if (selectedAgent) {
      axios.post(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/start`)
        .then(() => alert(`${selectedAgent.identity} started!`))
        .catch((error) => console.error(error));
    }
  };

  // Stop agent
  const handleStopAgent = () => {
    if (selectedAgent) {
      axios.post(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/stop`)
        .then(() => alert(`${selectedAgent.identity} stopped!`))
        .catch((error) => console.error(error));
    }
  };

  // Remove Agent
  const handleRemoveAgent = () => {
    if (selectedAgent) {
      axios.delete(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/remove`)
        .then(() => {
          alert(`${selectedAgent.identity} removed!`);
          setSelectedAgent(null);
          setConfigs([]);
          setSelectedConfig("");
          setConfigContent("");
          return axios.get("http://172.23.68.187:8000/agents");
        })
        .then((response) => setAgents(response.data.agents))
        .catch((error) => console.error("Error removing agent:", error));
    }
  };

  // Save updated config
  const handleSaveConfig = () => {
    if (selectedAgent && selectedConfig) {
      axios.post(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/configs/${selectedConfig}`, {
        content: configContent
      })
        .then(() => alert(`Config ${selectedConfig} saved!`))
        .catch((error) => console.error("Error saving config:", error));
    }
  };

  // Store new config
  const handleStoreConfig = () => {
    if (!selectedAgent || !newConfigName || !newConfigPath) {
      alert("Please provide a config name and path.");
      return;
    }
  
    axios.post(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/configs/`, {
      agent_identity: selectedAgent.identity,
      config_name: newConfigName,
      config_path: newConfigPath
    })
      .then(() => {
        alert(`Config ${newConfigName} stored!`);
        setNewConfigName("");
        setNewConfigPath("");
        return axios.get(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/configs`);
      })
      .then((response) => setConfigs(response.data.configs))
      .catch((error) => console.error("Error storing config:", error));
  };

  // Delete Config
  const handleDeleteConfig = () => {
    if (!selectedAgent || !selectedConfig) {
      alert("Please select a config to delete.");
      return;
    }
  
    axios.delete(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/configs/${selectedConfig}`)
      .then(() => {
        alert(`Config ${selectedConfig} deleted!`);
        setSelectedConfig(""); // Reset selection
        setConfigContent(""); // Clear content
        return axios.get(`http://172.23.68.187:8000/agents/${selectedAgent.identity}/configs`);
      })
      .then((response) => setConfigs(response.data.configs)) // Refresh config list
      .catch((error) => console.error("Error deleting config:", error));
  };

  // Install Agent
  const handleInstallAgent = () => {
    if (!installBaseDir || !installConfigFile || !installTag) {
      alert("Please fill all fields!");
      return;
    }
  
    axios.post(`http://172.23.68.187:8000/install-agent`, {
      base_dir: installBaseDir,
      config_file: installConfigFile,
      tag: installTag
    })
      .then((response) => {
        alert(response.data.message)
        fetchAgents();
      })
      .catch((error) => alert("Error installing agent: " + error.response.data.detail));
  };

  // Submit Experiment
  const handleSubmitExperiment = () => {
    axios.post(`http://172.23.68.187:8000/experiments/submit`, {
      experiment_id: experimentId,
      experimenter: experimenter,
      description: description,
      start_time: startTime,
      stop_time: stopTime,
      plants: plantList.split(",").map(a => a.trim())
    })
    .then(res => alert(`Experiment submitted: ${res.data.experiment_id}`))
    .catch(err => alert(`Error: ${err.response?.data?.detail || err.message}`));
  };

  // Authorize Experiment
  const handleAuthorizeExperiment = () => {
    axios.post(`http://172.23.68.187:8000/experiments/${authExperimentId}/authorise`, null, {
      params: {
        supervisor_name: supervisorName
      }
    })
    .then(res => alert(`Authorized: ${res.data.message}`))
    .catch(err => alert(`Error: ${err.response?.data?.detail || err.message}`));
  };

  // Finalize Experiment
  const handleMarkReady = () => {
    axios.post(`http://172.23.68.187:8000/experiments/${readyExperimentId}/ready`, {
      agents_for_experiment: readyAgents.split(",").map(a => a.trim()),
      topics_to_log: topicsToLog.split(",").map(t => t.trim())
    })
    .then(res => alert(`Ready: ${res.data.message}`))
    .catch(err => alert(`Error: ${err.response?.data?.detail || err.message}`));
  };


  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Left: Agent Manager UI */}
      <div style={{ width: "50%", overflowY: "auto", fontSize: "12px",...appStyle }}>
        <div style={{ textAlign: "center", marginTop: "10px" }}>
          <h2>VOLTTRON Agent Manager</h2>

          {/* Agent Statuses table */}        
          <h3 style={{ fontWeight: "bold", margin: "0" }}>Agent Statuses</h3>
          <button style={{fontSize: "9px"}} onClick={fetchStatuses}>Refresh Statuses</button>
          {Object.keys(agentStatuses).length > 0 && (
            <table style={{ margin: "10px auto", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{border: "1px solid #ccc", padding: "4px"}}>Identity</th>
                  <th style={{border: "1px solid #ccc", padding: "4px"}}>UUID</th>
                  <th style={{border: "1px solid #ccc", padding: "4px"}}>Status</th>
                  <th style={{border: "1px solid #ccc", padding: "4px"}}>Last Checked</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(agentStatuses).map(([id, info]) => (
                  <tr key={id}>
                    <td style={{border: "1px solid #ccc", padding: "4px"}}>{id}</td>
                    <td style={{border: "1px solid #ccc", padding: "4px"}}>{info.uuid}</td>
                    <td style={{border: "1px solid #ccc", padding: "4px"}}>
                      {info.status}
                    </td>
                    <td style={{border: "1px solid #ccc", padding: "4px"}}>
                      {new Date(info.last_checked * 1000).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
  
          {/* Agent Installation Section */}
          <div>
            <h3 style={{ fontWeight: "bold", margin: "0" }}>Agent Installation</h3>
            <button style={{fontSize: "9px"}} onClick={() => setShowInstallForm(!showInstallForm)}>
              {showInstallForm ? "Cancel Installation" : "Install New Agent"}
            </button>
          </div>

          {showInstallForm && (
            <div>
              <label>Base Directory:</label>
              <input
                type="text"
                value={installBaseDir}
                onChange={(e) => setInstallBaseDir(e.target.value)}
                placeholder="Enter base directory"
              />
              <br />

              <label>Config File:</label>
              <input
                type="text"
                value={installConfigFile}
                onChange={(e) => setInstallConfigFile(e.target.value)}
                placeholder="Enter config file path"
              />
              <br />

              <label>Tag:</label>
              <input
                type="text"
                value={installTag}
                onChange={(e) => setInstallTag(e.target.value)}
                placeholder="Enter agent tag"
              />
              <br />

              <button onClick={handleInstallAgent}>Install Agent</button>
            </div>
          )}

          {/* Agent Selection */}
          <div>
            <h3 style={{ fontWeight: "bold", margin: "0" }}>Agent Control</h3>
            <select
              onChange={(e) => {
                const agent = agents.find(a => a.identity === e.target.value);
                setSelectedAgent(agent || null);
              }}
            >
              <option value="">Select an Agent</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.identity}>
                  {agent.identity} ({agent.id})
                </option>
              ))}
            </select>
          </div>

          {selectedAgent && (
            <>
              <button onClick={handleStartAgent}>Start</button>
              <button onClick={handleStopAgent}>Stop</button>
              <button onClick={handleRemoveAgent}>Remove</button>
              <button onClick={() => setShowConfigEditor(!showConfigEditor)}>
                {showConfigEditor ? "Close Config Store" : "Open Config Store"}
              </button>
            </>
          )}

          {showConfigEditor && selectedAgent && (
            <div>
              <h3 style={{ fontWeight: "bold", margin: "0" }}>Configuration Store</h3>

              <div style={{ display: "flex", justifyContent: "center", alignItems: "center", marginBottom: "10px" }}>
                <select
                  onChange={(e) => setSelectedConfig(e.target.value)}
                  style={{ padding: "1px" }}
                >
                  <option value="">Select a Config</option>
                  {configs.map((config) => (
                    <option key={config} value={config}>{config}</option>
                  ))}
                </select>

                <button onClick={() => setShowAddConfig(!showAddConfig)}>
                  {showAddConfig ? "Cancel" : "Add New Config"}
                </button>
              </div>

              {selectedConfig && (
                <>
                  <textarea
                    value={configContent}
                    onChange={(e) => setConfigContent(e.target.value)}
                    rows="10"
                    cols="50"
                    style={{ display: "block", margin: "0 auto 10px" }}
                  />
                  <button onClick={handleSaveConfig}>Save Config</button>
                  <button onClick={handleDeleteConfig}>Delete Config</button>
                </>
              )}

              {showAddConfig && (
                <div>
                  <h4 style={{ fontWeight: "bold", margin: "0" }}>Add New Config</h4>

                  <input
                    type="text"
                    value={newConfigName}
                    onChange={(e) => setNewConfigName(e.target.value)}
                    placeholder="Enter config name"
                  />
                  <input
                    type="text"
                    value={newConfigPath}
                    onChange={(e) => setNewConfigPath(e.target.value)}
                    placeholder="Enter config file path"
                  />
                  <button onClick={handleStoreConfig}>Store Config</button>
                </div>
              )}
            </div>
          )}

          {/* Experiment Manager Section */}
          <div style={{ marginTop: "20px", padding: "10px", border: "1px solid #ccc", borderRadius: "8px" }}>
            <h2 style={{ fontWeight: "bold", textAlign: "center" }}>Experiment Manager</h2>

            {/* Submit Experiment */}
            <div style={{ marginBottom: "10px" }}>
              <h4>Submit Experiment</h4>
              <input
                type="text"
                placeholder="Experiment ID"
                value={experimentId}
                onChange={(e) => setExperimentId(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Experimenter"
                value={experimenter} 
                onChange={(e) => setExperimenter(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Experiment description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Start Time (ISO)"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Stop Time (ISO)"
                value={stopTime}
                onChange={(e) => setStopTime(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Plants (comma separated)"
                value={plantList}
                onChange={(e) => setAgentsList(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <button onClick={handleSubmitExperiment}>Submit Experiment</button>
            </div>

            {/* Authorize Experiment */}
            <div style={{ marginBottom: "10px" }}>
              <h4>Authorize Experiment</h4>
              <input
                type="text"
                placeholder="Experiment ID"
                value={authExperimentId}
                onChange={(e) => setAuthExperimentId(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Supervisor Name"
                value={supervisorName}
                onChange={(e) => setSupervisorName(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <button onClick={handleAuthorizeExperiment}>Authorize</button>
            </div>

            {/* Finalize Experiment */}
            <div>
              <h4>Finalize Experiment</h4>
              <input
                type="text"
                placeholder="Experiment ID"
                value={readyExperimentId}
                onChange={(e) => setReadyExperimentId(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Agents (comma separated)"
                value={readyAgents}
                onChange={(e) => setReadyAgents(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <input
                type="text"
                placeholder="Topics to Log (comma separated)"
                value={topicsToLog}
                onChange={(e) => setTopicsToLog(e.target.value)}
                style={{ marginBottom: "5px", display: "block", width: "100%" }}
              />
              <button onClick={handleMarkReady}>Finalize</button>
            </div>
          </div>
        </div>
      </div>


      {/* Right: Log Viewer */}
      <div style={{ width: "50%", borderLeft: "1px solid #ccc", display: "flex", flexDirection: "column" }}>
        <h2 style={{ textAlign: "center", marginTop: "10px" }}>Log Viewer</h2>

        <div
          id="log-box"
          style={{
            flex: 1,
            backgroundColor: "#f0f0f0",
            color: "#333",
            padding: "10px",
            border: "1px solid #ccc",
            borderRadius: "5px",
            fontFamily: "monospace",
            fontSize: "12px",
            overflowY: "auto",
            whiteSpace: "pre-wrap"
          }}
          
          dangerouslySetInnerHTML={{
            __html: logContent
              .split("\n")
              .map(highlightLogLine)
              .join("<br />")
          }}
          
        />
      </div>
    </div>
  );
};

export default App;