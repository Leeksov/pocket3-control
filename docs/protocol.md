# Pocket 3 Control Protocol Specification v0.1 (DUML V1)

Status legend: ✅ confirmed from binary/validated · 🟡 known-DJI default, to verify · ❓ unknown.

## Frame format ✅ (positions) / ✅ (CRC validated)
```
off  size  field
0    1     SOF = 0x55                                        ✅
1    2     ver_length (LE): length = v & 0x03FF (whole frame) ✅
                           version = (v >> 10) & 0x3F
3    1     CRC8(bytes[0..2], seed=0x77)                       ✅ validated
4    1     sender   = (dev_type & 0x1F) | (index<<5)          🟡
5    1     receiver = (dev_type & 0x1F) | (index<<5)          🟡
6    2     seq (LE)                                           ✅
8    1     cmd_type/flags (bit7=ack, bit5=enc — to verify)    🟡
9    1     cmd_set                                            ✅
10   1     cmd_id                                             ✅
11   n     payload                                            ✅
-2   2     CRC16(bytes[0..len-3], seed=0x3692, LE)            ✅ table/algo, 🟡 seed
```
Overhead = 13 bytes/frame.

### Validation done
- CRC8 table + seed `0x77`: header `55 0D 04` → `0x33` — matches canonical DJI DUML. ✅
- CRC tables `DjiCrc8Table`@0xb83a0, `DjiCrc16Table`@0xb84a0 extracted byte-exact from DJIMidWare. ✅
- Encoder/decoder round-trip + stream resync tested (`tests/test_duml.py`, 5/5). ✅

### Still to confirm (needs main-binary decompile of PackProviderImpl)
- CRC16 seed (0x3692 assumed — validate on a real reply).
- sender/receiver device-type numbers for app↔Pocket3.
- cmd_type bit meanings (ack request / encrypted).

## Message model ✅
- Request struct `dji::core::dji_cmd_req`, response `dji::core::dji_cmd_rsp`.
- Encoder `dji::crossplatform::PackProviderImpl`; decoder `dji::core::DjiProtocolDecoder::DecodeCommand`.
- Higher layer: keyed `dji::sdk` (`KeyHandlers`/`Characteristics`/`DJIValue`) + Action handlers.

## Command dispatch mechanism ✅
Every control command is dispatched as a C++ template send:
```
dji::sdk::key::SendActionPack<dji::core::<REQ_TYPE>>(
    IPackHandler*, dji_cmd_req& req, const Characteristics&, callback<RspType>, ...)
```
The `<REQ_TYPE>` IS the on-wire message identity. Full set (28) recovered from
RTTI in the main binary — see `src/pocket3/commands/registry.py::REQ_TYPES`.
P0 examples: `record_video_req` (REC), `take_photo_req`, `action_gimbal_set_reset_req`
(recenter), `set_gimbal_control_gimbal_speed_req` (pan/tilt), `set_camera_control_zoom_req`,
`liveview_transmit_ctrl`.

### REC command (`record_video_req`) — payload recovered, DUML-id pending
Handler `StartRecordAction`=sub_10206CD30 → builds `record_video_req` via ctor
sub_10206F0D0, wraps in `dji_cmd_req` (0xC8, vtable off_108E13358), sends via
`PackProviderImpl::SendData`. Payload default bytes + start overrides captured in
`registry.py::RECORD_VIDEO_REQ_DEFAULTS`.

## Command tables ❓ (cmd_set/cmd_id numbers)
Still numeric-unresolved. Each `<REQ_TYPE>`'s cmd_set/cmd_id are constants written
into `dji_cmd_req` by the `SendActionPack<T>` instantiation. Next: recover the
`dji_cmd_req` struct layout (offsets of cmd_set/cmd_id) via PackProviderImpl::SendData,
then read those offsets per REQ type.

## Transport binding
- BLE: service `FFF0`, write `FFF4` / notify `FFF5` / external `FFF3` 🟡 (order to verify).
  channel==4 → external characteristic (from `-[DJIServicePortBLE sendCommandData:commandChannel:]`).
- Wi-Fi: UDT reliable-UDP (`CUDT*`), separate video ServicePort.
- Wired: MFi (ExternalAccessory), `DJICommonMFIDataSeparator`.

## Session / handshake ❓
Crypto present (AES-CBC `dji_AES_cbc_encrypt`, RSA, MD5/SHA). Wi-Fi pairing via
`wifi_silent_trans_*` topics. Exact handshake sequence not yet decompiled.
