/*
 * Smart Street Light - Direct Database Version (No GCP)
 * Platform: Cytron Maker Feather AIoT S3 (ESP32-S3)
 * Communication: HTTP POST -> Python Backend -> MongoDB
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// === CONFIGURATION ===
const char* ssid = "Galaxy Note10 Lite2a71";
const char* password = "noob1234"; 

// REPLACE WITH YOUR LAPTOP'S IP ADDRESS (Run 'ipconfig' on Windows)
// e.g., "http://192.168.1.10:5000/data"
const char* serverUrl = "http://10.13.13.145:5000/data"; 

// === PIN CONFIGURATION ===
// Matching user's working Arduino code EXACTLY:
const int PIR_PIN = A3;  // Same as Arduino: pirPin = A3
const int LDR_PIN = 4;   // Same as Arduino: lightPin = 4
const int LED_PIN = 46;  // Built-in LED

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n--- Smart Street Light (Direct HTTP Mode) ---");

  // Initialize Pins
  pinMode(PIR_PIN, INPUT);
  pinMode(LDR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);

  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blink while connecting
  }
  
  Serial.println("\nWiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  digitalWrite(LED_PIN, LOW); // LED ON (Active Low usually) indicates connected
}

void loop() {
  // 1. Read Sensors
  int motionState = digitalRead(PIR_PIN);
  int lightValue = analogRead(LDR_PIN);

  // DEBUG: Print raw sensor values
  Serial.print("RAW -> Motion: ");
  Serial.print(motionState);
  Serial.print(" | Light: ");
  Serial.println(lightValue);

  // 2. Prepare Data JSON
  StaticJsonDocument<200> doc;
  doc["ldr"] = lightValue;
  doc["motion"] = motionState;
  
  // Simulated Power Calculation based on logic
  // If it's dark (high value?) and motion detected -> High Power
  // Adjust logic based on your sensor (0=Dark or 4095=Dark?)
  // Assuming 0=Dark for now based on typical LDR pull-up, but user said "0 = Dark"
  int brightness = 0;
  if (lightValue < 2000) { // Night time
      if (motionState == HIGH) brightness = 100;
      else brightness = 30;
  }
  doc["brightness"] = brightness;
  doc["power"] = (brightness * 10.0) / 100.0; 

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  // 3. Send via HTTP POST
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    Serial.print("Sending Data: ");
    Serial.println(jsonPayload);

    int httpResponseCode = http.POST(jsonPayload);

    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.print("Server Response: ");
      Serial.println(httpResponseCode); // Should be 201
    } else {
      Serial.print("Error on sending POST: ");
      Serial.println(httpResponseCode);
    }
    http.end();
  } else {
    Serial.println("WiFi Disconnected");
  }

  // 4. Wait before next reading
  delay(2000); 
}
