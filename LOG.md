# Project log

Working notes for the transient-capture FPGA. Newest entry first.

---

## 2026-09-09 — README (commands + both tops)

### Shipped

- `README.md` — status includes CT commands, synthesizable top, and GHA.
- Module table: `uart_rx`, `host_cmd`, `capture_top`.
- CT command format documented next to the locked TC dump format.
- `capture_sim_top` vs `capture_top` table (ADC model vs SPI pins, poke/UART vs button/UART, sim vs hardware defaults).
- Local CI: `pytest tb/` (same as `.github/workflows/sim.yml`).
- Vivado still notes-only. No XDC, no bitstream, no `--port`.

### Why this README pass

The sim-complete note was true before host UART existed. A reviewer now needs CT vs TC, and which top to synth later, without reading LOG. Build order gained a done step for RX/commands/top so the next item is still honestly “blink an LED once a board exists.”

### Explain out loud

- Which magic is host→FPGA vs FPGA→host?
- Why does `capture_top` not have `analog_code`?
- What command does CI run, and why is Vivado still not in that path?

### Open questions

Which lab board, if any. Same as before.

---

## 2026-09-09 — GitHub Actions sim CI

### Shipped

- `.github/workflows/sim.yml` — on push/PR to `main`: Ubuntu, Icarus (`iverilog`), Python 3.12 venv, `pip install -r requirements.txt`, `pytest tb/`.
- No Vivado. `sim_build/` stays gitignored; PNG skip in logger tests is fine.

### Why this job

The resume claim is “self-checking cocotb on Icarus.” A laptop-only green suite bit-rots. GHA Ubuntu + apt `iverilog` is the cheapest way to re-run the same `pytest tb/` a reviewer can run locally. Vivado WebPACK is tens of GB and is not needed until a board exists.

### Alternatives considered

- **Rejected: a Vivado/CI bitstream job.** No XDC, no board, no license dance.
- **Rejected: verilator.** The suite is written and passing on Icarus; switching runners now is churn.

### Timing numbers

- Local cached `pytest tb/`: ~3 s. Cold iverilog rebuild of every block: a couple of minutes.
- GHA will be cold each run (no `sim_build/` in git).

### Explain out loud

- What does CI prove that a local pytest does not? (reproducible Ubuntu + Icarus, not “works on my Homebrew”)
- Why is Vivado not in the workflow?

### Open questions

README: `capture_top` vs `capture_sim_top`, CT format, how to run the same command CI runs.

---

## 2026-09-09 — capture_top (synthesizable)

### Shipped

- `rtl/capture_top.sv` — board-shaped top, no ADC model, no XDC, no LED names.
- Ports: `clk`, `rst`, `uart_rx`, `uart_tx`, `adc_cs_n`, `adc_sclk`, `adc_sdata`, `arm_btn`, `status[1:0]`.
- Instantiates `adc_spi`, `capture_ctrl`, `uart_dump` (owns `uart_tx`), `uart_rx`, `host_cmd`.
- Hardware defaults: `DEPTH=2048`, `PRE=512`, `CLKS_PER_BIT=868`, `CLKS_PER_SCLK=5`, `SAMPLE_PERIOD_CLKS=100`. `HYSTERESIS=16` matches `capture_ctrl`.
- `tb/capture_top_tb.sv` — `adc_ad7476a_model` as a sibling, same idea as `adc_spi_tb`. Small sim params.
- `tb/test_capture_top.py` — ARM via CT UART, ARM via `arm_btn` rising edge. Both dump a TC frame.
- `pytest tb/test_capture_top.py tb/test_uart_tx.py` and `pytest tb/` green.

### Why 2-FF + rising-edge on arm_btn

`arm` on `capture_ctrl` is a 1-cycle strobe. An async Basys/Arty button is a dirty level. Feeding it raw would hold FILLING's `clear`/`arm` for as long as the finger is down and would violate CDC. 2-FF sync then `arm_btn_s & ~arm_btn_d` is one clean pulse per press, OR'd with UART `arm_pulse`. Level-sync without edge detect was rejected: a stuck button would re-arm every cycle in READY.

