"""cocotb tests for capture_ctrl. Run: pytest tb/test_capture_ctrl.py"""

from __future__ import annotations

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotb_tools.runner import get_runner

DEPTH = 16
WIDTH = 12
PRE_TRIGGER = 4
POST = DEPTH - PRE_TRIGGER
HYSTERESIS = 4
THRESHOLD = 100
CLK_PERIOD_NS = 10

ST_IDLE = 0
ST_FILLING = 1
ST_TRIGGERED = 2
ST_READY = 3
SAMPLE_GAP = 3


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.arm.value = 0
    dut.sample_valid.value = 0
    dut.sample.value = 0
    dut.threshold.value = THRESHOLD
    dut.rd_addr.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def pulse_arm(dut) -> None:
    dut.arm.value = 1
    await RisingEdge(dut.clk)
    dut.arm.value = 0


async def poke_sample(dut, value: int, gap: int = SAMPLE_GAP) -> None:
    """1-cycle sample_valid strobe, then idle a few clocks."""
    dut.sample.value = value
    dut.sample_valid.value = 1
    await RisingEdge(dut.clk)
    dut.sample_valid.value = 0
    if gap:
        await ClockCycles(dut.clk, gap)


async def wait_status(dut, expected: int, timeout: int = 64) -> None:
    for _ in range(timeout):
        if int(dut.status.value) == expected:
            return
        await RisingEdge(dut.clk)
    raise AssertionError(f"status stayed {int(dut.status.value)}, want {expected}")


@cocotb.test()
async def capture_idle_then_fill_trigger_ready(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    assert int(dut.status.value) == ST_IDLE
    assert int(dut.capture_ready.value) == 0

    await pulse_arm(dut)
    await wait_status(dut, ST_FILLING)
    assert int(dut.capture_ready.value) == 0

    for _ in range(PRE_TRIGGER):
        await poke_sample(dut, THRESHOLD + 40)
        assert int(dut.status.value) == ST_FILLING
        assert int(dut.capture_ready.value) == 0

    await poke_sample(dut, THRESHOLD - 40, gap=0)
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.status.value) == ST_TRIGGERED
    assert int(dut.capture_ready.value) == 0

    for _ in range(POST):
        await poke_sample(dut, THRESHOLD - 50)
    await wait_status(dut, ST_READY)
    assert int(dut.capture_ready.value) == 1
    assert int(dut.status.value) == ST_READY


@cocotb.test()
async def capture_ready_only_in_ready(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.capture_ready.value) == 0

    await pulse_arm(dut)
    await wait_status(dut, ST_FILLING)
    assert int(dut.capture_ready.value) == 0

    for _ in range(PRE_TRIGGER):
        await poke_sample(dut, THRESHOLD + 40)
        assert int(dut.capture_ready.value) == 0

    await poke_sample(dut, THRESHOLD - 40, gap=0)
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.status.value) == ST_TRIGGERED
    assert int(dut.capture_ready.value) == 0

    for _ in range(POST):
        await poke_sample(dut, 10)
        if int(dut.status.value) != ST_READY:
            assert int(dut.capture_ready.value) == 0

    await wait_status(dut, ST_READY)
    assert int(dut.capture_ready.value) == 1


@cocotb.test()
async def capture_second_arm_starts_new_fill(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await pulse_arm(dut)
    for _ in range(PRE_TRIGGER):
        await poke_sample(dut, THRESHOLD + 40)
    await poke_sample(dut, THRESHOLD - 40, gap=0)
    await RisingEdge(dut.clk)
    for _ in range(POST):
        await poke_sample(dut, 10)
    await wait_status(dut, ST_READY)
    assert int(dut.capture_ready.value) == 1

    await pulse_arm(dut)
    await wait_status(dut, ST_FILLING)
    assert int(dut.capture_ready.value) == 0
    assert int(dut.status.value) == ST_FILLING

    await poke_sample(dut, THRESHOLD + 40)
    assert int(dut.status.value) == ST_FILLING


@cocotb.test()
async def capture_status_encoding(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.status.value) == ST_IDLE

    await pulse_arm(dut)
    await wait_status(dut, ST_FILLING)
    assert int(dut.status.value) == ST_FILLING

    for _ in range(PRE_TRIGGER):
        await poke_sample(dut, THRESHOLD + 40)
    await poke_sample(dut, THRESHOLD - 40, gap=0)
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.status.value) == ST_TRIGGERED

    for _ in range(POST):
        await poke_sample(dut, 10)
    await wait_status(dut, ST_READY)
    assert int(dut.status.value) == ST_READY


def test_capture_ctrl_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "capture_ctrl"
    runner.build(
        sources=[
            root / "rtl" / "trigger_detect.sv",
            root / "rtl" / "circ_buffer.sv",
            root / "rtl" / "capture_ctrl.sv",
        ],
        hdl_toplevel="capture_ctrl",
        parameters={
            "DEPTH": DEPTH,
            "WIDTH": WIDTH,
            "PRE_TRIGGER": PRE_TRIGGER,
            "HYSTERESIS": HYSTERESIS,
        },
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="capture_ctrl",
        test_module="test_capture_ctrl",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_capture_ctrl_runner()
