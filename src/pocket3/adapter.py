"""CameraController abstraction + Pocket3Adapter (brief §24, §25).

The AI/director layer talks to CameraController and never sees DUML. Pocket3Adapter
translates the vendor-neutral calls into Pocket3Device commands. Other cameras
(Canon, etc.) implement the same interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional

from .device import Pocket3Device


class CameraController(ABC):
    """Vendor-neutral camera control surface for the AI director."""

    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def disconnect(self) -> None: ...
    @abstractmethod
    async def start_recording(self) -> bool: ...
    @abstractmethod
    async def stop_recording(self) -> bool: ...
    @abstractmethod
    async def set_iso(self, iso: int) -> bool: ...
    @abstractmethod
    async def set_shutter(self, num: int, den: int) -> bool: ...
    @abstractmethod
    async def set_ev(self, ev_index: int) -> bool: ...
    @abstractmethod
    async def pan(self, yaw_deg: float) -> bool: ...
    @abstractmethod
    async def tilt(self, pitch_deg: float) -> bool: ...
    @abstractmethod
    async def recenter(self) -> bool: ...
    @abstractmethod
    async def start_preview(self) -> bool: ...
    @abstractmethod
    async def stop_preview(self) -> bool: ...
    @abstractmethod
    def state(self) -> dict: ...


class Pocket3Adapter(CameraController):
    def __init__(self, device: Pocket3Device):
        self.d = device

    async def connect(self):      await self.d.connect()
    async def disconnect(self):   await self.d.disconnect()

    async def _ok(self, coro) -> bool:
        """Run a command and verify via ACK; True on success (brief §21)."""
        try:
            rsp = await coro
            return rsp is not None
        except Exception as e:                       # CommandUnresolved / TimeoutError
            self.d.log.event("CMD_FAILED", str(e))
            return False

    async def start_recording(self): return await self._ok(self.d.start_recording())
    async def stop_recording(self):  return await self._ok(self.d.stop_recording())
    async def set_iso(self, iso):    return await self._ok(self.d.set_iso(iso))
    async def set_shutter(self, n, d): return await self._ok(self.d.set_shutter(n, d))
    async def set_ev(self, ev):      return await self._ok(self.d.set_ev(ev))
    async def pan(self, yaw):        return await self._ok(self.d.rotate_gimbal(yaw, 0.0))
    async def tilt(self, pitch):     return await self._ok(self.d.rotate_gimbal(0.0, pitch))
    async def recenter(self):        return await self._ok(self.d.recenter_gimbal())
    async def start_preview(self):   return await self._ok(self.d.start_preview())
    async def stop_preview(self):    return await self._ok(self.d.stop_preview())

    def state(self) -> dict:         return self.d.snapshot()
