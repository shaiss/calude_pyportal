# CircuitPython ESP32 flashing passthrough with esptool DTR/RTS AUTO-RESET.
# esptool's classic reset drives: IO0 = NOT DTR, EN = NOT RTS. We mirror the host's
# DTR/RTS (from the usb_cdc data port) straight onto ESP_GPIO0/ESP_RESET, so esptool
# enters/exits the bootloader itself -- deterministic, no SAMD51 soft-reboots, no COM8
# disruption. Idle (port closed -> DTR/RTS deasserted) leaves the ESP32 running.
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

print("[ar-passthrough] mirroring DTR->IO0, RTS->EN; bridging usb_cdc.data <-> ESP UART")

while True:
    # esptool model: IO0 = NOT DTR, EN = NOT RTS
    reset.value = not ser.rts
    gpio0.value = not ser.dtr
    n = ser.in_waiting
    if n:
        uart.write(ser.read(n))
    m = uart.in_waiting
    if m:
        ser.write(uart.read(m))
