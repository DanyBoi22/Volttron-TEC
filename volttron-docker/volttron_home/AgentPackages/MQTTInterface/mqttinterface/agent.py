"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import json
import threading
import paho.mqtt.client as mqtt
import ssl
from datetime import datetime, timezone
from typing import List, Dict
import gevent

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from pydantic import BaseModel, Field, ValidationError
from metadata.metadata_mixin import MetadataMixin

class MessageHeader(BaseModel):
    source: str
    target: str
    timestamp: str
    additional: Dict = None

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.2"

def mqttinterface(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Mqttinterface
    :rtype: Mqttinterface
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    if not config:
        _log.info("Could not access config file for starting configuration.")
        exit()

    return Mqttinterface(config, **kwargs)


class Mqttinterface(Agent, MetadataMixin):
    """
    Document agent constructor here.
    """

    def __init__(self, config, **kwargs):
        super(Mqttinterface, self).__init__(**kwargs)
        #MetadataMixin.__init__(self, config, self.core.identity)

        self._agent_id = self.core.identity

        self._mqtt_config = config.get("mqtt", {})
        # TODO: remove topic registry from config and replace with querry to registry agent
        self._topic_registry_identity = config.get("topic_registry_identity", "topicregistryagent-0.1_1")
        
        self._topic_map_ext2int_command = {}
        self._topic_map_ext2int_noncommand = {}

        self._mqtt_client = None
        self._mqtt_thread = None
        self._incoming_message_queue: gevent.queue.Queue = gevent.queue.Queue(maxsize=1000)
        self._outgoing_message_queue: gevent.queue.Queue = gevent.queue.Queue(maxsize=1000)

        # Load dynamic config
        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        

    def _configure(self, config_name, action, contents):
        _log.info(f"Reconfiguring MQTT interface agent...")
        self._mqtt_config = contents.get("mqtt", self._mqtt_config)
        
        # TODO: remove topic registry from config and replace with querry to registry agent
        self._topic_registry_identity = contents.get("topic_registry_identity", self._topic_registry_identity)
        
        self._retrieve_mappings()
        self._setup_internal_subscriptions()
        self._reset_mqtt_client()
        self._process_incoming_messages()

    @RPC.export
    def test_comms(self):
        """
        Just a dummy method to test agents responsivenes 
        """
        return True

    def _retrieve_mappings(self):
        """
        Retrieves mappings for command and status topics from topic registry 

        Raises:
            Exception on fail
        """
        try:
            _log.debug(f"Requesting topic mappings from {self._topic_registry_identity}")
            self._topic_map_ext2int_command = self.vip.rpc.call(self._topic_registry_identity, "get_external_to_validated_commands_map").get(timeout=2)
            self._topic_map_ext2int_noncommand = self.vip.rpc.call(self._topic_registry_identity, "get_external_to_internal_noncommand_map").get(timeout=2)
        except gevent.Timeout as to:
            _log.error(f"Failed to retrieve topic mappings from registry, rpc time out: {to}")
        except Exception as e:
            _log.error(f"Failed to retrieve topic mappings from registry: {e}")


    def _setup_internal_subscriptions(self):
        """
        Subscribes to validated plant control topics on internal bus 
        and setups callback function to resend the message
        """
        for external_topic, internal_topic  in self._topic_map_ext2int_command.items():
            callback = self._create_internal_to_external_callback(external_topic)
            self.vip.pubsub.subscribe("pubsub", internal_topic, callback)
            _log.debug(f"Subscribed to internal topic '{internal_topic}' for MQTT topic '{external_topic}'")
    

# -------------- Message processing --------------

    def _create_internal_to_external_callback(self, external_topic):
        """
        Returns a callback that forwards Volttron bus messages to the MQTT broker.
        """

        def callback(peer, sender, bus, topic, headers, message):
            value = None
            timestamp = None
            # Parse and validate header
            try:
                header = MessageHeader(**headers)
                # Ignore messages originally sent by this agent
                if header.source == self._agent_id:
                    _log.debug(f"Ignoring own message {topic}")
                    return
                value = message
                timestamp = header.timestamp

                # TODO: here can be some kind of additional validation to make sure the message is from the right source
            except Exception as e:
                _log.warning(f"Invalid message header on '{topic}': {e}")
                return

            # Prepape and put the mqtt message into the queue 
            try:
                mqtt_payload = self._prepare_mqtt_payload(value, timestamp)

                # Non-blocking enqueue; drops messages if queue is full
                self._outgoing_message_queue.put_nowait((external_topic, mqtt_payload))
                _log.debug(f"Volttron → MQTT: {topic} → {external_topic} | {mqtt_payload}, timestamp: {timestamp}")

            except gevent.queue.Full:
                _log.warning(f"Outgoing MQTT queue full. Dropping message from {topic}")
            except Exception as e:
                _log.warning(f"Error preparing MQTT message from '{topic}': {e}")

        return callback
    
    def _prepare_mqtt_payload(self, value, timestamp):

        # Make sure the value is serializable. Not striclty nessecery because of how mqtt in volttron works but still
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            raise ValueError(f"value must be a serializable, got {type(value)}")
        
        if not isinstance(timestamp, str):
            raise ValueError(f"timestamp must be a string, got {type(timestamp)}")

        try:
            dt = datetime.fromisoformat(timestamp)
        except Exception as e:
            raise ValueError(f"Invalid ISO-8601 timestamp: {timestamp}") from e

        # If parsed datetime is naive, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to unix milliseconds
        unix_ms = int(dt.timestamp() * 1000)

        # TODO: find out how the message has to be build for the cybus 
        return {"value": value, "timestamp": unix_ms}
        #return value

    def _republish_external_to_internal(self, msg):
        """
        Resends message from external mqtt brocker to the internal volttron bus
        
        The MQTT payload is expected to be a JSON dict:
            {"value": <number>, "timestamp": <unix_ms>}

        The timestamp is converted to UTC ISO 8601 and placed into the Volttron
        message header. The payload published to Volttron contains only "value".
        """
        try:
            # Decode and parse payload
            external_topic = msg.topic
            raw_payload = msg.payload.decode("utf-8")
            json_payload = json.loads(raw_payload)

            internal_topic = self._topic_map_ext2int_noncommand.get(external_topic)
            if not internal_topic:
                _log.warning(f"No internal topic mapped for: {external_topic}")
                raise RuntimeError("No internal topic mapped")
            
            if not isinstance(json_payload, dict):
                _log.warning(f"Expected json_payload being a dict, got {type(json_payload)}")
                raise ValueError("Payload of the message is not dict")

            # Extract required fields
            if "timestamp" not in json_payload:
                _log.warning(f"Payload missing 'timestamp' in {external_topic}")
                raise ValueError("Payload missing 'timestamp'")
            if "value" not in json_payload:
                _log.warning(f"Payload missing 'value' in {external_topic}")
                raise ValueError("Payload missing 'value'")

            unix_ms = json_payload["timestamp"]
            value = json_payload["value"]

            # Convert millis ts into ISO8601 String with UTC timeyone
            timestamp_utc = (datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc).isoformat())

            # Build Volttron header
            header = MessageHeader(source=self._agent_id, target="volttron-bus", timestamp=timestamp_utc)

            # Publish only the value to Volttron
            self.vip.pubsub.publish("pubsub", internal_topic, header.model_dump(), value)

            #_log.debug(f"Cybus → Volttron: {external_topic} → {internal_topic} | value={value}, timestamp={timestamp_utc}")

        except json.JSONDecodeError:
            _log.error(f"Invalid JSON payload on topic {external_topic}: {msg.payload}")
        except Exception as e:
            _log.error(f"Error processing external message on {external_topic}: {e}",exc_info=True)

    def _process_incoming_messages(self):
        """
        Spawn a greenlet that will process incoming messages 
        """
        self.core.spawn(self._start_processing_loop)

    
    def _start_processing_loop(self):
        """
        Endless loop that just processes the message queue 
        """
        while True:
            # non blocking, non-poling if empty, greenlet context aware
            msg = self._incoming_message_queue.get() 
            self._republish_external_to_internal(msg)
                

