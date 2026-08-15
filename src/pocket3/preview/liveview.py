"""Live-preview channel de-framer — faithful port of DJILiveviewChannelSeparator.

Recovered from DJIMidWare (instance 3vfb):
  findMagic  @0x36f5c   magic = g_dji_live_view_channel_magic = 00 00 01 FF
  push       @0x36da4   FSM: FIND_MAGIC(0) -> READ_HEADER(1) -> READ_BODY(2)
  checkHeader@0x36fe0   header is 12 bytes at obj+8, validated by XOR8==0

Header (12 bytes, little-endian):
  [0..3]  magic 00 00 01 FF
  [4..5]  length low 16 bits
  [6]     channelID
  [7]     length high 8 bits    -> dataSize = h4 | h5<<8 | h7<<16  (<= 0x200000)
  [8..11] aux (timestamp/flags); whole 12-byte XOR8 == 0

Each demuxed channel payload is an elementary stream chunk (H.264/H.265) to feed
into a decoder (VideoToolbox on iOS; e.g. PyAV/ffmpeg on desktop).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

MAGIC = bytes([0x00, 0x00, 0x01, 0xFF])
HEADER_LEN = 12
MAX_FRAME = 0x200000  # 2 MB guard from checkHeader

# FSM states
_FIND, _HEAD, _BODY = 0, 1, 2


def xor8(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c & 0xFF


@dataclass
class LiveHeader:
    channel_id: int
    length: int
    raw: bytes

    @classmethod
    def parse(cls, hdr: bytes) -> Optional["LiveHeader"]:
        if len(hdr) != HEADER_LEN or hdr[0:4] != MAGIC:
            return None
        if xor8(hdr) != 0:
            return None
        length = hdr[4] | (hdr[5] << 8) | (hdr[7] << 16)
        if length > MAX_FRAME:
            return None
        return cls(channel_id=hdr[6], length=length, raw=bytes(hdr))


class LiveviewSeparator:
    """Feed raw transport bytes via push(); receive (channel_id, payload) chunks.

    Set default_channel_id != -1 to bypass framing (raw passthrough), matching
    the app's _defaultChannelID shortcut.
    """

    def __init__(self, on_data: Callable[[int, bytes], None],
                 default_channel_id: int = -1):
        self._on_data = on_data
        self._default = default_channel_id
        self._state = _FIND
        self._sig = 0          # magic match position
        self._hdr = bytearray()
        self._hdr_pos = 0
        self._data_size = 0
        self._data_pos = 0
        self._channel = 0

    def reset(self):
        self._state = _FIND
        self._sig = 0
        self._hdr = bytearray()
        self._hdr_pos = 0
        self._data_size = 0
        self._data_pos = 0

    def push(self, buf: bytes):
        if self._default != -1:
            self._on_data(self._default, buf)
            return
        i, n = 0, len(buf)
        while i < n:
            if self._state == _FIND:
                adv = self._find_magic(buf[i:])
                if adv < 0:
                    return
                i += adv
                self._state = _HEAD
                self._hdr = bytearray(MAGIC)   # magic already matched
                self._hdr_pos = 4
            elif self._state == _HEAD:
                take = min(HEADER_LEN - self._hdr_pos, n - i)
                self._hdr += buf[i:i + take]
                self._hdr_pos += take
                i += take
                if self._hdr_pos == HEADER_LEN:
                    h = LiveHeader.parse(bytes(self._hdr))
                    if h:
                        self._channel = h.channel_id
                        self._data_size = h.length
                        self._data_pos = 0
                        self._state = _BODY
                    else:
                        self.reset()
            else:  # _BODY
                remaining = self._data_size - self._data_pos
                take = min(remaining, n - i)
                self._on_data(self._channel, buf[i:i + take])
                self._data_pos += take
                i += take
                if self._data_pos >= self._data_size:
                    self.reset()

    def _find_magic(self, buf: bytes) -> int:
        """Return #bytes consumed up to & including a full magic match, or -1."""
        sig = self._sig
        for idx, b in enumerate(buf, start=1):
            if b == MAGIC[sig]:
                sig += 1
                if sig == 4:
                    self._sig = 0
                    return idx
            else:
                # replicate the run-of-zeros special case (magic starts 00 00)
                if sig >= 2 and b == 0 and sig == 2:
                    sig = 2
                else:
                    sig = 0
        self._sig = sig
        return -1