Threshold still only from `host_cmd` (default `0x800`). Button path does not set it.

Dump still on `capture_ready` rising edge, not on arm.

### Alternatives considered

- **Rejected: putting the ADC model inside `capture_top`.** That file has to synth.
- **Rejected: XDC / LED names.** No board in hand; `status[1:0]` is enough for later.
- **Rejected: debounce counter.** Not asked; 2-FF + edge is the interview CDC story. Bounce is a board bring-up problem.

### Timing numbers

- Button pulse appears two clocks after the async rising edge (metastability flops) plus one more flop of history.
- UART ARM still ~0.52 ms at 115200. Button ARM is a few clocks.
- Hardware dump of 2048 samples unchanged: ≈ 0.36 s at 115200.

### Explain out loud

- Why not wire `arm_btn` straight into `capture_ctrl.arm`?
- Rising-edge vs level-sync — what does a held button do?
- `capture_top` vs `capture_sim_top`: which one has `analog_code`, and why?

### Open questions

XDC once a Pmod is plugged in. CI so `pytest tb/` runs on push.

---

## 2026-09-09 — capture_sim_top host UART

### Shipped

- `rtl/capture_sim_top.sv` — added `rx`. Instantiates `uart_rx` + `host_cmd`.
- Threshold pin **removed**. One source: `host_cmd` (default `0x800`). `analog_code` stays a TB pin.
- TB `arm` poke is OR'd with UART `arm_pulse` so the original poke-arm path still works.
- `tb/test_capture_sim_top.py` — poke-arm dump still green; new test bit-bangs CT SET_THRESH (`0xB00`) then CT ARM on `rx`, drops analog `0xC00` → `0xA00` (below 0xB00, **above** default 0x800), parses TC dump on `tx`.
- `pytest tb/` — 14 passed, 1 skipped (PNG import). Dump still starts on `capture_ready` rising edge, not on arm.

### Why drop the threshold pin

Two inputs fighting over `capture_ctrl.threshold` would make a passing poke test prove nothing about UART SET_THRESH. Default `0x800` plus a droop to `0x100` would also fire if SET_THRESH were ignored. The UART test therefore uses a cut (`0xB00`) and a droop code (`0xA00`) that only crosses if the command landed.

### Alternatives considered

- **Rejected: keeping the threshold pin and ignoring it.** A dead port is a lie in an interview.
- **Rejected: removing the `arm` poke.** The original test is a useful bypass of UART bit timing; OR is honest (button vs UART will do the same on the board top).

### Timing numbers

- Command bytes on `rx` use the same `CLKS_PER_BIT=8` as the dump on `tx`.
- SET_THRESH is 8 bytes × 10 bits × 8 clocks; ARM is 6 bytes. Parser pulses `arm` one clock after `rx_valid` (NBA from `uart_rx`).
- Dump still: rising `capture_ready` → 1-cycle `dump_start`.

### Explain out loud

- Why is threshold not a top-level pin anymore?
- How does the UART test prove SET_THRESH, not just the default 0x800?
- Why OR poke-arm with UART arm rather than deleting the poke?

### Open questions

Synthesizable `capture_top` (no ADC model) with `arm_btn` sync.

---

## 2026-09-09 — host_cmd (CT command format)

### Shipped

- `rtl/host_cmd.sv` — byte-strobe parser (`rx_valid` / `rx_data`). No `uart_rx` inside.
- `host/cmd.py` — pack/xor helpers (`pack_arm`, `pack_set_thresh`). Source of truth for the wire format, same role as `host/frame.py` for TC dumps.
- `tb/test_host_cmd.py` — default thresh, ARM, SET_THRESH, 12-bit mask, bad magic/xor/len, unknown CMD, SET then ARM.
- `pytest tb/test_host_cmd.py tb/test_uart_tx.py` — green.

### Locked format (host → FPGA)

