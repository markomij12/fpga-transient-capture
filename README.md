# FPGA Transient Capture & Trigger Core

An FPGA digitizer that watches a PCB load-step, triggers on the voltage droop, buffers the waveform, and streams it to a host.

This repo is the working documentation and HDL for that design. Resume-facing project; PDN solver overlay is a stretch goal.

## Locked decisions

- **Resume-ready:** five RTL blocks, a self-checking cocotb test per block, a bitstream on a real Artix-7 board, and a plotted capture of a real analog step (function generator is enough).
- **Stretch:** overlay that capture against a PDN solver.
- **Language:** SystemVerilog RTL, cocotb testbenches, Icarus Verilog for fast sim.
- **Clock / UART:** 100 MHz, 115200 8N1 (`CLKS_PER_BIT = 868` on hardware).
- **Hardware, in order:** borrow from lab (any Artix-7 Digilent board with Pmod) → else buy Basys 3 ($165) + Pmod AD1 ($30). Arty A7-35T is retired; do not buy it new. Arty A7-100T ($314) is overkill.

## Blocks

1. **ADC interface FSM** — SPI read state machine, fixed sample rate
2. **Trigger-detect logic** — programmable threshold, droop edge
3. **Circular buffer (BRAM)** — pre-trigger / post-trigger capture
4. **UART TX core** — stream the captured buffer to a PC
5. **Top-level integration** — one design, one bitstream

## Status

UART TX is in simulation. No board yet. Dated notes live in [`LOG.md`](LOG.md).

## Simulate (no FPGA required)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# also: brew install icarus-verilog
pytest tb/test_uart_tx.py
```

## Build order

1. UART TX — simulate (current)
2. Blink an LED once a board exists — toolchain + constraints
3. UART on hardware — loop bytes to a laptop terminal
4. Circular buffer + trigger — simulate against a fake step
5. Real ADC over SPI
6. Capture a real analog step and plot it
7. Stretch: solver-vs-hardware plot

See `FPGA_Tinkering_Plan.pdf` for the original scoping note.
