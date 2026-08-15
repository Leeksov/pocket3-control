"""PreviewSession — start/stop live preview and demux the video channel.

Control:  liveview_transmit_ctrl / set_live_view_camera_source_new_pack
          + ToggleCameraLiveViewAction   (cmd bytes pending, see registry)
Data:     LiveviewSeparator -> H.264/H.265 elementary stream chunks per channel.

The sink receives (channel_id, payload). Plug a decoder (PyAV/ffmpeg/VideoToolbox)
into the sink to render frames.
"""
from __future__ import annotations
from typing import Callable, Optional

from .liveview import LiveviewSeparator


class PreviewSession:
    def __init__(self, device, sink: Callable[[int, bytes], None]):
        self.device = device
        self._sep = LiveviewSeparator(on_data=sink)
        self._active = False

    def feed(self, raw: bytes):
        """Route raw video-channel bytes from the transport into the demuxer."""
        self._sep.push(raw)

    async def start(self, channel: Optional[int] = None):
        from ..commands.registry import COMMANDS
        self._sep.reset()
        self._active = True
        # ToggleCameraLiveViewAction / liveview_transmit_ctrl — bytes pending
        return await self.device.send_command(COMMANDS["liveview_toggle"], b"\x01")

    async def stop(self):
        from ..commands.registry import COMMANDS
        self._active = False
        return await self.device.send_command(COMMANDS["liveview_toggle"], b"\x00")

    @property
    def active(self) -> bool:
        return self._active
