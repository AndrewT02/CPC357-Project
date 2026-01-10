# GCP VM MQTT Subscriber (Smart Version)
# Run this on your GCP VM to receive data from ESP32 and save to MongoDB

import json
import datetime
import time
import paho.mqtt.client as mqtt
from pymongo import MongoClient

# === CONFIGURATION ===
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "smartcity/streetlight/+/data"

# MongoDB Credentials
MONGO_URI = "mongodb+srv://teeandrew86_db_user:V7nnJejzgK28PXxx@project1.s2ihw2y.mongodb.net/?appName=Project1"
DB_NAME = "smart_city_db"
COLLECTION_NAME = "sensor_logs"

# === State Management Class ===
class DeviceState:
    def __init__(self):
        self.ldr_window = []
        self.window_size = 10
        self.is_night = False
        
        # Traffic Analytics
        self.motion_history = [] # Stores last 60 readings (approx 2-3 mins depending on send rate)
        self.history_size = 60

    def process(self, raw_ldr, motion):
        # 1. Sliding Window (Noise Filter)
        self.ldr_window.append(raw_ldr)
        if len(self.ldr_window) > self.window_size:
            self.ldr_window.pop(0)
        
        smooth_ldr = sum(self.ldr_window) / len(self.ldr_window)
        
        # 2. Hysteresis (Stability)
        # Thresholds: Night > 800, Day < 600
        if smooth_ldr > 800:
            self.is_night = True
        elif smooth_ldr < 600:
            self.is_night = False
            
        # 3. Traffic Analytics (Activity Intensity)
        self.motion_history.append(motion)
        if len(self.motion_history) > self.history_size:
            self.motion_history.pop(0)
            
        # Calculate Intensity (0-100%)
        # Sum of 1s divided by total samples
        intensity = (sum(self.motion_history) / len(self.motion_history)) * 100
        
        return smooth_ldr, self.is_night, intensity

# Global State Dictionary (Device ID -> DeviceState)
states = {}

# === MongoDB Connection ===
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]
print("✅ Connected to MongoDB Atlas")

# === MQTT Callbacks ===
def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker" if rc == 0 else f"❌ MQTT Failed: {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"📡 Subscribed to: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        print(f"📥 Raw: {data}")
        
        # Extract ID
        device_id = msg.topic.split('/')[2] if len(msg.topic.split('/')) > 2 else 'unknown'
        
        # Get or Create State
        if device_id not in states:
            states[device_id] = DeviceState()
        state = states[device_id]
        
        # Parse Inputs
        raw_ldr = int(data.get('ldr', 0))
        motion = int(data.get('motion', 0))
        power = float(data.get('power', 0.0))
        
        # === RUN SMART ALGORITHMS ===
        smooth_ldr, is_night, traffic_intensity = state.process(raw_ldr, motion)
        
        # Logic for Brightness (Cloud sees what it SHOULD be, validates what IS)
        if is_night:
            target_brightness = 100 if motion == 1 else 30
        else:
            target_brightness = 0
            
        # Anomaly Detection
        expected_power = target_brightness / 100.0 * 5.0
        anomaly = 1 if abs(power - expected_power) > 1.0 else 0

        # Create Enhanced Document
        document = {
            "timestamp": datetime.datetime.utcnow(),
            "device_id": device_id,
            "ldr_raw": raw_ldr,
            "ldr_smooth": int(smooth_ldr),     # ALGO 1: Smoothed
            "motion": motion,
            "brightness": target_brightness,
            "power": power,
            "is_night": bool(is_night),        # ALGO 2: Hysteresis Stable State
            "traffic_intensity": round(traffic_intensity, 1), # ALGO 3: Traffic Analytics
            "anomaly": anomaly,
            "source": "gcp_vm_mqtt"
        }
        
        result = collection.insert_one(document)
        print(f"🧠 Smart Processed: Night={is_night}, Traffic={traffic_intensity}%, Saved={result.inserted_id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

# === Main ===
if __name__ == "__main__":
    print("🚀 Starting Smart MQTT Subscriber...")
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_forever()
