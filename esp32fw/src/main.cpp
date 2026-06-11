// pyportal-claude-buddy : native ESP32 BLE firmware for the PyPortal Titano co-processor.
// Replaces nina-fw. Runs a NATIVE Bluedroid BLE GATT server (Nordic UART Service) -- which
// Windows/WinRT/Chromium Web Bluetooth CAN discover and (v2) pair with, unlike _bleio-over-HCI.
// Bridges BLE NUS <-> UART0 (GPIO1/GPIO3) so the SAMD51 is the brain, this ESP32 is the radio.
//
// v1: NO security yet -- prove native BLE GATT discovery + round-trip works on Windows first.
//     (v2 will add Just-Works bonding for the Claude app.)
#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define NUS_SERVICE "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX_UUID "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  // write  (central -> device)
#define NUS_TX_UUID "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  // notify (device -> central)

// Safety-net interval: if not connected, re-assert advertising every 30 s to recover from
// any silent advertising stop (e.g. glitchy resets while a central was connected).
#define READVERT_INTERVAL_MS 30000UL

static BLECharacteristic *txChar = nullptr;
// Standard Espressif two-flag pattern: callbacks only flip deviceConnected; loop() acts on it.
static volatile bool deviceConnected    = false;
static bool          oldDeviceConnected = false;
static unsigned long lastAdvMs          = 0;

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override    { deviceConnected = true;  }
  void onDisconnect(BLEServer *) override { deviceConnected = false; }
};

class RxCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    std::string v = c->getValue();
    if (!v.empty()) {
      // forward inbound BLE data to the SAMD51 over UART0
      Serial.write((const uint8_t *)v.data(), v.size());
    }
  }
};

void setup() {
  Serial.begin(115200);
  Serial.setRxBufferSize(2048);

  BLEDevice::init("Claude-PyPortal");
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());

  BLEService *svc = server->createService(NUS_SERVICE);
  txChar = svc->createCharacteristic(NUS_TX_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  txChar->addDescriptor(new BLE2902());
  BLECharacteristic *rxChar = svc->createCharacteristic(
      NUS_RX_UUID,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rxChar->setCallbacks(new RxCallbacks());
  svc->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NUS_SERVICE);
  adv->setScanResponse(true);
  adv->setMinPreferred(0x06);
  adv->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
  lastAdvMs = millis();
}

void loop() {
  // --- connection-state machine (Espressif canonical pattern) ---
  if (!deviceConnected && oldDeviceConnected) {
    // Just disconnected: let the BLE stack settle before restarting advertising.
    delay(500);
    BLEDevice::startAdvertising();
    lastAdvMs = millis();
    oldDeviceConnected = deviceConnected;
  }
  if (deviceConnected && !oldDeviceConnected) {
    // Just connected.
    oldDeviceConnected = deviceConnected;
  }

  // Safety net: if idle (not connected) and advertising may have silently stopped,
  // re-assert it every READVERT_INTERVAL_MS so we never need a manual power-cycle.
  if (!deviceConnected && (millis() - lastAdvMs >= READVERT_INTERVAL_MS)) {
    BLEDevice::startAdvertising();
    lastAdvMs = millis();
  }

  // SAMD51 -> BLE: forward any UART0 bytes out as NUS TX notifications.
  if (deviceConnected && txChar) {
    int avail = Serial.available();
    if (avail > 0) {
      uint8_t buf[180];
      int n = Serial.readBytes(buf, avail > 180 ? 180 : avail);
      if (n > 0) {
        txChar->setValue(buf, n);
        txChar->notify();
      }
    }
  }
  delay(3);
}
