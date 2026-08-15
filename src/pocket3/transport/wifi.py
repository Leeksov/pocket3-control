"""Wi-Fi transport over DJI 'SW_Pro' reliable-UDP (brief §7).

Recovered (DJIMidWare 3vfb, agent B): _SW_Pro_Add_Header_And_Send @0x97ce4,
_SW_Pro_Gnd_Entry_Start @0x96f40, recv FSM @0x981b4.

SW_Pro 8-byte header (integrity = checksum only, NO encryption):
  [0]     flag / high bits of length
  [0..1]  14-bit payload length (flag in top 2 bits)
  [2..3]  link id / session id
  [4..5]  seq
  [6]     type   (0=connect, 1=data/ack, 2/3=link-data)
  [7]     SW_CheckSum over header(+body)
Session bring-up generates a random session id + seq seed and runs recv +
keepalive threads with windowed ARQ.

NOTE: exact bitfield packing of [0..1] and the checksum polynomial still need
confirmation from _SW_Pro_Add_Header_And_Send before this is wire-ready. DUML
command frames are carried as the SW_Pro *payload*. This class is a documented
scaffold; connect() raises until the header packing is verified.
"""
from __future__ import annotations
import os
import struct
from typing import Optional

from .base import Transport

SW_TYPE_CONNECT = 0
SW_TYPE_DATA = 1


def sw_checksum(data: bytes) -> int:
    c = 0
    for b in data:
        c = (c + b) & 0xFF
    return c


class WifiSwProTransport(Transport):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self._sock = None
        self._session_id = int.from_bytes(os.urandom(2), "little")
        self._seq = int.from_bytes(os.urandom(2), "little")

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    async def connect(self) -> None:
        raise NotImplementedError(
            "SW_Pro header packing/checksum not yet byte-confirmed "
            "(_SW_Pro_Add_Header_And_Send @0x97ce4). Use BLE transport for now.")

    async def disconnect(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def _wrap(self, payload: bytes, type_: int = SW_TYPE_DATA) -> bytes:
        self._seq = (self._seq + 1) & 0xFFFF
        length = len(payload) & 0x3FFF
        hdr = bytes([
            length & 0xFF,
            (length >> 8) & 0x3F,
            self._session_id & 0xFF, (self._session_id >> 8) & 0xFF,
            self._seq & 0xFF, (self._seq >> 8) & 0xFF,
            type_ & 0xFF,
        ])
        return hdr + bytes([sw_checksum(hdr + payload)]) + payload

    async def send(self, data: bytes, *, channel: int = 0) -> None:
        if not self._sock:
            raise RuntimeError("Wi-Fi not connected")
        self._sock.sendto(self._wrap(data), (self.host, self.port))
