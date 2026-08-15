"""Camera state + capability store (brief §18, §23).

Holds the latest value of each subscribed topic (push) and the camera-advertised
capability ranges. Commands verify against this store (read-back, brief §21).

Topic->(cmd_set,cmd_id) numbers are pending; until then pushes are keyed by
their raw (cmd_set,cmd_id) and, once the mapping is filled in TOPIC_IDS, exposed
under their friendly name.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..protocol.duml import DumlFrame

# name -> (cmd_set, cmd_id); fill as recovered. Empty for now (unknown numbers).
TOPIC_IDS: Dict[str, Tuple[int, int]] = {}


@dataclass
class TopicValue:
    name: str
    raw: bytes
    ts: float
    parsed: Any = None


class StateStore:
    def __init__(self):
        self._by_id: Dict[Tuple[int, int], TopicValue] = {}
        self._by_name: Dict[str, TopicValue] = {}
        self._caps: Dict[str, Any] = {}
        self._subs: Dict[str, List[Callable[[TopicValue], None]]] = {}
        self._id_to_name = {v: k for k, v in TOPIC_IDS.items()}

    def ingest(self, frame: DumlFrame):
        key = (frame.cmd_set, frame.cmd_id)
        name = self._id_to_name.get(key, f"0x{frame.cmd_set:02x}:0x{frame.cmd_id:02x}")
        tv = TopicValue(name=name, raw=frame.payload, ts=time.time())
        parser = _PARSERS.get(name)
        if parser:
            try:
                tv.parsed = parser(frame.payload)
            except Exception:
                tv.parsed = None
        self._by_id[key] = tv
        self._by_name[name] = tv
        for cb in self._subs.get(name, []):
            cb(tv)
        return tv

    def get(self, name: str) -> Optional[TopicValue]:
        return self._by_name.get(name)

    def subscribe(self, name: str, cb: Callable[[TopicValue], None]):
        self._subs.setdefault(name, []).append(cb)

    # capability store (§18) — do not hardcode; read from *_capability / *RangeMsg
    def set_capability(self, name: str, value: Any):
        self._caps[name] = value

    def capability(self, name: str) -> Any:
        return self._caps.get(name)

    def snapshot(self) -> Dict[str, Any]:
        return {n: (tv.parsed if tv.parsed is not None else tv.raw.hex())
                for n, tv in self._by_name.items()}


# Payload parsers per topic — fill field layouts as recovered from the
# dji_topic_data_* structs. Signature: bytes -> dict.
_PARSERS: Dict[str, Callable[[bytes], Any]] = {}


def register_parser(name: str):
    def deco(fn):
        _PARSERS[name] = fn
        return fn
    return deco