# -------------- MQTT Client --------------

    def _init_mqtt(self):
        """
        Initialises from configuration in config and connect the MQTT Client to the MQTT Broker.
        Spawns a separate Thread that runs the client.
        """
        broker = self._mqtt_config.get("broker_address")
        port = int(self._mqtt_config.get("broker_port", 1883))

        if not broker:
            _log.error("Broker address not configured. MQTT client will not start.")
            return

        _log.info(f"Initializing MQTT client for broker {broker}:{port}")
        self._mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        
        # TLS configuration if enabled
        if self._mqtt_config.get("tls", False):
            try:
                _log.info("TLS enabled. Configuring SSL context...")
                
                ca_certs=self._mqtt_config.get("ca_cert")
                if not ca_certs == "":
                    # TODO: implement tsl certificates 
                    cert_reqs=ssl.CERT_REQUIRED
                else:
                    ca_certs=None
                    cert_reqs=ssl.CERT_NONE
 
                if self._mqtt_config.get("mutual_tls", False):
                    # TODO: implement mutual tsl certificates
                    certfile=self._mqtt_config.get("certfile")
                    keyfile=self._mqtt_config.get("keyfile")
                else:
                    certfile=None
                    keyfile=None
                
                tls_version=ssl.PROTOCOL_TLS
                self._mqtt_client.tls_set(ca_certs=ca_certs, certfile=certfile, keyfile=keyfile, cert_reqs=cert_reqs, tls_version=tls_version)
                if not ca_certs:
                    self._mqtt_client.tls_insecure_set(True)

                _log.info(f"TLS configured successfully.")
            except Exception as e:
                _log.error(f"Failed to configure TLS: {e}")
                return
        
        # Authentication
        if self._mqtt_config.get("username"):
            self._mqtt_client.username_pw_set(self._mqtt_config.get("username"), self._mqtt_config.get("password"))
        else:
            _log.error("User authentication missing. MQTT client will not start.")
            return

        # callbacks
        self._mqtt_client.on_connect = self._on_connect
        self._mqtt_client.on_subscribe = self._on_subscribe
        self._mqtt_client.on_message = self._on_message
        self._mqtt_client.on_disconnect = self._on_disconnect

        try:
            self._mqtt_client.connect(broker, port, keepalive=60)
            _log.info(f"Connecting to MQTT broker {broker}:{port}")
        except Exception as e:
            _log.error(f"Failed to connect to MQTT broker: {e}")
            return

        self._mqtt_thread = threading.Thread(target=self._mqtt_loop_with_outgoing_processing, daemon=True)
        self._mqtt_thread.start()
        _log.info("MQTT client thread started.")

    def _reset_mqtt_client(self):
        """
        Disconnects from Broker if previuosly connected.
        Reinitialises the Mqtt Client 
        """
        _log.info("Setting up MQTT client...")
        if self._mqtt_client:
            try:
                self._mqtt_client.disconnect()
                _log.info("Disconnected previous MQTT client successfully.")
            except Exception as e:
                _log.error(f"Failed to disconnect previous MQTT client: {e}")
        
        self._init_mqtt()


    def _mqtt_loop_with_outgoing_processing(self):
        """
        Runs the MQTT network loop and also processes outgoing messages from the queue.
        This thread acts as a bridge between gevent (Volttron) and the MQTT client.
        """
        client = self._mqtt_client

        while True:
            client.loop(timeout=0.5) 

        # TODO: publishing 
            try:
                topic, payload = self._outgoing_message_queue.get_nowait()
                json_payload = json.dumps(payload)
                result = client.publish(topic, json_payload)

                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    _log.warning(f"Failed to publish MQTT message to {topic}: rc={result.rc}")

            except gevent.queue.Empty:
                continue 
            except Exception as e:
                _log.error(f"Error processing outgoing MQTT message: {e}")
            


