import asyncio
import websockets
import http.server
import socketserver
import threading
import paho.mqtt.client as mqtt
import json
import mysql.connector
from datetime import datetime

# MQTT configuration
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC_SENSOR1 = "sensor1/data"
MQTT_TOPIC_SENSOR2 = "sensor2/data"
MQTT_CLIENT_ID = "web_socket"

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'remote',
    'password': 'admin',
    'database': 'iot'
}

# Global queue for sensor data
sensor_data_queue = asyncio.Queue()

# List to store connected WebSocket clients
connected_clients = []

# Save data to database
def save_to_database(sensor_data):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """INSERT INTO sensor_data (temperature1, humidity1, temperature2, humidity2, timestamp) \
                   VALUES (%s, %s, %s, %s, %s)"""
        timestamp = datetime.now()
        cursor.execute(query, (
            sensor_data.get("temperature1"),
            sensor_data.get("humidity1"),
            sensor_data.get("temperature2"),
            sensor_data.get("humidity2"),
            timestamp
        ))
        conn.commit()
        cursor.close()
        conn.close()
        print("Sensor data saved to database.")
    except Exception as e:
        print("Error saving to database:", e)

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC_SENSOR1)
        client.subscribe(MQTT_TOPIC_SENSOR2)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    try:
        message = msg.payload.decode("utf-8")
        sensor_data = {}

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

        print("Sensor data updated:", sensor_data)  # Debug output

        # Save to database
        save_to_database(sensor_data)

        # Enqueue data for WebSocket broadcast
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(sensor_data_queue.put_nowait, sensor_data)

    except Exception as e:
        print("Error processing MQTT message:", e)

# WebSocket Server
async def websocket_handler(websocket, path="/"):
    connected_clients.append(websocket)
    print(f"New WebSocket client connected. Total clients: {len(connected_clients)}")  # Debug log
    try:
        async for message in websocket:
            print(f"Message received from client: {message}")  # Debug log
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"WebSocket error: {e}")
    finally:
        connected_clients.remove(websocket)
        print(f"Client disconnected. Total clients: {len(connected_clients)}")

async def broadcast_data():
    while True:
        sensor_data = await sensor_data_queue.get()
        message = json.dumps(sensor_data)
        print("Broadcasting data to clients:", message)  # Debug output
        for client in connected_clients[:]:  # Use a copy of the list to avoid iteration issues
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                print("Client disconnected during broadcast.")
                connected_clients.remove(client)

async def start_websocket_server():
    print("Starting WebSocket server on port 8001...")
    try:
        async with websockets.serve(websocket_handler, "0.0.0.0", 8001):  # Bind to all interfaces
            await broadcast_data()
    except asyncio.CancelledError:
        print("WebSocket server shutting down.")

# HTTP Server
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            # Serve sensor data as JSON
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps({"message": "Data endpoint not implemented here"}), "utf-8"))
        elif self.path == "/" or self.path == "/index.html":
            # Default to serving sensors.html
            self.path = "/sensors.html"
            super().do_GET()
        else:
            super().do_GET()

# Start HTTP Server
def start_http_server():
    with socketserver.TCPServer(("0.0.0.0", 8000), MyRequestHandler) as httpd:  # Bind to all interfaces
        print("Serving HTTP on port 8000")
        httpd.serve_forever()

# Start Servers
def start_servers():
    # Start HTTP server in a separate thread
    http_thread = threading.Thread(target=start_http_server)
    http_thread.daemon = True
    http_thread.start()

    # Start MQTT client in a separate thread
    mqtt_thread = threading.Thread(target=run_mqtt_client)
    mqtt_thread.daemon = True
    mqtt_thread.start()

    # Run WebSocket server in the asyncio event loop
    asyncio.run(start_websocket_server())

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

if __name__ == "__main__":
    start_servers()