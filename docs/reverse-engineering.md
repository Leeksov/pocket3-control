# DJI Mimo / Osmo Pocket 3 — Reverse Engineering Reference

Single-source reference of the artifacts behind this project: app version,
binaries, IDA instances, and every function/data address recovered so far.

> Addresses are given as **RVA** (offset from image base) where possible so they
> stay valid regardless of ASLR slide. For the main binary the loaded VA =
> `0x100000000 + RVA`. For DJIMidWare the image base is `0x0`, so RVA == VA.

---

## 1. Application

| Field | Value |
|---|---|
| App | **DJI Mimo for iOS** |
| Version | **v2.11.5** |
| Package | `_ DJI Mimo_v2.11.5-AppAssassin.ipa` (decrypted, AppAssassin) |
| Bundle | `Payload/DJIMimo.app` |
| Main executable | `DJIMimo` — Mach-O 64-bit arm64, 176,671,520 bytes |
| UI stack | Flutter/Dart (`App.framework` AOT, `Flutter.framework`, `handheld_flutter.framework`) |
| Camera stack | C++ SDK `dji::core` / `dji::sdk` / `dji::crossplatform` (baked into main binary) + `DJIMidWare.framework` |
| Target device | DJI Osmo Pocket 3 |

Apple frameworks actually used for camera link: **CoreBluetooth** (BLE),
**ExternalAccessory** (wired MFi), **Network/CFNetwork + BSD sockets** (Wi-Fi),
**NetworkExtension** (join SoftAP), **VideoToolbox/CoreMedia/AVFoundation/Metal**
(preview decode), **Security/CommonCrypto** (cloud/DRM only — not the command link).

---

## 2. Binaries extracted (`ida_targets/`)

| Binary | Size | Role | Notes |
|---|---|---|---|
| `DJIMimo` | 176,671,520 | main app; C++ dji::core SDK, BLE stack, command handlers | image base `0x100000000` |
| `DJIMidWare` | 2,501,040 | transport + session + DUML checksums + UDT + liveview de-framer | image base `0x0`; md5 `51e4de968e4ffd481b25848d4f8ea322`; sha256 `453570ed…31e9d`; 6,615 funcs |
| `ilink_live` | 9,080,208 | **EXCLUDED** — Tencent/WeChat `mars` cloud livestream (视频号/RTMP), not camera | md5 `a9e09539…7fc08`; sha256 `d293e507…167a91`; 23,832 funcs |
| `GrandSerializer` | 212,704 | serialization helpers | |
| `HandheldUIKit` | 2,540,336 | high-level camera manager / UI glue | |
| `handheld_flutter` | 115,760 | Flutter↔native command bridge | |
| `App` (Dart) | 8,609,680 | compiled Dart UI/ViewModel logic | |
| `DJIFileSystem` | 252,992 | media/SD access | |
| `CameraAssetHTTPRequestBuilder` | 197,360 | HTTP media/thumbnails | |
| `lightShared` | 5,344,784 | shared DJI logic | |

`ilink_live` exclusion evidence — embedded source paths:
`.../ilink-network/marswrapper/{long,short}link_packer.cc`,
`micromsg-bin/ilink_findercreatelive`, `mars3cdn`, `mmspeedtest.pb.cc`.

---

## 3. IDA instances (MCP)

| instance_id | binary | base | notes |
|---|---|---|---|
| `wzxu` | DJIMimo (main) | `0x100000000` | auto-analysis complete |
| `3vfb` | DJIMidWare | `0x0` | |
| `tet3` | ilink_live | — | excluded from camera analysis |

---

## 4. DUML protocol — DJIMidWare (`3vfb`, RVA == VA)

### Checksums (frame integrity)
| Function | Addr | Purpose |
|---|---|---|
| `DjiCalcChecksumXor8` | `0x28b30` | XOR8 (used by liveview header) |
| `DjiCalcChecksumXor32` | `0x28b58` | XOR32 |
| `DjiCalcChecksumCrc8` | `0x28b8c` | header CRC8 (table lookup, seed arg) |
| `DjiAppendChecksumCrc8` | `0x28bb8` | |
| `DjiVerifyChecksumCrc8` | `0x28bf0` | |
| `DjiCalcChecksumCrc16` | `0x28c2c` | whole-frame CRC16 (table) |
| `DjiAppendChecksumCrc16` | `0x28d60` | |
| `DjiVerifyChecksumCrc16` | `0x28da4` | |

