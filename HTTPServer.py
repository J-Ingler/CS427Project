import asyncio
import websockets
import http.server
import socketserver
import threading
import paho.mqtt.client as mqtt
import json

# MQTT configuration
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "sensor/data"
MQTT_CLIENT_ID = "web_socket"

# Global variable for sensor data
sensor_data = {"temperature1": None, "humidity1": None, "temperature2": None, "humidity2": None}

# List to store connected WebSocket clients
connected_clients = []

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    global sensor_data
    try:
        message = msg.payload.decode("utf-8")
        data = message.split(",")
        # Assuming format: "temp1,hum1,temp2,hum2"
        if len(data) == 4:
            sensor_data["temperature1"] = data[0]
            sensor_data["humidity1"] = data[1]
            sensor_data["temperature2"] = data[2]
            sensor_data["humidity2"] = data[3]
            print("Sensor data updated:", sensor_data)

            # Broadcast updated data to all WebSocket clients
            loop = asyncio.get_running_loop()
            loop.create_task(broadcast_data())
    except Exception as e:
        print("Error processing MQTT message:", e)

async def broadcast_data():
    if connected_clients:  # Only send data if clients are connected
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
    # Register client
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
    async with websockets.serve(websocket_handler, "localhost", 8001):
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
    with socketserver.TCPServer(("", 8000), MyRequestHandler) as httpd:
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
