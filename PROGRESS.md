# pyportal-claude-buddy — progress / status

**Status: ✅ feature parity with the M5StickC reference** (`anthropics/claude-desktop-buddy`),
minus GIF pets (deliberately out of scope) and the IMU-only behaviours the Titano can't do.
Connects to the Windows Claude Desktop "Hardware Buddy" over BLE, shows live session data,
runs a full Tamagotchi-style pet, and approves/denies tool prompts by touch. Confirmed in
real use (live approvals + token-driven levelling persisted across reboots).

## What it does now
- **BLE link:** native ESP32 Bluedroid NUS firmware → Windows WinRT discovery works; SAMD51
  (CircuitPython) is the brain over UART. Answers `{"cmd":"status"}` polls to hold the link.
- **7 persona states** (sleep/idle/busy/attention/celebrate/dizzy/heart) driven by the
  heartbeat + gamification triggers.
- **18 faithful animated pets** — multi-frame pose sequences ported from the reference,
  **lazy-loaded** (one species resident at a time) so RAM stays flat. Tap the pet to cycle.
  State-keyed particle overlays (Zzz / hearts / confetti / swirl).
- **Approval relayout:** on a prompt the pet shrinks to a chip and big full-width
  **APPROVE / DENY** buttons fill the screen. Tap sends `{"cmd":"permission",…,"decision":…}`.
- **Gamification + persistence:** level (tokens/50K), fed, mood (velocity + deny ratio),
  energy, approval/denial counters — persisted to `microcontroller.nvm` (8192 B on this board).
- **Screens behind a touch tab bar:** HOME (pet + HUD) · PET (the stats screen) · INFO ·
  SET (settings).
- **SET / menu:** sound, brightness, HUD on/off, LED (NeoPixel pulses red on attention),
  demo mode, factory reset (tap-twice). Persisted.
- **Demo mode:** cycles fake scenarios while disconnected so the buddy stays lively.
- Audio + speaker-"haptic"; backlight screensaver; boot splash; owner/pet-name from the
  desktop.

## Architecture
- **ESP32 (NINA-W102):** native firmware `esp32fw/` = Nordic UART Service GATT server +
  transparent UART0 bridge. The radio. Advertises `Claude-PyPortal`. (Unchanged; stable.)
- **SAMD51 (CircuitPython), `flash/`:** `buddy_ui.py` (→ `D:\code.py`) orchestrates; logic
  lives in import-pure, host-tested modules:
  - `bud_proto.py` — wire protocol (status ack, heartbeat→state, permission send, owner/name).
  - `bud_stats.py` — gamification + `nvm` persistence + settings bit-flags.
  - `bud_screens.py` — screen geometry + hit-tests (approval / tab / menu rows) + particles.
  - `bud_species.py` — lazy species loader; `bud_species_<name>.py` = per-species pose DATA.
  - `buddy_audio.py` — audio/haptic (reused).

## Tests & tooling (host)
- **`tests/` + pytest** — 33 tests over the pure modules (protocol latch, level/mood math,
  hit-tests, settings persistence, every species × state renders a 5-line pose).
- **`tools/cam.py`** — webcam frame of the screen (deploy → look → verify).
- **`tools/drive.py`** — connects over BLE as a *synthetic desktop* to drive heartbeats /
  prompts (`busy` / `attention` / `level --ramp`) for on-device verification.
- **`tools/serial_log.py`** — COM7 console (boot prints, `[stats]`, tracebacks).
- **`tools/deploy.ps1`** — copies `buddy_audio.py` + every `bud_*.py` + `buddy_ui.py`→`code.py`.

## Build phases (done)
0. Modularize (`bud_proto`/`bud_stats`/`bud_screens`) + pytest harness — no behaviour change.
1. Approval relayout (shrink cat, big buttons).
2. Gamification + `nvm` persistence (level-up→celebrate, approve/deny counters).
3. Screen nav + PET stats + INFO.
4. Touch menu/settings (SET tab) + demo mode + NeoPixel + owner/name + splash + taller tabs.
5. Faithful 18-species pets (lazy-loaded) + tap-to-cycle + particle overlays.
   GIF pets: **out of scope** (backlog "not doing").

## Key facts
- Board: PyPortal Titano, CircuitPython 10.0.3. SAMD51 console = COM7; ESP32 flash
  passthrough data port = COM8 (only when `D:\boot.py` present).
- ESP32 control pins: `board.ESP_TX/ESP_RX/ESP_GPIO0/ESP_RESET`.
- BLE: device name `Claude-PyPortal`; NUS `6E400001-…` (RX `…02` write, TX `…03` notify).
- `nvm` is 8192 B; the packed stats record is 92 B (`bud_stats.NVM_SIZE`).
- Touch recalibration: set `TOUCH_DEBUG=True` in `buddy_ui.py` (see README).
- Serial soft-reboot for testing: send Ctrl-C then Ctrl-D to COM7.

## RECOVERY / undo
- **Restore WiFi (nina-fw 3.3.0):** with the flash passthrough running (`D:\boot.py` +
  `D:\code.py`=`flash/passthrough.py`, ESP32 in bootloader), flash `nina_w102_restore.bin`
  at `0x0` (chunked). Replaces the native BLE firmware.
- **Restore the NEAR Pulse app:** copy `D:\pulse_code_backup.py` → `D:\code.py`, delete
  `D:\boot.py`, hard-reset.
- **Re-flash the buddy:** `tools\deploy.ps1`; auto-reload applies it.

## Notes / gotchas learned
- **RAM is the main constraint.** Steady-state has ~200 KB free, but the boot build can fail
  a *small* alloc via heap **fragmentation** with too many resident displayio objects. Fixes
  that matter: lazy-load species (one at a time), keep label count low (INFO is one
  multi-line label), shrink the UART buffer (2048), and `gc.collect()` between screen builds.
  Boot prints `free=` — keep an eye on it.
- The CircuitPython USB-CDC bridge only reliably flashes <~17 KB writes — hence
  `chunkflash.ps1` (16 KB chunks) for `firmware.bin`. Small images flash directly.
- `time.monotonic()` does NOT reset on a soft reload — seed idle timers to `boot`, not 0.
- `adafruit_touchscreen.touch_point` can raise / return `None` — wrap in try/except (done).
- Each `code.py` deploy resets the ESP32 → BLE drops; the app reconnects in ~30–60 s.
- The permission decision is `{"cmd":"permission",…}` (NOT `"ack"` — that mislabel used to
  hang the gated tool call).