### Data tables (extracted verbatim → `src/pocket3/protocol/duml_tables.py`)
| Symbol | Addr | Content |
|---|---|---|
| `DjiCrc8Table` | `0xb83a0` | 256 bytes |
| `DjiCrc16Table` | `0xb84a0` | 256 × uint16 (LE) |
| `g_dji_live_view_channel_magic` | `0xb86f8` | `00 00 01 FF` |

**Validated seeds:** CRC8 seed `0x77` → header `55 0D 04` yields `0x33` (matches
canonical DJI DUML). CRC16 seed `0x3692` (to re-confirm on a live reply).

### Frame format (DUML V1 / "2014")
```
55 | ver_length(2,LE: len=v&0x3FF, ver=v>>10) | CRC8(hdr,seed77)
   | sender | receiver | seq(2) | cmd_type | cmd_set | cmd_id | payload | CRC16(2,seed3692)
```

---

## 5. Transport — DJIMidWare (`3vfb`)

| Function / class | Addr | Role |
|---|---|---|
| `-[DJIServiceManager sendCommandData:commandChannel:]` | `0x54e38` | unified TX dispatcher → currentServicePort |
| `-[DJIServicePortBLE sendCommandData:commandChannel:]` | `0x59488` | BLE (writeData: / writeExternalData:, channel 4=external) |
| `-[DJIServicePort2014 sendCommandData:commandChannel:]` | `0x5890c` | 2014/DUML over MFi common service |
| `-[DJIServicePortUDT sendCommandData:commandChannel:]` | `0x5aa1c` | Wi-Fi reliable-UDP |
| `-[DJIServicePortMFI …]` / `…USB…` | (class) | wired / USB |
| `-[DJIAsyncCommandQueue pushCommand:withOption:]` | `0x1d2d8` | per-channel cmd queue (ACK/retry via runloopWithTimeOutMS:) |

### BLE (DJIMidWare-level)
| Function | Addr |
|---|---|
| `-[DJIBLECentralManager checkSystemConnectedPeripherals]` | `0x20dd4` |
| `-[DJIBLECentralManager connectPeripheral:]` | `0x21604` |
| `-[DJIBLECentralManager centralManager:didConnectPeripheral:]` | `0x21a6c` |

BLE profile (main binary `DJIMimo`, strings **file offset** `0x7920333`):
service **FFF0**, chars **FFF5 / FFF4 / FFF3** (notify / write / external) + OTA
(`dmOTA*`). Classes: `DCSBLECentralManager`, `DCSBLEService`, `DCSBLEPortSinglton`.

### UDT (reliable UDP, Wi-Fi)
| Function | Addr |
|---|---|
| `CUDT::connect(sockaddr)` | `0x1525c` |
| `CUDT::connect(CPacket)` | `0x15884` |
| `CUDT::connect(sockaddr,CHandShake)` | `0x15db8` |
| `CUDT::packData(CPacket,uint64)` | `0x19064` |
| `CChannel::sendto` | `0x1362c` |
| `CChannel::recvfrom` | `0x13724` |

### Discovery / separators
| Function | Addr |
|---|---|
| `-[DJIMBonjourDataSeparator parseData:length:]` | `0x3c74c` |
| `-[DJIMBonjourDataSeparator packedData:]` | `0x3ca50` |
| `-[DJICommonMFIDataSeparator parseBuffer:length:completion:]` | `0x28e40` |

---

## 6. Live preview — DJIMidWare (`3vfb`)

| Function | Addr |
|---|---|
| `-[DJILiveviewChannelSeparator init]` | `0x36d28` |
| `-[DJILiveviewChannelSeparator push:length:]` | `0x36da4` |
| `-[DJILiveviewChannelSeparator findMagic:len:]` | `0x36f5c` |
| `-[DJILiveviewChannelSeparator checkHeader]` | `0x36fe0` |
| `-[DJILiveviewChannelSeparator sendDataToChannel:data:len:]` | `0x37048` |

