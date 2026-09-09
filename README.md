# FPGA Transient Capture & Trigger Core

An FPGA digitizer that watches a PCB load-step, triggers on the voltage droop, buffers the waveform, and streams it to a host for comparison against a PDN solver prediction.

This repo is the working documentation and HDL for that design.

## What it is

Five blocks, one design:

1. **ADC interface FSM** — SPI (or onboard ADC) read state machine at a fixed sample rate
2. **Trigger-detect logic** — comparator against a programmable threshold; detects the droop edge
3. **Circular buffer (BRAM)** — continuous pre-trigger / post-trigger capture; freezes on trigger
4. **UART TX core** — streams the captured buffer to a PC for logging and plotting
5. **Top-level integration** — wired together, with a self-checking testbench per block

## Target hardware

- Board: Digilent Arty A7-35T (Xilinx Artix-7)
- ADC: Digilent Pmod AD1 / AD2 (or equivalent SPI ADC on a Pmod header)

## Tooling

- Xilinx Vivado (WebPACK) — synthesis, P&R, bitstream
- Icarus Verilog + GTKWave — fast RTL iteration
- cocotb — Python testbenches
- Serial terminal (`minicom` / `screen`) — UART debug

## Build order

Do these in sequence. Do not skip.

1. Blink an LED — toolchain, constraints, and bitstream flow
2. UART TX core — simulate, then loop bytes to a laptop terminal
3. Circular buffer + trigger — simulate against a fake sawtooth / step waveform
4. Real ADC over SPI — debug on hardware with a function generator or the PCB
5. Full integration — capture a real load-step droop, export, compare to the solver
6. Write-up — block diagram, waveform screenshot, solver-vs-hardware plot

## Status

Planning. HDL not started.

See `FPGA_Tinkering_Plan.pdf` for the original scoping note.
