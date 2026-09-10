"""UART dump frame codec.

Little-endian. Total length 7 + 2*N + 1 + 2 bytes.

| Offset | Size | Name | Value |
|---|---|---|---|
| 0 | 1 | MAGIC0 | 0x54 'T' |
| 1 | 1 | MAGIC1 | 0x43 'C' |
| 2 | 1 | VER | 0x01 |
| 3 | 2 | N | uint16 LE sample count |
| 5 | 2 | PRE | uint16 LE pre-trigger count |
| 7 | 2N | SAMPLES | N × uint16 LE, bits[11:0]=ADC code, bits[15:12]=0 |
| 7+2N | 1 | XOR8 | XOR of all bytes from MAGIC0 through last sample byte |
| 8+2N | 2 | TRAILER | 0x0D 0x0A |

Sample i=0 is oldest (first pre-trigger). Sample i=PRE-1 is the trigger
sample. Sample i=PRE is first post.

Rejected alternatives: packed 12-bit (harder to debug). 16-bit BE (less
numpy-friendly on x86).
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass

MAGIC0 = 0x54
MAGIC1 = 0x43
MAGIC = bytes((MAGIC0, MAGIC1))
VER = 0x01
TRAILER = b"\x0d\x0a"

_HEADER_LEN = 7
_FOOTER_LEN = 3  # XOR8 + TRAILER
_SAMPLE_MASK = 0x0FFF


class FrameError(ValueError):
    """Raised when a dump frame is malformed or inconsistent."""


@dataclass
class Capture:
    n: int
    pre: int
    samples: list[int]

    def region(self, index: int) -> str:
        """Return ``pre``, ``trig``, or ``post`` for sample ``index``."""
        if self.pre <= 0:
            return "post"
        if index == self.pre - 1:
            return "trig"
        if index < self.pre - 1:
            return "pre"
        return "post"

    @property
    def trigger_index(self) -> int | None:
        if self.pre <= 0:
            return None
        return self.pre - 1


def _xor8(data: bytes) -> int:
    acc = 0
    for byte in data:
        acc ^= byte
    return acc


def _require_u16(name: str, value: int) -> int:
    value = int(value)
    if value < 0 or value > 0xFFFF:
        raise FrameError(f"{name} out of uint16 range: {value}")
    return value


def pack_frame(n: int, pre: int, samples: Sequence[int]) -> bytes:
    n = _require_u16("n", n)
    pre = _require_u16("pre", pre)
    if n != len(samples):
        raise FrameError(f"n={n} does not match sample count {len(samples)}")

    header = struct.pack("<BBBHH", MAGIC0, MAGIC1, VER, n, pre)
    payload = struct.pack(
        f"<{n}H" if n else "",
        *(int(sample) & _SAMPLE_MASK for sample in samples),
    )
    body = header + payload
    return body + bytes((_xor8(body),)) + TRAILER


def parse_frame(data: bytes) -> Capture:
    if len(data) < _HEADER_LEN + _FOOTER_LEN:
        raise FrameError("truncated frame")

    magic0, magic1, ver, n, pre = struct.unpack_from("<BBBHH", data, 0)
    if magic0 != MAGIC0 or magic1 != MAGIC1:
        raise FrameError("bad magic")
    if ver != VER:
        raise FrameError(f"unsupported version: {ver}")

    expected = _HEADER_LEN + 2 * n + _FOOTER_LEN
    if len(data) < expected:
        raise FrameError("truncated frame")
    if len(data) != expected:
        raise FrameError(f"length {len(data)} does not match n={n} (expected {expected})")

    samples: list[int] = []
    for i in range(n):
        (value,) = struct.unpack_from("<H", data, _HEADER_LEN + 2 * i)
        if value > _SAMPLE_MASK:
            raise FrameError(f"sample {i} exceeds 12 bits: 0x{value:04X}")
        samples.append(value)

    xor_off = _HEADER_LEN + 2 * n
    got_xor = data[xor_off]
    expect_xor = _xor8(data[:xor_off])
    if got_xor != expect_xor:
        raise FrameError(f"xor mismatch: got 0x{got_xor:02X}, expected 0x{expect_xor:02X}")

    trailer = data[xor_off + 1 : xor_off + 3]
    if trailer != TRAILER:
        raise FrameError(f"bad trailer: {trailer!r}")

    return Capture(n=n, pre=pre, samples=samples)
