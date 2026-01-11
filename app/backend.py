import os
import json
import datetime
import threading
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

# --- PROCESSING CONSTANTS (From C++) ---
WINDOW_SIZE = 10
MOTION_HISTORY_SIZE = 60  # 2-3 mins of history

# --- IN-MEMORY STATE (Replaces C++ State Files) ---
device_states = {}
state_lock = threading.Lock()

def get_device_state(device_id):
    """Get or initialize state for a device."""
    with state_lock:
        if device_id not in device_states:
            device_states[device_id] = {
                'ldr_readings': [0] * WINDOW_SIZE,
                'ldr_index': 0,
                'ldr_sum': 0,
                'is_night': False,
                'motion_history': [0] * MOTION_HISTORY_SIZE,
                'motion_index': 0,
                'motion_sum': 0
            }
        return device_states[device_id]

def process_sensor_data(device_id, raw_ldr, motion, power):
    """
    Python implementation of the C++ processing logic.
    Sliding window smoothing, hysteresis, traffic analytics.
    """
    state = get_device_state(device_id)
    
    with state_lock:
        # 1. Sliding Window (LDR) - for smoothing digital readings
        state['ldr_sum'] -= state['ldr_readings'][state['ldr_index']]
        state['ldr_readings'][state['ldr_index']] = raw_ldr
        state['ldr_sum'] += raw_ldr
        state['ldr_index'] = (state['ldr_index'] + 1) % WINDOW_SIZE
        smooth_ldr = state['ldr_sum']  # Sum of 10 readings (0-10 for digital sensor)
        
        # 2. Night Detection for DIGITAL LDR (0=day, 1=night)
        # If more than half the readings are "night" (1), consider it night
        if smooth_ldr > (WINDOW_SIZE // 2):
            state['is_night'] = True
        elif smooth_ldr < (WINDOW_SIZE // 2):
            state['is_night'] = False
        # If exactly half, maintain previous state (hysteresis)
        
        is_night = state['is_night']
        
        # 3. Traffic Analytics (Motion Intensity)
        state['motion_sum'] -= state['motion_history'][state['motion_index']]
        state['motion_history'][state['motion_index']] = motion
        state['motion_sum'] += motion
        state['motion_index'] = (state['motion_index'] + 1) % MOTION_HISTORY_SIZE
        
        traffic_intensity = (state['motion_sum'] / MOTION_HISTORY_SIZE) * 100.0
        
        # 4. Logic (Target Brightness)
        target_brightness = 0
        if is_night:
            target_brightness = 100 if motion > 0 else 30
        
        # 5. Anomaly Detection
        anomaly = 0
        # If target is High but Power is Low -> Blown Bulb
        if target_brightness > 10 and power < 0.1:
            anomaly = 1
        # If target is Off but Power is High -> Leakage
        if target_brightness == 0 and power > 1.0:
            anomaly = 2
    
    return {
        'smooth_ldr': smooth_ldr,
        'is_night': is_night,
        'brightness': target_brightness,
        'traffic_intensity': round(traffic_intensity, 1),
        'anomaly': anomaly
    }

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

# --- CORE LOGIC (Unified, Python-Only) ---
def process_data(device_id, raw_ldr, motion, power, source):
    """
    Unified logic channel. Used by both HTTP (Manual) and MQTT (Live).
    1. Caller invokes this function.
    2. Data is processed in Python (no C++ dependency).
    3. Result is saved to DB.
    4. Result is emitted to WebSockets.
    """
    try:
        # 1. PROCESS VIA PYTHON
        processed = process_sensor_data(device_id, raw_ldr, motion, power)
        
        # 2. PREPARE DB DOCUMENT (field names match frontend expectations)
        document = {
            "timestamp": datetime.datetime.utcnow(),
            "device_id": device_id,
            "ldr": raw_ldr,  # Frontend expects 'ldr'
            "smooth_ldr": processed['smooth_ldr'],  # Frontend expects 'smooth_ldr'
            "motion": motion,
            "brightness": processed['brightness'],
            "power": power,
            "is_night": processed['is_night'],
            "traffic_intensity": processed['traffic_intensity'],
            "anomaly": processed['anomaly'],
            "source": source
        }
        
        # 3. SAVE TO DB
        collection.insert_one(document)
        # Convert ObjectId
        doc_json = document.copy()
        doc_json['_id'] = str(doc_json['_id'])
        doc_json['timestamp'] = document['timestamp'].isoformat()

        # 4. EMIT REAL-TIME UPDATE (WebSockets)
        print(f"📡 Emitting WebSocket update: brightness={document.get('brightness')}, is_night={document.get('is_night')}")
        socketio.emit('update', doc_json) 
        
        return doc_json

    except Exception as e:
        print(f"❌ Processing Error: {e}")
        return None

# --- MQTT CLIENT (Background Thread) ---
def on_mqtt_connect(client, userdata, flags, rc, properties=None):
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
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    
    try:
        print(f"🔌 Connecting to MQTT Broker: {MQTT_BROKER}:{MQTT_PORT} (Topic: {MQTT_TOPIC})")
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

@app.route('/api/latest', methods=['GET'])
def get_latest():
    """Get the latest reading - used by frontend Dashboard"""
    try:
        latest = collection.find_one({"source": "gcp_vm_mqtt"}, sort=[("timestamp", -1)])
        if not latest:
            # Return empty defaults if no data
            return jsonify({
                "brightness": 0,
                "smooth_ldr": 0,
                "ldr": 0,
                "motion": 0,
                "power": 0,
                "is_night": False,
                "anomaly": 0
            })
        
        # Convert ObjectId and timestamp for JSON
        latest['_id'] = str(latest['_id'])
        if 'timestamp' in latest:
            latest['timestamp'] = latest['timestamp'].isoformat()
        
        return jsonify(latest)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """Historical Data for Charts"""
    try:
        # Filter to only main source
        cursor = collection.find({"source": "gcp_vm_mqtt"}).sort("timestamp", -1).limit(50)
        results = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            if 'timestamp' in doc:
                doc['timestamp'] = doc['timestamp'].isoformat()
            results.append(doc)
        return jsonify(results)
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
        "is_night": latest.get('is_night', False),
        "power": latest.get('power', 0)
    })
    
