"""Connect probe: bypass WinRT GATT service cache, enumerate NUS, round-trip."""
import asyncio
from bleak import BleakScanner, BleakClient

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # write  (central -> device)
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # notify (device -> central)


async def main():
    d = await BleakScanner.find_device_by_filter(
        lambda dev, adv: (adv.local_name or "").startswith("Claude"), timeout=10.0
    )
    if not d:
        print("not found")
        return
    print("found", d.address, flush=True)

    # Force fresh GATT discovery (avoid poisoned WinRT service cache)
    try:
        c = BleakClient(d, timeout=40.0, use_cached_services=False)
    except TypeError:
        c = BleakClient(d, timeout=40.0)

    try:
        print("connecting (40s, fresh discovery)...", flush=True)
        await c.connect()
        print("CONNECTED:", c.is_connected, flush=True)
        nus = False
        for s in c.services:
            print(" SVC", s.uuid)
            for ch in s.characteristics:
                print("   CHR", ch.uuid, list(ch.properties))
            if s.uuid.lower().startswith("6e400001"):
                nus = True
        print("NUS PRESENT:", nus)

        got = []

        def on_tx(_h, data):
            got.append(bytes(data))
            print("  <- TX:", bytes(data))

        try:
            await c.start_notify(NUS_TX, on_tx)
            await c.write_gatt_char(NUS_RX, b'{"hello":"pc"}\n', response=False)
            await asyncio.sleep(2.5)
            await c.stop_notify(NUS_TX)
        except Exception as e:
            print("  round-trip note:", repr(e))
        print("ROUND-TRIP:", len(got) > 0)
        print("VERIFY_RESULT: PASS" if nus else "VERIFY_RESULT: CONNECTED_NO_NUS")
    except Exception as e:
        print("connect error:", repr(e))
        try:
            print("attempting pair() then reconnect...", flush=True)
            await c.pair()
            await c.connect()
            print("CONNECTED after pair:", c.is_connected)
            for s in c.services:
                print(" SVC", s.uuid)
        except Exception as e2:
            print("pair/retry error:", repr(e2))
    finally:
        try:
            await c.disconnect()
        except Exception:
            pass


asyncio.run(main())
