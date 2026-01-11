/*
 * Smart Street Light - NON-BLOCKING VERSION
 * Platform: Cytron Maker Feather AIoT S3
 * 
 * Logic:
 * - LDR: Reads every 100ms (Smoothed).
 * - PIR: Retriggerable 30s timer.
 * - PWM: 100% Brightness on Motion, 30% on Standby (Night only).
 * - Connectivity: WiFi, MQTT (GCP), HTTP (Local).
 * - NETWORK FIX: Reconnects only every 5s to prevent freezing existing logic.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "secrets.h"

// === WI-FI CONFIGURATION ===
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD; 


// === LOCAL HTTP CONFIGURATION ===
const char* serverUrl = "http://10.174.2.145:5000/data"; 

// === MQTT CONFIGURATION (GCP VM) ===
const char* mqtt_server = MQTT_SERVER_IP;

const int mqtt_port = 1883;
const char* mqtt_topic = "smartcity/streetlight/1/data";
const char* device_id = "streetlight-001";

// === PIN CONFIGURATION ===
const int PIR_PIN = A2;     
const int MOSFET_PIN = 14; 
const int LDR_PIN = 4;      
const int LED_PIN = 46;     

// === PWM CONFIGURATION ===
const int PWM_CHANNEL = 0;
const int PWM_FREQ = 5000;    
const int PWM_RESOLUTION = 8; 

// === TIMING CONSTANTS ===
const unsigned long LIGHT_TIMER_MS = 30000;   // 30 seconds light duration
const unsigned long REPORT_INTERVAL_MS = 5000;
const unsigned long RECONNECT_INTERVAL_MS = 5000; // Try reconnecting every 5s
const float MAX_LED_POWER_W = 20.0; // Maximum power consumption of LED strip at 100%

// === STATE VARIABLES ===
unsigned long lastMotionSeenTime = 0;  
unsigned long lastReportTime = 0;
unsigned long lastLdrTime = 0;
unsigned long lastReconnectAttempt = 0; // For non-blocking MQTT

bool isNightMode = false;
volatile bool motionDetectedFlag = false; // Volatile for ISR 

// Sliding Window for LDR
const int WINDOW_SIZE = 10;
int ldrReadings[WINDOW_SIZE];
int ldrIndex = 0;
long ldrSum = 0;

// State tracking for event-driven reporting
bool lastSentMotionState = false;
bool lastSentNightMode = false;

// Forward declaration for helper function
void sendTelemetry(bool isNightMode, bool isMotionActive, int pwmValue, int ldrValue, long countdownSec);

// === PIR Interrupt Handler ===
void IRAM_ATTR onMotionDetected() {
    motionDetectedFlag = true;
}

// === Clients ===
WiFiClient espClient;
PubSubClient mqttClient(espClient);

void reconnectMQTT() {
  if (mqttClient.connected()) return; // Already connected

  unsigned long now = millis();
  if (now - lastReconnectAttempt > RECONNECT_INTERVAL_MS) {
    lastReconnectAttempt = now;
    
    Serial.print("Attempting MQTT connection... ");
    // Attempt to connect
    if (mqttClient.connect(device_id)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.println(mqttClient.state());
      Serial.println(" (retrying in 5 seconds)");
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000); 

  Serial.println("\n--- Smart Street Light (Non-Blocking) ---");

  pinMode(PIR_PIN, INPUT_PULLDOWN); 
  pinMode(LDR_PIN, INPUT); 
  pinMode(LED_PIN, OUTPUT);
  
  // === PIR INTERRUPT SETUP ===
  attachInterrupt(digitalPinToInterrupt(PIR_PIN), onMotionDetected, RISING);
  
  // === PWM SETUP ===
  #ifdef ESP_ARDUINO_VERSION_MAJOR
    #if ESP_ARDUINO_VERSION_MAJOR >= 3
      ledcAttach(MOSFET_PIN, PWM_FREQ, PWM_RESOLUTION);
    #else
      ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
      ledcAttachPin(MOSFET_PIN, PWM_CHANNEL);
    #endif
  #else
    ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
    ledcAttachPin(MOSFET_PIN, PWM_CHANNEL);
  #endif
  
  // Initialize LDR buffer
  for(int i=0; i<WINDOW_SIZE; i++) ldrReadings[i] = 0;

  // === WiFi Setup ===
  Serial.print("Connecting to WiFi: ");
  WiFi.begin(ssid, password);
  // Initial blocking wait for WiFi is okay in setup, but if it fails we continue
  int wifi_timeout = 20; 
  while (WiFi.status() != WL_CONNECTED && wifi_timeout > 0) {
    delay(500);
    Serial.print(".");
    wifi_timeout--;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nWiFi Connected!");
  } else {
      Serial.println("\nWiFi Not Connected (will try in background)");
  }

  // === MQTT Setup ===
  mqttClient.setServer(mqtt_server, mqtt_port);
}

void loop() {
  unsigned long now = millis();

  // === NETWORKING ===
  // Only handle network if WiFi is connected, otherwise ESP usually auto-reconnects in background
  if (WiFi.status() == WL_CONNECTED) {
      reconnectMQTT(); // Non-blocking check
      if (mqttClient.connected()) {
          mqttClient.loop();
      }
  }

  // === 1. LDR READING ===
  // Option A: Simple instant logic (currently active)
  // Digital output: 1=dark (night), 0=bright (day)
  static int smoothedLdr = 0;
  
  int rawLdr = digitalRead(LDR_PIN);
  smoothedLdr = rawLdr; // Store for telemetry
  isNightMode = (rawLdr == 1); // Instant reaction: 1=night, 0=day
  
  // --- Option B: HYSTERESIS (Commented - uncomment to use instead of Option A) ---
  // Prevents flickering at sunrise/sunset by requiring multiple consistent readings
  /*
  static int smoothedLdr = 0;
  if (now - lastLdrTime > 100) {
      lastLdrTime = now;
      
      int rawLdr = digitalRead(LDR_PIN);
      
      ldrSum -= ldrReadings[ldrIndex];
      ldrReadings[ldrIndex] = rawLdr;
      ldrSum += rawLdr;
      ldrIndex = (ldrIndex + 1) % WINDOW_SIZE;
      
      smoothedLdr = ldrSum; // Sum of 10 readings (0-10)
      
      // Hysteresis thresholds: Night when >7/10 dark, Day when <3/10 dark
      if (smoothedLdr > (WINDOW_SIZE / 2 + 2)) {
          isNightMode = true;
      } else if (smoothedLdr < (WINDOW_SIZE / 2 - 2)) {
          isNightMode = false;
      }
      // Between 3-7: maintain previous state (no change)
  }
  */

  // === 2. MOTION LOGIC (Interrupt + Retriggerable Timer) ===
  // Check interrupt flag (set by ISR)
  if (motionDetectedFlag) {
      motionDetectedFlag = false; // Clear flag
      lastMotionSeenTime = now;
  }
  
  bool isMotionActive = isNightMode && (now - lastMotionSeenTime < LIGHT_TIMER_MS);

  // === 3. CONTROL LOGIC ===
  // YES, this is affected by ANY delay in the loop. 
  // By making reconnectMQTT non-blocking, we ensure this runs thousands of times per second.
  int pwmValue = 0;

  if (isNightMode) {
      if (isMotionActive) {
         pwmValue = 255; 
         digitalWrite(LED_PIN, HIGH);
      } else {
         pwmValue = 77; 
         digitalWrite(LED_PIN, LOW);
      }
  } else {
      pwmValue = 0;     
      digitalWrite(LED_PIN, LOW);
  }
  
  #ifdef ESP_ARDUINO_VERSION_MAJOR
    #if ESP_ARDUINO_VERSION_MAJOR >= 3
      ledcWrite(MOSFET_PIN, pwmValue);
    #else
      ledcWrite(PWM_CHANNEL, pwmValue);
    #endif
  #else
     ledcWrite(PWM_CHANNEL, pwmValue);
  #endif

  // === 4. EVENT-DRIVEN REPORTING (Runs every loop!) ===
  // Calculate countdown (only valid when motion is active)
  long countdown = isMotionActive ? (LIGHT_TIMER_MS - (now - lastMotionSeenTime)) / 1000 : 0;
  
  bool stateChanged = (isMotionActive != lastSentMotionState) || (isNightMode != lastSentNightMode);
  if (stateChanged) {
      Serial.println(">>> STATE CHANGE DETECTED! Sending immediately...");
      sendTelemetry(isNightMode, isMotionActive, pwmValue, smoothedLdr, countdown);
      lastSentMotionState = isMotionActive;
      lastSentNightMode = isNightMode;
      lastReportTime = now; // Reset heartbeat timer
  }

  // === 5. PERIODIC HEARTBEAT (Every 2s) ===
  if (now - lastReportTime > REPORT_INTERVAL_MS) {
    lastReportTime = now;
    sendTelemetry(isNightMode, isMotionActive, pwmValue, smoothedLdr, countdown);
    lastSentMotionState = isMotionActive;
    lastSentNightMode = isNightMode;
  }
}

