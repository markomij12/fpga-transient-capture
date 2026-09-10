"""cocotb tests for uart_rx. Run: pytest tb/test_uart_rx.py"""

from __future__ import annotations

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotb_tools.runner import get_runner

# Fast sim clock divider. Hardware uses 868 (100 MHz / 115200).
CLKS_PER_BIT = 8
CLK_PERIOD_NS = 10


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.rx.value = 1
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def drive_byte(dut, value: int) -> None:
    """Drive one 8N1 frame: start, LSB-first data, stop. Full bit times."""
    dut.rx.value = 0
    await ClockCycles(dut.clk, CLKS_PER_BIT)
    for bit in range(8):
        dut.rx.value = (value >> bit) & 1
        await ClockCycles(dut.clk, CLKS_PER_BIT)
    dut.rx.value = 1
    await ClockCycles(dut.clk, CLKS_PER_BIT)


async def collect_rx_pulses(dut, pulses: list[int]) -> None:
    """Record rx_data on every cycle where rx_valid is high."""
    while True:
        await RisingEdge(dut.clk)
        if int(dut.rx_valid.value) == 1:
            pulses.append(int(dut.rx_data.value))


@cocotb.test()
async def uart_rx_idle_after_reset(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.rx_valid.value) == 0
    dut.rx.value = 1
    await ClockCycles(dut.clk, 16)
    assert int(dut.rx_valid.value) == 0


@cocotb.test()
async def uart_rx_known_bytes(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    for value in (0x00, 0xFF, 0x55, 0xA5, 0x31):
        pulses: list[int] = []
        mon = cocotb.start_soon(collect_rx_pulses(dut, pulses))
        await drive_byte(dut, value)
        await ClockCycles(dut.clk, 2)
        mon.cancel()
        assert pulses == [value], f"expected one pulse 0x{value:02X}, got {pulses}"
        assert int(dut.rx_valid.value) == 0


@cocotb.test()
async def uart_rx_drops_false_start(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    pulses: list[int] = []
    mon = cocotb.start_soon(collect_rx_pulses(dut, pulses))

    for low_clks in (1, 2):
        dut.rx.value = 0
        await ClockCycles(dut.clk, low_clks)
        dut.rx.value = 1
        await ClockCycles(dut.clk, CLKS_PER_BIT * 4)

    mon.cancel()
    assert pulses == [], f"false start produced rx_valid: {pulses}"


@cocotb.test()
async def uart_rx_drops_bad_stop(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    pulses: list[int] = []
    mon = cocotb.start_soon(collect_rx_pulses(dut, pulses))

    value = 0x5A
    dut.rx.value = 0
    await ClockCycles(dut.clk, CLKS_PER_BIT)
    for bit in range(8):
        dut.rx.value = (value >> bit) & 1
        await ClockCycles(dut.clk, CLKS_PER_BIT)
    dut.rx.value = 0
    await ClockCycles(dut.clk, CLKS_PER_BIT)
    dut.rx.value = 1
    await ClockCycles(dut.clk, CLKS_PER_BIT * 2)

    mon.cancel()
    assert pulses == [], f"bad stop produced rx_valid: {pulses}"


@cocotb.test()
async def uart_rx_back_to_back(dut) -> None:
    """Next start immediately after one stop bit still frames both bytes."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    pulses: list[int] = []
    mon = cocotb.start_soon(collect_rx_pulses(dut, pulses))
    await drive_byte(dut, 0x12)
    await drive_byte(dut, 0x34)
    await ClockCycles(dut.clk, 2)
    mon.cancel()
    assert pulses == [0x12, 0x34], f"back-to-back got {pulses}"


def test_uart_rx_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "uart_rx"
    runner.build(
        sources=[root / "rtl" / "uart_rx.sv"],
        hdl_toplevel="uart_rx",
        parameters={"CLKS_PER_BIT": CLKS_PER_BIT},
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="uart_rx",
        test_module="test_uart_rx",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_uart_rx_runner()
