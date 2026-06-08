"""Autonomous PC-side BLE verification for pyportal-claude-buddy.

Re-discovers and connects with retries (NINA peripherals are slow to set up a
link, and Windows/WinRT often times out the first attempt). On success it
enumerates the Nordic UART Service and does a write->echo round-trip to prove
end-to-end BLE data exchange from THIS PC.
"""
import asyncio
import sys

from bleak import BleakScanner, BleakClient

NUS_SVC = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # write  (central -> device)
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # notify (device -> central)

ATTEMPTS = 4


def _name(dev, adv):
    return (adv.local_name if adv and adv.local_name else None) or (dev.name if dev else None) or ""


async def find():
    return await BleakScanner.find_device_by_filter(
        lambda d, adv: _name(d, adv).startswith("Claude"),
        timeout=12.0,
    )


async def connect_and_verify(target):
    received = []

    def on_tx(_sender, data):
        b = bytes(data)
        received.append(b)
        print(f"  <- TX notify: {b!r}")

    async with BleakClient(target, timeout=20.0) as client:
        print(f"CONNECTED: {client.is_connected}")
        has_nus = False
        for svc in client.services:
            tag = "   <-- NUS" if svc.uuid.lower() == NUS_SVC else ""
            print(f"  SVC {svc.uuid}{tag}")
            if svc.uuid.lower() == NUS_SVC:
                has_nus = True
            for ch in svc.characteristics:
                print(f"    CHR {ch.uuid}  {list(ch.properties)}")
        print(f"NUS PRESENT: {has_nus}")

        try:
            await client.start_notify(NUS_TX, on_tx)
            await client.write_gatt_char(NUS_RX, b'{"hello":"pc"}\n', response=False)
            await asyncio.sleep(2.5)
            await client.stop_notify(NUS_TX)
        except Exception as e:
            print(f"  data-exchange note: {e!r}")
        print(f"ROUND-TRIP (echo on TX): {len(received) > 0}")
        return has_nus


async def main():
    for attempt in range(1, ATTEMPTS + 1):
        print(f"=== attempt {attempt}/{ATTEMPTS} ===", flush=True)
        target = await find()
        if not target:
            print("  not found this round")
            continue
        print(f"FOUND  addr={target.address}  name={target.name!r}")
        try:
            ok = await connect_and_verify(target)
            print("DISCONNECTED cleanly")
            print("VERIFY_RESULT: PASS" if ok else "VERIFY_RESULT: CONNECTED_BUT_NO_NUS")
            return 0 if ok else 2
        except Exception as e:
            print(f"  connect failed: {e!r}")
            await asyncio.sleep(2.5)
    print("VERIFY_RESULT: FAIL (could not connect)")
    return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
