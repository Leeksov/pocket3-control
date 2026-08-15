"""Discovery (brief §5, §6, §7).

Pocket 3 primary path = BLE scan (DataLinkServiceFactoryImpl::StartBLEScan /
DCSBLECentralManager). Bonjour/mDNS also exists (DJIMBonjourDataSeparator) for
networked discovery. Wi-Fi SoftAP is joined after BLE hands over credentials.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class Discovered:
    transport: str      # "ble" | "bonjour" | "wifi"
    name: str
    address: str
    rssi: int = 0


async def scan_ble(timeout: float = 6.0) -> List[Discovered]:
    from ..transport.ble import scan
    return [Discovered("ble", d["name"], d["address"], d.get("rssi", 0))
            for d in await scan(timeout)]


async def scan_all(timeout: float = 6.0) -> List[Discovered]:
    found: List[Discovered] = []
    try:
        found += await scan_ble(timeout)
    except Exception:
        pass
    # bonjour/mDNS discovery can be added here (service type from DJIMBonjour*)
    return found
