# pyportal-claude-buddy : SAMD51 buddy-protocol responder.
# The ESP32 runs native BLE (NUS) and bridges NUS<->UART0. This script is the "brain":
# it boots the ESP32 in run mode, reads newline-framed JSON the desktop sends over the
# Nordic UART Service, and replies to {"cmd":"status"} with {"ack":"status","ok":true}
# so the Claude Hardware Buddy doesn't time out (the connect/disconnect loop fix).
import time
import board
import busio
import digitalio

# Bring the ESP32 up in RUN mode (native BLE firmware).
gpio0 = digitalio.DigitalInOut(board.ESP_GPIO0)
gpio0.switch_to_output(True)   # high = normal boot
reset = digitalio.DigitalInOut(board.ESP_RESET)
reset.switch_to_output(True)
gpio0.value = True
reset.value = False
time.sleep(0.1)
reset.value = True
time.sleep(0.6)

uart = busio.UART(board.ESP_TX, board.ESP_RX, baudrate=115200,
                  timeout=0, receiver_buffer_size=1024)
print("[buddy] ESP32 in run mode; protocol responder active")

boot = time.monotonic()
buf = b""

while True:
    n = uart.in_waiting
    if n:
        buf += uart.read(n)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                print("[rx]", line.decode("utf-8", "replace"))
            except Exception:
                pass
            # Acknowledge the desktop's status poll (prevents the ~30s timeout/disconnect).
            if b'"cmd"' in line and b'"status"' in line:
                up = int(time.monotonic() - boot)
                reply = ('{"ack":"status","ok":true,"data":{"name":"Claude-PyPortal",'
                         '"sec":true,"sys":{"up":%d}}}\n' % up)
                uart.write(reply.encode("utf-8"))
                print("[tx] status ack (up=%ds)" % up)
    time.sleep(0.01)
