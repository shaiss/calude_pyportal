"""Synthetic test of the buddy status responder: send {"cmd":"status"} over BLE NUS,
expect {"ack":"status","ok":true} notified back. Proves the loop fix before the real app."""
import asyncio
from bleak import BleakScanner, BleakClient

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


async def main():
    d = await BleakScanner.find_device_by_filter(
        lambda dev, adv: (adv.local_name or "").startswith("Claude"), timeout=12.0)
    if not d:
        print("device not found")
        return
    got = []
    async with BleakClient(d, timeout=20.0) as c:
        print("connected:", c.is_connected)
        await c.start_notify(NUS_TX, lambda _h, data: got.append(bytes(data)))
        # mimic the desktop's status poll a few times
        for _ in range(3):
            await c.write_gatt_char(NUS_RX, b'{"cmd":"status"}\n', response=False)
            await asyncio.sleep(0.6)
        await c.stop_notify(NUS_TX)
    reply = b"".join(got)
    print("reply bytes:", reply)
    ok = b'"ack":"status"' in reply and b'"ok":true' in reply
    print("STATUS_ACK_OK:", ok)


asyncio.run(main())
