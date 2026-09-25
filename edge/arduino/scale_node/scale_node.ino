/*
  AutoBasket scale node — Arduino Uno/Nano + up to 4 HX711 load-cell amplifiers.

  Reads every slot once a second and prints one line per slot on the USB serial port (9600 baud):
      W,<slot>,<grams>       a weight, slot is 1-based
      R,<slot>,<raw>         raw count, printed instead of W until that slot is calibrated
      E,<slot>               that HX711 did not answer (unplugged, or still powering up)

  Calibration (type in the Arduino IDE serial monitor, "Newline" line ending):
      T 1          tare slot 1: the platform is empty right now
      C 1 500      a known 500 g weight sits on slot 1 right now
      S            show offset and scale for every slot
      R            print raw counts once (for debugging)
  Tare and scale are kept in EEPROM, so they survive power cycles.

  No library needed: the HX711 is bit-banged below (24-bit, channel A, gain 128).

  Wiring per HX711:  VCC -> 5V, GND -> GND, DT -> DT_PIN[i], SCK -> SCK_PIN[i].
  You can wire just one HX711 (slot 1, pins 2 and 3); unplugged slots print E and cost nothing.
  The ESP32-CAM listens on this same serial line (see edge/README.md for the divider).
*/

#include <EEPROM.h>

const uint8_t N_SLOTS = 4;
const uint8_t DT_PIN[N_SLOTS]  = {2, 4, 6, 8};
const uint8_t SCK_PIN[N_SLOTS] = {3, 5, 7, 9};

const unsigned long REPORT_EVERY_MS = 1000;
const unsigned long READY_TIMEOUT_MS = 200;
const uint8_t SAMPLES = 5;              // median of 5 raw reads per report
const uint8_t EEPROM_MAGIC = 0xA7;

struct Calibration {
  long offset;   // raw counts with an empty platform
  float scale;   // raw counts per gram
};

Calibration cal[N_SLOTS];
char line[32];
uint8_t lineLen = 0;

// ---------- HX711 ----------

bool hxReady(uint8_t i) { return digitalRead(DT_PIN[i]) == LOW; }

// One 24-bit conversion. Returns false if the chip never signalled ready.
bool hxReadRaw(uint8_t i, long &out) {
  unsigned long start = millis();
  while (!hxReady(i)) {
    if (millis() - start > READY_TIMEOUT_MS) return false;
  }
  unsigned long value = 0;
  noInterrupts();
  for (uint8_t b = 0; b < 24; b++) {
    digitalWrite(SCK_PIN[i], HIGH);
    delayMicroseconds(1);
    value = (value << 1) | digitalRead(DT_PIN[i]);
    digitalWrite(SCK_PIN[i], LOW);
    delayMicroseconds(1);
  }
  // 25th pulse selects channel A, gain 128 for the next conversion.
  digitalWrite(SCK_PIN[i], HIGH);
  delayMicroseconds(1);
  digitalWrite(SCK_PIN[i], LOW);
  interrupts();
  if (value & 0x800000UL) value |= 0xFF000000UL;   // sign-extend 24 -> 32 bit
  out = (long)value;
  return true;
}

// Median of SAMPLES reads; false if fewer than 3 succeeded.
bool hxReadMedian(uint8_t i, long &out) {
  long s[SAMPLES];
  uint8_t n = 0;
  for (uint8_t k = 0; k < SAMPLES; k++) {
    long v;
    if (hxReadRaw(i, v)) s[n++] = v;
    else if (k == 0) return false;   // nothing answered on the first try: slot is unplugged, do not wait 4 more times
  }
  if (n < 3) return false;
  for (uint8_t a = 1; a < n; a++) {          // insertion sort, n <= 5
    long v = s[a];
    int8_t b = a - 1;
    while (b >= 0 && s[b] > v) { s[b + 1] = s[b]; b--; }
    s[b + 1] = v;
  }
  out = s[n / 2];
  return true;
}

