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

# Global variable for sensor data
sensor_data = {"temperature1": None, "humidity1": None, "temperature2": None, "humidity2": None}

# List to store connected WebSocket clients
connected_clients = []

# Save data to database
def save_to_database():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """INSERT INTO sensor_data (temperature1, humidity1, temperature2, humidity2, timestamp) \
                   VALUES (%s, %s, %s, %s, %s)"""
        timestamp = datetime.now()
        cursor.execute(query, (
            sensor_data["temperature1"],
            sensor_data["humidity1"],
            sensor_data["temperature2"],
            sensor_data["humidity2"],
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

from asyncio import run_coroutine_threadsafe

def on_message(client, userdata, msg):
    print("On message invoked")
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

        print("Sensor data updated:", sensor_data)  # Debug output

        # Save to database after update
        save_to_database()

        # Broadcast updated data to all WebSocket clients
        asyncio.run_coroutine_threadsafe(broadcast_data(), asyncio.get_event_loop())
        # Broadcast updated data to all WebSocket clients

    except Exception as e:
        print("Error processing MQTT message:", e)


async def broadcast_data():
    print("broadcasting data...")
    print(f"Connected clients: {len(connected_clients)}")  # Debug output
    #if connected_clients:  # Only send data if clients are connected
    message = json.dumps(sensor_data)
    print("Broadcasting data to clients:", message)  # Debug output
    await asyncio.gather(*(client.send(message) for client in connected_clients if client.open))

# MQTT Client in a separate thread


def run_mqtt_client():
    # Create and set an event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

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
    # Register client
    print("websocket_handler invoked")
    connected_clients.append(websocket)
    try:
        # Keep connection alive
        async for _ in websocket:
            pass
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket client disconnected")
    finally:
        # Unregister client on disconnect
        connected_clients.remove(websocket)

async def start_websocket_server():
    print("Starting WebSocket server on port 8001...")
    async with websockets.serve(websocket_handler, "0.0.0.0", 8001):  # Bind to all interfaces
        await asyncio.Future()  # Keep the server running indefinitely

# HTTP Server
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            # Serve sensor data as JSON
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(sensor_data), "utf-8"))
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

if __name__ == "__main__":
    start_servers()
