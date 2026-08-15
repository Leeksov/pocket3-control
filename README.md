# Osmo Pocket 3 — independent control SDK (interop research)

Reverse-engineering DJI Mimo (iOS) to build a minimal local control adapter for
a user-owned **DJI Osmo Pocket 3**. Interoperability / automation only.

## Status
- ✅ Architecture, transport, protocol mechanism fully recovered (`docs/`).
- ✅ DUML V1 codec — byte-exact CRC tables, CRC8 seed validated.
- ✅ Live-preview de-framer — faithful `DJILiveviewChannelSeparator` port (magic `00 00 01 FF`, 12-byte header, XOR8, 24-bit len, channel demux).
- ✅ Full SDK scaffold: device API, multi-cam manager, AI-facing adapter, state store, logger, CLI. **11/11 offline tests pass.**
- ✅ Commands: local DUML is **unencrypted** (no crypto handshake needed for control).
- 🟡 Numeric `cmd_set/cmd_id` + exact payload field maps — pending (see task 4). Commands raise `CommandUnresolved` until filled.

## Layout
```
docs/          findings & specs (architecture, protocol, commands, handshake, ios-mimo-analysis)
ida_targets/   binaries extracted for RE (DJIMidWare, DJIMimo, ilink_live, …)
research/      strings sweeps & symbol dumps
src/pocket3/
  protocol/    DUML V1 codec (duml.py, duml_tables.py)
  transport/   base, ble (bleak), wifi (SW_Pro scaffold)
  commands/    registry: 28 SendActionPack req-types + API command map
  state/       state + capability store, topic dispatch
  preview/     liveview de-framer + PreviewSession
  device.py    Pocket3Device — §20 API (record/expo/gimbal/zoom/preview/state)
  manager.py   CameraManager — multi-camera (§26)
  adapter.py   CameraController + Pocket3Adapter — vendor-neutral (§24)
  logger.py    protocol logger (§22)
  cli.py       pocket3 CLI (§19)
tools/         packet-decoder (+ logger, analyzer)
tests/         offline self-tests (DUML, liveview, device end-to-end)
```

## Try it now (no camera)
```bash
python3 tests/test_duml.py && python3 tests/test_liveview.py && python3 tests/test_device.py
```

## With a camera (once cmd_set/cmd_id are filled)
```bash
pip install -r requirements.txt
python3 -m pocket3.cli scan
python3 -m pocket3.cli record start --address <BLE-ADDR>
python3 -m pocket3.cli iso 400 --address <BLE-ADDR>
python3 -m pocket3.cli gimbal rotate --yaw -5 --address <BLE-ADDR>
python3 -m pocket3.cli preview start --address <BLE-ADDR>
```

## AI director integration (§24)
```python
from pocket3 import Pocket3Device, Pocket3Adapter
from pocket3.transport.ble import BleTransport
cam = Pocket3Adapter(Pocket3Device(BleTransport(addr)))
await cam.connect()
await cam.set_iso(640)      # vendor-neutral; adapter → DUML
await cam.recenter()
```

## Principle
Every command verifies via ACK / state read-back (brief §21). Unresolved commands
fail loudly (`CommandUnresolved`) rather than emit a wrong frame. Local control
needs no DJI account/cloud/crypto.

> Not affiliated with DJI. For controlling your own hardware.
