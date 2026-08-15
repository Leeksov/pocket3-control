# Handshake / сессия / крипто-слой (DJIMidWare)

Анализ фреймворка **DJIMidWare** (IDA-инстанс `3vfb`). Цель — задокументировать легитимный
механизм установления сессии и аутентификации/шифрования данных. Никакого обхода защиты, только
структура штатного протокола. Все адреса — file offset из этого модуля.

---

## Что установлено

### 1. Крипто-примитивы (AES)

В бинаре присутствуют **три независимых** AES-стека:

**(a) OpenSSL-производный AES (`_dji_AES_*`)** — стандартная реализация rijndael на таблицах.
- `_dji_AES_set_encrypt_key` `0x6c50`, `_dji_AES_set_decrypt_key` `0x6f2c`
  (decrypt-key просто вызывает encrypt-key `0x6f3c`, затем разворачивает раундовые ключи и
  применяет InvMixColumns через таблицы `Td0..Td3`/`Te4` — канонический OpenSSL-код).
- `_dji_AES_encrypt` `0x7164`, `_dji_AES_decrypt` `0x74c4`.
- `_dji_AES_cbc_encrypt` `0x7824` — CBC-обвязка: IV в аргументе `a5`, режим (enc/dec) в `a6`,
  ключ (развёрнутые раунды) в `a4`. Классический CBC: `P ^ IV -> AES -> C`, IV обновляется
  последним блоком. Прямых xref внутри модуля нет (вызывается по указателю/из других фреймворков).

**(b) White-box AES (`WAES` / `_dji_white_box_decrypt` `0x1afac`)** — CBC-decrypt поверх
white-box-таблиц (`_WAES_decrypt` `0x9ae84`). Снимает PKCS-подобный паддинг (последний байт =
длина паддинга, отбрасывает если > 0x10). IV передаётся в `a4`; в вызовах используется
зашитая константа `xmmword_B87E0`.
- Используется **только** для расшифровки встроенного сертификата/лицензии:
  `_DJIGetCertificateData` `0x5f170` расшифровывает два блока white-box'ом и сверяет
  `CC_SHA256(data)` с расшифрованным дайджестом (integrity-проверка сертификата).
  Также используется в обфусцированной `_d080c83b543de264dab5a46be59db35` `0x67134`.
- Это DRM/сертификат, **не** канал команд.

**(c) Apple CommonCrypto (`CCCrypt`) через категорию NSData** — прикладное шифрование.
- `-[NSData AES256EncryptWithKey:initVector:]` `0x81c40` и `...Decrypt...` `0x81de0`:
  `CCCrypt(op, alg=0 (kCCAlgorithmAES), options=1 (kCCOptionPKCS7Padding), key, keyLength=0x20,
  iv=...)`. **AES-256, PKCS7**. Ключ читается как C-строка `getCString:maxLength:33 encoding:4`
  (NSUTF8) → 32 байта. Если IV не задан (`a4==nil`) — IV отсутствует (по сути ECB-подобно для
  первого блока), иначе первые ≤16 байт строки IV.
- Также есть AES128 (`0x820b8`/`0x81f78`) и общий диспетчер
  `-[NSData dataEncryptedUsingAlgorithm:key:initializationVector:options:error:]` `0x8301c`
  (плюс DES/CAST — `0x82cf0`/`0x82e00`).

### 2. Генерация ключей / RSA

- `+[DJIKeyGenerator randomAES256Key]` `0x33c34`: `arc4random_buf(32)` → base64 → `substringToIndex:32`
  (32-символьный ключ).
- `+[DJIKeyGenerator genKeyWithKeyInfo:]` `0x33d64`: берёт 15-байтовую структуру keyInfo, шифрует
  `djiAES256EncryptWithKey:` ключом из обфусцированной `d60a024daa947631a20350e042(36)`, затем
  прогоняет через подстановочные таблицы `off_1054B8` → печатаемая строка-ключ.
- RSA-набор: `-[NSData dji_RSAEncryptWithPublicKeyInDER:]` `0x83b54`,
  `dji_RSADecryptWithPrivateKeyInP12:usingPassword:` `0x83c4c`,
  `dji_RSASignWithPrivateKeyInP12:usingPassword:` `0x83d40`,
  `dji_RSAVerifyWithPublicDER:andSignature:` `0x83eb4`,
  `dji_RSASHA256VerifyWithSignature:publicKey:` `0x84150`, `_DJI_RSA_verify` `0x92aa4`.
  Используется для проверки подписей (облако/сертификаты), не для канала команд.

### 3. Облачная активация (где реально применяется AES-256)

