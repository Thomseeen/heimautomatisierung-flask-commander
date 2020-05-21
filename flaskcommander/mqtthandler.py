import os, sys, time, ssl, json
import paho.mqtt.client as mqtt


class MqttHandler:
  """ Handler for Paho-MQTT client tailored for Tasmota """

  def __init__(self, config_file, plug_def_file, tls_ca_file):
    """ Constructor """

    #print(f"Debug-constructor: config_file: {config_file}, plug_def_file:{plug_def_file}")

    # Setup subscription queries
    self._QUERIES = {
        "online-state": {
            "prefix":
                "tele",
            "type":
                "LWT",
            "target":
                lambda plug_id, state: self._tasmota_plugs_state[plug_id].update(
                    {"online-state": state})
        },
        "command-result": {
            "prefix":
                "stat",
            "type":
                "RESULT",
            "target":
                lambda plug_id, result: self._tasmota_plugs_state[plug_id]["command-result"].update(
                    json.loads(result))
        },
        "common-status": {
            "prefix":
                "stat",
            "type":
                "STATUS",
            "target":
                lambda plug_id, result: self._tasmota_plugs_state[plug_id]["common-status"].update(
                    json.loads(result))
        }
    }

    # Read CONFIG.json
    with open(config_file) as file:
      self._CONFIG = json.load(file)

    # Setup MQTT client
    self._mqtt_client = mqtt.Client()
    self._mqtt_client.on_connect = self._on_connect
    self._mqtt_client.on_message = self._on_message

    self._mqtt_client.tls_set(ca_certs=tls_ca_file)
    self._mqtt_client.username_pw_set(
        self._CONFIG["MQTT_BROKER"]["USER"], password=self._CONFIG["MQTT_BROKER"]["PASSWORD"])
    self._mqtt_client.connect(self._CONFIG["MQTT_BROKER"]["IP"],
                              self._CONFIG["MQTT_BROKER"]["PORT"], 60)

    # Read TASMOTA_PLUGS.json
    with open(plug_def_file) as file:
      self._tasmota_plugs_state = json.load(file)

    # Create additional nested dictionaries to update
    for query, params in self._QUERIES.items():
      for plug in self._tasmota_plugs_state:
        self._tasmota_plugs_state[plug][query] = {}

    # Start MQTT background thread
    self._mqtt_client.loop_start()

  def _on_connect(self, mqtt_client, userdata, flags, rc):
    """ Callback for Paho-MQTT client """

    #print(f"Debug-on_connect: Connected with result code {rc}")

    # Subscribe to needed topics
    for query, params in self._QUERIES.items():
      mqtt_client.subscribe(f"{params['prefix']}/+/{params['type']}")

    # Manually trigger MODULE, STATE and STATUS query
    for plug in self._tasmota_plugs_state:
      mqtt_client.publish(f"cmnd/{plug}/MODULE", '')  # responds to command-result
      mqtt_client.publish(f"cmnd/{plug}/STATE", '')  # responds to command-result
      mqtt_client.publish(f"cmnd/{plug}/STATUS", '0')  # responds to common-status

  def _on_message(self, mqtt_client, userdata, msg):
    """ Callback for Paho-MQTT client"""

    #print(f"Debug-on_message: Recieved at {msg.topic}: {msg.payload}")

    # Parse topic
    message_prefix = msg.topic.split('/')[0]
    message_type = msg.topic.split('/')[-1]
    plug_id = '/'.join(msg.topic.split('/')[1:-1])

    # Get the right message handler according to topic
    for query, params in self._QUERIES.items():
      if message_prefix == params["prefix"] and message_type == params["type"]:
        params["target"](plug_id, msg.payload.decode("utf-8"))

  def get_full_plugs_state(self):
    """ Get dictionary with current information on all registered plugs """

    return self._tasmota_plugs_state

  def get_short_plugs_state(self):
    """ Get dictionary with most important information on all registered plugs """

    # really ugly bit, don't look,
    short_info = dict()
    for plug_id, info in self._tasmota_plugs_state.items():
      current_module = str(info["common-status"]["Status"]["Module"])
      short_info[plug_id] = dict()
      short_info[plug_id]["name"] = info["name"]
      short_info[plug_id]["online-state"] = info["online-state"]
      short_info[plug_id]["time"] = info["command-result"]["Time"]
      short_info[plug_id]["module"] = info["command-result"]["Module"][current_module]
      short_info[plug_id]["relais"] = dict()
      if short_info[plug_id]["module"] == "Gosund SP1":
        short_info[plug_id]["relais"]["230V"] = info["command-result"]["POWER"]
      elif short_info[plug_id]["module"] == "Gosund SP112":
        short_info[plug_id]["relais"]["230V"] = info["command-result"]["POWER1"]
        short_info[plug_id]["relais"]["5V"] = info["command-result"]["POWER2"]
    return short_info


if __name__ == "__main__":

  from reprint import output

  CONFIG_FILE = "instance/MQTT_CONFIG.json"
  PLUG_DEF_FILE = "instance/TASMOTA_PLUGS.json"
  TLS_CA_FILE = "instance/mosquitto_ca.crt"

  mqtth = MqttHandler(CONFIG_FILE, PLUG_DEF_FILE, TLS_CA_FILE)

  with output(
      output_type="list", initial_len=len(mqtth.get_plugs_state()) * 2, interval=0) as output_list:
    while True:
      for ii, (plug, p) in enumerate(mqtth.get_plugs_state().items()):
        if "_online-state" in p and 'Time' in p:
          output_list[ii *
                      2] = f"{(p['_name'] + ':').ljust(30)} {p['_online-state']} at {p['Time']}"
        if "POWER" in p:
          output_list[ii * 2 + 1] = f"{''.rjust(30)} 230V: {p['POWER']}"
        if "POWER1" in p:
          output_list[ii * 2 + 1] = f"{''.rjust(30)} 230V: {p['POWER1']}, 5V: {p['POWER2']}"

      time.sleep(1)
