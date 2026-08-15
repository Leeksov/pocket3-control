# tools/

| Tool | Status | Purpose |
|---|---|---|
| `packet-decoder/decode.py` | ✅ working | decode DUML frames from hex or a binary capture |
| `logger/` | via `src/pocket3/logger.py` | structured TX/RX/EVENT protocol log (importable) |
| `protocol-analyzer/` | planned | diff/annotate captures against `docs/protocol.md` |

## packet-decoder
```bash
python3 tools/packet-decoder/decode.py 55 0f 00 c3 0a 07 34 12 00 04 03 01 90 b8 10
python3 tools/packet-decoder/decode.py --file capture.bin
```
