"""pocket3 CLI (brief §19). Async over BLE.

    python -m pocket3.cli scan
    python -m pocket3.cli status   --address <addr>
    python -m pocket3.cli record   start|stop --address <addr>
    python -m pocket3.cli photo     --address <addr>
    python -m pocket3.cli iso       400 --address <addr>
    python -m pocket3.cli shutter   1 50 --address <addr>
    python -m pocket3.cli ev        3  --address <addr>
    python -m pocket3.cli wb        5000 --address <addr>
    python -m pocket3.cli gimbal    center|rotate [--yaw Y --pitch P] --address <addr>
    python -m pocket3.cli preview   start|stop --address <addr>

Unresolved commands exit(3) with a clear message instead of sending a wrong frame.
"""
from __future__ import annotations
import argparse
import asyncio
import sys

from .transport.ble import scan as ble_scan, BleTransport
from .device import Pocket3Device, CommandUnresolved


async def _with(address, fn):
    dev = Pocket3Device(BleTransport(address))
    await dev.connect()
    try:
        await fn(dev)
    finally:
        await dev.disconnect()


async def cmd_scan(_):
    devs = await ble_scan()
    print("\n".join(f"{d['address']}  rssi={d['rssi']:>4}  {d['name']}" for d in devs)
          or "no Pocket 3 found")


async def cmd_status(a):
    async def run(d):
        await asyncio.sleep(1.0)          # let pushes arrive
        snap = d.snapshot()
        print(f"connected={d.connected}  topics={len(snap)}")
        for k, v in snap.items():
            print(f"  {k}: {v}")
    await _with(a.address, run)


def _p(rsp): print("reply:", rsp)


async def cmd_record(a):
    await _with(a.address, lambda d: (d.start_recording() if a.state == "start"
                                      else d.stop_recording()))


async def cmd_photo(a):   await _with(a.address, lambda d: d.take_photo())
async def cmd_iso(a):     await _with(a.address, lambda d: d.set_iso(a.value))
async def cmd_ev(a):      await _with(a.address, lambda d: d.set_ev(a.value))
async def cmd_wb(a):      await _with(a.address, lambda d: d.set_white_balance(a.kelvin))
async def cmd_shutter(a): await _with(a.address, lambda d: d.set_shutter(a.num, a.den))


async def cmd_gimbal(a):
    async def run(d):
        if a.action == "center":
            await d.recenter_gimbal()
        else:
            await d.rotate_gimbal(a.yaw, a.pitch)
    await _with(a.address, run)


async def cmd_preview(a):
    await _with(a.address, lambda d: (d.start_preview() if a.state == "start"
                                      else d.stop_preview()))


def main(argv=None):
    p = argparse.ArgumentParser(prog="pocket3")
    sub = p.add_subparsers(dest="cmd", required=True)

    def addr(sp): sp.add_argument("--address", required=True)

    sub.add_parser("scan").set_defaults(fn=cmd_scan)
    addr(s := sub.add_parser("status")); s.set_defaults(fn=cmd_status)
    r = sub.add_parser("record"); r.add_argument("state", choices=["start", "stop"]); addr(r); r.set_defaults(fn=cmd_record)
    addr(s := sub.add_parser("photo")); s.set_defaults(fn=cmd_photo)
    i = sub.add_parser("iso"); i.add_argument("value", type=int); addr(i); i.set_defaults(fn=cmd_iso)
    e = sub.add_parser("ev"); e.add_argument("value", type=int); addr(e); e.set_defaults(fn=cmd_ev)
    w = sub.add_parser("wb"); w.add_argument("kelvin", type=int); addr(w); w.set_defaults(fn=cmd_wb)
    sh = sub.add_parser("shutter"); sh.add_argument("num", type=int); sh.add_argument("den", type=int); addr(sh); sh.set_defaults(fn=cmd_shutter)
    g = sub.add_parser("gimbal"); g.add_argument("action", choices=["center", "rotate"])
    g.add_argument("--yaw", type=float, default=0.0); g.add_argument("--pitch", type=float, default=0.0)
    addr(g); g.set_defaults(fn=cmd_gimbal)
    pv = sub.add_parser("preview"); pv.add_argument("state", choices=["start", "stop"]); addr(pv); pv.set_defaults(fn=cmd_preview)

    args = p.parse_args(argv)
    try:
        asyncio.run(args.fn(args))
    except CommandUnresolved as ex:
        print(f"[unresolved] {ex}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
