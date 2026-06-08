# SAMD51 "run + bridge" mode for TESTING the freshly-flashed ESP32 BLE firmware.
# Resets the ESP32 into RUN mode (GPIO0 high) so the new firmware boots, then transparently
# bridges the ESP32 UART0 <-> USB data CDC (COM8). Lets the PC inject/observe the UART side
# while a BLE central (bleak / Claude app) talks to the ESP32's native BLE on the other side.
import time
import board
import busio
import digitalio
import usb_cdc

ser = usb_cdc.data
if ser is None:
    print("ERROR: usb_cdc.data not enabled (need boot.py).")
    while True:
        time.sleep(1)

gpio0 = digitalio.DigitalInOut(board.ESP_GPIO0)
gpio0.switch_to_output(True)   # HIGH = normal boot / run firmware
reset = digitalio.DigitalInOut(board.ESP_RESET)
reset.switch_to_output(True)

uart = busio.UART(board.ESP_TX, board.ESP_RX, baudrate=115200,
                  timeout=0, receiver_buffer_size=1024)
ser.timeout = 0

# Reset ESP32 into RUN mode and capture its boot banner.
gpio0.value = True
reset.value = False
time.sleep(0.1)
reset.value = True
time.sleep(0.4)

banner = b""
t0 = time.monotonic()
while time.monotonic() - t0 < 1.5:
    k = uart.in_waiting
    if k:
        banner += uart.read(k)
print("[run] ESP32 boot bytes:", len(banner))
if banner:
    try:
        print("[run] boot:", banner.decode("utf-8", "replace")[:400])
    except Exception:
        pass
print("[run] bridging UART0 <-> usb_cdc.data (COM8); ESP32 firmware running")

while True:
    n = ser.in_waiting
    if n:
        uart.write(ser.read(n))
    m = uart.in_waiting
    if m:
        ser.write(uart.read(m))
