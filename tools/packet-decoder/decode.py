#!/usr/bin/env python3
"""Decode DUML frames from a hex string or a binary capture.

    python tools/packet-decoder/decode.py 55 0e 04 33 0a 07 01 00 40 1a 0e ...
    python tools/packet-decoder/decode.py --file capture.bin
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from pocket3.protocol.duml import find_frames  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hex", nargs="*", help="space/colon separated hex bytes")
    ap.add_argument("--file", help="binary capture file")
    a = ap.parse_args()
    if a.file:
        data = open(a.file, "rb").read()
    else:
        data = bytes(int(x, 16) for x in " ".join(a.hex).replace(":", " ").split())
    n = 0
    for chunk, f in find_frames(data):
        n += 1
        print(f"#{n} set=0x{f.cmd_set:02x} id=0x{f.cmd_id:02x} seq={f.seq} "
              f"snd=0x{f.sender:02x} rcv=0x{f.receiver:02x} type=0x{f.cmd_type:02x} "
              f"len={len(f.payload)} payload={f.payload.hex()}")
    if not n:
        print("no valid DUML frames found")


if __name__ == "__main__":
    main()
