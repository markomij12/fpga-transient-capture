"""pytest tests for the UART dump frame codec and host logger."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.capture_logger import main
from host.frame import FrameError, pack_frame, parse_frame

N = 8
PRE = 2
STEP_HIGH = 0x0C00
STEP_LOW = 0x0100
STEP = [STEP_HIGH, STEP_HIGH] + [STEP_LOW] * 6


def test_pack_parse_roundtrip_step() -> None:
    data = pack_frame(N, PRE, STEP)
    assert len(data) == 7 + 2 * N + 1 + 2
    cap = parse_frame(data)
    assert cap.n == N
    assert cap.pre == PRE
    assert cap.samples == STEP
    assert cap.region(0) == "pre"
    assert cap.region(1) == "trig"
    assert cap.region(2) == "post"


def test_xor_mismatch_raises() -> None:
    data = bytearray(pack_frame(N, PRE, STEP))
    data[7 + 2 * N] ^= 0xFF
    with pytest.raises(FrameError, match="xor"):
        parse_frame(bytes(data))


def test_truncated_data_raises() -> None:
    data = pack_frame(N, PRE, STEP)
    with pytest.raises(FrameError, match="truncated"):
        parse_frame(data[:-1])
    with pytest.raises(FrameError, match="truncated"):
        parse_frame(data[:5])


def test_bad_magic_raises() -> None:
    data = bytearray(pack_frame(N, PRE, STEP))
    data[0] = 0x00
    with pytest.raises(FrameError, match="magic"):
        parse_frame(bytes(data))


def test_upper_nibble_masked_on_pack() -> None:
    raw = [0xFABC, 0x1FFF]
    cap = parse_frame(pack_frame(2, 1, raw))
    assert cap.samples == [0x0ABC, 0x0FFF]


def test_logger_writes_csv(tmp_path: Path) -> None:
    bin_path = tmp_path / "cap.bin"
    bin_path.write_bytes(pack_frame(N, PRE, STEP))
    csv_path = tmp_path / "out.csv"

    assert main(["--input", str(bin_path), "--csv", str(csv_path)]) == 0

    with csv_path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["index", "sample", "region"]
    assert rows[1] == ["0", str(STEP_HIGH), "pre"]
    assert rows[2] == ["1", str(STEP_HIGH), "trig"]
    assert rows[3] == ["2", str(STEP_LOW), "post"]
    assert len(rows) == 1 + N


@pytest.mark.skip(reason="numpy/matplotlib import can hang in this environment; PNG is CLI-only until a board")
def test_logger_writes_png(tmp_path: Path) -> None:
    bin_path = tmp_path / "cap.bin"
    bin_path.write_bytes(pack_frame(N, PRE, STEP))
    png_path = tmp_path / "out.png"

    assert main(["--input", str(bin_path), "--png", str(png_path)]) == 0
    assert png_path.is_file()
    assert png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
