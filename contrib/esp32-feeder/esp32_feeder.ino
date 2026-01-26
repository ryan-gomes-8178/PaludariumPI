// ESP32-C3 WiFi Feeder Firmware
// Matches TerrariumPI ESP32 WiFi feeder driver expectations
// Endpoints:
//   GET  /status -> JSON status
//   POST /feed   -> body JSON {feed_angle, rest_angle, rotate_duration, feed_hold_duration, portion_size}
//   POST /test   -> body JSON {feed_angle, rest_angle, rotate_duration}
// Libraries needed: ESP32Servo, ArduinoJson (install via Library Manager)

#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

// ---------- USER CONFIG ----------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Optional static IP (comment out to use DHCP)
//#define USE_STATIC_IP
#ifdef USE_STATIC_IP
IPAddress local_IP(192, 168, 1, 150);
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);
IPAddress secondaryDNS(1, 1, 1, 1);
#endif

// Hardware pins
const int SERVO_PIN = 5;  // Change if your signal wire uses another GPIO

// Servo defaults (override per request)
const int DEFAULT_FEED_ANGLE = 90;
const int DEFAULT_REST_ANGLE = 0;
const int DEFAULT_ROTATE_MS = 1000;
const int DEFAULT_HOLD_MS = 1500;

// ---------- INTERNAL STATE ----------
WebServer server(80);
Servo feederServo;
unsigned long lastFeedMillis = 0;

// Move servo to angle with small guard
void moveServoTo(int angle, int settleMs) {
  angle = constrain(angle, 0, 180);
  feederServo.write(angle);
  delay(settleMs);
}

// Run feed sequence using provided config
bool runFeed(int feedAngle, int restAngle, int rotateMs, int holdMs) {
  feedAngle = constrain(feedAngle, 0, 180);
  restAngle = constrain(restAngle, 0, 180);
  rotateMs = max(50, rotateMs);
  holdMs = max(50, holdMs);

  moveServoTo(feedAngle, rotateMs);
  delay(holdMs);
  moveServoTo(restAngle, rotateMs);
  feederServo.write(0); // stop pulses
  return true;
}

// Parse JSON body safely
bool parseJsonBody(JsonDocument& doc) {
  if (!server.hasArg("plain")) {
    return false;
  }
  DeserializationError err = deserializeJson(doc, server.arg("plain"));
  return !err;
}

void handleFeed() {
  StaticJsonDocument<512> doc;
  if (!parseJsonBody(doc)) {
    server.send(400, "application/json", "{\"error\":\"invalid json\"}");
    return;
  }

  int feedAngle = doc["feed_angle"] | DEFAULT_FEED_ANGLE;
  int restAngle = doc["rest_angle"] | DEFAULT_REST_ANGLE;
  int rotateMs = doc["rotate_duration"] | DEFAULT_ROTATE_MS;
  int holdMs = doc["feed_hold_duration"] | DEFAULT_HOLD_MS;
  float portion = doc["portion_size"] | 1.0f;

  runFeed(feedAngle, restAngle, rotateMs, holdMs);
  lastFeedMillis = millis();

  StaticJsonDocument<256> resp;
  resp["status"] = "success";
  resp["message"] = "feed complete";
  resp["portion_size"] = portion;
  resp["feed_angle"] = feedAngle;
  resp["rest_angle"] = restAngle;
  resp["rotate_duration"] = rotateMs;
  resp["feed_hold_duration"] = holdMs;

  String out;
  serializeJson(resp, out);
  server.send(200, "application/json", out);
}

void handleTest() {
  StaticJsonDocument<256> doc;
  if (!parseJsonBody(doc)) {
    server.send(400, "application/json", "{\"error\":\"invalid json\"}");
    return;
  }

  int feedAngle = doc["feed_angle"] | DEFAULT_FEED_ANGLE;
  int restAngle = doc["rest_angle"] | DEFAULT_REST_ANGLE;
  int rotateMs = doc["rotate_duration"] | DEFAULT_ROTATE_MS;

  runFeed(feedAngle, restAngle, rotateMs, 250); // short hold

  StaticJsonDocument<128> resp;
  resp["status"] = "success";
  resp["message"] = "test complete";

  String out;
  serializeJson(resp, out);
  server.send(200, "application/json", out);
}

void handleStatus() {
  StaticJsonDocument<256> resp;
  resp["status"] = "ok";
  resp["uptime"] = millis() / 1000; // seconds
  resp["wifi_rssi"] = WiFi.RSSI();
  resp["ip"] = WiFi.localIP().toString();
  resp["last_feed_timestamp"] = lastFeedMillis ? lastFeedMillis / 1000 : 0;
  resp["battery_percent"] = nullptr; // placeholder (add ADC if you wire a battery monitor)
  resp["battery_voltage"] = nullptr;

  String out;
  serializeJson(resp, out);
  server.send(200, "application/json", out);
}

void handleRoot() {
  server.send(200, "text/plain", "ESP32 Feeder online. Use /status, /feed, /test.");
}

void setupWiFi() {
#ifdef USE_STATIC_IP
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS, secondaryDNS)) {
    Serial.println("[WiFi] Failed to configure static IP, continuing with DHCP");
  }
#endif
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Connecting");
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    retries++;
    if (retries > 60) { // ~30s timeout
      Serial.println("\n[WiFi] Failed to connect. Rebooting...");
      delay(2000);
      ESP.restart();
    }
  }
  Serial.print("\n[WiFi] Connected. IP: ");
  Serial.println(WiFi.localIP());
}

void setupServer() {
  server.on("/", HTTP_GET, handleRoot);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/feed", HTTP_POST, handleFeed);
  server.on("/test", HTTP_POST, handleTest);
  server.begin();
  Serial.println("[HTTP] Server started on port 80");
}

void setupServo() {
  // Attach servo once at boot; detach not needed for most hobby servos
  feederServo.setPeriodHertz(50); // 50Hz for SG90
  feederServo.attach(SERVO_PIN, 500, 2400); // uS min/max
  feederServo.write(DEFAULT_REST_ANGLE);
}

void setup() {
  Serial.begin(115200);
  delay(100);
  setupWiFi();
  setupServo();
  setupServer();
}

void loop() {
  server.handleClient();
}
