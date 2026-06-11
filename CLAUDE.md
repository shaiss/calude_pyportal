# CLAUDE.md — PyPortal-Claude-Buddy

A desk-pet companion for Claude Desktop's "Hardware Buddy", on an **Adafruit PyPortal
Titano**. It watches Claude sessions over BLE and lets you **approve/deny tool prompts by
touch**. This is a port of `anthropics/claude-desktop-buddy` (originally M5StickC).

> Status: **feature parity achieved** (PRs #1–3 merged to `main`) — 7 states, 18 lazy-loaded
> animated species + particles, gamification + `nvm` persistence, HOME/PET/INFO/SET screens
> behind a touch tab bar, menu/settings, demo mode, owner/splash. GIF custom-character packs
> are **out of scope** ("not doing"). Spec/plan archived in `docs/superpowers/`.

## Architecture — two chips

```
Claude Desktop (Windows, WinRT/Web Bluetooth)
   │  BLE — Nordic UART Service (RX 6E400002 write, TX 6E400003 notify)
   ▼
ESP32 NINA-W102 ── native Bluedroid firmware (esp32fw/) ──┐   the RADIO
   │  UART0 @115200, newline-framed JSON                   │
   ▼                                                       │
SAMD51 ── CircuitPython (flash/ → D:\code.py) ─────────────┘   the BRAIN
   ├─ 3.5" 320×480 HX8357 TFT (portrait) — pet + status + approval
   ├─ resistive touch — the only input (no buttons)
   └─ speaker (simpleio.tone) — chimes + low-freq "haptic" thud
```

The ESP32 is a pure BLE radio bridged over UART; **the SAMD51 is the brain** (CircuitPython
UI + wire protocol). The custom ESP32 firmware is what makes Windows BLE discovery work — do
**not** reflash it with `nina-fw` unless you mean to remove BLE (a restore image is included).

## Code layout

- `flash/` — what runs on the device. `buddy_ui.py` → deploy as `D:\code.py` (orchestrator);
  logic lives in import-pure, host-tested modules: `bud_proto` (wire protocol), `bud_stats`
  (gamification + nvm + settings), `bud_screens` (geometry / hit-tests / particles),
  `bud_species` (lazy loader) + `bud_species_<name>.py` (18 per-species pose DATA);
  `buddy_audio` (reused audio).
- `esp32fw/` — native ESP32 BLE firmware (PlatformIO/Arduino, NUS GATT + UART bridge). Stable.
- `tests/` — host pytest over the pure modules (no hardware).
- `tools/` — host helpers: `deploy.ps1`, `cam.py` (webcam), `drive.py` (synthetic-desktop BLE
  driver), `serial_log.py` (COM7 console), BLE bring-up tests.
- `.claude/skills/device-eyes/` — the webcam verification skill (see below).
- `nina_w102_restore.bin` — stock WiFi firmware to undo the BLE flash.

## Hardware facts & constraints

- **PyPortal Titano**: SAMD51J20 + ESP32 (NINA-W102), 320×480 HX8357, resistive touch, speaker,
  NeoPixel, microSD slot. **No IMU. No RTC.** CircuitPython 10.x (`CIRCUITPY` = `D:`).
- **Persist via `microcontroller.nvm`** (8192 B here; packed record is 92 B) — the CircuitPython
  filesystem is read-only to the device while USB is mounted, so you can't write files at runtime.
- **RAM / fragmentation (the recurring trap):** ~200KB free at steady state, but the boot build
  can fail a *small* alloc via heap fragmentation if too many displayio objects accrue. Keep
  labels few (consolidate multi-line text), lazy-load species (one resident at a time), keep the
  UART buffer small, and `gc.collect()` between screen builds. Boot prints `free=` — watch it.
- **No IMU** → the reference's shake→dizzy / face-down→nap / landscape-clock don't port;
  re-trigger those via touch/timers (nap ≈ screensaver idle).
- `time.monotonic()` does NOT reset on soft reload — seed timers from a captured `boot`.
- `touchscreen.touch_point` can raise / return None — always wrap in try/except.
- COM7 = SAMD51 console; COM8 = ESP32 flash passthrough (only when `D:\boot.py` is present).

## Common commands

```powershell
tools/deploy.ps1                     # copy buddy_audio + every bud_*.py + buddy_ui.py→D:\code.py
python tools/cam.py                  # webcam-capture the screen → ./cam.jpg  (then Read it)
python tools/drive.py busy           # synthetic Claude desktop over BLE (busy/attention/level --ramp)
python tools/serial_log.py COM7 10   # log the device console (boot prints, [stats], tracebacks)
python -m pytest tests/ -q           # host tests over the pure modules (no hardware)
cd esp32fw ; pio run                 # build the ESP32 BLE firmware
```
Serial soft-reboot for testing: send Ctrl-C then Ctrl-D to COM7. Device libs in `D:\lib/`
(Adafruit CP 10.x bundle): `adafruit_display_text`, `adafruit_display_shapes`,
`adafruit_touchscreen`, `neopixel`, `simpleio` (`adafruit_hx8357` is built into the board).

## Verifying changes — look at the device

There is a **USB webcam pointed at the screen**. After any deploy, **capture and look** — do
not claim a UI change works from code alone. Use the **`device-eyes`** skill (or
`python tools/cam.py`, then Read `cam.jpg`). The glossy HX8357 reflects glare; re-grab if a
frame is washed out. A near-black frame usually means the screensaver dimmed it (tap to wake),
not a crash.

## Conventions & invariants

- **Don't break BLE approve/deny.** It's the one feature that already works end-to-end; every
  change must keep the device connecting to Claude Desktop and sending correct
  `{"cmd":"permission",...}` decisions.
- Persist to `nvm` **sparingly** (significant events only) — flash has limited write cycles.
- Match the existing CircuitPython style (displayio groups, terminalio font, the v1 color set).
- **Don't push** to `github.com/shaiss/calude_pyportal` without asking. Work on a feature branch.
- A `code.py` deploy resets the ESP32 → BLE drops; the app reconnects in ~30–60s. Expected.

## Reference

The upstream behavior targeted: `anthropics/claude-desktop-buddy` — 7 states
(sleep/idle/busy/attention/celebrate/dizzy/heart), 18 ASCII species, gamification (level/fed/
mood/energy), touch menu/settings, PET/INFO screens — **all ported**. GIF custom-character
packs are intentionally NOT ported (out of scope). Wire protocol in its `REFERENCE.md`.
