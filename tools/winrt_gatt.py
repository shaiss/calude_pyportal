"""Raw WinRT GATT test, forcing a real connection via GattSession.maintain_connection
(what robust WinRT apps do) instead of relying on the OS cache. This is the closest
proxy to the Windows Claude app's BLE path, independent of bleak.
"""
import asyncio
import threading

from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.bluetooth.advertisement import (
    BluetoothLEAdvertisementWatcher,
    BluetoothLEScanningMode,
)
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattCommunicationStatus,
    GattSession,
)


def find_addr(timeout=15.0):
    watcher = BluetoothLEAdvertisementWatcher()
    watcher.scanning_mode = BluetoothLEScanningMode.ACTIVE
    box = {"addr": None}
    ev = threading.Event()

    def on_recv(_sender, args):
        if box["addr"] is not None:
            return
        try:
            name = args.advertisement.local_name
        except Exception:
            name = None
        match = bool(name and name.startswith("Claude"))
        if not match:
            try:
                for u in args.advertisement.service_uuids:
                    if str(u).lower().startswith("6e400001"):
                        match = True
                        break
            except Exception:
                pass
        if match:
            box["addr"] = args.bluetooth_address
            ev.set()

    watcher.add_received(on_recv)
    watcher.start()
    ev.wait(timeout)
    try:
        watcher.stop()
    except Exception:
        pass
    return box["addr"]


async def gatt_test(addr):
    print(f"addr=0x{addr:012X}")
    dev = await BluetoothLEDevice.from_bluetooth_address_async(addr)
    if dev is None:
        print("RAW_WINRT_RESULT: DEVICE_NONE")
        return
    print(f"device: name={dev.name!r} connection_status={dev.connection_status}")

    # Force a real connection the robust way.
    session = await GattSession.from_device_id_async(dev.bluetooth_device_id)
    session.maintain_connection = True
    print("forcing connection via GattSession.maintain_connection ...", flush=True)
    for i in range(20):
        await asyncio.sleep(1.0)
        print(f"  t={i+1}s session_status={session.session_status} conn={dev.connection_status}")
        if int(dev.connection_status) == 1:  # Connected
            break

    print("get_gatt_services_async() ...", flush=True)
    res = await dev.get_gatt_services_async()
    print("  services status:", res.status)
    if res.status == GattCommunicationStatus.SUCCESS:
        svcs = list(res.services)
        print("  service count:", len(svcs))
        nus = False
        for s in svcs:
            print("   SVC", s.uuid)
            if str(s.uuid).lower().startswith("6e400001"):
                nus = True
            cr = await s.get_characteristics_async()
            if cr.status == GattCommunicationStatus.SUCCESS:
                for c in cr.characteristics:
                    print("     CHR", c.uuid)
        print("RAW_WINRT_RESULT:", "SUCCESS_NUS" if nus else "SUCCESS_NO_NUS")
    else:
        print("RAW_WINRT_RESULT: DISCOVERY_FAILED", res.status)

    try:
        session.maintain_connection = False
        session.close()
    except Exception:
        pass


def main():
    addr = find_addr()
    if addr is None:
        print("device not found via advertisement")
        return
    asyncio.run(gatt_test(addr))


if __name__ == "__main__":
    main()
