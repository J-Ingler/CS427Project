import http.server
import socketserver
import os
import threading
import time
#TODO fix this damn mqtt thing
import paho.mqtt.client as mqtt
import json

# MQTT configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensor/data"
MQTT_CLIENT_ID = "web_socket"

# Global variable for sensor data
sensor_data = {"temperature1": None, "humidity1": None, "temperature2": None, "humidity2": None}

# MQTT Callback for connection
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

# MQTT Callback for receiving messages
def on_message(client, userdata, msg):
    global sensor_data
    try:
        message = msg.payload.decode("utf-8")
        data = message.split(",")
        # Assuming format: "temp1,hum1,temp2,hum2"
        sensor_data["temperature1"] = data[0]
        sensor_data["humidity1"] = data[1]
        sensor_data["temperature2"] = data[2]
        sensor_data["humidity2"] = data[3]
        print("Sensor data updated:", sensor_data)
    except Exception as e:
        print("Error processing MQTT message:", e)

# Function to run the MQTT client
def run_mqtt_client():
    client = mqtt.Client(MQTT_CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

# Start MQTT client in a separate thread
mqtt_thread = threading.Thread(target=run_mqtt_client)
mqtt_thread.daemon = True
mqtt_thread.start()

# HTTP server configuration
PORT = 8000

class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            # Serve sensor data as JSON
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(sensor_data), "utf-8"))
        else:
            super().do_GET()

    def translate_path(self, path):
        # Allow serving files from the current directory
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = os.path.normpath(path)
        words = path.split('/')
        words = filter(None, words)
        path = os.getcwd() + '/' + '/'.join(words)
        return path

with socketserver.TCPServer(("", PORT), MyRequestHandler) as httpd:
    print("Serving on port", PORT)
    httpd.serve_forever()
