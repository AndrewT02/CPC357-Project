# Google Cloud Platform (GCP) IoT Integration Guide

This guide walks you through setting up GCP for your Smart Street Lighting System.

## Architecture Overview

```
[Maker Feather S3] --MQTT--> [GCP IoT Core] --> [Pub/Sub] --> [Cloud Functions] --> [BigQuery/Dashboard]
```

---

## Step 1: Create a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" > "New Project"
3. Name it: `smart-streetlight-project`
4. Note your **Project ID** (you'll need this later)

---

## Step 2: Enable Required APIs

In Cloud Console, enable these APIs:

- **Cloud IoT Core API**
- **Cloud Pub/Sub API**

```bash
# Or via gcloud CLI:
gcloud services enable cloudiot.googleapis.com
gcloud services enable pubsub.googleapis.com
```

---

## Step 3: Create a Pub/Sub Topic

```bash
gcloud pubsub topics create streetlight-telemetry
```

Or via Console:

1. Go to **Pub/Sub** > **Topics**
2. Click **Create Topic**
3. Topic ID: `streetlight-telemetry`

---

## Step 4: Create an IoT Core Registry

```bash
gcloud iot registries create streetlight-registry \
    --region=asia-southeast1 \
    --event-notification-config=topic=streetlight-telemetry
```

Or via Console:

1. Go to **IoT Core** > **Registries**
2. Click **Create Registry**
3. Registry ID: `streetlight-registry`
4. Region: `asia-southeast1` (or closest to you)
5. Pub/Sub topic: `streetlight-telemetry`

---

## Step 5: Generate Device Keys

Run this in your terminal to create an ES256 key pair:

```bash
# Generate private key
openssl ecparam -genkey -name prime256v1 -noout -out ec_private.pem

# Generate public key
openssl ec -in ec_private.pem -pubout -out ec_public.pem
```

**Keep `ec_private.pem` secure!** It goes on your device.

---

## Step 6: Register Your Device

```bash
gcloud iot devices create streetlight-001 \
    --region=asia-southeast1 \
    --registry=streetlight-registry \
    --public-key path=ec_public.pem,type=es256
```

---

## Step 7: Update Firmware for GCP

Modify `smart_light.ino` to connect to GCP IoT Core:

```cpp
// GCP IoT Core Configuration
const char* mqtt_server = "mqtt.googleapis.com";
const int mqtt_port = 8883;  // TLS

// Your GCP Project Details
const char* project_id = "smart-streetlight-project";
const char* cloud_region = "asia-southeast1";
const char* registry_id = "streetlight-registry";
const char* device_id = "streetlight-001";

// MQTT Topic for GCP
// Format: /devices/{device-id}/events
String mqtt_topic = String("/devices/") + device_id + "/events";
```

You'll also need to:

1. Add JWT authentication (use a library like `google-cloud-iot-arduino`)
2. Use WiFiClientSecure with GCP's root certificate

---

## Step 8: Verify Data in Pub/Sub

Create a subscription to test:

```bash
gcloud pubsub subscriptions create test-sub --topic=streetlight-telemetry

# Pull messages
gcloud pubsub subscriptions pull test-sub --auto-ack --limit=10
```

---

## Step 9: Store Data in BigQuery (Optional)

1. Create a BigQuery dataset: `streetlight_data`
2. Create a Cloud Function triggered by Pub/Sub
3. Insert data into BigQuery table

---

## Quick Start: Test Without GCP

For now, you can test with the **public MQTT broker** (already configured):

```cpp
const char* mqtt_server = "test.mosquitto.org";
const int mqtt_port = 1883;
```

This works without any cloud setup!

---

## Files to Create for GCP Production

| File             | Purpose                           |
| ---------------- | --------------------------------- |
| `ec_private.pem` | Device private key (keep secure!) |
| `ec_public.pem`  | Registered with GCP               |
| `roots.pem`      | GCP Root CA certificate           |

---

## Useful GCP CLI Commands

```bash
# List devices in registry
gcloud iot devices list --registry=streetlight-registry --region=asia-southeast1

# View device details
gcloud iot devices describe streetlight-001 --registry=streetlight-registry --region=asia-southeast1

# Send command to device
gcloud iot devices commands send --device=streetlight-001 \
    --registry=streetlight-registry \
    --region=asia-southeast1 \
    --command-data='{"brightness_override": 100}'
```
