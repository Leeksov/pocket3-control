"""End-to-end plumbing test with a loopback transport — no camera, no BLE.

Proves: DUML tx -> ACK future resolves; unsolicited frame -> state ingest;
video bytes -> preview demux. Uses a manually-resolved command spec (since real
cmd_set/cmd_id are not recovered yet) to exercise the path.
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pocket3.transport.base import Transport            # noqa: E402
from pocket3.device import Pocket3Device                # noqa: E402
from pocket3.commands.registry import CommandSpec       # noqa: E402
from pocket3.protocol.duml import DumlFrame             # noqa: E402


class LoopbackTransport(Transport):
    """Echoes each sent DUML frame back as an ACK with the same seq."""
    def __init__(self):
        super().__init__()
        self._connected = False

    @property
    def is_connected(self): return self._connected
    async def connect(self): self._connected = True
    async def disconnect(self): self._connected = False

    async def send(self, data: bytes, *, channel: int = 0):
        f = DumlFrame.decode(data)
        ack = DumlFrame(f.cmd_set, f.cmd_id, b"\x00", seq=f.seq).encode()
        if self._on_rx:
            self._on_rx(ack)


async def _run():
    dev = Pocket3Device(LoopbackTransport(), device_id="CAM01", log=False)
    await dev.connect()
    assert dev.connected

    # manually resolve a spec to exercise tx/ack (real numbers still pending)
    spec = CommandSpec("test_cmd", "record_video_req", cmd_set=0x02, cmd_id=0x03)
    rsp = await dev.send_command(spec, b"\x01", timeout=1.0)
    assert rsp is not None and rsp.seq == 1 and rsp.cmd_set == 0x02

    # unsolicited push -> state store
    push = DumlFrame(0x02, 0x20, b"\x64", seq=999).encode()
    dev._on_bytes(push)                                     # noqa: SLF001
    assert dev.state.get("0x02:0x20") is not None

    # preview demux
    from pocket3.preview.liveview import MAGIC, xor8
    body = b"videochunk"
    hdr = bytearray(MAGIC) + bytes([len(body), 0, 5, 0, 0, 0, 0, 0])
    hdr[11] ^= xor8(hdr)
    got = []
    dev.on_video(lambda ch, d: got.append((ch, bytes(d))))
    dev.preview.feed(bytes(hdr) + body)
    assert got == [(5, b"videochunk")]

    await dev.disconnect()
    print("ok: loopback tx/ack, state push, preview demux")


def test_end_to_end():
    asyncio.run(_run())


if __name__ == "__main__":
    test_end_to_end()
    print("\n1 test passed")
