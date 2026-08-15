"""BLE transport for Osmo Pocket 3.

UUIDs recovered from the main DJIMimo binary (string cluster @0x7920333) and
the DJIBLEService model (serviceUUID + write/notify/external + OTA):

    Service        FFF0
    FFF4 / FFF5 / FFF3  -> write / notify / external  (ORDER TO VERIFY against
                           DCSBLEService in the main binary)

Discovery + connect mirror DataLinkServiceFactoryImpl::StartBLEScan/ConnectBLE
and DJIBLECentralManager. Requires `bleak` (cross-platform CoreBluetooth on mac).
"""
from __future__ import annotations
import asyncio
from typing import List, Optional

from .base import Transport

DJI_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
CHAR_WRITE = "0000fff4-0000-1000-8000-00805f9b34fb"    # WRITE / WRITE_NO_RESP
CHAR_NOTIFY = "0000fff5-0000-1000-8000-00805f9b34fb"   # NOTIFY
CHAR_EXTERNAL = "0000fff3-0000-1000-8000-00805f9b34fb"  # external (channel 4)

# Pocket 3 advertises its name; refine once we see real advertisement data.
NAME_PREFIXES = ("Osmo Pocket 3", "OsmoPocket3", "Pocket 3", "DJI Osmo")


async def scan(timeout: float = 6.0) -> List[dict]:
    """Return candidate Pocket 3 peripherals [{name, address, rssi}]."""
    from bleak import BleakScanner
    found = []
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for dev, adv in devices.values():
        name = dev.name or adv.local_name or ""
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        if any(name.startswith(p) for p in NAME_PREFIXES) or DJI_SERVICE_UUID in uuids:
            found.append({"name": name, "address": dev.address, "rssi": adv.rssi})
    return found


class BleTransport(Transport):
    def __init__(self, address: str):
        super().__init__()
        self.address = address
        self._client = None

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    async def connect(self) -> None:
        from bleak import BleakClient
        self._client = BleakClient(self.address)
        await self._client.connect()
        await self._client.start_notify(CHAR_NOTIFY, self._notify_cb)

    def _notify_cb(self, _char, data: bytearray) -> None:
        if self._on_rx:
            self._on_rx(bytes(data))

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.stop_notify(CHAR_NOTIFY)
            except Exception:
                pass
            await self._client.disconnect()
            self._client = None

    async def send(self, data: bytes, *, channel: int = 0) -> None:
        if not self.is_connected:
            raise RuntimeError("BLE not connected")
        char = CHAR_EXTERNAL if channel == 4 else CHAR_WRITE
        await self._client.write_gatt_char(char, data, response=False)
