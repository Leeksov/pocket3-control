"""CameraManager — multiple Pocket 3 cameras (brief §26). No global singletons.

Each camera has its own Device (transport, session, queue, state, preview).
"""
from __future__ import annotations
from typing import Dict, List, Optional

from .device import Pocket3Device
from .transport.ble import BleTransport


class CameraManager:
    def __init__(self):
        self._cams: Dict[str, Pocket3Device] = {}

    def add_ble(self, address: str, device_id: Optional[str] = None) -> Pocket3Device:
        did = device_id or f"CAM{len(self._cams) + 1:02d}"
        dev = Pocket3Device(BleTransport(address), device_id=did)
        self._cams[did] = dev
        return dev

    def add(self, device: Pocket3Device) -> Pocket3Device:
        self._cams[device.device_id] = device
        return device

    def get(self, device_id: str) -> Optional[Pocket3Device]:
        return self._cams.get(device_id)

    def all(self) -> List[Pocket3Device]:
        return list(self._cams.values())

    async def connect_all(self):
        for c in self._cams.values():
            if not c.connected:
                await c.connect()

    async def disconnect_all(self):
        for c in self._cams.values():
            if c.connected:
                await c.disconnect()