- `+[DJIRegistInfo createUrlRequestWithKey:otherInfo:]` `0x4f71c`: собирает строку
  `app_key=...,uuid=...,platform=2,level=3,packageid=...[,info=<json>]`, шифрует
  `djiAES256EncryptWithKey:` (ключ из `d60a024daa947631a20350e042(33)` — зашитый секрет SDK),
  base64+url-escape, POST на `https://dev.dji.com/sdk?app_key=...&data=...`.
- Это регистрация/активация SDK в облаке DJI. AES-256 command-layer применяется **здесь**, а не
  на линке с камерой.

### 4. Транспорт сессии / «handshake»

В модуле два транспортных стека, оба со своим понятием «сессии»:

**(A) UDT (UDP-based Data Transfer)** — C++-библиотека `CUDT`/`CUDTUnited`/`CHandShake`.
- `CHandShake::serialize/deserialize` `0x8a7b8`/`0x8a83c`, `CUDT::connect(...CHandShake*)` `0x15db8`,
  `CUDTUnited::newConnection` `0x8400`. Полноценный UDT-хендшейк (SYN/cookie, seq, MTU).
- В DJIMidWare это транспорт для **debug-bridge / screen-mirroring по сети** (см.
  `enterDebugMode...`, `setupWSBridge`), а не крипто-хендшейк с устройством. Шифрования нет.

**(B) «SW_Pro» (DUSS/Pro) — собственный надёжный UDP-протокол DJI** (screen-mirroring/контроль).
- Формат кадра строит `_SW_Pro_Add_Header_And_Send` `0x97ce4`, 8-байтовый заголовок:
  - word0 = `(len+8) & 0x3FFF | 0x8000` — бит15 = флаг, биты0..13 = длина;
  - word1 = `a5` (id линка/сессии);
  - word2 = seq (`*a6`);
  - первые 3 слова конвертируются в LE (`SW_Conv_Little_Endian_Array_16(...,3)`);
  - byte6 = тип (control): 0 = запрос соединения, 1 = data/ack, 2/3 = link-data;
  - byte7 = `SW_CheckSum` по первым 7 байтам (integrity заголовка).
- Bring-up линка: `_SW_Pro_Gnd_Entry_Start` `0x96f40` — генерирует **случайный** id сессии
  (`SW_Get_Random`), инициализирует последовательность (`SW_Seq_Init`), поднимает 2 потока:
  `SW_Pro_Gnd_Manage_Recv_Run` `0x981b4` (приём) и `SW_Pro_Gnd_Manage_Check_Run` `0x985d8`
  (таймауты/keepalive), таймеры `SW_Timer_Init`.
- В приёмнике `0x981b4` виден стейт-машина по control-байту: тип 0 = установка нового линка
  (calloc состояния, `SW_Alg_Recv_Init` x2 для двух окон, `SW_Pro_Send_Link_Init`,
  очередь ожидания `SW_Pkt_Wait_Queue_Init`), типы 1/2/3 = данные/ack с оконным ARQ
  (`SW_Alg_Recv_Deal_Win`, `SW_Pro_Deal_Send_Ack` `0x97e54`). На каждый валидный пакет
  сбрасывается таймер линка (`SW_Timer_Init(link+32)`) — это механизм keepalive/таймаута.
- Отправка: `_SW_Pro_Gnd_Ctrl_Send` `0x96c6c` → `SW_Alg_Send_Send_Data`. Шифрования нет —
  только checksum и ARQ.

### 5. Канал команд DUML (cmd_set/cmd_id)

- Верхнеуровневая отправка: `-[DJIServiceManager sendCommandData:commandChannel:]` `0x54e38`
  → `-[DJIServicePort sendCommandData:commandChannel:]` (диспетчер по serviceType:
  UDT/USB/MFI/BLE, в debug-режиме — по bridge-порту). Приём: `service:didReadBuffer:length:info:`
  `0x585fc` пробрасывается делегату.
- Контрольные суммы DUML: `_DjiCalcChecksumCrc8` `0x28b8c` (таблица `DjiCrc8Table`),
  `_DjiAppendChecksumCrc8` `0x28bb8`, `_DjiVerifyChecksumCrc8` `0x28bf0`,
  `_DjiCalcChecksumXor8/32` `0x28b30`/`0x28b58`.
- MFI-транспорт-парсер `-[DJICommonMFIDataSeparator parseBuffer:length:completion:]` `0x28e40`:
  2-байтовая сигнатура (`byte_B86B0`) + `packType`(2) + `packDataLength` — обёртка аксессуара,
  не крипто.
- **В этом модуле команды по DUML не шифруются**: путь `sendCommandData → writeData` не вызывает
  ни один AES/RSA. Целостность = CRC8/XOR, надёжность = ARQ на транспорте.

