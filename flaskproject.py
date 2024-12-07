from flask import Flask, jsonify, render_template, request
from datetime import datetime
import mysql.connector

app = Flask(__name__, template_folder="www/")

DB_CONFIG = {
    'host': 'localhost',
    'user': 'remote',
    'password': 'admin',
    'database': 'iot'
}

@app.route('/sensor_dth', methods=['POST'])
def add_dht():
    try:
        # Receive JSON data from the request
        data = request.get_json()
        print(data)

        # Extract sensor data
        temperature1 = data.get('temperature1')
        humidity1 = data.get('humidity1')
        temperature2 = data.get('temperature2')
        humidity2 = data.get('humidity2')
        current_time = datetime.now()
        date_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"Timestamp: {date_time}")

        # Connect to the database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Insert data into the sensor_data table
        query = """
        INSERT INTO sensor_data (temperature1, humidity1, temperature2, humidity2, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (temperature1, humidity1, temperature2, humidity2, date_time))
        conn.commit()

        # Close the connection
        cursor.close()
        conn.close()

        resp = jsonify(message="Data received and saved successfully!")
        resp.status_code = 200
        return resp

    except Exception as e:
        print(f"Error: {e}")
        return jsonify(message="Data error"), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