Header layout (object-relative; header at `obj+8`, 12 bytes, `XOR8==0`):
`headPos@obj+0x18`, `dataSize@obj+0x1C`, length low16 `@obj+0xC` (header+4),
length high8 `@obj+0xF` (header+7), `channelID` header+6.
→ `dataSize = h[4] | h[5]<<8 | h[7]<<16` (≤ `0x200000`). Magic `00 00 01 FF`.
Port: `src/pocket3/preview/liveview.py`.

---

## 7. Command layer — main binary `DJIMimo` (`wzxu`, VA = 0x100000000+RVA)

### Dispatch mechanism (confirmed)
Every control command = `dji::sdk::key::SendActionPack<dji::core::<X_req>>(IPackHandler*, dji_cmd_req&, Characteristics&, cb<RspType>, …)`
→ `dji::crossplatform::PackProviderImpl::SendData(uint64, const dji_cmd_req&, cb, cb)`.

### REC command (`record_video_req`) — fully traced
| Symbol | Addr (VA) | Notes |
|---|---|---|
| `StartRecordAction` | `0x10206CD30` | RTTI name string @ `0x10796A587` |
| `record_video_req` ctor | `0x10206F0D0` | sets payload defaults |
| send/build wrapper | `0x10206DCE0` | allocates 0xC8 `dji_cmd_req`, vtable `off_108E13358` |
| `dji_cmd_req` move-ctor | `0x10206F5E4` | string fields @ off 32/112/152/184 |
| vtable `off_108E13358` | `0x108E13358` | record_video_req IPackHandler; methods `sub_10206F16C/…288/…3A4/…3FC/…41C/…544/…558/…568/…5D8` |
| RTTI `SendActionPack<record_video_req>` | str @ `0x107D5CC50` / `0x107D5CD71` | |

**`record_video_req` payload** (from ctor + StartRecord overrides):
ctor defaults `[0..3]=01 01 02 02`, `[5..8]=02 00 00 03`, `[12..13]=0x574D ('WM')`,
`[20..23]=500`, `byte[6]=runtime device id`; START overrides `[+2]=0x02`,
`[+4]=0x03`, `[+7]=0x01`. → `src/pocket3/commands/registry.py::RECORD_VIDEO_REQ_DEFAULTS`.

### Gimbal
| Symbol | Addr (VA) | Notes |
|---|---|---|
| `RotateByAngleNewAction` | `0x10214C73C` | casts DjiValue → `dji::sdk::ControlGimbalAngle`; RTTI str @ `0x10797A9CC` |

### Full command req-type map (28) — RTTI sweep
`record_video_req, take_photo_req, set_camera_control_zoom_req,
set_gimbal_control_gimbal_speed_req, action_gimbal_set_reset_req,
action_gimbal_system_param_operate_req, action_gimbal_auto_calibration,
action_gimbal_time_lapse_control_pack, gimbal_feature_control_pack,
set_gimbal_turn_on_off_pack, gimbal_send_gps_nav_data_pack,
liveview_transmit_ctrl, set_live_view_camera_source_new_pack,
camera_playback_action_pack, format_sdcard_req, gui_service_cmd_pack,
gui_service_cmd_param_get_pack, gui_service_cmd_param_set_pack,
wifi_start_req, wifi_stop_req, wifi_restart_req,
wifi_silent_trans_report_status_pack, audio_wireless_mic_set_audio_pack,
audio_wireless_mic_set_params_pack, ble_nfc_read_write_pack,
rc_ios_screen_mirroring_pack, log_export_change_state_pack,
general_accesslocker_query_state_pack`.
Extended set (166 `_req` total incl. `set_iso_req`, `set_camera_shutter_speed_req`,
`set_camera_exposure_mode_req`, `set_camera_exposure_compensation_req`,
`set_camera_white_balance_req`, `set_camera_video_format_req`, …) in
`research/strings/` and `docs/commands.md`.

**⚠ Numeric `cmd_set`/`cmd_id` are NOT present** as strings or IDB structs — they
are set by templated C++ through a runtime-polymorphic `SendData`. Last-mile
numbers are best captured **dynamically** (BLE/USB sniff or Frida hook on
`-[DJIServiceManager sendCommandData:commandChannel:]`).

---

## 8. Crypto / session — DJIMidWare (`3vfb`)

**Local DUML commands are UNENCRYPTED** (integrity = CRC8/XOR only; the send path
invokes no AES/RSA). AES/RSA are for cloud SDK activation + DRM cert only.

