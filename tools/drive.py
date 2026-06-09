"""Drive the PyPortal buddy over BLE as a *synthetic Claude desktop*.

Connects to the Claude-PyPortal Nordic UART service and repeatedly sends a heartbeat (or a
named scenario) so the device's REAL connected path can be exercised and webcam-verified
without the actual desktop app. Heartbeats are resent every 2s (the device treats >8s of
silence as disconnected). With --ramp, the `tokens` field grows each send so the device
credits deltas and crosses level boundaries (to trigger level-up / celebrate).

Usage:
  python tools/drive.py busy                 # named scenario, held ~20s
  python tools/drive.py attention            # includes a permission prompt
  python tools/drive.py level --ramp 30000   # ramp tokens to force level-ups
  python tools/drive.py --json '{"total":2,"running":1}' --hold 15
"""
import asyncio
import json
import sys
import time

from bleak import BleakScanner, BleakClient

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # write  (central -> device)
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # notify (device -> central)

SCENARIOS = {
    "idle":      {"total": 1, "running": 0, "waiting": 0, "tokens": 12000,
                  "tokens_today": 3000, "msg": "thinking"},
    "busy":      {"total": 4, "running": 3, "waiting": 0, "tokens": 89000,
                  "tokens_today": 24000, "msg": "yarn build"},
    "attention": {"total": 2, "running": 1, "waiting": 1, "tokens": 45000,
                  "tokens_today": 12000, "msg": "approve: Bash",
                  "prompt": {"id": "req_demo", "tool": "Bash", "hint": "rm -rf /tmp/foo"}},
    "level":     {"total": 1, "running": 1, "waiting": 0, "tokens": 40000,
                  "tokens_today": 51000, "msg": "big job", "_ramp": 30000},
}


async def main():
    a = sys.argv[1:]
    hold, ramp, payload = 20.0, 0, None
    if "--hold" in a:
        i = a.index("--hold"); hold = float(a[i + 1]); del a[i:i + 2]
    if "--ramp" in a:
        i = a.index("--ramp"); ramp = int(a[i + 1]); del a[i:i + 2]
    if "--json" in a:
        i = a.index("--json"); payload = json.loads(a[i + 1]); del a[i:i + 2]
    elif a and a[0] in SCENARIOS:
        payload = dict(SCENARIOS[a[0]])
    if payload is None:
        print("usage: drive.py <%s> | --json '{...}' [--hold S] [--ramp N]"
              % "|".join(SCENARIOS))
        return
    if "_ramp" in payload:
        ramp = ramp or payload.pop("_ramp")
    base = payload.get("tokens", 0)

    dev = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or "").startswith("Claude"), timeout=12.0)
    if not dev:
        print("device not found (is it advertising / not bonded elsewhere?)")
        return
    got = []
    async with BleakClient(dev, timeout=20.0) as c:
        print("connected:", c.is_connected, "name:", dev.name)
        await c.start_notify(NUS_TX, lambda _h, b: got.append(bytes(b)))
        t0, i = time.monotonic(), 0
        while time.monotonic() - t0 < hold:
            if ramp:
                payload["tokens"] = base + ramp * i
            await c.write_gatt_char(NUS_RX, (json.dumps(payload) + "\n").encode(), response=False)
            i += 1
            await asyncio.sleep(2.0)
        await c.stop_notify(NUS_TX)
    dec = b"".join(got)
    if b"permission" in dec:
        print("device decisions:", dec.decode("utf-8", "replace").strip())
    print("done; %d sends over %.0fs" % (i, hold))


asyncio.run(main())
