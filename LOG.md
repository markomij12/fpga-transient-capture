# Project log

Working notes for the transient-capture FPGA. Newest entry first.

---

## 2026-09-09

### Shipped

- SystemVerilog `uart_tx` (8N1, parameterized `CLKS_PER_BIT`).
- cocotb + Icarus testbench: idle-after-reset, known-byte frames (`00 FF 55 A5 31`), busy-start ignored.
- Sim environment: Homebrew `icarus-verilog` 13.0, cocotb 2.1, pytest. GTKWave installed for later waveform inspection.
- `pytest tb/test_uart_tx.py` — 3/3 passed.

### Still open (no board required)

1. **Trigger + circular buffer** — next RTL. Working assumption: 2048 × 12-bit samples, 512 pre-trigger (2 ms window at 1 MSPS). Simulate against a fake step/sawtooth.
2. **ADC SPI FSM** — can be written from the Pmod AD1 datasheet (AD7476A) before the module exists.
3. **Host logger** — Python script to read UART bytes and plot a capture. Useful even with a function-generator step.
4. **Vivado WebPACK** — long download; needed for bitstream later, not for sim.

### Blocked on hardware

- LED blink, UART loopback on a board, real ADC, analog-step screenshot.
- Lab borrow first (any Artix-7 Digilent board with Pmod). Else buy Basys 3 + Pmod AD1 (~$195, ~$166 academic).

---

## 2026-09-08

### Repo

- Public GitHub: https://github.com/markomij12/fpga-transient-capture
- Seeded with `FPGA_Tinkering_Plan.pdf` and README.

### Locked

| Decision | Choice |
|---|---|
| Why this exists | Resume FPGA/ASIC bullet. Defendable HDL + testbench + board capture. |
| Analog target | Board-level droop, ~1 MSPS, 10–12 bit. Not package first-droop. |
| Resume-ready bar | Five RTL blocks, cocotb per block, bitstream, plotted analog step (function generator OK). |
| Stretch | Overlay capture vs PDN solver. Not a gate. |
| Language | SystemVerilog RTL, cocotb TB, Icarus for fast sim. |
| Clock / UART | 100 MHz, 115200 8N1, `CLKS_PER_BIT = 868` on hardware. |
| Board | Do not buy retired Arty A7-35T. Lab first. Buy-fallback: Basys 3, not Arty A7-100T. |
| ADC | Pmod AD1 (SPI FSM is the interview block). On-chip XADC is fallback only. |
