# Documentation index

| Doc | Contents |
|---|---|
| [reverse-engineering.md](reverse-engineering.md) | **Reference**: app version, binaries, IDA instances, all recovered function/data addresses (DUML, transport, BLE, UDT, live preview, command layer, crypto/white-box, SW_Pro). |
| [architecture.md](architecture.md) | Recovered vertical command path + transport model (BLE / Wi-Fi-UDT / MFi). |
| [protocol.md](protocol.md) | DUML V1 frame spec, validated CRC, command dispatch mechanism. |
| [commands.md](commands.md) | Full command / topic / capability catalog (from strings sweep). |
| [handshake.md](handshake.md) | Session/handshake + crypto analysis (commands are unencrypted). |
| [ios-mimo-analysis.md](ios-mimo-analysis.md) | Stage-1 static triage of the IPA. |

## Reproduce the analysis
Binaries are **not** committed (copyright + size). To reproduce:
1. Obtain a decrypted `DJI Mimo` IPA that you are licensed to analyze.
2. `unzip` it; copy the binaries listed in `ida_targets/README.md`.
3. Load them in IDA; addresses in `reverse-engineering.md` are RVA
   (VA = image_base + RVA).

## Report format
Each analysis note follows: **Что установлено / Чем подтверждено / Что
предполагается / Что неизвестно / Следующий эксперимент** (facts vs hypotheses
kept separate).
