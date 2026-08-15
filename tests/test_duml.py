"""Self-tests for the DUML codec — runnable now, no camera needed."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pocket3.protocol.duml import DumlFrame, crc8, crc16, find_frames  # noqa: E402
from pocket3.protocol.duml_tables import DJI_CRC8_TABLE, DJI_CRC16_TABLE  # noqa: E402


def test_tables_shape():
    assert len(DJI_CRC8_TABLE) == 256 and DJI_CRC8_TABLE[1] == 94
    assert len(DJI_CRC16_TABLE) == 256 and DJI_CRC16_TABLE[1] == 4489


def test_roundtrip():
    f = DumlFrame(cmd_set=0x04, cmd_id=0x03, payload=b"\x01\x02\x03", seq=0x1234)
    raw = f.encode()
    assert raw[0] == 0x55
    g = DumlFrame.decode(raw)
    assert (g.cmd_set, g.cmd_id, g.payload, g.seq) == (0x04, 0x03, b"\x01\x02\x03", 0x1234)


def test_header_crc8_position():
    f = DumlFrame(cmd_set=0x00, cmd_id=0x00, payload=b"", seq=1)
    raw = f.encode()
    assert crc8(raw[0:3]) == raw[3]


def test_frame_crc16_tail():
    f = DumlFrame(cmd_set=0x01, cmd_id=0x02, payload=b"\xaa\xbb", seq=7)
    raw = f.encode()
    assert crc16(raw[:-2]) == (raw[-2] | (raw[-1] << 8))


def test_stream_scan_skips_junk():
    f = DumlFrame(cmd_set=0x09, cmd_id=0x09, payload=b"\xde\xad", seq=99)
    stream = b"\x00\xff\x55garbage" + f.encode() + b"\x55\x01"
    frames = list(find_frames(stream))
    assert len(frames) == 1 and frames[0][1].seq == 99


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok:", fn.__name__)
    print(f"\n{len(fns)} tests passed")
