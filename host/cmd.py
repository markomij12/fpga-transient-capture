"""Host-to-FPGA CT command codec.

Little-endian. Distinct from dump magic TC (0x54, 0x43). This is the
opposite direction.

| Offset | Size | Name | Value |
|---|---|---|---|
| 0 | 1 | MAGIC0 | 0x43 'C' |
| 1 | 1 | MAGIC1 | 0x54 'T'  // "CT" = command to trigger-core |
| 2 | 1 | VER | 0x01 |
| 3 | 1 | CMD | 0x01 ARM (no payload) OR 0x02 SET_THRESH (payload uint16 LE) |
| 4 | 1 | LEN | payload byte count (0 or 2) |
| 5.. | LEN | PAYLOAD | ARM: empty. SET_THRESH: uint16 LE (low byte then high) |
| last | 1 | XOR8 | XOR of ALL bytes from MAGIC0 through last payload byte |

ARM frame (6 bytes): 43 54 01 01 00 | xor
SET_THRESH (8 bytes): 43 54 01 02 02 lo hi | xor
"""

from __future__ import annotations

import struct

MAGIC0 = 0x43
MAGIC1 = 0x54
MAGIC = bytes((MAGIC0, MAGIC1))
VER = 0x01
CMD_ARM = 0x01
CMD_SET_THRESH = 0x02


def xor8(data: bytes) -> int:
    acc = 0
    for byte in data:
        acc ^= byte
    return acc & 0xFF


def pack_body(cmd: int, payload: bytes = b"") -> bytes:
    """Header + payload, no XOR byte."""
    return bytes((MAGIC0, MAGIC1, VER, cmd & 0xFF, len(payload))) + payload


def pack_cmd(cmd: int, payload: bytes = b"") -> bytes:
    body = pack_body(cmd, payload)
    return body + bytes((xor8(body),))


def pack_arm() -> bytes:
    return pack_cmd(CMD_ARM, b"")


def pack_set_thresh(value: int) -> bytes:
    return pack_cmd(CMD_SET_THRESH, struct.pack("<H", int(value) & 0xFFFF))
