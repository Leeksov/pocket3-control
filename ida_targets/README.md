# ida_targets/ — analysis binaries (NOT committed)

These DJI binaries and IDA databases are intentionally excluded from git
(`.gitignore`): they are copyrighted DJI material and are large (~2.9 GB with
`.i64`). Populate this folder locally to reproduce the analysis.

## How to populate
From a decrypted **DJI Mimo v2.11.5** IPA that you are licensed to analyze:

```bash
unzip "DJI Mimo.ipa" -d work
APP=work/Payload/DJIMimo.app
cp "$APP/DJIMimo"                                   ida_targets/DJIMimo
cp "$APP/Frameworks/DJIMidWare.framework/DJIMidWare" ida_targets/DJIMidWare
cp "$APP/Frameworks/ilink_live.framework/ilink_live" ida_targets/ilink_live
# ...others as needed (GrandSerializer, HandheldUIKit, App, ...)
```

## Expected binaries & identities
| File | Size | md5 | role |
|---|---|---|---|
| `DJIMimo` | 176,671,520 | — | main app; dji::core SDK, BLE, command handlers |
| `DJIMidWare` | 2,501,040 | `51e4de968e4ffd481b25848d4f8ea322` | transport, DUML checksums, UDT, liveview |
| `ilink_live` | 9,080,208 | `a9e09539e34b07659c9475d5eed7fc08` | WeChat mars livestream — **excluded from camera analysis** |

Image bases: `DJIMimo` = `0x100000000`, `DJIMidWare` = `0x0`.
Addresses throughout `docs/reverse-engineering.md` are RVA.
