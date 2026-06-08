# Minimal CircuitPython ESP32 flashing passthrough for PyPortal Titano.
# Enters the ESP32 ROM bootloader once (GPIO0 low across reset), then transparently
# bridges usb_cdc.data (COM8) <-> ESP32 UART for esptool (--before no-reset).
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
gpio0.switch_to_output(True)
reset = digitalio.DigitalInOut(board.ESP_RESET)
reset.switch_to_output(True)

uart = busio.UART(board.ESP_TX, board.ESP_RX, baudrate=115200,
                  timeout=0, receiver_buffer_size=4096)
ser.timeout = 0

# Enter serial download mode: GPIO0 low across a reset pulse.
gpio0.value = False
reset.value = False
time.sleep(0.1)
reset.value = True
time.sleep(0.3)
gpio0.value = True

print("[pt] ESP32 in bootloader; bridging usb_cdc.data <-> ESP UART @115200")

while True:
    n = ser.in_waiting
    if n:
        uart.write(ser.read(n))
    m = uart.in_waiting
    if m:
        ser.write(uart.read(m))
