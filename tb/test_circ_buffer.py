"""cocotb tests for circ_buffer. Run: pytest tb/test_circ_buffer.py"""

from __future__ import annotations

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge
from cocotb_tools.runner import get_runner

DEPTH = 16
WIDTH = 12
PRE_TRIGGER = 4
POST = DEPTH - PRE_TRIGGER
CLK_PERIOD_NS = 10


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.clear.value = 0
    dut.wr_en.value = 0
    dut.wr_data.value = 0
    dut.trigger.value = 0
    dut.rd_addr.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def write_word(dut, value: int) -> None:
    dut.wr_data.value = value
    dut.wr_en.value = 1
    await RisingEdge(dut.clk)
    dut.wr_en.value = 0


async def pulse_trigger(dut) -> None:
    dut.trigger.value = 1
    await RisingEdge(dut.clk)
    dut.trigger.value = 0


async def pulse_clear(dut) -> None:
    dut.clear.value = 1
    await RisingEdge(dut.clk)
    dut.clear.value = 0


async def read_physical(dut, addr: int) -> int:
    """Registered BRAM read: address, one clock, then sample after NBA."""
    dut.rd_addr.value = addr
    await RisingEdge(dut.clk)
    await ReadOnly()
    value = int(dut.rd_data.value)
    await RisingEdge(dut.clk)
    return value


async def sample_levels(dut) -> None:
    """Advance one clock so the previous edge's registered flags are visible."""
    await RisingEdge(dut.clk)


async def read_chrono(dut, index: int) -> int:
    oldest = int(dut.oldest_addr.value)
    addr = (oldest + index) % DEPTH
    return await read_physical(dut, addr)


@cocotb.test()
async def circ_wrap_write_then_read(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    n_writes = DEPTH + 4
    for i in range(n_writes):
        await write_word(dut, 0x100 + i)

    for addr in range(DEPTH):
        last = addr
        while last + DEPTH < n_writes:
            last += DEPTH
        got = await read_physical(dut, addr)
        assert got == 0x100 + last, f"addr {addr}: got {got:#x}"


@cocotb.test()
async def circ_trigger_rejected_before_prefill(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    for i in range(PRE_TRIGGER - 1):
        await write_word(dut, 0x200 + i)
    await sample_levels(dut)
    assert int(dut.pre_filled.value) == 0

    await pulse_trigger(dut)
    for i in range(POST + 2):
        await write_word(dut, 0x280 + i)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 0


@cocotb.test()
async def circ_post_writes_then_frozen(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    for i in range(PRE_TRIGGER):
        await write_word(dut, 0x300 + i)
    await sample_levels(dut)
    assert int(dut.pre_filled.value) == 1

    await pulse_trigger(dut)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 0

    for i in range(POST - 1):
        await write_word(dut, 0x310 + i)
        await sample_levels(dut)
        assert int(dut.frozen.value) == 0

    await write_word(dut, 0x310 + (POST - 1))
    await sample_levels(dut)
    assert int(dut.frozen.value) == 1

    await write_word(dut, 0x3FF)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 1


@cocotb.test()
async def circ_chrono_read_matches_wrap(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # Extra pre-trigger writes so the ring wraps before freeze.
    extra = 6
    written: list[int] = []
    for i in range(extra):
        val = 0x400 + i
        await write_word(dut, val)
        written.append(val)
    await sample_levels(dut)
    assert int(dut.pre_filled.value) == 1

    await pulse_trigger(dut)
    for i in range(POST):
        val = 0x480 + i
        await write_word(dut, val)
        written.append(val)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 1

    expected = written[-DEPTH:]
    for i, exp in enumerate(expected):
        got = await read_chrono(dut, i)
        assert got == exp, f"chrono[{i}]: got {got:#x}, exp {exp:#x}"


@cocotb.test()
async def circ_trigger_sample_at_pre_minus_one(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    extra = 6
    for i in range(extra):
        await write_word(dut, 0x500 + i)
    crossing = 0x5A5
    await write_word(dut, crossing)
    await pulse_trigger(dut)
    for i in range(POST):
        await write_word(dut, 0x580 + i)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 1

    got = await read_chrono(dut, PRE_TRIGGER - 1)
    assert got == crossing, f"trigger index: got {got:#x}, exp {crossing:#x}"


@cocotb.test()
async def circ_clear_unfreezes(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    for i in range(PRE_TRIGGER):
        await write_word(dut, 0x600 + i)
    await pulse_trigger(dut)
    for i in range(POST):
        await write_word(dut, 0x610 + i)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 1

    await pulse_clear(dut)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 0
    assert int(dut.pre_filled.value) == 0
    assert int(dut.oldest_addr.value) == 0

    await write_word(dut, 0x6AA)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 0
    got = await read_physical(dut, 0)
    assert got == 0x6AA


@cocotb.test()
async def circ_crossing_sample_not_lost(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    for i in range(PRE_TRIGGER - 1):
        await write_word(dut, 0x700 + i)
    crossing = 0x7E1
    await write_word(dut, crossing)
    # trigger_pulse arrives the cycle after the crossing write.
    await pulse_trigger(dut)
    for i in range(POST):
        await write_word(dut, 0x780 + i)
    await sample_levels(dut)
    assert int(dut.frozen.value) == 1

    got = await read_chrono(dut, PRE_TRIGGER - 1)
    assert got == crossing, f"lost crossing: got {got:#x}, exp {crossing:#x}"


def test_circ_buffer_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "circ_buffer"
    runner.build(
        sources=[root / "rtl" / "circ_buffer.sv"],
        hdl_toplevel="circ_buffer",
        parameters={"DEPTH": DEPTH, "WIDTH": WIDTH, "PRE_TRIGGER": PRE_TRIGGER},
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="circ_buffer",
        test_module="test_circ_buffer",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_circ_buffer_runner()
