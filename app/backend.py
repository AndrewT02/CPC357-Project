import os
import json
import datetime
import threading
import subprocess
import platform
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    MONGO_URI = os.environ.get("MONGO_URI")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "smartcity/streetlight/+/data")

TRADITIONAL_LIGHT_POWER_W = 100.0
MAX_SMART_LIGHT_POWER_W = 20.0

# --- SETUP APP ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# --- DATABASE ---
try:
    client = MongoClient(MONGO_URI)
    db = client['smart_city_db']
    collection = db['sensor_logs']
    print("✅ Connected to MongoDB Atlas!")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")

# --- LOCK FOR C++ EXECUTABLE (Concurrency Fix) ---
cpp_lock = threading.Lock()

# --- CORE LOGIC (Unified) ---
def process_data(device_id, raw_ldr, motion, power, source):
    """
    Unified logic channel. Used by both HTTP (Manual) and MQTT (Live).
    1. Caller invokes this function.
    2. Data is passed to C++ Executable (Safe Lock).
    3. Result is saved to DB.
    4. Result is emitted to WebSockets.
    """
    try:
        # Determine executable path based on OS
        binary_name = "processing.exe" if platform.system() == "Windows" else "./processing"
        exe_path = os.path.join(os.path.dirname(__file__), binary_name)
        
        # 1. PROCESS VIA C++
        # Usage: ./processing process <device_id> <ldr> <motion> <power>
        with cpp_lock:
            result = subprocess.run(
                [exe_path, "process", str(device_id), str(raw_ldr), str(motion), str(power)],
                capture_output=True,
                text=True,
                check=True
            )
        
        # Parse Output
        # Expected: {"smooth_ldr": ..., "is_night": ..., "brightness": ..., "traffic_intensity": ..., "anomaly": ...}
        processed = json.loads(result.stdout)
        
        # 2. PREPARE DB DOCUMENT
        document = {
            "timestamp": datetime.datetime.utcnow(),
            "device_id": device_id,
            "ldr_raw": raw_ldr,
            "ldr_smooth": processed.get('smooth_ldr', raw_ldr),
            "motion": motion,
            "brightness": processed.get('brightness', 0),
            "power": power,
            "is_night": bool(processed.get('is_night', 0)),
            "traffic_intensity": round(processed.get('traffic_intensity', 0.0), 1), # From C++ now!
            "anomaly": processed.get('anomaly', 0),
            "source": source
        }
        
        # 3. SAVE TO DB
        collection.insert_one(document)
        # Convert ObjectId
        doc_json = document.copy()
        doc_json['_id'] = str(doc_json['_id'])

        # 4. EMIT REAL-TIME UPDATE (WebSockets)
        socketio.emit('update', doc_json) 
        
        return doc_json

    except FileNotFoundError:
        print("❌ Error: 'processing.exe' not found.")
        return None
    except Exception as e:
        print(f"❌ Processing Error: {e}")
        return None

# --- MQTT CLIENT (Background Thread) ---
def on_mqtt_connect(client, userdata, flags, rc):
    print(f"✅ MQTT Connected (rc={rc})")
    client.subscribe(MQTT_TOPIC)

def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        topic_parts = msg.topic.split('/')
        device_id = topic_parts[2] if len(topic_parts) > 2 else 'unknown'
        
        # Extract inputs
        ldr = int(payload.get('ldr', 0))
        motion = int(payload.get('motion', 0))
        power = float(payload.get('power', 0.0))
        
        # UNIFIED PROCESSING CALL
        process_data(device_id, ldr, motion, power, source="gcp_vm_mqtt")
        
        print(f"📥 Processed MQTT from {device_id}")
        
    except Exception as e:
        print(f"❌ MQTT Message Error: {e}")

def start_mqtt():
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start() # Run in background thread
        print("🚀 MQTT Listener Started")
    except Exception as e:
        print(f"⚠️ MQTT Connection Failed: {e}")

# --- API ENDPOINTS ---

