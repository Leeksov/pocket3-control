"""Pocket3Device — high-level SDK surface (brief §20).

One instance == one camera (multi-cam safe: own transport, seq, pending map,
state, logger, preview). Commands are DUML frames; they resolve on the matching
-seq reply (ACK) and are verified against the state store (brief §21/§22).

Commands whose cmd_set/cmd_id are not yet recovered raise CommandUnresolved
rather than emit a wrong frame.
"""
from __future__ import annotations
import asyncio
import itertools
from typing import Any, Callable, Dict, Optional

from .protocol.duml import DumlFrame, find_frames
from .transport.base import Transport
from .commands.registry import COMMANDS, CommandSpec
from .state.store import StateStore
from .logger import ProtocolLogger
from .preview.session import PreviewSession


class CommandUnresolved(NotImplementedError):
    """Raised when a command's cmd_set/cmd_id has not been recovered yet."""


# channel used for BLE 'external' characteristic; video rides its own port
CH_DEFAULT = 0
CH_EXTERNAL = 4


class Pocket3Device:
    def __init__(self, transport: Transport, device_id: str = "CAM01",
                 log: bool = True):
        self.device_id = device_id
        self.t = transport
        self.t.set_rx_handler(self._on_bytes)
        self._seq = itertools.count(1)
        self._pending: Dict[int, asyncio.Future] = {}
        self._rx_buf = bytearray()
        self.state = StateStore()
        self.log = ProtocolLogger(device_id, echo=log)
        self.preview = PreviewSession(self, sink=self._on_video)
        self._video_sink: Optional[Callable[[int, bytes], None]] = None
        self.connected = False

    # ---- lifecycle ----
    async def connect(self) -> None:
        await self.t.connect()
        self.connected = True
        self.log.event("CONNECTED", self.device_id)

    async def disconnect(self) -> None:
        self.connected = False
        await self.t.disconnect()
        self.log.event("DISCONNECTED", self.device_id)

    # ---- rx path (DjiProtocolDecoder::DecodeCommand equivalent) ----
    def _on_bytes(self, data: bytes) -> None:
        self._rx_buf.extend(data)
        consumed = 0
        for chunk, frame in find_frames(bytes(self._rx_buf)):
            consumed = self._rx_buf.find(chunk, consumed) + len(chunk)
            self._dispatch(frame)
        if consumed:
            del self._rx_buf[:consumed]

    def _dispatch(self, frame: DumlFrame) -> None:
        fut = self._pending.pop(frame.seq, None)
        if fut and not fut.done():
            self.log.rx(frame)
            fut.set_result(frame)
            return
        # unsolicited -> state push
        tv = self.state.ingest(frame)
        self.log.event("PUSH", tv.name)

    def on_video(self, sink: Callable[[int, bytes], None]):
        self._video_sink = sink

    def _on_video(self, channel: int, payload: bytes):
        if self._video_sink:
            self._video_sink(channel, payload)

    # ---- tx path with ACK + verify (brief §21/§22) ----
    async def send_command(self, spec: CommandSpec, payload: bytes = b"",
                           *, channel: int = CH_DEFAULT, timeout: float = 2.0,
                           expect_ack: bool = True) -> Optional[DumlFrame]:
        if not spec.resolved:
            raise CommandUnresolved(
                f"{spec.name}: cmd_set/cmd_id not recovered "
                f"(handler/req-type: {spec.handler})")
        seq = next(self._seq) & 0xFFFF
        frame = DumlFrame(spec.cmd_set, spec.cmd_id, payload, seq=seq)
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        if expect_ack:
            self._pending[seq] = fut
        self.log.tx(frame, spec.name)
        await self.t.send(frame.encode(), channel=channel)
        if not expect_ack:
            return None
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._pending.pop(seq, None)
            self.log.event("TIMEOUT", f"{spec.name} seq={seq}")
            raise

    async def _cmd(self, name: str, payload: bytes = b"", **kw):
        return await self.send_command(COMMANDS[name], payload, **kw)

    # ================= §20 public API =================
    # recording
    async def start_recording(self):   return await self._cmd("record_start")
    async def stop_recording(self):    return await self._cmd("record_stop")
    async def take_photo(self):        return await self._cmd("take_photo")

    # exposure
    async def set_exposure_mode(self, mode: int):
        return await self._cmd("set_exposure_mode", bytes([mode & 0xFF]))

    async def set_iso(self, iso: int):
        return await self._cmd("set_iso", _u16le(iso))

    async def set_shutter(self, numerator: int, denominator: int):
        return await self._cmd("set_shutter", _u16le(numerator) + _u16le(denominator))

    async def set_ev(self, ev_index: int):
        return await self._cmd("set_ev", bytes([ev_index & 0xFF]))

    async def set_white_balance(self, kelvin: int):
        return await self._cmd("set_white_balance", _u16le(kelvin))

    # video
    async def set_video_format(self, resolution: int, fps: int):
        return await self._cmd("set_video_format", bytes([resolution & 0xFF, fps & 0xFF]))

    async def set_video_codec(self, codec: int):
        return await self._cmd("set_video_codec", bytes([codec & 0xFF]))

    # gimbal
    async def recenter_gimbal(self):   return await self._cmd("gimbal_recenter")

    async def rotate_gimbal(self, yaw_deg: float, pitch_deg: float, speed: int = 30):
        return await self._cmd("gimbal_rotate", _build_rotate(yaw_deg, pitch_deg, speed))

    async def gimbal_speed(self, yaw_dps: float, pitch_dps: float):
        return await self._cmd("gimbal_speed", _build_speed(yaw_dps, pitch_dps))

    # zoom / focus
    async def set_zoom(self, ratio: float):
        return await self._cmd("zoom_ratio", _u16le(int(ratio * 100)))

    # storage
    async def format_sd(self):         return await self._cmd("format_sd")

    # preview
    async def start_preview(self):     return await self.preview.start()
    async def stop_preview(self):      return await self.preview.stop()

    # state read-back helpers (§21 verify, §23 subscribe)
    def get_state(self, topic: str):   return self.state.get(topic)
    def snapshot(self) -> Dict[str, Any]: return self.state.snapshot()
    def subscribe(self, topic: str, cb): self.state.subscribe(topic, cb)
    def get_battery(self):             return self.state.get("battery_dynamic_info_push")
    def get_storage(self):             return self.state.get("camera_storage_info_push")
    def get_capabilities(self):        return self.state._caps  # noqa: SLF001


# ---- payload builders (structure known; exact field maps pending) ----
def _u16le(v: int) -> bytes:
    return bytes([v & 0xFF, (v >> 8) & 0xFF])


def _s16le(v: int) -> bytes:
    return _u16le(v & 0xFFFF)


def _build_rotate(yaw_deg: float, pitch_deg: float, speed: int) -> bytes:
    # RotateByAngleNewAction -> dji::sdk::ControlGimbalAngle {yaw, pitch, speed}
    return _s16le(int(yaw_deg * 10)) + _s16le(int(pitch_deg * 10)) + bytes([speed & 0xFF])


def _build_speed(yaw_dps: float, pitch_dps: float) -> bytes:
    # set_gimbal_control_gimbal_speed_req {yaw_speed, pitch_speed} (0.1 deg/s units)
    return _s16le(int(yaw_dps * 10)) + _s16le(int(pitch_dps * 10))
