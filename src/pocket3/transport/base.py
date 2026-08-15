"""Transport abstraction — mirrors DJIServicePort in DJIMidWare.

Every medium (BLE / Wi-Fi-UDT / MFi) implements Transport. A transport moves
already-serialized DUML frames; it knows nothing about commands.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Optional


class Transport(ABC):
    """One physical link to a single Pocket 3 (no global singletons)."""

    def __init__(self) -> None:
        self._on_rx: Optional[Callable[[bytes], None]] = None

    def set_rx_handler(self, cb: Callable[[bytes], None]) -> None:
        """Register callback for raw bytes arriving from the camera (notify)."""
        self._on_rx = cb

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send(self, data: bytes, *, channel: int = 0) -> None:
        """Write raw DUML bytes. channel=4 maps to BLE 'external' characteristic."""

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...