---

## Чем подтверждено

- AES-примитивы: декомпиляция `0x6f2c`, `0x7824` (таблицы Td/Te, CBC-обвязка).
- White-box + сертификат: `0x1afac`, `_DJIGetCertificateData` `0x5f170` (SHA256-сверка).
- CommonCrypto AES-256/PKCS7: `-[NSData AES256EncryptWithKey:initVector:]` `0x81c40`.
- Источник ключей: `+[DJIKeyGenerator randomAES256Key]` `0x33c34`,
  `genKeyWithKeyInfo:` `0x33d64`.
- Облачная активация как единственный потребитель command-layer AES:
  `+[DJIRegistInfo createUrlRequestWithKey:otherInfo:]` `0x4f71c` (URL `dev.dji.com/sdk`).
- Транспорт-хендшейк и стейт-машина: `_SW_Pro_Add_Header_And_Send` `0x97ce4`,
  `_SW_Pro_Gnd_Entry_Start` `0x96f40`, `_SW_Pro_Gnd_Manage_Recv_Run` `0x981b4`,
  `_SW_Pro_Gnd_Ctrl_Send` `0x96c6c`; UDT — `CHandShake::serialize` `0x8a7b8`.
- Отсутствие шифрования DUML-команд: декомпиляция `sendCommandData` `0x54e38`
  (нет вызовов crypto), CRC8-набор `0x28b8c`+.

---

## Что предполагается (гипотезы, не подтверждено на 100%)

- `_dji_AES_cbc_encrypt`/`_dji_AES_set_*` (OpenSSL-стек) в DJIMidWare, вероятно, **не задействованы
  напрямую** для канала команд (нет xref); скорее это код-донор для другого фреймворка или для
  оффлайн-операций (лог/файл-крипто). Требует проверки в других модулях.
- SW_Pro id-сессии (`word1`) + случайный seed из `SW_Get_Random` играют роль анти-replay/session-id,
  но это **не** криптографическая аутентификация — подтверждение только по `SW_CheckSum`.
- Обфусцированная `d60a024daa947631a20350e042(n)` возвращает зашитый секрет/ключ SDK по индексу
  (33/36 — разные ключи для разных потоков активации). Точное содержимое не извлекалось.
- «Сессия камеры» на уровне DUML, вероятно, устанавливается обменом cmd_set=0 (common)/
  версий/capability вне этого модуля (в DJISDK-core), поэтому здесь нет 0x55-парсера DUML-кадра.

## Что неизвестно (открытые вопросы)

- Где физически парсится/строится DUML app-кадр (SOF `0x55`, ver+len, crc8 header, cmd_type с
  битами шифрования 0..2)? В `3vfb` не найдено (нет immediate `0x55`, нет 0x55-парсера) — вероятно
  в другом фреймворке/либе.
- Использует ли Osmo Pocket 3 вообще encrypt-биты cmd_type на линке (BLE/USB/Wi-Fi), или канал
  открытый? В этом модуле — открытый (только CRC).
- Полная семантика control-байта SW_Pro (значения 0/1/2/3) и точный keepalive-интервал
  (значения в `SW_Timer`/`Check_Run` не расшифрованы численно).
- Есть ли ECDH/обмен ключами устройства? В `3vfb` признаков не найдено (нет строк
  handshake/nonce/session key/ECDH; RSA — только verify/облако).
- Как связаны white-box-ключ сертификата и активация: используется ли расшифрованный сертификат
  для подписи/валидации команд где-то выше.

## Следующий эксперимент

1. Найти DUML-кадр-парсер: искать `0x55` (SOF) и таблицу CRC16 в **соседних** инстансах
   (`DJISDK`-core / транспортные либы), а не в `3vfb`. Проверить cmd_type-байт на бит шифрования.
2. Пройти xref к `_DjiVerifyChecksumCrc8`/`_DjiAppendChecksumCrc8` **по указателям** (они без
   прямых xref) — установить, кто собирает исходящий DUML-кадр и не применяется ли AES перед CRC.
3. Проверить связь command-layer AES-256 c реальным линком: перехватить, действительно ли
   `AES256EncryptWithKey:` вызывается только на HTTP-активацию (Frida-хук селектора) — подтвердить,
   что канал команд идёт в открытую.
4. Численно снять keepalive: инструментировать `SW_Timer_Init`/`SW_Pro_Gnd_Manage_Check_Run`
   (`0x985d8`) — период heartbeat и таймаут разрыва линка.
5. Расшифровать `d60a024daa947631a20350e042` (что за секреты по индексам 33/36) статически —
   но только для документирования активации, без извлечения приватных ключей DRM.
