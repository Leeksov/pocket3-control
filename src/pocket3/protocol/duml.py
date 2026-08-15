"""DUML V1 frame encode/decode (DJI "2014" protocol).

Frame layout (little-endian), reconstructed from DJIMidWare + dji::core:

    off  size  field
    0    1     SOF = 0x55
    1    2     ver_length: length = val & 0x03FF (total frame length incl CRC16)
                            version = (val >> 10) & 0x3F
    3    1     CRC8 over bytes[0..2]           (seed DJI_CRC8_INIT)
    4    1     sender   = (dev_type & 0x1F) | (index << 5)
    5    1     receiver = (dev_type & 0x1F) | (index << 5)
    6    2     seq
    8    1     cmd_type / flags  (bit7=ack, bit5=encrypted — TO VERIFY)
    9    1     cmd_set
    10   1     cmd_id
    11   n     payload
    -2   2     CRC16 over bytes[0..len-3]      (seed DJI_CRC16_INIT)

STATUS: CRC tables are byte-exact from the binary. The field *positions* match
DJI DUML V1. The seeds and sender/receiver/cmd_type conventions are the known
DJI defaults and must be confirmed against `PackProviderImpl` (main binary)
before trusting them on the wire — see docs/protocol.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .duml_tables import (
    DJI_CRC8_TABLE, DJI_CRC16_TABLE, DJI_CRC8_INIT, DJI_CRC16_INIT,
)

SOF = 0x55
HEADER_LEN = 11          # 0x55 .. cmd_id inclusive
CRC16_LEN = 2
OVERHEAD = HEADER_LEN + CRC16_LEN  # 13 bytes of framing per packet


def crc8(data: bytes, seed: int = DJI_CRC8_INIT) -> int:
    c = seed
    for b in data:
        c = DJI_CRC8_TABLE[(c ^ b) & 0xFF]
    return c & 0xFF


def crc16(data: bytes, seed: int = DJI_CRC16_INIT) -> int:
    c = seed
    for b in data:
        c = DJI_CRC16_TABLE[(c ^ b) & 0xFF] ^ (c >> 8)
    return c & 0xFFFF


def device_id(dev_type: int, index: int = 0) -> int:
    return (dev_type & 0x1F) | ((index & 0x07) << 5)


@dataclass
class DumlFrame:
    cmd_set: int
    cmd_id: int
    payload: bytes = b""
    seq: int = 0
    sender: int = 0x0A        # app-side id (VERIFY)
    receiver: int = 0x07      # camera/gimbal id (VERIFY)
    cmd_type: int = 0x00      # request; ack bit etc. (VERIFY)
    version: int = 0

    def encode(self) -> bytes:
        length = OVERHEAD + len(self.payload)
        if length > 0x03FF:
            raise ValueError(f"DUML frame too long: {length}")
        ver_length = (length & 0x03FF) | ((self.version & 0x3F) << 10)
        hdr = bytes([SOF, ver_length & 0xFF, (ver_length >> 8) & 0xFF])
        hdr += bytes([crc8(hdr)])
        body = bytes([
            self.sender & 0xFF,
            self.receiver & 0xFF,
            self.seq & 0xFF, (self.seq >> 8) & 0xFF,
            self.cmd_type & 0xFF,
            self.cmd_set & 0xFF,
            self.cmd_id & 0xFF,
        ]) + self.payload
        frame = hdr + body
        c = crc16(frame)
        frame += bytes([c & 0xFF, (c >> 8) & 0xFF])
        return frame

    @classmethod
    def decode(cls, buf: bytes) -> "DumlFrame":
        if len(buf) < OVERHEAD or buf[0] != SOF:
            raise ValueError("not a DUML frame")
        ver_length = buf[1] | (buf[2] << 8)
        length = ver_length & 0x03FF
        version = (ver_length >> 10) & 0x3F
        if crc8(buf[0:3]) != buf[3]:
            raise ValueError("header CRC8 mismatch")
        if len(buf) < length:
            raise ValueError("short buffer")
        if crc16(buf[0:length - 2]) != (buf[length - 2] | (buf[length - 1] << 8)):
            raise ValueError("frame CRC16 mismatch")
        return cls(
            cmd_set=buf[9], cmd_id=buf[10], payload=bytes(buf[11:length - 2]),
            seq=buf[6] | (buf[7] << 8), sender=buf[4], receiver=buf[5],
            cmd_type=buf[8], version=version,
        )


def find_frames(stream: bytes):
    """Yield (frame_bytes, DumlFrame) from a byte stream; skips junk/partials."""
    i, n = 0, len(stream)
    while i < n:
        if stream[i] != SOF:
            i += 1
            continue
        if i + 3 > n:
            break
        length = (stream[i + 1] | (stream[i + 2] << 8)) & 0x03FF
        if length < OVERHEAD or i + length > n:
            i += 1
            continue
        chunk = stream[i:i + length]
        try:
            yield chunk, DumlFrame.decode(chunk)
            i += length
        except ValueError:
            i += 1
