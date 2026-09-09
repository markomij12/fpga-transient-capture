"""cocotb tests for uart_tx. Run: pytest tb/test_uart_tx.py"""

from __future__ import annotations

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge
from cocotb_tools.runner import get_runner

# Fast sim clock divider. Hardware uses 868 (100 MHz / 115200).
CLKS_PER_BIT = 8
CLK_PERIOD_NS = 10


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.tx_start.value = 0
    dut.tx_data.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def send_byte(dut, value: int) -> None:
    await RisingEdge(dut.clk)
    dut.tx_data.value = value
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    dut.tx_start.value = 0


async def recv_byte(dut) -> int:
    """Sample the UART line at the midpoint of each bit."""
    while int(dut.tx.value) == 1:
        await RisingEdge(dut.clk)

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
async def uart_idle_after_reset(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.tx.value) == 1
    assert int(dut.tx_busy.value) == 0


@cocotb.test()
async def uart_send_known_bytes(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    for value in (0x00, 0xFF, 0x55, 0xA5, 0x31):
        await send_byte(dut, value)
        await ReadOnly()
        assert int(dut.tx_busy.value) == 1
        got = await recv_byte(dut)
        assert got == value, f"sent 0x{value:02X}, got 0x{got:02X}"
        while int(dut.tx_busy.value) == 1:
            await RisingEdge(dut.clk)
        assert int(dut.tx.value) == 1


@cocotb.test()
async def uart_ignores_start_while_busy(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await send_byte(dut, 0x11)
    await RisingEdge(dut.clk)
    dut.tx_data.value = 0x22
    dut.tx_start.value = 1
    await ClockCycles(dut.clk, 4)
    dut.tx_start.value = 0

    got = await recv_byte(dut)
    assert got == 0x11, f"busy start overwrote the frame: 0x{got:02X}"


def test_uart_tx_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "uart_tx"
    runner.build(
        sources=[root / "rtl" / "uart_tx.sv"],
        hdl_toplevel="uart_tx",
        parameters={"CLKS_PER_BIT": CLKS_PER_BIT},
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="uart_tx",
        test_module="test_uart_tx",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_uart_tx_runner()
