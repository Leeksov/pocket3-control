# DJI Mimo iOS — статический анализ (Stage 1)

App: **DJI Mimo v2.11.5** (AppAssassin decrypted IPA), iOS arm64.
Устройство-цель: **DJI Osmo Pocket 3**.
Дата: 2026-08-15.

---

## Что установлено (факты)

### 1. Архитектура приложения
- UI построен на **Flutter** (`Flutter.framework`, `App.framework` = скомпилированный Dart AOT, `handheld_flutter.framework` = мост Flutter↔native).
- Основная нативная логика связи с камерой — в **DJI-фреймворках** и в главном 176 MB бинаре `DJIMimo` (в него статически влинковано множество DJI-библиотек).
- Язык: смесь Objective-C (транспорт/протокол) + Swift (новые слои) + C/C++ (UDT, crypto, video).

### 2. Ключевые бинарники (скопированы в `ida_targets/`)
| Бинарь | Роль |
|---|---|
| `DJIMimo` (176 MB) | BLE-транспорт (`DCSBLE*`), connection/pairing flow, приложение |
| `DJIMidWare` (2.5 MB) | **Транспорт + сессия + crypto**: DJIServicePort*, DJIServiceManager, UDT, DUML CRC |
| `ilink_live` (9 MB) | link-транспорт + live preview (видео) |
| `GrandSerializer` (212 KB) | сериализация |
| `HandheldUIKit` (2.5 MB) | высокоуровневые camera-manager вызовы |
| `App` (Dart) | ViewModel/UI логика команд |

### 3. Реально используемые Apple-фреймворки (imports главного бинаря)
- **CoreBluetooth** — BLE discovery/connect (в главном бинаре).
- **ExternalAccessory** — проводное MFi-подключение (`EAAccessoryDidConnect/Disconnect`).
- **Network.framework / CFNetwork** + BSD sockets (`socket/connect/sendto/recvfrom`) — Wi-Fi канал.
- **NetworkExtension** — управление Wi-Fi (подключение к SoftAP камеры).
- **VideoToolbox / CoreMedia / AVFoundation / Metal** — декодирование и рендер live preview (H.264/H.265).
- **Security + CommonCrypto** — RSA (`SecKeyEncrypt/Decrypt`), AES (`dji_AES_cbc_encrypt`), MD5/SHA.

### 4. Транспортный слой (в DJIMidWare) — ПОДТВЕРЖДЁН
Единый диспетчер:
```
-[DJIServiceManager sendCommandData:commandChannel:]   @0x54e38
    → -[DJIServiceManager currentServicePort]
        → -[DJIServicePort sendCommandData:commandChannel:]   (полиморфно по среде)
```
Подклассы `DJIServicePort` (абстракция транспорта по средам):
| Класс | Среда |
|---|---|
| `DJIServicePortBLE` | Bluetooth LE (`DJIBLEService writeData:` / `writeExternalData:`) |
| `DJIServicePortMFI` | проводной MFi (ExternalAccessory) |
| `DJIServicePortUSB` | USB |
| `DJIServicePortUDT`, `DJIServicePortUDT_WM220` | Wi-Fi reliable-UDP (UDT) |
| `DJIServicePortTCP_WM100`, `DJIServicePortSW_WM100` | Wi-Fi TCP (старые дроны) |
| `DJIServicePort2014` | протокол «2014» (DUML v1) поверх MFi common service |

`commandChannel` (a4) кодирует канал: значение `4` = external-канал (BLE `writeExternalData:`).

### 5. Очередь и модель команды
- `-[DJIAsyncCommandQueue pushCommand:withOption:]` @0x1d2d8 — асинхронная очередь; команда-объект имеет `tag`, `cancelMark`; опции: bit0=insert-front (приоритет), bit1=cancel-previous-with-same-tag. Runloop с таймаутом (`runloopWithTimeOutMS:`) = механизм ACK/timeout/retry.
- `DJIAdvancedQueue`, `DJICirularQueue` — низкоуровневые буферы.
- Каждый канал/камера имеет собственную очередь → архитектура уже мульти-девайсная (соответствует требованию мульти-Pocket3).

