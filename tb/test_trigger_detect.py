"""cocotb tests for trigger_detect. Run: pytest tb/test_trigger_detect.py"""

from __future__ import annotations

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotb_tools.runner import get_runner

WIDTH = 12
HYSTERESIS = 4
THRESHOLD = 100
CLK_PERIOD_NS = 10


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.arm.value = 0
    dut.sample_valid.value = 0
    dut.sample.value = 0
    dut.threshold.value = THRESHOLD
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def poke_sample(dut, value: int) -> None:
    """Drive a 1-cycle sample_valid strobe with the given ADC code."""
    dut.sample.value = value
    dut.sample_valid.value = 1
    await RisingEdge(dut.clk)
    dut.sample_valid.value = 0


@cocotb.test()
async def trigger_idle_after_reset(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.trigger_pulse.value) == 0
    await ClockCycles(dut.clk, 8)
    assert int(dut.trigger_pulse.value) == 0


@cocotb.test()
async def trigger_no_pulse_while_disarmed(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.arm.value = 0

    await poke_sample(dut, THRESHOLD + 20)
    await poke_sample(dut, THRESHOLD - 20)
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 0
    await ClockCycles(dut.clk, 4)
    assert int(dut.trigger_pulse.value) == 0


@cocotb.test()
async def trigger_falling_cross_pulses_once(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.arm.value = 1

    await poke_sample(dut, THRESHOLD + 20)
    await poke_sample(dut, THRESHOLD - 20)
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 1
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 0


@cocotb.test()
async def trigger_no_retrigger_below(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.arm.value = 1

    await poke_sample(dut, THRESHOLD + 20)
    await poke_sample(dut, THRESHOLD - 20)
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 1

    for _ in range(6):
        await poke_sample(dut, THRESHOLD - 30)
        await RisingEdge(dut.clk)
        assert int(dut.trigger_pulse.value) == 0


@cocotb.test()
async def trigger_rearm_after_hysteresis(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.arm.value = 1

    await poke_sample(dut, THRESHOLD + 20)
    await poke_sample(dut, THRESHOLD - 20)
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 1

    # Below re-arm level (threshold + HYSTERESIS) must not re-arm.
    await poke_sample(dut, THRESHOLD + HYSTERESIS - 1)
    await poke_sample(dut, 0)
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 0

    await poke_sample(dut, THRESHOLD + HYSTERESIS)
    await poke_sample(dut, 0)
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 1
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 0


@cocotb.test()
async def trigger_rising_step_does_not_fire(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.arm.value = 1

    await poke_sample(dut, THRESHOLD - 20)
    await poke_sample(dut, THRESHOLD + 20)
    await RisingEdge(dut.clk)
    assert int(dut.trigger_pulse.value) == 0
    await ClockCycles(dut.clk, 4)
    assert int(dut.trigger_pulse.value) == 0


def test_trigger_detect_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "trigger_detect"
    runner.build(
        sources=[root / "rtl" / "trigger_detect.sv"],
        hdl_toplevel="trigger_detect",
        parameters={"WIDTH": WIDTH, "HYSTERESIS": HYSTERESIS},
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="trigger_detect",
        test_module="test_trigger_detect",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_trigger_detect_runner()
