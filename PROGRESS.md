# pyportal-claude-buddy — progress / status

**Status: ✅ working end-to-end.** The PyPortal Titano connects to the Windows Claude
Desktop "Hardware Buddy" over BLE, shows live session data, and approves/denies
tool-permission prompts by touch. See `README.md` for the reproducible build guide.

## What it does now
- Native ESP32 BLE firmware (Bluedroid NUS) → Windows WinRT GATT discovery works.
- SAMD51 (CircuitPython) = the brain: wire protocol + portrait pet UI + touch + audio.
- Live: state, run/wait/total counts, activity message, session + daily tokens.
- Touch APPROVE / DENY → sends `{"ack":"permission",…}` (calibrated, debounced, crash-guarded).
- Audio + speaker-"haptic" feedback; backlight screensaver; emotional reactions.

## Architecture
- **ESP32 (NINA-W102):** native firmware `esp32fw/` = Nordic UART Service GATT server +
  transparent UART0 bridge to the SAMD51. The radio. Advertises `Claude-PyPortal`.
- **SAMD51:** CircuitPython `flash/buddy_ui.py` (→ `D:\code.py`) + `flash/buddy_audio.py`.
  Talks to the ESP32 over `busio.UART(board.ESP_TX, board.ESP_RX)` @115200. The brain.

## Milestones (done)
1. ✅ Root-caused the Windows BLE failure: `_bleio`-over-NINA can't bond / lacks the
   Service-Changed service WinRT needs (confirmed via `tools/winrt_gatt.py` + app logs).
2. ✅ Built + flashed native ESP32 Bluedroid firmware (NUS, open chars). WinRT → SUCCESS_NUS.
3. ✅ Connect/disconnect loop fixed: device now answers `{"cmd":"status"}` polls.
4. ✅ Portrait pet UI: state-driven faces, counts, message, tokens, approval panel.
5. ✅ Touch calibrated & wired: `px=ly, py=480−lx`; APPROVE/DENY send permission acks.
6. ✅ Audio + haptic (reused Pulse `AudioManager`): boot/tap/approve/deny cues.
7. ✅ Polish: backlight screensaver (dim 0.15 after 60 s idle), blink + wink idle life,
   sleepy disconnected face, reactions (celebrate→heart on approve, dizzy on deny,
   heart+beep on reconnect).

## Key facts
- Board: PyPortal Titano, CircuitPython 10.0.3. SAMD51 console = COM7; ESP32 flash
  passthrough data port = COM8 (only when `D:\boot.py` is present).
- ESP32 control pins: `board.ESP_TX/ESP_RX/ESP_GPIO0/ESP_RESET`.
- BLE: device name `Claude-PyPortal`; NUS `6E400001-…` (RX `…02` write, TX `…03` notify).
- esptool.exe: `C:\Users\Shai\AppData\Roaming\Python\Python312\Scripts\esptool.exe`.
- Touch recalibration: set `TOUCH_DEBUG=True` in `buddy_ui.py` (see README).

## Possible next steps (optional)
- **Just-Works bonding** in `esp32fw/src/main.cpp` (BLESecurity + `ESP_LE_AUTH_REQ_SC_BOND`)
  — only if the Claude app ever requires a bonded link (it currently connects to open chars).
- **Info pages / touch tabs** (Pulse-style nav) for a stats screen.
- **WiFi-based features** after restoring `nina-fw` (would require moving BLE off the ESP32).

## RECOVERY / undo
- **Restore WiFi (nina-fw 3.3.0):** with the flash passthrough running (`D:\boot.py` +
  `D:\code.py`=`flash/passthrough.py`, ESP32 in bootloader), flash
  `nina_w102_restore.bin` at `0x0` (1.33 MB → chunked, or the Arduino passthrough route
  for reliability). This replaces the native BLE firmware.
- **Restore the NEAR Pulse app:** copy `D:\pulse_code_backup.py` → `D:\code.py`, delete
  `D:\boot.py`, hard-reset.
- **Re-flash the buddy:** `tools\deploy.ps1` (copies `flash/buddy_ui.py`→`D:\code.py`
  and `flash/buddy_audio.py`); auto-reload applies it.

## Notes / gotchas learned
- The CircuitPython USB-CDC bridge only reliably flashes <~17 KB writes — hence
  `chunkflash.ps1` (16 KB chunks) for `firmware.bin`. Small images flash directly.
- `time.monotonic()` does NOT reset on a soft reload — seed idle timers to `boot`, not 0.
- `adafruit_touchscreen.touch_point` can raise on ADC glitches and returns `None` when
  pressure is out of range — wrap it in try/except (done).
- Each `code.py` deploy resets the ESP32 → BLE drops; the app reconnects in ~30–60 s.
