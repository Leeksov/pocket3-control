"""Live-preview de-framer tests — runnable now, no camera needed.

Validates the DJILiveviewChannelSeparator port: magic 00 00 01 FF, 12-byte
header, XOR8==0, 24-bit length, channel demux, resync across split buffers.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pocket3.preview.liveview import LiveviewSeparator, LiveHeader, MAGIC, xor8  # noqa: E402


def _make_frame(channel: int, payload: bytes) -> bytes:
    n = len(payload)
    hdr = bytearray(MAGIC)                 # [0..3]
    hdr += bytes([n & 0xFF, (n >> 8) & 0xFF])   # [4..5] length low16
    hdr += bytes([channel & 0xFF])              # [6] channel
    hdr += bytes([(n >> 16) & 0xFF])            # [7] length high8
    hdr += bytes(4)                             # [8..11] aux
    hdr[11] = xor8(hdr) ^ hdr[11]               # make XOR8 == 0
    assert xor8(hdr) == 0 and len(hdr) == 12
    return bytes(hdr) + payload


def test_header_parse():
    f = _make_frame(3, b"\x11\x22\x33")
    h = LiveHeader.parse(f[:12])
    assert h and h.channel_id == 3 and h.length == 3


def test_single_frame():
    out = []
    sep = LiveviewSeparator(on_data=lambda ch, d: out.append((ch, d)))
    sep.push(_make_frame(7, b"ABCDEF"))
    assert out == [(7, b"ABCDEF")]


def test_split_across_buffers():
    out = []
    sep = LiveviewSeparator(on_data=lambda ch, d: out.append((ch, bytes(d))))
    frame = _make_frame(1, bytes(range(20)))
    for i in range(0, len(frame), 3):          # dribble 3 bytes at a time
        sep.push(frame[i:i + 3])
    joined = b"".join(d for _, d in out)
    assert joined == bytes(range(20))


def test_junk_then_frame():
    out = []
    sep = LiveviewSeparator(on_data=lambda ch, d: out.append((ch, bytes(d))))
    sep.push(b"\xde\xad\x00\x00\x00" + _make_frame(2, b"XY"))
    assert out and out[-1] == (2, b"XY")


def test_two_frames():
    out = []
    sep = LiveviewSeparator(on_data=lambda ch, d: out.append((ch, bytes(d))))
    sep.push(_make_frame(1, b"aa") + _make_frame(2, b"bbb"))
    assert (1, b"aa") in out and (2, b"bbb") in out


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok:", fn.__name__)
    print(f"\n{len(fns)} tests passed")
