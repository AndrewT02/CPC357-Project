# Smart Adaptive Street Lighting System

A smart city IoT solution for energy-efficient street lighting using adaptive brightness control and traffic analytics.

The project integrates an IoT node (ESP32), a Python/Flask backend, and a React frontend to provide real-time monitoring, intelligent control, and data analytics.

## Specifications

### IoT Hardware

- **Main Microcontroller:** Cytron Maker Feather AIoT S3 (ESP32-S3)
- **Communications:** WiFi & MQTT (GCP)
- **Sensors:**
  - LDR (Light Dependent Resistor) - for ambient light detection
  - PIR Motion Sensor - for traffic/pedestrian detection
- **Actuators:**
  - LED / MOSFET Driver (PWM Control)

### UI & Software

- **Communication Protocol:** MQTT (GCP VM Mosquitto Broker) & HTTP (Local)
- **Backend:** Python Flask with Socket.IO for real-time updates
- **Database:** MongoDB Atlas (Cloud Storage)
- **Frontend:** React.js + Vite + Tailwind CSS (Dashboard & Analytics)
- **Data Processing:** Python-based Sliding Window & Hysteresis algorithms

## Setup

### Prerequisites

- **PlatformIO (VS Code Extension):**
  - Project configured with `platformio.ini` for automatic library management.
- **Backend Server:**
  - Python 3.9+
  - MongoDB Atlas Connection String
  - Google Cloud Platform (GCP) VM with Mosquitto Broker
- **Frontend Client:**
  - Node.js & npm

### Environment Variables

**Server (`app/.env`)**

```env
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MQTT_BROKER=<GCP_VM_IP>
MQTT_PORT=1883
MQTT_TOPIC=smartcity/streetlight/+/data
```

**Firmware (`firmware/src/secrets.h`)**

```cpp
#define WIFI_SSID "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"
#define MQTT_SERVER_IP "your_gcp_vm_ip"
```

## Development

### 1. Firmware (ESP32)

1. Open the `firmware` folder in VS Code with PlatformIO extension installed.
2. The `platformio.ini` file will automatically install necessary dependencies.
3. Update `src/secrets.h` with your WiFi and MQTT credentials.
4. Verify Pin Configuration in `src/main.cpp`:
   - PIR_PIN: A2
   - LDR_PIN: 4
   - MOSFET/LED_PIN: 14/46
5. Click **PlatformIO: Upload** to flash the code to the ESP32 board.

### 2. Backend (Python/Flask)

Navigate to the `app` directory:

```bash
cd app
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r ../requirements.txt
python backend.py
```

_The server runs on `http://localhost:5000`_

### 3. Frontend (React)

Navigate to the `app/frontend` directory:

```bash
cd app/frontend
npm install
npm run dev
```

_The web app runs on `http://localhost:5173`_

### 4. Verify on GCP (MQTT Broker)

To manually verify that the GCP VM is receiving data from the ESP32, SSH into your VM and run:

```bash
# Subscribe to all streetlight data topics
mosquitto_sub -h <GCP_VM_IP> -t "smartcity/streetlight/+/data" -v
```

You should see JSON payloads arriving every 2 seconds or on motion events.
