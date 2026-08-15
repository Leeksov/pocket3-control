"""Protocol logger (brief §22) — structured TX/RX/EVENT records with timestamps."""
from __future__ import annotations
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional, TextIO

from .protocol.duml import DumlFrame


def _ts() -> str:
    t = time.time()
    lt = time.localtime(t)
    return time.strftime("%H:%M:%S", lt) + f".{int((t % 1) * 1000):03d}"


@dataclass
class LogRecord:
    kind: str          # TX | RX | EVENT
    ts: str
    device: str
    text: str
    raw: Optional[bytes] = None


class ProtocolLogger:
    def __init__(self, device_id: str = "CAM01", stream: TextIO = sys.stderr,
                 keep: int = 2000, echo: bool = True):
        self.device_id = device_id
        self.records: List[LogRecord] = []
        self._stream = stream
        self._keep = keep
        self._echo = echo

    def _emit(self, rec: LogRecord):
        self.records.append(rec)
        if len(self.records) > self._keep:
            self.records = self.records[-self._keep:]
        if self._echo:
            hexs = f"  [{rec.raw.hex()}]" if rec.raw else ""
            print(f"{rec.ts} {rec.kind:5} {rec.device}  {rec.text}{hexs}",
                  file=self._stream)

    def tx(self, frame: DumlFrame, name: str = ""):
        self._emit(LogRecord("TX", _ts(), self.device_id,
                   f"{name or 'cmd'} set=0x{frame.cmd_set:02x} id=0x{frame.cmd_id:02x} "
                   f"seq={frame.seq} len={len(frame.payload)}", frame.encode()))

    def rx(self, frame: DumlFrame):
        self._emit(LogRecord("RX", _ts(), self.device_id,
                   f"ACK set=0x{frame.cmd_set:02x} id=0x{frame.cmd_id:02x} "
                   f"seq={frame.seq} len={len(frame.payload)}", None))

    def event(self, name: str, detail: str = ""):
        self._emit(LogRecord("EVENT", _ts(), self.device_id,
                   f"{name} {detail}".rstrip()))

    def dump(self) -> str:
        return "\n".join(
            f"{r.ts} {r.kind:5} {r.device}  {r.text}" for r in self.records)
