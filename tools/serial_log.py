"""Log the PyPortal CircuitPython console (COM7) with timestamps.

Captures the device's prints -- "[ui] buddy UI ready", "[stats] ...", "[touch] APPROVE id=..."
-- and any Python traceback if code.py crashes, which is the fastest way to tell a deploy
went bad. Prints to stdout; optionally tees to a file with --out.

Usage: python tools/serial_log.py [PORT] [SECONDS] [--out FILE]   (default COM7, 150s)
"""
import sys
import time

try:
    import serial
except ImportError:
    print("pyserial missing (pip install pyserial)")
    raise SystemExit(1)

args = [a for a in sys.argv[1:]]
out_path = None
if "--out" in args:
    i = args.index("--out"); out_path = args[i + 1]; del args[i:i + 2]
PORT = args[0] if len(args) > 0 else "COM7"
DUR = float(args[1]) if len(args) > 1 else 150.0

try:
    s = serial.Serial(PORT, 115200, timeout=0.2)
except Exception as e:
    print("open %s failed: %s" % (PORT, e))
    raise SystemExit(1)

f = open(out_path, "w", encoding="utf-8") if out_path else None
t0 = time.monotonic()
buf = b""
print("=== serial %s dur=%.0fs ===" % (PORT, DUR))
while time.monotonic() - t0 < DUR:
    try:
        chunk = s.read(256)
    except Exception as e:
        print("[read err] %s" % e)
        break
    if chunk:
        buf += chunk
        while b"\n" in buf:
            ln, buf = buf.split(b"\n", 1)
            msg = "[%7.2f] %s" % (time.monotonic() - t0, ln.decode("utf-8", "replace").rstrip())
            # the Windows console is cp1252; CircuitPython's banner has a snake emoji -> sanitize
            print(msg.encode("ascii", "replace").decode("ascii"))
            if f:
                f.write(msg + "\n"); f.flush()
try:
    s.close()
except Exception:
    pass
if f:
    f.close()
print("=== serial log done ===")
