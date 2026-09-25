/*
  AutoBasket fridge camera — ESP32-CAM (AI-Thinker).

  What it does
    - Listens to the Arduino scale node on a second UART (GPIO 14 = RX, GPIO 15 = TX) for "W,<slot>,<grams>".
    - Posts the latest weights to the API every READINGS_EVERY_S seconds.
    - When any slot's weight jumps by WEIGHT_CHANGE_G or more (something was taken or put back) it waits
      SETTLE_MS for the shelf to stop moving, posts the weights, then photographs the shelf with the flash LED
      on and posts the JPEG to /vision/device/trays/<TRAY_POSITION>/photo.
    - Also posts a photo once after boot and then every PHOTO_EVERY_S seconds, so the camera can be tested
      before any scale is wired. No door switch is needed.
    - Never reboot-loops: no Wi-Fi or no API means keep the latest readings and retry with backoff.

  Copy config.h.example to config.h and fill it in. Status lines go to the USB serial monitor at 115200.
*/

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include "config.h"

// ---- AI-Thinker ESP32-CAM pin map ----
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

const int FLASH_PIN = 4;
const int SCALE_RX_PIN = 14;
const int SCALE_TX_PIN = 15;
const int MAX_SLOTS = 8;

const unsigned long BACKOFF_MIN_MS = 5000;
const unsigned long BACKOFF_MAX_MS = 300000;
const unsigned long STATUS_EVERY_MS = 30000;

float slotGrams[MAX_SLOTS];
bool slotFresh[MAX_SLOTS];
unsigned long slotSeenAt[MAX_SLOTS];

unsigned long lastReadingsPost = 0;
unsigned long backoffMs = BACKOFF_MIN_MS;
unsigned long nextTryAt = 0;
unsigned long lastStatus = 0;
bool cameraOk = false;

float prevGrams[MAX_SLOTS];
bool changePending = false;          // a slot moved; photograph once it settles
unsigned long changedAt = 0;
unsigned long lastPhotoPost = 0;     // 0 = never, so the first photo goes right after boot

String scaleLine;

// ---------- helpers ----------

void logf(const char *fmt, ...) {
  char buf[160];
  va_list args;
  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  Serial.println(buf);
}

bool apiIsHttps() { return String(API_URL).startsWith("https://"); }

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  logf("[wifi] connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(250);
  if (WiFi.status() == WL_CONNECTED) logf("[wifi] connected, ip %s", WiFi.localIP().toString().c_str());
  else logf("[wifi] not connected yet; will keep trying");
}

void noteFailure() {
  nextTryAt = millis() + backoffMs;
  backoffMs = min(backoffMs * 2, BACKOFF_MAX_MS);
  logf("[api] failed; next try in %lu s", backoffMs / 1000);
}

void noteSuccess() { backoffMs = BACKOFF_MIN_MS; nextTryAt = 0; }

// One HTTP POST with the device token. contentType/body may be JSON or multipart.
int apiPost(const String &path, const String &contentType, const uint8_t *body, size_t len) {
  if (WiFi.status() != WL_CONNECTED) return -1;
  HTTPClient http;
  WiFiClientSecure secure;
  WiFiClient plain;
  String url = String(API_URL) + path;
  bool ok;
  if (apiIsHttps()) {
#if TLS_INSECURE
    secure.setInsecure();   // accepts any certificate; see README before using this outside your home network
#endif
    ok = http.begin(secure, url);
  } else {
    ok = http.begin(plain, url);
  }
  if (!ok) return -1;
  http.setTimeout(20000);
  http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
  http.addHeader("Content-Type", contentType);
  int code = http.POST((uint8_t *)body, len);
  if (code < 200 || code >= 300) {
    String reply = http.getString();
    logf("[api] %s -> %d %s", path.c_str(), code, reply.substring(0, 80).c_str());
  }
  http.end();
  return code;
}

// ---------- scale node ----------

void handleScaleLine(const String &line) {
  // W,<slot>,<grams>   or   E,<slot>
  if (line.length() < 3) return;
  int c1 = line.indexOf(',');
  int c2 = line.indexOf(',', c1 + 1);
  if (line[0] == 'W' && c1 > 0 && c2 > c1) {
    int slot = line.substring(c1 + 1, c2).toInt();
    float g = line.substring(c2 + 1).toFloat();
    if (slot >= 1 && slot <= MAX_SLOTS) {
      if (slotFresh[slot - 1] && fabs(g - prevGrams[slot - 1]) >= WEIGHT_CHANGE_G) {
        changePending = true;         // keeps resetting while the weight is still moving
        changedAt = millis();
        logf("[scale] slot %d moved %.0f g; settling for %lu ms", slot, g - prevGrams[slot - 1], (unsigned long)SETTLE_MS);
      }
      prevGrams[slot - 1] = g;
      slotGrams[slot - 1] = g;
      slotFresh[slot - 1] = true;
      slotSeenAt[slot - 1] = millis();
    }
  }
}

void pollScale() {
  while (Serial1.available()) {
    char c = Serial1.read();
    if (c == '\n' || c == '\r') {
      if (scaleLine.length()) { handleScaleLine(scaleLine); scaleLine = ""; }
    } else if (scaleLine.length() < 40) {
      scaleLine += c;
    }
  }
}

