import os
import json
import threading
import datetime
import pathlib
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import paho.mqtt.client as mqtt

app = Flask(__name__)
CORS(app) # Enable CORS for React Frontend

# --- CONFIGURATION ---
# ⚠️ SECURITY WARNING: Never commit passwords to GitHub. Use Environment Variables in production.
# For now, I have kept your URI but you should be careful sharing this file.
MONGO_URI = "mongodb+srv://teeandrew86_db_user:V7nnJejzgK28PXxx@project1.s2ihw2y.mongodb.net/?appName=Project1"
MQTT_BROKER = "test.mosquitto.org"
MQTT_TOPIC = "smartcity/streetlight/+/data" # '+' wildcard allows listening to all streetlights

# Path to C++ Executable
# Assumes processing.exe is in the same folder as this script (app/)
CPP_EXE = pathlib.Path(__file__).parent / "processing.exe"

# --- DATABASE CONNECTION ---
try:
    client = MongoClient(MONGO_URI)
    db = client['smart_city_db']
    collection = db['sensor_logs']
    # Check connection
    client.admin.command('ping')
    print("✅ Connected to MongoDB Atlas!")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")

# --- C++ PROCESSING HELPER ---
def process_via_cpp(ldr, motion, power):
    """
    Calls the C++ executable to process sensor data (Sliding Window & Hysteresis).
    Command: processing.exe process <ldr> <motion> <power>
    """
    try:
        if not CPP_EXE.exists():
            print(f"❌ Critical Error: processing.exe not found at {CPP_EXE}")
            return None

        # Run C++ Executable
        result = subprocess.run(
            [str(CPP_EXE), "process", str(ldr), str(motion), str(power)],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse JSON Output from C++
        # Expected: {"smooth_ldr": 123, "is_night": 1, "brightness": 100, "anomaly": 0}
        return json.loads(result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"❌ C++ Runtime Error: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ C++ Output Invalid JSON: {result.stdout}")
        return None
    except Exception as e:
        print(f"❌ Unexpected Error calling C++: {e}")
        return None

# --- MQTT HANDLERS ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        # 1. Extract Raw Data from Firmware
        raw_ldr = int(data.get('ldr', 0))
        motion = int(data.get('motion', 0))
        reported_power = float(data.get('power', 0.0))

        # 2. Process Data using C++ Backend
        # This overwrites the firmware's simple logic with your C++ Backend's superior logic
        cpp_result = process_via_cpp(raw_ldr, motion, reported_power)
        
        if cpp_result:
            print(f"⚡ C++ Processed: {cpp_result}")
            final_smooth_ldr = cpp_result.get('smooth_ldr', raw_ldr)
            final_brightness = cpp_result.get('brightness', 0)
            final_anomaly = cpp_result.get('anomaly', 0)
            is_night = cpp_result.get('is_night', 0)
        else:
            print("⚠️ C++ Failed, using Raw Firmware Data")
            final_smooth_ldr = raw_ldr
            final_brightness = int(data.get('brightness', 0))
            final_anomaly = 0
            is_night = int(data.get('is_night', 0))
        
        # 3. Save to MongoDB
        document = {
            "timestamp": datetime.datetime.utcnow(),
            "device_id": msg.topic.split('/')[2], # Extracts '1' from 'smartcity/streetlight/1/data'
            "ldr_raw": raw_ldr,
            "ldr_smooth": final_smooth_ldr,
            "motion": motion,
            "brightness": final_brightness,
            "power": reported_power,
            "is_night": bool(is_night),
            "anomaly": final_anomaly
        }
        
        collection.insert_one(document)
        print("💾 Data Saved to MongoDB")

    except Exception as e:
        print(f"❌ Error processing MQTT message: {e}")

def start_mqtt():
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(MQTT_BROKER, 1883, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"❌ MQTT Connection Error: {e}")

# --- API ENDPOINTS (For React Frontend) ---

@app.route('/data', methods=['POST'])
def manual_data():
    """Manual data injection for testing without hardware"""
    try:
        data = request.json
        print(f"📡 INCOMING DATA: {data}") # DEBUG LOG
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # 1. Extract Raw Data
        raw_ldr = int(data.get('ldr', 0))
        motion = int(data.get('motion', 0))
        reported_power = float(data.get('power', 0.0))

        # 2. Process via C++
        cpp_result = process_via_cpp(raw_ldr, motion, reported_power)

        if cpp_result:
            final_smooth_ldr = cpp_result.get('smooth_ldr', raw_ldr)
            final_brightness = cpp_result.get('brightness', 0)
            final_anomaly = cpp_result.get('anomaly', 0)
            is_night = cpp_result.get('is_night', 0)
        else:
            final_smooth_ldr = raw_ldr
            final_brightness = int(data.get('brightness', 0))
            final_anomaly = 0
            is_night = int(data.get('is_night', 0))

        # 3. Save to MongoDB
        document = {
            "timestamp": datetime.datetime.utcnow(),
            "device_id": "manual_test",
            "ldr_raw": raw_ldr,
            "ldr_smooth": final_smooth_ldr,
            "motion": motion,
            "brightness": final_brightness,
            "power": reported_power,
            "is_night": bool(is_night),
            "anomaly": final_anomaly
        }
        
        collection.insert_one(document)
        # Convert ObjectId to string for JSON serialization
        document['_id'] = str(document['_id'])
        
        print("💾 Manual Data Logged")
        return jsonify({"status": "success", "processed_data": document}), 201

    except Exception as e:
        print(f"❌ API Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """Returns the last 50 readings for charts"""
    try:
        cursor = collection.find().sort("timestamp", -1).limit(50)
        data = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            data.append(doc)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/latest', methods=['GET'])
def get_latest():
    """Returns only the absolute latest reading for real-time status cards"""
    try:
        doc = collection.find_one(sort=[("timestamp", -1)])
        if doc:
            doc['_id'] = str(doc['_id'])
            return jsonify(doc)
        return jsonify({})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Start MQTT in background
mqtt_thread = threading.Thread(target=start_mqtt)
mqtt_thread.daemon = True
mqtt_thread.start()

if __name__ == '__main__':
    print(f"🚀 Backend running. Waiting for processing.exe at: {CPP_EXE}")
    app.run(host='0.0.0.0', port=5000, debug=True)