Little-endian. Opposite direction from the dump frame. Dump magic is `TC` (`0x54 0x43`); commands are `CT` (`0x43 0x54`) so a host that hex-dumps the line can tell which way a blob is going.

| Offset | Size | Name | Value |
|---|---|---|---|
| 0 | 1 | MAGIC0 | `0x43` `'C'` |
| 1 | 1 | MAGIC1 | `0x54` `'T'` |
| 2 | 1 | VER | `0x01` |
| 3 | 1 | CMD | `0x01` ARM (no payload) or `0x02` SET_THRESH (uint16 LE) |
| 4 | 1 | LEN | payload byte count (`0` or `2`) |
| 5.. | LEN | PAYLOAD | ARM: empty. SET_THRESH: uint16 LE |
| last | 1 | XOR8 | XOR of MAGIC0 through last payload byte (not the XOR byte). **No trailer.** |

ARM is 6 bytes. SET_THRESH is 8 bytes. XOR covers header+payload only, same rule as the TC dump (dump also skips its own XOR and trailer).

### Why a byte FSM, not uart_rx inside

`uart_rx` already turns the wire into 1-cycle strobes. Keeping `host_cmd` on bytes means it tests without bit timing, and the two modules can be written in parallel. Parent wires `uart_rx` → `host_cmd` in the tops.

Default threshold `12'h800` (mid-scale). SET_THRESH stores `[11:0]` of the uint16 (`0xFFFF` → `0xFFF`). `arm_pulse` / `cmd_error` are registered 1-cycle; never both on the same command. Unknown CMD with LEN 0 or 2 is consumed through XOR then `cmd_error`. LEN > 2 errors immediately so a garbage LEN cannot stall the parser.

### Alternatives considered

- **Rejected: folding the parser into `uart_rx`.** Mixes baud timing with protocol; worse standalone tests.
- **Rejected: a trailer on CT.** Dump needs CRLF for a terminal-visible end. Commands are short and already framed by LEN+XOR.
- **Rejected: threshold as a bitstream generic.** Host must be able to change it without re-synth.

### Timing numbers

- Pulse fires on the posedge that samples the XOR byte (or the early-error byte).
- UART still 115200 8N1; a 6-byte ARM is 60 bits ≈ 0.52 ms on the wire.

### Explain out loud

- Why `CT` not `TC`? (direction; a hex dump of TX vs RX must not collide)
- XOR does not include itself. Why?
- What does a bad LEN vs unknown CMD do, and why bound LEN at 2?

### Open questions

Wire `rx` into `capture_sim_top`. Threshold comes from `host_cmd` only (drop the competing top-level pin).

---

## 2026-09-09 — UART RX

### Shipped

- `rtl/uart_rx.sv` — 8N1 receiver, parameterized `CLKS_PER_BIT` (hardware 868, tests 8).
- `tb/test_uart_rx.py` — idle, known bytes (`00 FF 55 A5 31`), false start, bad stop, back-to-back.
- `pytest tb/test_uart_rx.py tb/test_uart_tx.py` — both runners green. `uart_tx` unchanged.

### Why this sampling

Match the TX testbench `recv_byte`: detect falling `rx`, sample the start bit at midpoint (`clk_cnt == CLKS_PER_BIT/2 - 1`, T4 when the divider is 8), then sample data/stop every full bit. Start must stay low and stop must be high, else drop the frame (`rx_valid` stays 0). `rx_valid` is a registered 1-cycle pulse on the stop midpoint with `rx_data` presented that cycle.

No 2-FF sync on `rx` inside this block. Extra delay would shift the sample point relative to `uart_tx` at the sim divider of 8. Button debounce/sync is a board-top problem, not a UART FSM problem.

### Alternatives considered

- **Rejected: oversampling majority vote.** Heavier for Icarus and not needed at 115200 with a 100 MHz clock (868 clocks/bit).
- **Rejected: 2-FF sync in `uart_rx`.** Would still work on hardware (868 >> 2) but would break midpoint math vs `recv_byte` at `CLKS_PER_BIT=8`.

