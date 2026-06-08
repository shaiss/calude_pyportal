"""Log the PyPortal CircuitPython console (COM7) with timestamps, for tap diagnostics.

Usage: python tools/serial_log.py [PORT] [SECONDS]   (default COM7, 150s)
Writes timestamped lines to serial.log and stdout. Captures the device's prints,
notably "[touch] APPROVE id=..." / "[touch] DENY id=..." when the screen is tapped.
"""
import sys
import time

try:
    import serial
except ImportError:
    print("pyserial missing (pip install pyserial)")
    raise SystemExit(1)

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM7"
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
OUT = r"C:\Users\Shai\pyportal-claude-buddy\serial.log"

try:
    s = serial.Serial(PORT, 115200, timeout=0.2)
except Exception as e:
    print("open %s failed: %s" % (PORT, e))
    raise SystemExit(1)

t0 = time.monotonic()
with open(OUT, "w", encoding="utf-8") as f:
    hdr = "=== serial %s dur=%.0fs ===" % (PORT, DUR)
    print(hdr)
    f.write(hdr + "\n")
    f.flush()
    buf = b""
    while time.monotonic() - t0 < DUR:
        try:
            chunk = s.read(256)
        except Exception as e:
            msg = "[read err] %s" % e
            print(msg)
            f.write(msg + "\n")
            break
        if chunk:
            buf += chunk
            while b"\n" in buf:
                ln, buf = buf.split(b"\n", 1)
                msg = "[%7.2f] %s" % (time.monotonic() - t0,
                                      ln.decode("utf-8", "replace").rstrip())
                print(msg)
                f.write(msg + "\n")
                f.flush()
    try:
        s.close()
    except Exception:
        pass
print("=== serial log done ===")