// ---------- posting ----------

bool postReadings() {
  String body = "{\"readings\":[";
  bool any = false;
  for (int i = 0; i < MAX_SLOTS; i++) {
    if (!slotFresh[i] || millis() - slotSeenAt[i] > 30000) continue;   // ignore slots silent for 30 s
    if (any) body += ",";
    body += "{\"tray\":" + String(TRAY_POSITION) + ",\"slot\":" + String(i + 1) + ",\"weight_grams\":" + String(slotGrams[i], 1) + "}";
    any = true;
  }
  body += "]}";
  if (!any) { logf("[scale] no fresh readings to post"); return true; }
  int code = apiPost("/devices/me/readings", "application/json", (const uint8_t *)body.c_str(), body.length());
  if (code == 200) { logf("[api] readings posted"); return true; }
  return false;
}

bool postPhoto() {
  if (!cameraOk) { logf("[cam] camera not initialised; skipping photo"); return true; }
  digitalWrite(FLASH_PIN, HIGH);
  delay(150);
  camera_fb_t *fb = esp_camera_fb_get();        // discard one frame so exposure settles with the flash on
  if (fb) { esp_camera_fb_return(fb); fb = NULL; }
  fb = esp_camera_fb_get();
  digitalWrite(FLASH_PIN, LOW);
  if (!fb) { logf("[cam] capture failed"); return false; }

  const char *boundary = "----AutoBasketBoundary7MA4YWxk";
  String head = String("--") + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"shelf.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
  String tail = String("\r\n--") + boundary + "--\r\n";
  size_t total = head.length() + fb->len + tail.length();
  uint8_t *buf = (uint8_t *)malloc(total);
  if (!buf) { esp_camera_fb_return(fb); logf("[cam] out of memory for upload"); return false; }
  memcpy(buf, head.c_str(), head.length());
  memcpy(buf + head.length(), fb->buf, fb->len);
  memcpy(buf + head.length() + fb->len, tail.c_str(), tail.length());
  size_t jpegLen = fb->len;
  esp_camera_fb_return(fb);

  String path = String("/vision/device/trays/") + TRAY_POSITION + "/photo";
  int code = apiPost(path, String("multipart/form-data; boundary=") + boundary, buf, total);
  free(buf);
  if (code == 200) { logf("[api] photo posted (%u bytes)", (unsigned)jpegLen); return true; }
  if (code == 503) { logf("[api] vision not set up on the server; photo ignored"); return true; }
  return false;
}

// ---------- camera ----------

bool initCamera() {
  camera_config_t c;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM;  c.pin_d1 = Y3_GPIO_NUM;  c.pin_d2 = Y4_GPIO_NUM;  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;  c.pin_d5 = Y7_GPIO_NUM;  c.pin_d6 = Y8_GPIO_NUM;  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM; c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = psramFound() ? FRAMESIZE_SVGA : FRAMESIZE_VGA;
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.grab_mode = CAMERA_GRAB_LATEST;
  c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) { logf("[cam] init failed 0x%x", err); return false; }
  logf("[cam] ready (%s)", psramFound() ? "PSRAM" : "no PSRAM, VGA");
  return true;
}

// ---------- main ----------

void setup() {
  Serial.begin(115200);
  delay(300);
  logf("[boot] AutoBasket fridge camera, tray %d", TRAY_POSITION);
  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW);
  Serial1.begin(9600, SERIAL_8N1, SCALE_RX_PIN, SCALE_TX_PIN);
  cameraOk = initCamera();
  connectWifi();
}

void loop() {
  pollScale();
  unsigned long now = millis();

  if (WiFi.status() != WL_CONNECTED && (now % 10000) < 20) connectWifi();

  if (now - lastStatus >= STATUS_EVERY_MS) {
    lastStatus = now;
    int fresh = 0;
    for (int i = 0; i < MAX_SLOTS; i++) if (slotFresh[i] && now - slotSeenAt[i] <= 30000) fresh++;
    logf("[status] wifi=%s slots=%d heap=%u", WiFi.status() == WL_CONNECTED ? "up" : "down", fresh,
         (unsigned)ESP.getFreeHeap());
  }

  bool canTry = nextTryAt == 0 || (long)(now - nextTryAt) >= 0;

  bool settled = changePending && now - changedAt >= SETTLE_MS;
  bool photoDue = PHOTO_EVERY_S > 0 && (lastPhotoPost == 0 || now - lastPhotoPost >= (unsigned long)PHOTO_EVERY_S * 1000UL);
  if ((settled || photoDue) && canTry) {
    changePending = false;
    bool ok = postReadings() && postPhoto();
    if (ok) { noteSuccess(); lastReadingsPost = now; lastPhotoPost = now; } else noteFailure();
  }

  if (canTry && now - lastReadingsPost >= (unsigned long)READINGS_EVERY_S * 1000UL) {
    if (postReadings()) { noteSuccess(); lastReadingsPost = now; } else noteFailure();
  }

  delay(5);
}