# -------------- MQTT Callbacks --------------

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        On connect to the mqtt broker subscribe to all external topics for plant status, sensor and error messages 
        """
        if rc.is_failure:
            _log.error(f"Connection failed with result code {rc}")
        else:
            _log.info("Successfully connected to MQTT broker.")
            for external_topic, _ in self._topic_map_ext2int_noncommand.items():
                client.subscribe(external_topic)
                _log.debug(f"Subscribed to external topic: {external_topic}")

    def _on_subscribe(self, client, userdata, mid, rc_list, properties):
        """
        On subscribe log callback
        """
        if rc_list[0].is_failure:
            _log.warning(f"Subscription failed. Reason: {rc_list[0]}, mid={mid}, properties={properties}")
        else:
            _log.debug(f"Subscription successfull. mid={mid}, QoS: {rc_list[0].value}, properties={properties}")

    def _on_message(self, client, userdata, msg):
        """
        On message from mqtt broker push the message to the incoming message queue
        """
        try:
            self._incoming_message_queue.put_nowait(msg)  # non-blocking; raises exception if full
        except gevent.queue.Full:
            _log.warning(f"MQTT message queue is full. Dropping message {msg.topic}.")

    def _on_disconnect(self, client, userdata, flags, rc, properties):
        """
        On disconnect log reason code
        """
        _log.info(f"Disconnected from MQTT broker. Reason: {rc}")

def main():
    """Main method called to start the agent."""
    utils.vip_main(mqttinterface, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
