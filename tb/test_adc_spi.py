"""cocotb tests for adc_spi. Run: pytest tb/test_adc_spi.py"""

from __future__ import annotations

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge
from cocotb_tools.runner import get_runner

# Fast sim dividers. Hardware uses 5 / 100 (20 MHz SCLK, 1 MSPS).
CLKS_PER_SCLK = 2
SAMPLE_PERIOD_CLKS = 40
CLK_PERIOD_NS = 10


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.enable.value = 0
    dut.analog_code.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def wait_sample_valid(dut) -> int:
    while True:
        await RisingEdge(dut.clk)
        if int(dut.sample_valid.value) == 1:
            return int(dut.sample.value)


async def count_sclk_falls_one_frame(dut) -> int:
    await FallingEdge(dut.cs_n)
    falls = 0
    prev = int(dut.sclk.value)
    for _ in range(SAMPLE_PERIOD_CLKS + 8):
        await RisingEdge(dut.clk)
        cur = int(dut.sclk.value)
        if prev == 1 and cur == 0:
            falls += 1
        prev = cur
        if int(dut.cs_n.value) == 1 and falls > 0:
            break
    return falls


@cocotb.test()
async def adc_idle_after_reset(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.cs_n.value) == 1
    assert int(dut.sclk.value) == 1
    for _ in range(SAMPLE_PERIOD_CLKS):
        await RisingEdge(dut.clk)
        assert int(dut.enable.value) == 0
        assert int(dut.cs_n.value) == 1
        assert int(dut.sclk.value) == 1
        assert int(dut.sample_valid.value) == 0


@cocotb.test()
async def adc_sixteen_sclks_per_sample(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.analog_code.value = 0xA50
    dut.enable.value = 1

    for _ in range(2):
        falls = await count_sclk_falls_one_frame(dut)
        assert falls == 16, f"expected 16 SCLK falls, got {falls}"


@cocotb.test()
async def adc_known_codes_round_trip(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    codes = (0x000, 0xFFF, 0xA50, 0x5A5, 0x001, 0x800)
    dut.analog_code.value = codes[0]
    dut.enable.value = 1

    for i, code in enumerate(codes):
        got = await wait_sample_valid(dut)
        assert got == code, f"sent 0x{code:03X}, got 0x{got:03X}"
        if i + 1 < len(codes):
            dut.analog_code.value = codes[i + 1]


@cocotb.test()
async def adc_sample_valid_period(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.analog_code.value = 0x5A5
    dut.enable.value = 1

    await wait_sample_valid(dut)
    for _ in range(3):
        clocks = 0
        while True:
            await RisingEdge(dut.clk)
            clocks += 1
            if int(dut.sample_valid.value) == 1:
                break
        assert clocks == SAMPLE_PERIOD_CLKS, (
            f"sample_valid spacing {clocks}, expected {SAMPLE_PERIOD_CLKS}"
        )


@cocotb.test()
async def adc_leading_zeros_stripped(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    dut.analog_code.value = 0xABC
    dut.enable.value = 1

    got = await wait_sample_valid(dut)
    assert got == 0xABC, f"leading zeros not stripped: got 0x{got:03X}"
    assert got != ((0xABC << 1) & 0xFFF), "sample looks left-shifted"
    assert got != (0xABC >> 1), "sample looks right-shifted (extra leading zero)"


def test_adc_spi_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "adc_spi"
    runner.build(
        sources=[
            root / "rtl" / "adc_spi.sv",
            root / "tb" / "adc_ad7476a_model.sv",
            root / "tb" / "adc_spi_tb.sv",
        ],
        hdl_toplevel="adc_spi_tb",
        parameters={
            "CLKS_PER_SCLK": CLKS_PER_SCLK,
            "SAMPLE_PERIOD_CLKS": SAMPLE_PERIOD_CLKS,
        },
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="adc_spi_tb",
        test_module="test_adc_spi",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_adc_spi_runner()
