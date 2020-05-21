import os

from flask import Flask, jsonify
from flaskcommander.mqtthandler import MqttHandler


def create_app(test_config=None):
  # create and configure the app
  app = Flask(__name__, instance_relative_config=True)
  app.config.from_mapping(SECRET_KEY="dev")

  if test_config is None:
    # load the instance config, if it exists, when not testing
    app.config.from_pyfile("config.py", silent=True)
  else:
    # load the test config if passed in
    app.config.from_mapping(test_config)

  # ensure the instance folder exists
  try:
    os.makedirs(app.instance_path)
  except OSError:
    pass

  # create MQTT-Handler
  mqtth = MqttHandler(
      os.path.join(app.instance_path, app.config["MQTT_CONFIG_FILE"]),
      os.path.join(app.instance_path, app.config["PLUG_DEF_FILE"]),
      os.path.join(app.instance_path, app.config["MQTT_TLS_CA"]))

  # a simple test route showing plug states
  @app.route("/full-state")
  def full_state():
    return jsonify(mqtth.get_full_plugs_state())

  # a simple test route showing simplified plug states
  @app.route("/short-state")
  def short_state():
    return jsonify(mqtth.get_short_plugs_state())

  return app
