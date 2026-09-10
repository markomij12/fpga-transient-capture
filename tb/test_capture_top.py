"""cocotb tests for capture_top. Run: pytest tb/test_capture_top.py"""

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

from host.cmd import pack_arm, pack_set_thresh
from host.frame import parse_frame

DEPTH = 32
PRE_TRIGGER = 8
HYSTERESIS = 4
CLKS_PER_BIT = 8
CLKS_PER_SCLK = 2
SAMPLE_PERIOD_CLKS = 40
CLK_PERIOD_NS = 10

DEFAULT_THRESH = 0x800
CODE_HIGH = 0xC00
CODE_LOW = 0x100

UART_THRESH = 0xB00
UART_CODE_HIGH = 0xC00
UART_CODE_LOW = 0xA00

FRAME_LEN = 7 + 2 * DEPTH + 1 + 2

ST_IDLE = 0
ST_FILLING = 1
ST_READY = 3


async def reset_dut(dut, analog: int = CODE_HIGH) -> None:
    dut.rst.value = 1
    dut.uart_rx.value = 1
    dut.arm_btn.value = 0
    dut.analog_code.value = analog
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def pulse_arm_btn(dut) -> None:
    """Level-high for a few clocks; 2-FF sync makes a rising-edge pulse."""
    dut.arm_btn.value = 1
    await ClockCycles(dut.clk, 4)
    dut.arm_btn.value = 0


async def drive_rx_byte(dut, value: int) -> None:
    dut.uart_rx.value = 0
    await ClockCycles(dut.clk, CLKS_PER_BIT)
    for bit in range(8):
        dut.uart_rx.value = (value >> bit) & 1
        await ClockCycles(dut.clk, CLKS_PER_BIT)
    dut.uart_rx.value = 1
    await ClockCycles(dut.clk, CLKS_PER_BIT)


async def drive_rx_frame(dut, frame: bytes) -> None:
    for byte in frame:
        await drive_rx_byte(dut, byte)
    await ClockCycles(dut.clk, 4)


async def recv_byte(dut, timeout_cycles: int = 50_000) -> int:
    for _ in range(timeout_cycles):
        if int(dut.uart_tx.value) == 0:
            break
        await RisingEdge(dut.clk)
    else:
        raise AssertionError("timeout waiting for UART start bit")

    await ClockCycles(dut.clk, CLKS_PER_BIT // 2)
    assert int(dut.uart_tx.value) == 0, "start bit was not held low"

    data = 0
    for bit in range(8):
        await ClockCycles(dut.clk, CLKS_PER_BIT)
        data |= int(dut.uart_tx.value) << bit

    await ClockCycles(dut.clk, CLKS_PER_BIT)
    assert int(dut.uart_tx.value) == 1, "stop bit was not high"
    return data


async def recv_dump(dut) -> bytes:
    raw = bytearray()
    for _ in range(FRAME_LEN):
        raw.append(await recv_byte(dut))
    return bytes(raw)


async def wait_status(dut, want: int, timeout: int) -> None:
    for _ in range(timeout):
        if int(dut.status.value) == want:
            return
        await RisingEdge(dut.clk)
    raise AssertionError(f"status never reached {want}, last={int(dut.status.value)}")


async def wait_ready_and_dump(dut, thresh: int, high: int, low: int) -> None:
    await wait_status(dut, ST_FILLING, 64)
    await ClockCycles(dut.clk, PRE_TRIGGER * SAMPLE_PERIOD_CLKS + 8 * SAMPLE_PERIOD_CLKS)
    dut.analog_code.value = low
    for _ in range((DEPTH + 8) * SAMPLE_PERIOD_CLKS):
        if int(dut.status.value) == ST_READY:
            break
        await RisingEdge(dut.clk)
    assert int(dut.status.value) == ST_READY, "capture never reached READY"

    cap = parse_frame(await recv_dump(dut))
    assert cap.n == DEPTH
    assert cap.pre == PRE_TRIGGER
    for i in range(PRE_TRIGGER - 1):
        assert cap.samples[i] >= thresh, f"pre[{i}]=0x{cap.samples[i]:03X} not high"
        assert cap.samples[i] >= high
    assert cap.samples[PRE_TRIGGER - 1] < thresh, "trigger sample was not the falling cross"
    for i in range(PRE_TRIGGER, DEPTH):
        assert cap.samples[i] < thresh, f"post[{i}]=0x{cap.samples[i]:03X} not low"


@cocotb.test()
async def capture_top_arm_via_uart(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, analog=UART_CODE_HIGH)
    assert int(dut.status.value) == ST_IDLE

    await drive_rx_frame(dut, pack_set_thresh(UART_THRESH))
    await drive_rx_frame(dut, pack_arm())
    await wait_ready_and_dump(dut, UART_THRESH, UART_CODE_HIGH, UART_CODE_LOW)


@cocotb.test()
async def capture_top_arm_via_btn(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, analog=CODE_HIGH)
    assert int(dut.status.value) == ST_IDLE

    await pulse_arm_btn(dut)
    await wait_ready_and_dump(dut, DEFAULT_THRESH, CODE_HIGH, CODE_LOW)


def test_capture_top_runner() -> None:
    sim = os.getenv("SIM", "icarus")
    root = Path(__file__).resolve().parents[1]
    runner = get_runner(sim)
    build_dir = root / "tb" / "sim_build" / "capture_top"
    runner.build(
        sources=[
            root / "rtl" / "uart_tx.sv",
            root / "rtl" / "uart_rx.sv",
            root / "rtl" / "host_cmd.sv",
            root / "rtl" / "trigger_detect.sv",
            root / "rtl" / "circ_buffer.sv",
            root / "rtl" / "capture_ctrl.sv",
            root / "rtl" / "adc_spi.sv",
            root / "rtl" / "uart_dump.sv",
            root / "rtl" / "capture_top.sv",
            root / "tb" / "adc_ad7476a_model.sv",
            root / "tb" / "capture_top_tb.sv",
        ],
        hdl_toplevel="capture_top_tb",
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
        hdl_toplevel="capture_top_tb",
        test_module="test_capture_top",
        waves=True,
        build_dir=build_dir,
    )


if __name__ == "__main__":
    test_capture_top_runner()
