"""cocotb tests for host_cmd. Run: pytest tb/test_host_cmd.py"""

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

from host.cmd import (
    CMD_ARM,
    CMD_SET_THRESH,
    MAGIC0,
    pack_arm,
    pack_body,
    pack_set_thresh,
    xor8,
)

CLK_PERIOD_NS = 10
DEFAULT_THRESH = 0x800


async def reset_dut(dut) -> None:
    dut.rst.value = 1
    dut.rx_valid.value = 0
    dut.rx_data.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def send_byte(dut, value: int) -> None:
    """Drive a 1-cycle rx_valid strobe with the given byte."""
    dut.rx_data.value = value
    dut.rx_valid.value = 1
    await RisingEdge(dut.clk)
    dut.rx_valid.value = 0


async def send_frame(dut, data: bytes, *, xor: int | None = None) -> None:
    """Send a CT body (XOR appended) or a complete frame if xor is given."""
    if xor is None and len(data) >= 5 and data[-1] == xor8(data[:-1]):
        frame = data
    elif xor is None:
        frame = data + bytes((xor8(data),))
    else:
        frame = data + bytes((xor & 0xFF,))
    for byte in frame:
        await send_byte(dut, byte)


async def wait_pulse(dut, name: str, max_cycles: int = 3) -> None:
    sig = getattr(dut, name)
    other = dut.cmd_error if name == "arm_pulse" else dut.arm_pulse
    for _ in range(max_cycles):
        if int(sig.value) == 1:
            assert int(other.value) == 0, f"{name} and the other pulse both high"
            await RisingEdge(dut.clk)
            assert int(sig.value) == 0, f"{name} lasted more than one cycle"
            return
        await RisingEdge(dut.clk)
    raise AssertionError(f"{name} not seen within {max_cycles} clocks")


async def expect_no_arm(dut, cycles: int = 4) -> None:
    for _ in range(cycles):
        assert int(dut.arm_pulse.value) == 0
        await RisingEdge(dut.clk)


@cocotb.test()
async def host_cmd_default_threshold(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.threshold.value) == DEFAULT_THRESH
    assert int(dut.arm_pulse.value) == 0
    assert int(dut.cmd_error.value) == 0


@cocotb.test()
async def host_cmd_arm(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await send_frame(dut, pack_body(CMD_ARM))
    await wait_pulse(dut, "arm_pulse")
    assert int(dut.threshold.value) == DEFAULT_THRESH
    assert int(dut.cmd_error.value) == 0


@cocotb.test()
async def host_cmd_set_thresh(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await send_frame(dut, pack_set_thresh(0x0ABC))
    await expect_no_arm(dut, cycles=3)
    assert int(dut.threshold.value) == 0xABC
    assert int(dut.cmd_error.value) == 0
    assert int(dut.arm_pulse.value) == 0


@cocotb.test()
async def host_cmd_thresh_masked(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await send_frame(dut, pack_set_thresh(0xFFFF))
    await ClockCycles(dut.clk, 2)
    assert int(dut.threshold.value) == 0xFFF
    assert int(dut.arm_pulse.value) == 0
    assert int(dut.cmd_error.value) == 0


@cocotb.test()
async def host_cmd_bad_magic(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await send_byte(dut, 0x54)
    await wait_pulse(dut, "cmd_error")
    await expect_no_arm(dut, cycles=2)

    await send_byte(dut, MAGIC0)
    await send_byte(dut, 0x43)
    await wait_pulse(dut, "cmd_error")
    assert int(dut.arm_pulse.value) == 0
    assert int(dut.threshold.value) == DEFAULT_THRESH


@cocotb.test()
async def host_cmd_bad_xor(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    body = pack_body(CMD_ARM)
    await send_frame(dut, body, xor=xor8(body) ^ 0xFF)
    await wait_pulse(dut, "cmd_error")
    assert int(dut.arm_pulse.value) == 0
    assert int(dut.threshold.value) == DEFAULT_THRESH


@cocotb.test()
async def host_cmd_bad_len(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    arm_long = bytes((MAGIC0, 0x54, 0x01, CMD_ARM, 0x02, 0x00, 0x00))
    await send_frame(dut, arm_long)
    await wait_pulse(dut, "cmd_error")
    assert int(dut.arm_pulse.value) == 0

    await send_frame(dut, pack_body(CMD_SET_THRESH, b""))
    await wait_pulse(dut, "cmd_error")
    assert int(dut.arm_pulse.value) == 0
    assert int(dut.threshold.value) == DEFAULT_THRESH

    await send_byte(dut, MAGIC0)
    await send_byte(dut, 0x54)
    await send_byte(dut, 0x01)
    await send_byte(dut, CMD_ARM)
    await send_byte(dut, 0x03)
    await wait_pulse(dut, "cmd_error")
    assert int(dut.arm_pulse.value) == 0


@cocotb.test()
async def host_cmd_unknown_cmd(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await send_frame(dut, pack_body(0x03))
    await wait_pulse(dut, "cmd_error")
    assert int(dut.arm_pulse.value) == 0
    assert int(dut.threshold.value) == DEFAULT_THRESH


@cocotb.test()
async def host_cmd_arm_after_set(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await send_frame(dut, pack_set_thresh(0x0ABC))
    await ClockCycles(dut.clk, 2)
    assert int(dut.threshold.value) == 0xABC
    assert int(dut.arm_pulse.value) == 0
    assert int(dut.cmd_error.value) == 0

    await send_frame(dut, pack_arm())
    await wait_pulse(dut, "arm_pulse")
    assert int(dut.threshold.value) == 0xABC
    assert int(dut.cmd_error.value) == 0


def test_host_cmd_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "host_cmd"
    runner.build(
        sources=[root / "rtl" / "host_cmd.sv"],
        hdl_toplevel="host_cmd",
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=build_dir,
    )
    runner.test(
        hdl_toplevel="host_cmd",
        test_module="test_host_cmd",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_host_cmd_runner()
