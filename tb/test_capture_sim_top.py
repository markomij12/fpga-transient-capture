"""cocotb tests for capture_sim_top. Run: pytest tb/test_capture_sim_top.py"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.frame import parse_frame

DEPTH = 32
PRE_TRIGGER = 8
HYSTERESIS = 4
CLKS_PER_BIT = 8
CLKS_PER_SCLK = 2
SAMPLE_PERIOD_CLKS = 40
CLK_PERIOD_NS = 10

THRESHOLD = 0x800
CODE_HIGH = 0xC00
CODE_LOW = 0x100

FRAME_LEN = 7 + 2 * DEPTH + 1 + 2

ST_IDLE = 0
ST_FILLING = 1
ST_TRIGGERED = 2
ST_READY = 3


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.arm.value = 0
    dut.analog_code.value = CODE_HIGH
    dut.threshold.value = THRESHOLD
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def pulse_arm(dut) -> None:
    dut.arm.value = 1
    await RisingEdge(dut.clk)
    dut.arm.value = 0


async def recv_byte(dut, timeout_cycles: int = 50_000) -> int:
    for _ in range(timeout_cycles):
        if int(dut.tx.value) == 0:
            break
        await RisingEdge(dut.clk)
    else:
        raise AssertionError("timeout waiting for UART start bit")

    await ClockCycles(dut.clk, CLKS_PER_BIT // 2)
    assert int(dut.tx.value) == 0, "start bit was not held low"

    data = 0
    for bit in range(8):
        await ClockCycles(dut.clk, CLKS_PER_BIT)
        data |= int(dut.tx.value) << bit

    await ClockCycles(dut.clk, CLKS_PER_BIT)
    assert int(dut.tx.value) == 1, "stop bit was not high"
    return data


@cocotb.test()
async def capture_path_dumps_fake_step(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    assert int(dut.status.value) == ST_IDLE

    await pulse_arm(dut)
    for _ in range(16):
        if int(dut.status.value) == ST_FILLING:
            break
        await RisingEdge(dut.clk)
    assert int(dut.status.value) == ST_FILLING

    # Let the pre-window fill with high codes, then drop.
    await ClockCycles(dut.clk, PRE_TRIGGER * SAMPLE_PERIOD_CLKS + 8 * SAMPLE_PERIOD_CLKS)
    dut.analog_code.value = CODE_LOW

    for _ in range(POST_TIMEOUT := (DEPTH + 8) * SAMPLE_PERIOD_CLKS):
        if int(dut.capture_ready.value) == 1:
            break
        await RisingEdge(dut.clk)
    assert int(dut.capture_ready.value) == 1, "capture never reached READY"
    assert int(dut.status.value) == ST_READY

    raw = bytearray()
    for _ in range(FRAME_LEN):
        raw.append(await recv_byte(dut))

    cap = parse_frame(bytes(raw))
    assert cap.n == DEPTH
    assert cap.pre == PRE_TRIGGER
    assert len(cap.samples) == DEPTH

    for i in range(PRE_TRIGGER - 1):
        assert cap.samples[i] >= THRESHOLD, f"pre[{i}]=0x{cap.samples[i]:03X} not high"
    assert cap.samples[PRE_TRIGGER - 1] < THRESHOLD, "trigger sample was not the falling cross"
    for i in range(PRE_TRIGGER, DEPTH):
        assert cap.samples[i] < THRESHOLD, f"post[{i}]=0x{cap.samples[i]:03X} not low"


def test_capture_sim_top_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "capture_sim_top"
    runner.build(
        sources=[
            root / "rtl" / "uart_tx.sv",
            root / "rtl" / "trigger_detect.sv",
            root / "rtl" / "circ_buffer.sv",
            root / "rtl" / "capture_ctrl.sv",
            root / "rtl" / "adc_spi.sv",
            root / "tb" / "adc_ad7476a_model.sv",
            root / "rtl" / "uart_dump.sv",
            root / "rtl" / "capture_sim_top.sv",
        ],
        hdl_toplevel="capture_sim_top",
        parameters={
            "DEPTH": DEPTH,
            "WIDTH": 12,
            "PRE_TRIGGER": PRE_TRIGGER,
            "HYSTERESIS": HYSTERESIS,
            "CLKS_PER_BIT": CLKS_PER_BIT,
            "CLKS_PER_SCLK": CLKS_PER_SCLK,
            "SAMPLE_PERIOD_CLKS": SAMPLE_PERIOD_CLKS,
        },
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="capture_sim_top",
        test_module="test_capture_sim_top",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_capture_sim_top_runner()