@app.route('/api/manual', methods=['POST'])
def manual_data():
    """Manual Injection Endpoint (Test/Demo)"""
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400
    
    ldr = int(data.get('ldr', 0))
    motion = int(data.get('motion', 0))
    power = float(data.get('power', 0.0))
    
    result = process_data("http_manual", ldr, motion, power, source="http_app")
    
    if result:
        return jsonify({"status": "success", "data": result}), 201
    return jsonify({"error": "Processing failed"}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """Historical Data for Charts"""
    try:
        # Filter to only main source
        cursor = collection.find({"source": "gcp_vm_mqtt"}).sort("timestamp", -1).limit(50)
        return jsonify([ {**doc, '_id': str(doc['_id'])} for doc in cursor ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status_card():
    # Only return the VERY latest reading regardless of history
    latest = collection.find_one({"source": "gcp_vm_mqtt"}, sort=[("timestamp", -1)])
    if not latest: return jsonify({})
    
    b = latest.get('brightness', 0)
    mode = "OFF" if b == 0 else (f"ECO ({b}%)" if b < 50 else f"ACTIVE ({b}%)")
    
    # Calculate last motion time
    last_motion = collection.find_one({"source": "gcp_vm_mqtt", "motion": 1}, sort=[("timestamp", -1)])
    last_motion_str = "Unknown"
    if last_motion:
        delta = datetime.datetime.utcnow() - last_motion['timestamp']
        last_motion_str = f"{int(delta.total_seconds() / 60)} mins ago"

    return jsonify({
        "mode": mode,
        "last_motion": last_motion_str,
        "is_night": latest.get('is_night', False), # Now boolean from DB
        "power": latest.get('power', 0)
    })
    
# Analytics Endpoints (Energy, Traffic, Modes) - Kept same logic
@app.route('/api/analytics/energy', methods=['GET'])
def get_energy_analytics():
    # Efficiency logic...
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    logs = list(collection.find({"source": "gcp_vm_mqtt", "timestamp": {"$gte": cutoff}}))
    if not logs: return jsonify({"efficiency_score": 0, "smart_avg_w": 0, "traditional_w": TRADITIONAL_LIGHT_POWER_W})
    
    avg_smart = sum(l.get('power',0) for l in logs) / len(logs)
    saved = TRADITIONAL_LIGHT_POWER_W - avg_smart
    score = (saved / TRADITIONAL_LIGHT_POWER_W) * 100
    
    return jsonify({"efficiency_score": round(score, 1), "smart_avg_w": round(avg_smart, 1), "traditional_w": TRADITIONAL_LIGHT_POWER_W})

@app.route('/api/analytics/traffic', methods=['GET'])
def get_traffic_analytics():
    pipeline = [
        {"$match": {"source": "gcp_vm_mqtt", "motion": 1, "timestamp": {"$gte": datetime.datetime.utcnow() - datetime.timedelta(days=7)}}},
        {"$group": {"_id": {"$hour": "$timestamp"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    result = list(collection.aggregate(pipeline))
    hourly = {i: 0 for i in range(24)}
    for r in result: hourly[r['_id']] = r['count']
    return jsonify([{"hour": f"{h}:00", "count": c} for h, c in hourly.items()])

@app.route('/api/analytics/modes', methods=['GET'])
def get_mode_analytics():
    pipeline = [
        {"$match": {"source": "gcp_vm_mqtt", "timestamp": {"$gte": datetime.datetime.utcnow() - datetime.timedelta(days=7)}}},
        {"$project": {"status": {"$switch": {"branches": [{"case": {"$eq": ["$brightness", 0]}, "then": "OFF"}, {"case": {"$lt": ["$brightness", 50]}, "then": "ECO"}], "default": "ACTIVE"}}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify([{"name": r["_id"], "value": r["count"]} for r in result])

# --- MAIN ---
if __name__ == '__main__':
    print(f"🚀 Unified Backend Starting...")
    start_mqtt()
    # Use socketio.run instead of app.run
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)