### Timing numbers

- Hardware: 100 MHz / 115200 ≈ 868 clocks/bit; midpoint at count 433.
- Sim: 8 clocks/bit; start sampled at T4; `rx_valid` during the stop bit, before a full-bit `drive_byte` returns — tests monitor in parallel.
- `drive_byte` / TX start bit is 8 clocks low. Detect on first `rx==0`.

### Explain out loud

- Why midpoint, not the edge? (edge is the noisiest point; midpoint is where `recv_byte` already samples TX)
- What happens on a 1–2 clock glitch? (false start, back to IDLE, no pulse)
- Why is `rx_valid` 1-cycle and registered?

### Open questions

Host command parser (`host_cmd`) on these bytes. Wire into `capture_sim_top` after that.

---

## 2026-09-09 — README / Vivado notes

### Shipped

- `README.md` — sim-complete status, module list, UART frame, every pytest command, Vivado-later notes.
- `pytest.ini` — ignore `tb/sim_build` so `pytest tb/` does not walk waveform junk.
- `pytest tb/` — 12 passed, 1 skipped (PNG import). No WebPACK download. No `.xdc`. No bitstream.

### Why notes-only

Vivado WebPACK is tens of GB and only pays off once a board (lab Artix-7 + Pmod, or buy-fallback Basys 3 + Pmod AD1) is in hand. Pin maps for Basys 3 vs Arty A7 would be fiction until that choice is real. Simulation is the resume-defendable work until then.

Rejected writing a placeholder XDC “so the repo looks finished.” A wrong constraint file is worse in an interview than an honest “blocked on hardware.”

### Explain out loud

- What is proven without a board? (ADC model → trigger → BRAM → UART frame → parser)
- What is still blocked? (LED blink, loopback, real AD7476A, analog-step plot)
- Why Basys 3 + Pmod AD1, not Arty A7-35T / A7-100T?

### Open questions

Which lab board, if any.

---

## 2026-09-09 — integration sim top

### Shipped

- `rtl/uart_dump.sv` — walks frozen BRAM in chronological order, emits the locked TC frame through existing `uart_tx`.
- `rtl/capture_sim_top.sv` — ADC model → `adc_spi` → `capture_ctrl` → `uart_dump`. No board pins.
- `tb/test_capture_sim_top.py` — fake analog step, one UART dump, `parse_frame` checks pre high / trigger+post low.
- `pytest tb/test_capture_sim_top.py` — 1/1 passed.

### Why this wiring

Dump is a separate FSM so UART bit timing does not sit inside the capture controller. `dump_start` is a rising edge of `capture_ready`. BRAM `rd_data` is registered: set `rd_addr`, wait one clock, then issue both LE bytes. XOR accumulates while sending header+samples, then the XOR byte and CRLF.

Sim defaults are small (`DEPTH=32`, `PRE=8`, `CLKS_PER_BIT=8`, `CLKS_PER_SCLK=2`, `SAMPLE_PERIOD_CLKS=40`) so the dump finishes in tens of microseconds of sim time. Hardware defaults stay on the leaf modules (2048/512/868/5/100).

Icarus: compile with `-s capture_sim_top` and every RTL file plus `tb/adc_ad7476a_model.sv`. `always @(*)` for the dump byte mux — `always_comb` bit-selects warn on Icarus 13.

### Alternatives considered

- **Rejected: dumping from Python by peeking BRAM.** Would not prove UART framing or `uart_tx` handshake.
- **Rejected: packing 12-bit on the wire here.** Frame is already locked as 16-bit LE.

### Timing numbers

- UART start bit begins the clock after `tx_start` is sampled in IDLE (unchanged `uart_tx`).
- 74-byte sim frame at `CLKS_PER_BIT=8` ≈ 5920 clocks of UART plus ~32 sample periods to fill.
- Hardware dump of 2048 samples: 4106 bytes × 10 bits / 115200 ≈ 0.36 s.

