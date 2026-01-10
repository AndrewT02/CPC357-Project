import os
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
CORS(app) # Enable CORS for React Frontend

# --- CONSTANTS ---
TRADITIONAL_LIGHT_POWER_W = 100.0  # Watts (for comparison)
MAX_SMART_LIGHT_POWER_W = 20.0     # Watts (LED at 100%)

# --- CONFIGURATION ---
# Uses environment variables for security, with fallback for development
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://teeandrew86_db_user:V7nnJejzgK28PXxx@project1.s2ihw2y.mongodb.net/?appName=Project1")

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

# --- API ENDPOINTS (For React Frontend) ---


def manual_data():
    """Manual data injection for testing without hardware (Optional - Keep for debugging)"""
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

        # --- NEW: Traffic Analytics (Python Layer) ---
        # We add this layer on top of C++ to match the Cloud VM features
        global motion_history
        if 'motion_history' not in globals(): motion_history = []
        
        motion_history.append(motion)
        if len(motion_history) > 60: # Keep last ~2-3 mins
            motion_history.pop(0)
            
        traffic_intensity = (sum(motion_history) / len(motion_history)) * 100

        # 3. Save to MongoDB
        document = {
            "timestamp": datetime.datetime.utcnow(),
            "device_id": "http_local",
            "ldr_raw": raw_ldr,
            "ldr_smooth": final_smooth_ldr,
            "motion": motion,
            "brightness": final_brightness,
            "power": reported_power,
            "is_night": bool(is_night),
            "traffic_intensity": round(traffic_intensity, 1), # Added Feature
            "anomaly": final_anomaly,
            "source": "http_local" # Explicit source for local backend
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
    """Returns the last 50 readings from MQTT (GCP VM) for charts"""
    try:
        # Filter to only show MQTT data from GCP VM
        cursor = collection.find({"source": "gcp_vm_mqtt"}).sort("timestamp", -1).limit(50)
        data = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            data.append(doc)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/latest', methods=['GET'])
def get_latest():
    """Returns only the absolute latest MQTT reading for real-time status cards"""
    try:
        # Filter to only show MQTT data from GCP VM
        doc = collection.find_one({"source": "gcp_vm_mqtt"}, sort=[("timestamp", -1)])
        if doc:
            doc['_id'] = str(doc['_id'])
            return jsonify(doc)
        return jsonify({})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ANALYTICS ENDPOINTS ---

@app.route('/api/analytics/energy', methods=['GET'])
def get_energy_analytics():
    """
    Returns energy efficiency comparison since start of data or last 24h.
    Goal: "65% Reduction in Energy Waste"
    """
    # 1. Get all logs (or last 7 days to be faster)
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    logs = list(collection.find({"source": "gcp_vm_mqtt", "timestamp": {"$gte": cutoff}}))
    
    if not logs:
        return jsonify({"efficiency_score": 0, "saved_kwh": 0, "message": "No data"})

    count = len(logs)
    avg_smart_power = sum(log.get('power', 0) for log in logs) / count
    avg_traditional_power = TRADITIONAL_LIGHT_POWER_W 
    
    # Efficiency Score = (Saved / Traditional) * 100
    saved = avg_traditional_power - avg_smart_power
    efficiency_score = (saved / avg_traditional_power) * 100
    
    return jsonify({
        "efficiency_score": round(efficiency_score, 1),
        "smart_avg_w": round(avg_smart_power, 1),
        "traditional_w": TRADITIONAL_LIGHT_POWER_W
    })

@app.route('/api/analytics/traffic', methods=['GET'])
def get_traffic_analytics():
    """Returns motion counts grouped by Hour of Day."""
    pipeline = [
        {"$match": {"source": "gcp_vm_mqtt", "motion": 1, "timestamp": {"$gte": datetime.datetime.utcnow() - datetime.timedelta(days=7)}}},
        {"$group": {"_id": {"$hour": "$timestamp"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    result = list(collection.aggregate(pipeline))
    hourly_data = {i: 0 for i in range(24)}
    for r in result: hourly_data[r['_id']] = r['count']
    return jsonify([{"hour": f"{h}:00", "count": c} for h, c in hourly_data.items()])

@app.route('/api/analytics/modes', methods=['GET'])
def get_mode_analytics():
    """Returns distribution of states: OFF, ECO, ACTIVE."""
    pipeline = [
        {"$match": {"source": "gcp_vm_mqtt", "timestamp": {"$gte": datetime.datetime.utcnow() - datetime.timedelta(days=7)}}},
        {"$project": {"status": {"$switch": {"branches": [{"case": {"$eq": ["$brightness", 0]}, "then": "OFF"}, {"case": {"$lt": ["$brightness", 50]}, "then": "ECO"}], "default": "ACTIVE"}}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    result = list(collection.aggregate(pipeline))
    return jsonify([{"name": r["_id"], "value": r["count"]} for r in result])

@app.route('/api/status', methods=['GET'])
def get_status_card():
    """Returns real-time status for the header cards."""
    latest = collection.find_one({"source": "gcp_vm_mqtt"}, sort=[("timestamp", -1)])
    if not latest: return jsonify({})
    b = latest.get('brightness', 0)
    mode = "OFF" if b == 0 else (f"ECO ({b}%)" if b < 50 else f"ACTIVE ({b}%)")
    
    last_motion = collection.find_one({"source": "gcp_vm_mqtt", "motion": 1}, sort=[("timestamp", -1)])
    last_motion_str = "Unknown"
    if last_motion:
        delta = datetime.datetime.utcnow() - last_motion['timestamp']
        last_motion_str = f"{int(delta.total_seconds() / 60)} mins ago"

    return jsonify({
        "mode": mode,
        "last_motion": last_motion_str,
        "is_night": latest.get('ldr', 0) > 800,
        "power": latest.get('power', 0)
    })


if __name__ == '__main__':
    print(f"🚀 Backend API running. Reading from Cloud DB...")
    app.run(host='0.0.0.0', port=5000, debug=True)