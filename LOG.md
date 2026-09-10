# Project log

Working notes for the transient-capture FPGA. Newest entry first.

---

## 2026-09-09 — circular buffer

### Shipped

- `rtl/circ_buffer.sv` — BRAM-inferable ring, pre/post split, freeze, registered read path.
- `tb/test_circ_buffer.py` — wrap, reject trigger before pre-fill, exact POST writes then freeze, chronological dump via `oldest_addr`, crossing sample at index `PRE-1`, `clear` unfreezes without wiping memory.
- `pytest tb/test_circ_buffer.py` — 7/7 passed. UART tests still green.

### Why this memory style / freeze timing

A ring that keeps writing until the post-window is full, then freezes. Trigger is ignored until `PRE_TRIGGER` writes this run so the pre-window is not reset junk. Freeze after `POST = DEPTH - PRE_TRIGGER` **subsequent** writes; the crossing sample is already stored because `trigger_pulse` is one cycle late. After freeze, `oldest_addr` is the next write pointer, so chronological dump is `(oldest_addr + i) % DEPTH` even after wrap. `clear`/`rst` reset pointers only — resetting the array would break Block RAM inference. Write and read are separate; `rd_data` is registered (1-cycle latency).

### Alternatives considered

- **Rejected: combinational freeze-before-write.** Would drop the sample that crossed threshold — the one you actually care about.
- **Rejected: async/sync reset of the memory array.** Infers LUT RAM, not BRAM, on Artix-7.
- **Rejected: smart buffer that also owns idle/filling/ready.** That policy belongs in `capture_ctrl` so the BRAM stays a dumb ring in an interview.

### Timing numbers

- Hardware: 2048 × 12-bit, 512 pre / 1536 post.
- At 1 MSPS: pre ≈ **0.512 ms**, full window ≈ **2.048 ms**. The earlier “~2 ms” note was the full buffer, not the pre-window.
- Sim tests: `DEPTH=16`, `PRE_TRIGGER=4`.
- UART dump later walks physical addresses; account for 1-cycle read latency.

### Explain out loud

- How does pre-trigger survive wrap? (`oldest_addr` after freeze.)
- How do we freeze without losing the sample that crossed threshold? (write on `sample_valid`, pulse next cycle, that write is last pre.)
- Why not reset the BRAM array?

### Open questions

None on depth/split. `clear` is a 1-cycle strobe from the controller; dump must not read while `wr_en` hits the same address (dump only after freeze).

---

## 2026-09-09 — trigger detect

### Shipped

- `rtl/trigger_detect.sv` — programmable threshold, falling (droop) edge, hysteresis re-arm, 1-cycle registered pulse.
- `tb/test_trigger_detect.py` — idle, disarmed, one-shot falling cross, no retrigger below threshold, re-arm after hysteresis, rising step ignored.
- `pytest tb/test_trigger_detect.py` — 6/6 passed. Existing `pytest tb/test_uart_tx.py` still green.

### Why this FSM / timing

Droop is a falling ADC-code cross, not “any sample below threshold,” so a load-step fires once. The pulse is registered **one cycle after** `sample_valid` so the BRAM write of the crossing sample has already happened, and the controller sees a clean strobe. After a fire, stay deaf until `sample >= threshold + HYSTERESIS` (add saturates at `{WIDTH{1'b1}}`) so noise around the threshold cannot retrigger. Unsigned compares: these are codes, not volts. `arm=0` still tracks the last sample so the first armed edge is real.

Default hardware `HYSTERESIS=16` (~4 mV if 3.3 V / 4096). Tests use 4.

### Alternatives considered

- **Rejected: level trigger** (pulse every sample below threshold). That would retrigger for the entire droop and fill the post-window from a mess of extra pulses. The controller also ignores pulses outside FILLING, but the detector itself must be interview-defendable standalone.
- **Rejected: combinational same-cycle pulse.** Faster, but glitchy for BRAM enable/trigger in one NBA region, and it would freeze-before-write if the buffer sampled trigger in the same cycle as `wr_en`.

### Timing numbers

- Sysclk 100 MHz. `sample_valid` is a 1-cycle strobe (hardware: every 100 clocks at 1 MSPS).
- `trigger_pulse` is 1 cycle, one clock after the crossing strobe.
- UART unchanged: 115200 8N1, `CLKS_PER_BIT=868` hardware / 8 in sim.

### Explain out loud

- Why falling-only, not “below threshold”?
- Why hysteresis, and what saturating the add prevents?
- Why is the pulse late by one clock — and how does that protect the crossing sample?

### Open questions

None. Threshold is a port (testbench / later host), not a bitstream constant.

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
