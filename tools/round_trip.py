"""Full data-plane round-trip over the native firmware:
  PC --BLE write(NUS RX)--> ESP32 --UART0--> SAMD51 bridge --> COM8 (PC reads)
  PC --COM8 write--> SAMD51 bridge --UART0--> ESP32 --BLE notify(NUS TX)--> PC
Proves the entire buddy datapath end to end.
"""
import asyncio
import time
import serial
from bleak import BleakScanner, BleakClient

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # write  (central -> device)
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # notify (device -> central)


async def main():
    d = await BleakScanner.find_device_by_filter(
        lambda dev, adv: (adv.local_name or "").startswith("Claude"), timeout=12.0)
    if not d:
        print("device not found")
        return
    print(f"found {d.address}")
    ser = serial.Serial("COM8", 115200, timeout=0.2)
    time.sleep(0.3)
    ser.reset_input_buffer()

    got = []
    async with BleakClient(d, timeout=20.0) as c:
        print("BLE connected:", c.is_connected)
        await c.start_notify(NUS_TX, lambda _h, data: got.append(bytes(data)))

        # (1) BLE -> UART
        await c.write_gatt_char(NUS_RX, b"PING-from-PC\n", response=False)
        await asyncio.sleep(0.7)
        com8 = ser.read(300)
        print("COM8 got (BLE->UART):", com8)

        # (2) UART -> BLE notify
        ser.write(b"PONG-from-UART\n")
        ser.flush()
        await asyncio.sleep(0.9)
        await c.stop_notify(NUS_TX)
        rx = b"".join(got)
        print("BLE notify got (UART->BLE):", rx)

    ser.close()
    print("RESULT ble->uart:", b"PING-from-PC" in com8)
    print("RESULT uart->ble:", b"PONG-from-UART" in rx)


asyncio.run(main())