// === HELPER: Send telemetry data ===
void sendTelemetry(bool isNight, bool isMotion, int pwm, int ldrValue, long countdownSec) {
    // Calculate actual power from PWM duty cycle
    float power = (pwm / 255.0) * MAX_LED_POWER_W;
    
    // Serial Reporting
    Serial.print("M: "); Serial.print(isNight ? "NIGHT" : "DAY");
    Serial.print(" | Motion: "); Serial.print(isMotion ? "ACTIVE" : "idle");
    Serial.print(" | LDR: "); Serial.print(ldrValue);
    Serial.print(" | PWM: "); Serial.print(pwm);
    Serial.print(" | Power: "); Serial.print(power, 1); Serial.print("W");
    
    // Show countdown if motion is active
    if (isMotion && countdownSec > 0) {
        Serial.print(" | Off in: "); Serial.print(countdownSec); Serial.println("s");
    } else {
        Serial.println("");
    }
    
    // Prepare JSON
    StaticJsonDocument<200> doc;
    doc["ldr"] = ldrValue; 
    doc["motion"] = isMotion ? 1 : 0;
    doc["brightness"] = (pwm * 100) / 255;
    doc["power"] = power; 

    String jsonPayload;
    serializeJson(doc, jsonPayload);

    // Send to MQTT only (HTTP removed to prevent blocking lag)
    if (mqttClient.connected()) {
      mqttClient.publish(mqtt_topic, jsonPayload.c_str());
    }
}