| Function | Addr | Purpose |
|---|---|---|
| `dji_AES_set_encrypt_key` | `0x6c50` | OpenSSL-derived AES (donor) |
| `dji_AES_set_decrypt_key` | `0x6f2c` | |
| `dji_AES_cbc_encrypt` | `0x7824` | |
| `dji_white_box_decrypt` | `0x1afac` | white-box AES (cert DRM only) |
| `WAES_decrypt` | `0x9ae84` | |
| `DJIGetCertificateData` | `0x5f170` | SHA256-verified cert decrypt |
| `-[NSData AES256EncryptWithKey:initVector:]` | `0x81c40` | AES-256 PKCS7 (cloud) |
| `+[DJIKeyGenerator randomAES256Key]` | `0x33c34` | arc4random_buf(32)→base64 |
| `+[DJIRegistInfo createUrlRequestWithKey:otherInfo:]` | `0x4f71c` | encrypts app_key/uuid → dev.dji.com/sdk |
| `DJI_RSA_verify` | `0x92aa4` | signature verify (cloud) |
| `dji_RSA*` | `0x83b54`+ | |

### White-box AES — structural analysis (no key extraction)
Scope: DRM path only (decrypts the embedded activation certificate). Documented
for research; **no key recovery / no DRM bypass performed**. Commands do not use it.

Call chain: `dji_white_box_decrypt` `0x1afac` → `WAES_decrypt` `0x9ae84`
→ `WAES_decrypt_real` `0x9adac` (helpers `shift_rows_inverse`, `mix_shift`).

**Mode:** AES-128 **CBC** + PKCS7. `dji_white_box_decrypt(ct, size, &out, iv)`
loops 16-byte blocks: `WAES_decrypt(block)` → `veor` with previous ciphertext
(IV for block 0) → PKCS7 unpad (last byte < 0x11, returns `size - pad`).

**Cipher core `WAES_decrypt_real(in, out, t_box)`** — classic Chow-style white-box:
1. `shift_rows_inverse(in → tmp[16])`.
2. Round 0: `out[i] = t_box[i*256 + tmp[i]]` (16 byte-indexed T-boxes).
3. Rounds 1..9: `mix_shift(out → tmp)` (MixColumns∘ShiftRows) then
   `out[i] = t_box[4096*round + i*256 + tmp[i]]`.
4. **10 rounds total → AES-128.**

**T-box table `t_box` @`0x10cd00`** (`__data`): `10 rounds × 16 positions × 256`
= **40,960 bytes** (`0x10cd00`–`0x116d00`). First bytes: `66 E1 15 36 44 BC 5E 8E …`.

**Structural notes (facts, not a break):**
- Round keys are folded into the T-boxes (inherent to white-box) — not extracted here.
- MixColumns is computed in code (`mix_shift`), not tabled.
- No external input/output encodings on the block I/O (CBC XOR is plaintext),
  i.e. a comparatively light white-box — T-box key-folding only.
- Consumer: `DJIGetCertificateData` `0x5f170` (SHA256-verified cert). Not on the
  camera command path (commands are unencrypted).

### Wi-Fi session "SW_Pro" (reliable UDP)
| Function | Addr | Purpose |
|---|---|---|
| `SW_Pro_Add_Header_And_Send` | `0x97ce4` | builds 8-byte header (flag+14b len, link/session id, seq, type, SW_CheckSum) |
| `SW_Pro_Gnd_Entry_Start` | `0x96f40` | link bring-up: random session id + seq seed, recv + keepalive threads |
| `SW_Pro_Gnd_Manage_Recv_Run` | `0x981b4` | recv FSM (type 0=connect,1=data/ack,2/3=link-data), windowed ARQ |
| `CHandShake` (UDT) | `0x8a7b8` | UDT handshake (debug-bridge/screen-mirror, not command crypto) |

Details: `docs/handshake.md`.

---

## 9. Open items (need dynamic capture with the physical camera)
1. Numeric `cmd_set`/`cmd_id` per req-type (esp. `record_video_req` = P0).
2. Exact payload field maps for exposure/gimbal req types.
3. CRC16 seed confirmation on a real reply; sender/receiver device ids; cmd_type bits.
4. SW_Pro header bitfield packing + checksum polynomial.
5. BLE FFF4/FFF5 write/notify order confirmation.
