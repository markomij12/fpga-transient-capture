# FPGA Transient Capture & Trigger Core

An FPGA digitizer that watches a PCB load-step, triggers on the voltage droop, buffers the waveform, and streams it to a host.

This repo is the working documentation and HDL for that design. Resume-facing project; PDN solver overlay is a stretch goal.

## Locked decisions

- **Resume-ready:** five RTL blocks, a self-checking cocotb test per block, a bitstream on a real Artix-7 board, and a plotted capture of a real analog step (function generator is enough).
- **Stretch:** overlay that capture against a PDN solver.
- **Language:** SystemVerilog RTL, cocotb 2.x testbenches, Icarus Verilog for fast sim, pytest runners.
- **Clock / UART:** 100 MHz, 115200 8N1 (`CLKS_PER_BIT = 868` on hardware). Sim UART tests use a divider of 8.
- **Hardware, in order:** borrow from lab (any Artix-7 Digilent board with Pmod) → else buy Basys 3 ($165) + Pmod AD1 ($30). Arty A7-35T is retired; do not buy it new. Arty A7-100T ($314) is overkill.
- **ADC:** Pmod AD1 (AD7476A) SPI FSM is the interview block. XADC is fallback only.
- **Buffer:** 2048 × 12-bit samples, 512 pre-trigger (~0.512 ms at 1 MSPS; full window ~2.048 ms).

Dated design notes (why, not just what) live in [`LOG.md`](LOG.md).

## Status

**Simulation complete. No board yet.** ADC model → trigger → circular buffer → UART dump → host parser is proven in Icarus. Do not download Vivado until a board is identified.

Blocked on hardware: LED blink bitstream, XDC, on-hardware UART loopback, real AD7476A, analog-step screenshot.

## Modules

| Module | File | Role |
|---|---|---|
| `uart_tx` | `rtl/uart_tx.sv` | 8N1 transmitter |
| `trigger_detect` | `rtl/trigger_detect.sv` | Falling (droop) threshold, hysteresis, 1-cycle pulse |
| `circ_buffer` | `rtl/circ_buffer.sv` | BRAM ring, 512 pre / 1536 post, freeze, registered read |
| `capture_ctrl` | `rtl/capture_ctrl.sv` | Glue: IDLE / FILLING / TRIGGERED / READY |
| `adc_spi` | `rtl/adc_spi.sv` | AD7476A Mode 3, 16 SCLK, 1 MSPS |
| `uart_dump` | `rtl/uart_dump.sv` | Frozen buffer → UART TC frame |
| `capture_sim_top` | `rtl/capture_sim_top.sv` | Sim-only path (not a board top) |

Sim-only ADC: `tb/adc_ad7476a_model.sv`. Host: `host/frame.py`, `host/capture_logger.py`.

## UART dump frame

Little-endian. Length `7 + 2*N + 1 + 2` bytes (`N` = sample count).

| Offset | Size | Name | Value |
|---|---|---|---|
| 0 | 1 | MAGIC0 | `0x54` `'T'` |
| 1 | 1 | MAGIC1 | `0x43` `'C'` |
| 2 | 1 | VER | `0x01` |
| 3 | 2 | N | uint16 LE sample count |
| 5 | 2 | PRE | uint16 LE pre-trigger count |
| 7 | 2N | SAMPLES | N × uint16 LE, bits[11:0]=ADC, bits[15:12]=0 |
| 7+2N | 1 | XOR8 | XOR of bytes from MAGIC0 through last sample |
| 8+2N | 2 | TRAILER | `0x0D 0x0A` |

Sample `i=0` is oldest (first pre-trigger). Sample `i=PRE-1` is the trigger sample.

```bash
python -m host.capture_logger --input capture.bin --csv out.csv --png out.png
```

`--port` is stubbed until a board exists.

## Simulate (no FPGA required)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# also: brew install icarus-verilog
pytest tb/                          # all blocks + UART + logger + integration
# pytest.ini ignores tb/sim_build (Icarus/cocotb junk)
```

Per block:

```bash
pytest tb/test_uart_tx.py
pytest tb/test_trigger_detect.py
pytest tb/test_circ_buffer.py
pytest tb/test_capture_ctrl.py
pytest tb/test_adc_spi.py
pytest tb/test_capture_logger.py
pytest tb/test_capture_sim_top.py
```

cocotb tests are **not** named `test_*` (pytest would collect them). Each file has a `test_*_runner`. Hardware dividers stay as RTL defaults; tests pass small `parameters={...}`.

## Vivado (later — do not download unless asked)

WebPACK is free from AMD and is tens of GB plus an account. Needed for bitstream, not for this sim. Install when a board exists.

Constraints (`.xdc`) come after the board is identified:

- Lab borrow: whatever Artix-7 Digilent board with a Pmod header shows up.
- Buy-fallback: Basys 3 + Pmod AD1 on a JA-style 6-pin Pmod: `CS`, `D0`, `SCLK` (`D1` unused).

Do not write Basys 3 vs Arty A7 pin maps until that choice is real. LED blink is the first bitstream, then UART loopback, then this capture path.

## Build order

1. UART TX — simulate (done)
2. Trigger + circular buffer + capture controller — simulate (done)
3. ADC SPI FSM + fake AD7476A — simulate (done)
4. Host logger + UART frame — fake bytes (done)
5. Integration sim top — fake analog step over UART (done)
6. Blink an LED once a board exists — toolchain + constraints
7. UART on hardware — loop bytes to a laptop terminal
8. Real ADC over SPI
9. Capture a real analog step and plot it
10. Stretch: solver-vs-hardware plot

See `FPGA_Tinkering_Plan.pdf` for the original scoping note.