# Analytics Endpoints (Energy, Traffic, Modes)
@app.route('/api/analytics/energy', methods=['GET'])
def get_energy_analytics():
    """
    Energy Savings Calculation using Normalized Formulas:
    
    E_baseline = P_full × T_night (where P_full = 1.0)
    T_night = T_full + T_dim + T_off (total night readings)
    E_adaptive = T_full + α × T_dim (where α = 0.3 for ECO mode)
    Energy Saved (%) = ((E_baseline - E_adaptive) / E_baseline) × 100
    """
    ALPHA = 0.3  # Dimming factor for ECO mode (30% brightness)
    
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    logs = list(collection.find({"source": "gcp_vm_mqtt", "timestamp": {"$gte": cutoff}}))
    
    if not logs:
        return jsonify({
            "energy_saved_percent": 0,
            "t_full": 0,
            "t_dim": 0,
            "t_off": 0,
            "t_night": 0,
            "e_baseline": 0,
            "e_adaptive": 0,
            "formula_breakdown": "No data available"
        })
    
    # Count readings in each mode based on brightness
    t_full = 0  # Brightness = 100% (FULL mode)
    t_dim = 0   # Brightness = 30% (ECO mode)
    t_off = 0   # Brightness = 0% (OFF mode, daytime)
    
    for log in logs:
        brightness = log.get('brightness', 0)
        if brightness == 0:
            t_off += 1
        elif brightness < 50:
            t_dim += 1  # ECO mode (30%)
        else:
            t_full += 1  # FULL mode (100%)
    
    # Calculate using the formulas
    # T_night = total night operation time (only when light is ON)
    t_night = t_full + t_dim
    
    if t_night == 0:
        # All readings are during daytime (OFF), no night operation
        return jsonify({
            "energy_saved_percent": 100.0,
            "t_full": t_full,
            "t_dim": t_dim,
            "t_off": t_off,
            "t_night": t_night,
            "e_baseline": 0,
            "e_adaptive": 0,
            "formula_breakdown": "System is OFF during monitoring period"
        })
    
    # E_baseline = P_full × T_night (with P_full = 1.0)
    e_baseline = 1.0 * t_night  # = t_night
    
    # E_adaptive = (P_full × T_full) + (α × P_full × T_dim)
    # Simplified: E_adaptive = T_full + α × T_dim
    e_adaptive = t_full + (ALPHA * t_dim)
    
    # Energy Saved (%) = ((E_baseline - E_adaptive) / E_baseline) × 100
    energy_saved_percent = ((e_baseline - e_adaptive) / e_baseline) * 100
    
    # Create formula breakdown string for display
    formula_breakdown = f"E_baseline = {t_night} | E_adaptive = {t_full} + (0.3 × {t_dim}) = {e_adaptive:.1f}"
    
    return jsonify({
        "energy_saved_percent": round(energy_saved_percent, 1),
        "t_full": t_full,
        "t_dim": t_dim,
        "t_off": t_off,
        "t_night": t_night,
        "e_baseline": round(e_baseline, 2),
        "e_adaptive": round(e_adaptive, 2),
        "formula_breakdown": formula_breakdown
    })

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
    print(f"🚀 Backend Starting (Python Processing - No C++ Required)...")
    start_mqtt()
    # Use socketio.run instead of app.run
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)