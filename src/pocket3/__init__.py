"""Minimal, independent Osmo Pocket 3 control SDK (reverse-engineered from DJI Mimo).

Layers mirror the recovered app architecture:
    protocol/  DUML V1 encode/decode (byte-exact CRC tables)
    transport/ BLE / Wi-Fi-SW_Pro / (MFi)        == DJIServicePort
    commands/  command + topic registry           == KeyHandlers/SendActionPack<X>
    state/     state + capability store            == dji::core topic pub-sub
    preview/   live-view de-framer + session       == DJILiveviewChannelSeparator
    device     Pocket3Device high-level API         == dji::sdk key layer
    manager    multi-camera (§26)
    adapter    vendor-neutral CameraController (§24)
"""
from .device import Pocket3Device, CommandUnresolved  # noqa: F401
from .protocol.duml import DumlFrame  # noqa: F401
from .manager import CameraManager  # noqa: F401
from .adapter import CameraController, Pocket3Adapter  # noqa: F401
from .preview.liveview import LiveviewSeparator, LiveHeader  # noqa: F401
from .logger import ProtocolLogger  # noqa: F401

__all__ = [
    "Pocket3Device", "DumlFrame", "CommandUnresolved", "CameraManager",
    "CameraController", "Pocket3Adapter", "LiveviewSeparator", "LiveHeader",
    "ProtocolLogger",
]
__version__ = "0.2.0"