float grams(uint8_t i, long raw) {
  if (cal[i].scale == 0) return 0;
  return (raw - cal[i].offset) / cal[i].scale;
}

// ---------- EEPROM ----------

void loadCalibration() {
  if (EEPROM.read(0) != EEPROM_MAGIC) {
    for (uint8_t i = 0; i < N_SLOTS; i++) { cal[i].offset = 0; cal[i].scale = 0; }
    return;
  }
  EEPROM.get(1, cal);
}

void saveCalibration() {
  EEPROM.update(0, EEPROM_MAGIC);
  EEPROM.put(1, cal);
}

// ---------- serial commands ----------

void showCalibration() {
  for (uint8_t i = 0; i < N_SLOTS; i++) {
    Serial.print(F("S,")); Serial.print(i + 1); Serial.print(',');
    Serial.print(cal[i].offset); Serial.print(','); Serial.println(cal[i].scale, 4);
  }
}

void handleCommand(char *cmd) {
  char op = toupper(cmd[0]);
  if (op == 'S') { showCalibration(); return; }
  if (op == 'R') {
    for (uint8_t i = 0; i < N_SLOTS; i++) {
      long raw;
      Serial.print(F("R,")); Serial.print(i + 1); Serial.print(',');
      if (hxReadMedian(i, raw)) Serial.println(raw); else Serial.println(F("none"));
    }
    return;
  }
  int slot = 0; long known = 0;
  if (op == 'T' && sscanf(cmd + 1, "%d", &slot) == 1 && slot >= 1 && slot <= N_SLOTS) {
    long raw;
    if (!hxReadMedian(slot - 1, raw)) { Serial.println(F("ERR,no reading")); return; }
    cal[slot - 1].offset = raw;
    saveCalibration();
    Serial.print(F("OK,tare,")); Serial.println(slot);
    return;
  }
  if (op == 'C' && sscanf(cmd + 1, "%d %ld", &slot, &known) == 2 && slot >= 1 && slot <= N_SLOTS && known > 0) {
    long raw;
    if (!hxReadMedian(slot - 1, raw)) { Serial.println(F("ERR,no reading")); return; }
    cal[slot - 1].scale = (float)(raw - cal[slot - 1].offset) / (float)known;
    saveCalibration();
    Serial.print(F("OK,scale,")); Serial.print(slot); Serial.print(','); Serial.println(cal[slot - 1].scale, 4);
    return;
  }
  Serial.println(F("ERR,commands: T <slot> | C <slot> <grams> | S | R"));
}

void pollSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen > 0) { line[lineLen] = 0; handleCommand(line); lineLen = 0; }
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = c;
    }
  }
}

// ---------- main ----------

void setup() {
  Serial.begin(9600);
  for (uint8_t i = 0; i < N_SLOTS; i++) {
    pinMode(DT_PIN[i], INPUT_PULLUP);   // an unplugged slot reads HIGH (= "not ready") instead of floating
    pinMode(SCK_PIN[i], OUTPUT);
    digitalWrite(SCK_PIN[i], LOW);
  }
  loadCalibration();
  Serial.println(F("I,autobasket-scale-node,1"));
  showCalibration();
}

unsigned long lastReport = 0;

void loop() {
  pollSerial();
  if (millis() - lastReport < REPORT_EVERY_MS) return;
  lastReport = millis();
  for (uint8_t i = 0; i < N_SLOTS; i++) {
    long raw;
    if (!hxReadMedian(i, raw)) {
      Serial.print(F("E,")); Serial.println(i + 1);
      continue;
    }
    if (cal[i].scale == 0) {
      // Not calibrated yet: stream the raw count so wiring can be checked live. Calibrate with T then C.
      Serial.print(F("R,")); Serial.print(i + 1); Serial.print(','); Serial.println(raw);
      continue;
    }
    Serial.print(F("W,")); Serial.print(i + 1); Serial.print(','); Serial.println(grams(i, raw), 1);
  }
}