### Explain out loud

- How does chronological dump survive wrap? (`oldest_addr`, then +1 wrap)
- When does dump start relative to READY? (rising edge, one-cycle `dump_start`)
- How do we freeze without losing the crossing sample? (still: write, pulse next cycle, last pre)

### Open questions

Board top / XDC once a Pmod is plugged in. This sim top is not that file.

---

## 2026-09-09 — UART dump frame + host logger

### Shipped

- Frame documented in `host/frame.py` (this is the source of truth; RTL dump must match).
- `host/frame.py` — `pack_frame` / `parse_frame`, `FrameError`.
- `host/capture_logger.py` — `--input file.bin` or `-` (stdin) → CSV; `--png` optional; `--port` stub (needs hardware).
- `tb/test_capture_logger.py` — round-trip, bad xor/magic/truncated, 12-bit mask, CSV from fake bytes.
- `pytest tb/test_capture_logger.py` — 6 passed, 1 skipped (PNG: numpy/matplotlib import can hang in this environment; CLI still has `--png`).
- `requirements.txt` — numpy, matplotlib (for plots on a real machine).

### Frame format

Little-endian. Length `7 + 2*N + 1 + 2`.

| Offset | Size | Name | Value |
|---|---|---|---|
| 0 | 1 | MAGIC0 | `0x54` `'T'` |
| 1 | 1 | MAGIC1 | `0x43` `'C'` |
| 2 | 1 | VER | `0x01` |
| 3 | 2 | N | uint16 LE sample count |
| 5 | 2 | PRE | uint16 LE pre-trigger count |
| 7 | 2N | SAMPLES | N × uint16 LE, bits[11:0]=ADC, bits[15:12]=0 |
| 7+2N | 1 | XOR8 | XOR of MAGIC0 through last sample byte |
| 8+2N | 2 | TRAILER | `0x0D 0x0A` |

Sample `i=0` is oldest. Sample `i=PRE-1` is the trigger sample. Sample `i=PRE` is first post.

At 115200 8N1, a 2048-sample dump is 4106 bytes ≈ 0.36 s.

### Why this packing

16-bit LE, 12-bit right-aligned: hex dumps are readable, numpy `uint16` on x86 is a straight `frombuffer`. XOR8 is a “UART dropped a byte” check, cheap in FPGA (running XOR while shifting BRAM out). XOR covers header+samples only, not itself or the trailer. CRLF is a terminal-visible end and a resync mark if the host becomes a stream parser later.

### Alternatives considered

- **Rejected: packed 12-bit** (3 bytes / 2 samples). Denser on 115200, miserable to debug, easy to desync.
- **Rejected: 16-bit big-endian.** Host is LE; BE would byteswap every capture for no RTL win.
- **Rejected: no checksum.** Silent UART drops would plot garbage and waste interview time.

### Explain out loud

- Why 16-bit LE over packed 12-bit?
- XOR is over the payload only; CRLF is not in the XOR. Why?
- Trigger is sample `PRE-1`; oldest is `i=0`.

### Open questions

Live `--port` UART capture once a board exists.

---

## 2026-09-09 — ADC SPI (AD7476A)

### Shipped

- `rtl/adc_spi.sv` — Mode 3 SPI master, 16 SCLK, fixed sample rate, 12-bit `sample` + `sample_valid`.
- `tb/adc_ad7476a_model.sv` — sim-only part model (latches on CS fall). Idle SDATA is `0`, not `Z` (Icarus X-propagates `1'bz`; the real part three-states).
- `tb/adc_spi_tb.sv` — wrapper so cocotb sees one toplevel.
- `tb/test_adc_spi.py` — idle, 16 SCLK falls/sample, known codes `000/FFF/A50/5A5/001/800`, `sample_valid` period, leading zeros stripped.
- `pytest tb/test_adc_spi.py` — 5/5 passed.

### Why this SPI / timing

