"""Write CSV and PNG from a captured UART dump frame.

Examples::

    python -m host.capture_logger --input path.bin --csv out.csv --png out.png
    python -m host.capture_logger --input -
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from host.frame import Capture, FrameError, parse_frame


def read_frame_bytes(source: str) -> bytes:
    if source == "-":
        return sys.stdin.buffer.read()
    return Path(source).read_bytes()


def write_csv(capture: Capture, path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["index", "sample", "region"])
        for index, sample in enumerate(capture.samples):
            writer.writerow([index, sample, capture.region(index)])


def write_png(capture: Capture, path: Path) -> None:
    import os

    os.environ.setdefault("MPLBACKEND", "Agg")
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as exc:
        raise SystemExit("matplotlib and numpy are required for --png") from exc

    ys = np.asarray(capture.samples, dtype=np.uint16)
    fig, ax = plt.subplots()
    ax.plot(ys, drawstyle="steps-post")
    trig = capture.trigger_index
    if trig is not None:
        ax.axvline(trig, color="C3", linestyle="--", label="trigger")
        ax.legend()
    ax.set_xlabel("index")
    ax.set_ylabel("ADC code")
    ax.set_title("UART capture")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        help="Complete frame file, or - for stdin",
    )
    parser.add_argument("--csv", type=Path, default=None, help="Output CSV path")
    parser.add_argument("--png", type=Path, default=None, help="Output PNG path")
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port (not implemented; needs hardware)",
    )
    args = parser.parse_args(argv)

    if args.port is not None:
        raise SystemExit(
            "--port is not implemented; live UART capture needs hardware"
        )

    try:
        capture = parse_frame(read_frame_bytes(args.input))
    except FrameError as exc:
        raise SystemExit(f"frame error: {exc}") from exc

    if args.csv is not None:
        write_csv(capture, args.csv)
    if args.png is not None:
        write_png(capture, args.png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
