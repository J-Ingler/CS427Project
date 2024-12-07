import os
import asyncio
import websockets
import http.server
import socketserver
import threading
import paho.mqtt.client as mqtt
import json
from datetime import datetime

# MQTT configuration
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC_SENSOR1 = "sensor1/data"
MQTT_TOPIC_SENSOR2 = "sensor2/data"
MQTT_CLIENT_ID = "web_socket"

# Global variable for sensor data
sensor_data = {"temperature1": None, "humidity1": None, "temperature2": None, "humidity2": None}

# List to store connected WebSocket clients
connected_clients = []

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC_SENSOR1)
        client.subscribe(MQTT_TOPIC_SENSOR2)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    global sensor_data
    try:
        message = msg.payload.decode("utf-8")
        if msg.topic == MQTT_TOPIC_SENSOR1:
            data = message.split(",")
            if len(data) == 2:
                sensor_data["temperature1"] = float(data[0])
                sensor_data["humidity1"] = float(data[1])
        elif msg.topic == MQTT_TOPIC_SENSOR2:
            data = message.split(",")
            if len(data) == 2:
                sensor_data["temperature2"] = float(data[0])
                sensor_data["humidity2"] = float(data[1])

        print("Sensor data updated:", sensor_data)

        # Broadcast updated data to all WebSocket clients
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(asyncio.create_task, broadcast_data())

    except Exception as e:
        print("Error processing MQTT message:", e)

async def broadcast_data():
    if connected_clients:
        message = json.dumps(sensor_data)
        await asyncio.gather(*(client.send(message) for client in connected_clients if client.open))

# MQTT Client in a separate thread
def run_mqtt_client():
    client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print("MQTT client error:", e)
        client.disconnect()

# WebSocket Server
async def websocket_handler(websocket, path="/"):
    connected_clients.append(websocket)
    try:
        async for _ in websocket:
            pass
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket client disconnected")
    finally:
        connected_clients.remove(websocket)

async def start_websocket_server():
    print("Starting WebSocket server on port 8001...")
    async with websockets.serve(websocket_handler, "localhost", 8001):
        await asyncio.Future()

# HTTP Server
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(sensor_data), "utf-8"))
        else:
            # Serve static files
            if self.path == "/":
                self.path = "/sensors.html"
            elif self.path.endswith(".html") or self.path.endswith(".css"):
                super().do_GET()
            else:
                self.send_error(404, "File not found")

# Start HTTP Server
def start_http_server():
    with socketserver.TCPServer(("", 8000), MyRequestHandler) as httpd:
        print("Serving HTTP on port 8000")
        httpd.serve_forever()

# Start Servers
def start_servers():
    http_thread = threading.Thread(target=start_http_server)
    http_thread.daemon = True
    http_thread.start()

    mqtt_thread = threading.Thread(target=run_mqtt_client)
    mqtt_thread.daemon = True
    mqtt_thread.start()

    asyncio.run(start_websocket_server())

if __name__ == "__main__":
    start_servers()
