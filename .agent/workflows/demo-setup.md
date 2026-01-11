---
description: Set up and run the Smart Adaptive Street Lighting System Demo
---

1. Install Python Dependencies
   // turbo
   cd app
   pip install -r ../requirements.txt

2. GCP Setup Instructions (Manual Action Required)
   echo "=== GCP VM SETUP REQUIRED ==="; echo "1. SSH into your GCP VM."; echo "2. Install Mosquitto: sudo apt install mosquitto mosquitto-clients -y"; echo "3. Start Service: sudo systemctl start mosquitto"; echo "4. Ensure Firewall allows TCP port 1883"; echo "============================="

3. Start the Backend Server (Term 1)
   cd app
   python backend.py

4. Start the Frontend Application (Term 2)
   cd frontend
   npm install
   npm run dev