### 6. DUML framing (протокол «V1 / 2014») — ПОДТВЕРЖДЁН частично
- Пакер/парсер оперируют полями **CmdSet / CmdId / Seq / Length** (сигнатура `...WithCmdSet:withCmdId:withSeq:withLength:`).
- Контрольные суммы (точные функции DUML):
  - `DjiCalcChecksumCrc8` / `DjiAppendChecksumCrc8` / `DjiVerifyChecksumCrc8` — CRC8 заголовка.
  - `DjiCalcChecksumCrc16` @0x28c2c — CRC16 всего пакета, таблично (`DjiCrc16Table`).
  - `DjiCalcChecksumXor8/Xor32` — XOR-контрольки (используются в video-канале).

### 7. Live preview framing — ПОДТВЕРЖДЁН
`DJILiveviewChannelSeparator` (@0x36d28…): потоковый разборщик видео.
- `findMagic:len:` → `checkHeader` → `sendDataToChannel:data:len:`.
- Заголовок кадра: **12 байт**, проверка `DjiCalcChecksumXor8(header,12)==0`.
- Длина полезной нагрузки: **24 бита** (`lengthData[0..2]`), максимум `0x200000` (2 MB на кадр).
- Мультиплексирование по `channelID` (несколько логических потоков в одном транспорте).

### 8. Discovery-компоненты
- `DJIMBonjourDataSeparator` (`parseData:length:`, `packedData:`) — **mDNS/Bonjour** discovery + framing поверх сети.
- `DJIBLECentralManager` / `DCSBLECentralManager` — BLE scan/connect.
- BLE-сервис DJI: **UUID `FFF0`**, характеристики **`FFF3/FFF4/FFF5`** (в главном бинаре, кластер @0x7920333). Модель: `serviceUUID` + `writeCharacteristic`(FFF4?) + `notifyCharacteristic`(FFF5?) + `externalCharacteristic`(FFF3?) + отдельный OTA-сервис (`dmOTA*`).
- BLE несёт обмен Wi-Fi-конфигом для livestream (`LiveStream-BLEWiFiConfigFetchingLogic`) + fallback NFC auth flow.

---

## Чем подтверждено
IDA-декомпиляция `ida_targets/DJIMidWare` (instance 3vfb): функции по адресам выше; strings главного бинаря `DJIMimo` (BLE UUID кластер, DCSBLE* классы).

## Что предполагается (гипотезы, не факт)
- Полный DUML-кадр: `55 | len(13b)+ver(3b) | crc8 | src | dst | seq(2) | cmdtype | cmdset | cmdid | payload | crc16(2)` — классический формат DJI; **точные смещения ещё не извлечены из пакера** (пакер-функция в DJIMidWare не самоочевидна — вероятно в главном бинаре/ilink_live либо в объекте команды).
- Соответствие FFF4=write / FFF5=notify / FFF3=external — по типовому профилю DJI, порядок нужно сверить с кодом `DCSBLEService`.
- Основной канал управления Pocket 3 — Wi-Fi (UDT) для видео + BLE для discovery/wake/control; проводной MFi при подключении кабелем. Нужно доказать, какой канал несёт команды при беспроводном коннекте.

## Что неизвестно (открытые вопросы)
1. Точный байтовый layout DUML-кадра (нужна функция-сборщик).
2. Таблицы CmdSet/CmdId для Pocket 3 (значения enum'ов).
3. Реальные значения UUID характеристик (write/notify) — сверить порядок.
4. Механизм pairing/handshake (nonce, session id, RSA/AES обмен ключами).
5. Где именно строится команда: ObjC-объект vs Dart vs C — цепочка `setISO(400) → …`.
6. Динамика (реальные пакеты) — **невозможна без физической камеры + MITM/Frida на устройстве**; сейчас только статика.

## Следующий эксперимент (один, самый информативный)
Найти **функцию-сборщик DUML-кадра**: извлечь `DjiCrc16Table` и найти все её xref по всем бинарям (`DJIMidWare` их почти не имеет → искать в главном `DJIMimo` и `ilink_live`). Функция, которая пишет `0x55`, затем длину, затем зовёт CRC16 — это сериализатор. От неё вверх по call-graph выйдем на `Command`-объект и таблицы CmdSet/CmdId.
