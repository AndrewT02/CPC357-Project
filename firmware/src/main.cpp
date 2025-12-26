/*
 * Smart Adaptive Street Lighting System - Controller Firmware
 * Platform: Cytron Maker Feather AIoT S3 (ESP32-S3)
 * Language: C++ (PlatformIO)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

// === MAKER FEATHER S3 PIN DEFINITIONS ===
// Reference: https://docs.cytron.io/maker-feather-aiot-s3

// Analog Pins (ADC)
const int LDR_PIN = 1;     // A0 on Maker Feather S3 (GPIO1)

// Digital Pins
const int PIR_PIN = 5;     // D5 on Maker Feather S3 (GPIO5)
const int LED_PIN = 46;    // Built-in LED (active low) or use GPIO for external LED

// NeoPixel (Built-in RGB LED on Maker Feather S3)
const int NEOPIXEL_PIN = 38;  // WS2812B NeoPixel on GPIO38
const int NUM_PIXELS = 1;
Adafruit_NeoPixel pixel(NUM_PIXELS, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

// Buzzer (optional feedback)
const int BUZZER_PIN = 2;  // Built-in buzzer on GPIO2

// === WIFI & MQTT CONFIGURATION ===
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Option 1: Public MQTT Broker (for testing)
const char* mqtt_server = "test.mosquitto.org";
const int mqtt_port = 1883;

// Option 2: GCP IoT Core (uncomment for production)
// const char* mqtt_server = "mqtt.googleapis.com";
// const int mqtt_port = 8883;

const char* mqtt_topic_pub = "smartcity/streetlight/1/data";
const char* mqtt_topic_sub = "smartcity/streetlight/1/command";

WiFiClient espClient;
PubSubClient client(espClient);

// === GLOBAL STATE ===
unsigned long lastMsg = 0;
const long MSG_INTERVAL = 2000; // Publish every 2 seconds

bool is_night = false;
int brightness_level = 0;

// === SLIDING WINDOW FILTER ===
const int WINDOW_SIZE = 10;
int ldr_readings[WINDOW_SIZE];
int read_index = 0;
long ldr_sum = 0;

// === HYSTERESIS THRESHOLDS ===
// Adjust these based on your LDR sensor characteristics
const int LDR_THRESHOLD_NIGHT = 2500; // Above this -> Night (12-bit ADC: 0-4095)
const int LDR_THRESHOLD_DAY = 1500;   // Below this -> Day

// === FUNCTION PROTOTYPES ===
void setup_wifi();
void callback(char* topic, byte* payload, unsigned int length);
void reconnect();
int get_smoothed_ldr(int raw_val);
void setStatusLED(uint8_t r, uint8_t g, uint8_t b);
void beep(int duration_ms);

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=================================");
  Serial.println("Smart Street Light - Maker Feather S3");
  Serial.println("=================================");

  // Initialize pins
  pinMode(PIR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  
  // Initialize NeoPixel
  pixel.begin();
  pixel.setBrightness(50);
  setStatusLED(255, 165, 0); // Orange = Initializing
  
  // Initialize Sliding Window
  for (int i = 0; i < WINDOW_SIZE; i++) {
    ldr_readings[i] = 0;
  }

  // Connect to WiFi
  setup_wifi();
  
  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  
  setStatusLED(0, 255, 0); // Green = Ready
  beep(100);
}

void setup_wifi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  setStatusLED(0, 0, 255); // Blue = Connecting
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi Connection Failed! Running in offline mode.");
    setStatusLED(255, 0, 0); // Red = Error
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message received on topic: ");
  Serial.println(topic);
  
  // Parse command JSON
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  
  if (!error) {
    if (doc.containsKey("brightness_override")) {
      brightness_level = doc["brightness_override"];
      Serial.print("Brightness Override: ");
      Serial.println(brightness_level);
    }
  }
}

void reconnect() {
  int retries = 0;
  while (!client.connected() && retries < 3) {
    Serial.print("Attempting MQTT connection...");
    
    String clientId = "MakerFeatherS3-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected!");
      client.subscribe(mqtt_topic_sub);
      setStatusLED(0, 255, 0); // Green = Connected
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 2s...");
      setStatusLED(255, 0, 0); // Red = Error
      delay(2000);
      retries++;
    }
  }
}

// === ALGORITHM: SLIDING WINDOW FILTER ===
int get_smoothed_ldr(int raw_val) {
  ldr_sum -= ldr_readings[read_index];
  ldr_readings[read_index] = raw_val;
  ldr_sum += raw_val;
  read_index = (read_index + 1) % WINDOW_SIZE;
  return ldr_sum / WINDOW_SIZE;
}

// === NEOPIXEL HELPER ===
void setStatusLED(uint8_t r, uint8_t g, uint8_t b) {
  pixel.setPixelColor(0, pixel.Color(r, g, b));
  pixel.show();
}

// === BUZZER HELPER ===
void beep(int duration_ms) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(duration_ms);
  digitalWrite(BUZZER_PIN, LOW);
}

void loop() {
  // Maintain MQTT connection
  if (WiFi.status() == WL_CONNECTED) {
    if (!client.connected()) {
      reconnect();
    }
    client.loop();
  }

  unsigned long now = millis();
  if (now - lastMsg > MSG_INTERVAL) {
    lastMsg = now;

    // 1. READ SENSORS
    int raw_ldr = analogRead(LDR_PIN);  // 12-bit ADC (0-4095)
    int motion = digitalRead(PIR_PIN);  // 1 = Motion detected

    // 2. PROCESS: Sliding Window Filter
    int smooth_ldr = get_smoothed_ldr(raw_ldr);

    // 3. PROCESS: Hysteresis for Day/Night
    if (smooth_ldr > LDR_THRESHOLD_NIGHT) {
      is_night = true;
    } else if (smooth_ldr < LDR_THRESHOLD_DAY) {
      is_night = false;
    }
    // (Values between thresholds keep previous state)

    // 4. LOGIC: Determine Brightness
    if (!is_night) {
      brightness_level = 0;  // Daytime -> OFF
    } else {
      if (motion) {
        brightness_level = 100; // Night + Motion -> FULL
        setStatusLED(0, 255, 255); // Cyan = Motion detected
      } else {
        brightness_level = 30;  // Night + No Motion -> DIM
        setStatusLED(128, 0, 128); // Purple = Night mode
      }
    }

    // 5. ACTUATE: Set LED brightness (PWM)
    int pwm_value = map(brightness_level, 0, 100, 0, 255);
    analogWrite(LED_PIN, pwm_value);

    // 6. CALCULATE: Simulated Power Draw
    float power_w = (brightness_level * 10.0) / 100.0;

    // 7. ANOMALY DETECTION
    int anomaly = 0;
    // In real system: compare expected vs actual current draw

    // 8. PUBLISH TO MQTT
    StaticJsonDocument<256> doc;
    doc["ldr"] = raw_ldr;
    doc["smooth_ldr"] = smooth_ldr;
    doc["motion"] = motion;
    doc["is_night"] = is_night;
    doc["brightness"] = brightness_level;
    doc["power"] = power_w;
    doc["anomaly"] = anomaly;

    String payload;
    serializeJson(doc, payload);

    Serial.print("Publishing: ");
    Serial.println(payload);

    if (client.connected()) {
      client.publish(mqtt_topic_pub, payload.c_str());
    }
  }
}
