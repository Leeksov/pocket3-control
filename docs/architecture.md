# Pocket 3 Control — восстановленная архитектура (v0.2)

Источник: статический анализ DJI Mimo v2.11.5 (IDA: `DJIMidWare`=3vfb, `ilink_live`=tet3; strings главного `DJIMimo`).

## Ключевой вывод
Всё управление камерой реализовано **кросс-платформенным C++ SDK DJI**, влинкованным в главный бинарь `DJIMimo`, с полными (немаскированными) символами. Пространства имён: `dji::core`, `dji::sdk`, `dji::crossplatform`. Модель — **keyed / topic pub-sub поверх DUML**.

⚠️ `ilink_live.framework` — это **не** управление камерой, а сетевой стек Tencent/WeChat **mars** для облачного лайвстрима (视频号/Finder, RTMP). По ТЗ §27 — игнорируем.

## Вертикальный путь команды (восстановлен)
```
Flutter UI (Dart, App.framework)
   │  method-channel → handheld_flutter.framework
   ▼
dji::sdk  Key/Action слой
   KeyHandlers + Characteristics + DJIValuePtr + ActionCallback
   (напр. StartRecordAction, RotateByAngleNewAction, ResetGimbalAction)
   │
   ▼
dji::core  модель сообщения
   dji_cmd_req  ──serialize──►  PackProviderImpl (DUML frame builder)
   │                             (cmdset/cmdid/seq/payload + CRC8/CRC16)
   ▼
dji::core  DataLink транспорт
   BaseDataLinkServiceMgr → выбор ServicePort по DatalinkType
   DataLinkDirectSender::SendData / DataLinkServiceFactoryImpl::SendBLEDataWithType
   │
   ▼  (ObjC мост в DJIMidWare)
-[DJIServiceManager sendCommandData:commandChannel:]
   → DJIServicePort{BLE|MFI|USB|UDT|TCP}  →  writeData:
   │
   ▼
Bluetooth LE (FFF0/FFF4/FFF5)  ИЛИ  Wi-Fi (UDT reliable-UDP)  ИЛИ  проводной MFi
   │
   ▼
        Osmo Pocket 3
   │
   ▼  ответ / ACK / push
DjiProtocolDecoder::DecodeCommand  →  dji_cmd_rsp
   → topic push (SingleDeviceStateProvider::ListenPack<...>)
   → обновление состояния → KVO/Rx → UI
```

## Транспорт (DatalinkType)
| Среда | Классы | Роль |
|---|---|---|
| **BLE** | `DataLinkServiceFactoryImpl` (`StartBLEScan`, `ConnectBLE`, `SendBLEDataWithType`, `GetConnectedBLEPeripheral`), ObjC `DCSBLECentralManager`/`DCSBLEService`, `DJIServicePortBLE` | discovery, wake, обмен Wi-Fi-конфигом, команды |
| **Wi-Fi (UDT)** | `CUDT*` (reliable UDP), `DJIServicePortUDT` | команды + видео + телеметрия при беспроводном коннекте |
| **Проводной MFi** | ExternalAccessory, `DJIServicePortMFI`, `DJICommonMFIDataSeparator` | всё по кабелю |
| **USB** | `DJIServicePortUSB` | всё по USB |

`BaseDataLinkServiceMgr` держит карту ServicePort'ов (обычные + video-порты) и умеет `StartServicePortWithType` / `UpdateVideoPortId` — т.е. отдельный порт под видеопоток.

## Discovery
- **BLE scan** (`DataLinkServiceFactoryImpl::StartBLEScan`, `DCSBLECentralManager`) — основной путь для Pocket 3.
- **Bonjour/mDNS** (`DJIMBonjourDataSeparator`) — для сетевого обнаружения.
- **Wi-Fi silent transmission pairing** (`wifi_silent_trans_pairing_push`, `wifi_silent_backhaul_pairing_status_push`) — пейринг по Wi-Fi.

## Live preview
- Разборщик кадров: `DJILiveviewChannelSeparator` — header 12 байт, XOR8-контроль, 24-битная длина (≤2 MB), мультиплекс по channelID.
- Кодек/параметры: topic `dji_topic_data_camera_cam_video_codec`, декод — VideoToolbox (H.264/H.265).
- Отдельный video ServicePort (`OnServicePortVideoAdded` / `UpdateVideoPortId`).

## Session / handshake (частично)
- `DjiProtocolDecoder::DecodeCommand` — вход парсера.
- Crypto: `dji_AES_cbc_encrypt`, RSA (`SecKeyEncrypt/Decrypt`), MD5/SHA — для аутентификации сессии/OTA.
- `wifi_silent_trans_config_push` / `wifi_silent_trans_status_push` — конфигурация защищённого Wi-Fi-канала.
- Точный handshake (nonce/session-id/обмен ключами) — **ещё не декомпилирован**.