AD7476A `tCONVERT = 16 × tSCLK`. Four leading zeros then 12-bit MSB first. CS falling is the sample instant and clocks out the first leading zero. Remaining bits shift on SCLK falling; FPGA samples on rising (Mode 3 / CPOL=1 CPHA=1). DB11..DB0 are rising edges **4–15**. The 16th rising sample is Hi-Z and is ignored, but the 16th falling edge still has to happen — raising CS early **aborts** the conversion.

Hardware: `CLKS_PER_SCLK=5` → 20 MHz (datasheet max). `SAMPLE_PERIOD_CLKS=100` → **1.00 MSPS**. 16×5 = 80 clocks converting, 20 clocks CS high = 200 ns quiet > 50 ns `tQUIET`. Low/high 2+3 clocks meets t5/t6 ≥ 0.4 period. Channel **D0 only** (Pmod AD1 pin 2); D1 unused.

Sim: `CLKS_PER_SCLK=2`, `SAMPLE_PERIOD_CLKS=40` (≥ 16×2+5).

### Alternatives considered

- **Rejected: Mode 0** (SCLK idle low). Does not match the datasheet idle-high clock.
- **Rejected: `CLKS_PER_SCLK=4` (25 MHz).** Over the 20 MHz max.
- **Rejected: fewer than 16 SCLKs / early CS.** Aborts conversion.
- **Rejected: Python bit-bang SDATA.** Weaker interview artifact than an SV model.
- **Rejected: on-chip XADC.** Fallback only; the resume block is the SPI FSM.

### Timing numbers

- 100 MHz sysclk. SCLK 20 MHz. Sample 1 MSPS. UART still 115200 / 868.
- `t2` CS→SCLK ≥ 10 ns: 1 sysclk of CS low, SCLK high, then first fall.

### Explain out loud

- Why 16 SCLK cycles on AD7476A?
- When is the analog input sampled? (CS falling)
- Which rising edges are DB11..DB0, and why ignore the 16th?
- Why idle SDATA=0 in the model?

### Open questions

None for one channel. Dual-channel D0+D1 is out of scope.

---

## 2026-09-09 — capture controller

### Shipped

- `rtl/capture_ctrl.sv` — glue: instantiates `trigger_detect` + `circ_buffer`. Status `IDLE / FILLING / TRIGGERED / READY`.
- Exposed `oldest_addr` (not in the first port sketch) so UART dump can walk chronological samples without reaching into the BRAM.
- `tb/test_capture_ctrl.py` — arm→fill→trigger→ready, `capture_ready` only in READY, second arm starts a new fill, status encoding.
- `pytest tb/test_capture_ctrl.py` — 4/4 passed.

### Why this FSM

The trigger stays a pure edge detector and the buffer stays a dumb ring. IDLE waits for an arm strobe and pulses `clear`; FILLING writes every `sample_valid` and arms the detector only after `pre_filled`; TRIGGERED keeps writing and ignores extra pulses; READY is `frozen` and another arm starts a new fill. `status` is the FSM; `capture_ready` is READY-only.

`arm` on the controller is a **1-cycle strobe**. `arm` on the detector is a **level** (`FILLING && pre_filled`). READY is one cycle after `frozen` because the FSM is registered.

Icarus: compile with `-s capture_ctrl` and all three sources, otherwise iverilog elaborates the first file and reports `Unknown module type: trigger_detect`.

### Alternatives considered

- **Rejected: folding the FSM into `trigger_detect`.** Mixes policy with the edge detector; worse interview story and worse standalone tests.
- **Rejected: auto-dump from READY.** Dump is a separate module so UART timing does not pollute capture.

### Timing numbers

- Sim: `DEPTH=16`, `PRE=4`, `HYSTERESIS=4`, `sample_valid` strobes with a 3-cycle gap (not every clock).
- Hardware defaults: 2048 / 512 / 16.

### Explain out loud

- Strobe vs level `arm`.
- When does FILLING become triggerable? (`pre_filled`)
- Why expose `oldest_addr` from the controller, not only the buffer?

### Open questions

None.

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
