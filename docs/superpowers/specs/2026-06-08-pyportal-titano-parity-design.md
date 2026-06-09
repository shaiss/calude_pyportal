# PyPortal Titano Buddy — Feature-Parity Design

**Date:** 2026-06-08
**Branch:** `feature/parity`
**Goal:** Bring the PyPortal Titano port (`flash/buddy_ui.py`) to feature parity with the
M5StickC reference (`anthropics/claude-desktop-buddy`), adapting button-driven UX to touch
and dropping only what the hardware can't do.

---

## 1. Context

The reference is an ESP32/Arduino desk pet that watches Claude desktop sessions over BLE
Nordic UART: it shows session counts/activity/tokens, surfaces tool-permission prompts you
approve/deny on-device, and gamifies it (level, mood, energy, fed) with 18 ASCII species +
optional GIF characters across **7 emotional states**.

Our port already nails the hard part — **transport**. The user replaced `nina-fw` with native
ESP32 Bluedroid firmware (`esp32fw/`) exposing a real NUS GATT server, so Windows/WinRT
discovery works and approve/deny is verified bidirectional. The SAMD51 runs CircuitPython
(`flash/buddy_ui.py` → `code.py`) as the brain over UART. What's missing is the entire
**Tamagotchi + content + navigation layer**.

### Hardware deltas (PyPortal Titano vs M5StickC Plus)

| | M5StickC Plus | PyPortal Titano | Consequence |
|---|---|---|---|
| Input | 2 buttons + power | **resistive touch only** | nav becomes on-screen tabs/buttons |
| Motion | IMU (accel) | **none** | shake/face-down/landscape-clock don't port |
| Display | 135×240 | 320×480 (HX8357) | more room; bigger approval buttons |
| Persist | NVS (Preferences) | `microcontroller.nvm` (~256B) | packed struct instead of keyed store |
| LED | red LED | NeoPixel | attention pulse → NeoPixel |
| Radio | built-in BLE | ESP32 (native fw) | already solved |
| RTC | yes (coin cell) | none | charging-clock face = optional/deferred |

### Out of scope (explicit)

- **GIF pets** until the final phase (Phase 6): folder-push receiver over UART + `gifio`
  decode + microSD storage. Sequenced last by agreement.
- **Charging-clock face** (no RTC): optional, deferred; if added later, drive time from the
  bridge `time` sync, portrait-only (no IMU rotation).
- **BLE pairing passkey UI**: the ESP32 chars are open/Just-Works; skip.
- Settings that don't apply on Titano: bluetooth toggle (BLE is always-on via ESP32),
  wifi (no stack while BLE fw is flashed), clock-rotation.

---

## 2. Architecture

The 450-line `buddy_ui.py` becomes a thin orchestrator (`code.py`) plus focused modules
deployed alongside it on `CIRCUITPY`. Python's module system gives us the isolation the
reference faked with header-only file-static state.

```
code.py            main loop: poll proto, derive state, tick pet, route touch, persist
bud_proto.py       UART line-framing, JSON parse, status ack, heartbeat→TamaState, permission send
bud_stats.py       gamification (level/fed/mood/energy/counters/velocity) + nvm persistence + settings
bud_pets.py        species renderer (pose sequences + particle layer), cycling, peek mode
bud_species.py     the 18 species' frame data (ported from buddies/*.cpp)
bud_screens.py     HOME / PET / INFO draw + approval relayout
bud_menu.py        touch menu + settings + reset overlays
bud_ui.py          shared: colors, layout constants, tab bar, touch hit-testing, NeoPixel
buddy_audio.py     unchanged (reuse)
```

**Module boundaries / contracts:**
- `bud_proto` owns a `TamaState` (sessions/tokens/msg/lines/prompt/connected). `code.py` reads
  it; nothing else writes it. Mirrors the reference `TamaState` in `data.h`.
- `bud_stats` owns the persisted struct + derived tiers. Pure logic + nvm I/O; no display deps.
  Exposes `on_bridge_tokens`, `on_approval(secs)`, `on_denial`, `on_nap_end(secs)`, `on_wake`,
  and read-only `level/fed/mood/energy/counters/settings`.
- `bud_pets` owns one `displayio.Group` for the pet; `tick(state)` advances animation;
  `set_species_idx`/`next_species`/`peek`. Knows nothing about screens.
- `bud_screens`/`bud_menu` own their groups; `code.py` toggles which is active.
- `bud_ui` holds shared constants/colors and the persistent tab bar + touch routing helpers.

**CircuitPython constraints to respect:**
- Filesystem is read-only to CircuitPython while USB is mounted → **persist via
  `microcontroller.nvm`**, not files. (GIF storage in Phase 6 uses microSD to sidestep this.)
- `time.monotonic()` does not reset on soft reload → seed timers from a captured `boot`.
- `touchscreen.touch_point` can raise on ADC glitches / return None → wrap in try/except
  (already done in v1; preserve).
- RAM is ~256KB; watch module + species-data footprint (see §6).

---

## 3. Wire protocol (unchanged, already working)

Newline-framed JSON over UART. Keep v1 behavior; just move it into `bud_proto`.

| Dir | Message | Action |
|---|---|---|
| app→dev | `{"cmd":"status"}` | reply `{"ack":"status","ok":true,"data":{"name":"Claude-PyPortal","sec":true,"sys":{"up":N}}}` |
| app→dev | `{"total","running","waiting","tokens","tokens_today","msg","entries","prompt"}` | drive UI + stats |
| app→dev | `{"cmd":"owner","name":...}` / `{"cmd":"name",...}` | store owner / pet name (NEW: persist) |
| app→dev | `{"time":[epoch,tzoff]}` | optional soft-clock seed (deferred feature) |
| dev→app | `{"cmd":"permission","id":...,"decision":"once"|"deny"}` | approve/deny |

Add to the status `data` ack over time: `bat`, `stats:{appr,deny,vel,nap,lvl}` (the desktop
stats panel reads these). Battery: PyPortal has no fuel gauge; report what's available or omit.

---

## 4. State model (restore the reference's 7 states)

`derive(state)` base states, plus one-shot overlays:

- **sleep** — not connected (or screensaver) → sleepy face, slow.
- **idle** — connected, nothing urgent.
- **busy** — `running > 0` (reference uses ≥3; we keep `>0` — fewer sessions on a desk pet).
- **attention** — `waiting > 0` (prompt pending) → NeoPixel pulse.
- **celebrate** — one-shot on **level-up** (every 50K tokens), 3s.
- **dizzy** — one-shot on **deny** (IMU shake substitute), 1.5s; also tap-the-pet.
- **heart** — one-shot on **approve < 5s**, and on reconnect, 2s.

One-shots take over `activeState` until they expire, then fall back to the derived base.

---

## 5. Gamification + persistence (port `stats.h`)

`bud_stats` ports the reference logic verbatim where it's pure:

- `TOKENS_PER_LEVEL = 50000`; `level = tokens // 50000`.
- `fed` = `(tokens % 50000) // 5000` → 0..9 on a 10-pip bar (the 10th fills only at level-up).
- `mood` 0..4 from **median of an 8-slot velocity ring** (seconds-to-respond) minus a penalty
  when denial ratio is high (`d>a → −2`, `2d>a → −1`); neutral (2) with no data.
- `energy` 0..5: boots at 3, set to 5 on nap-end, drains 1 per 2h since last nap.
- Token accounting: bridge sends cumulative `tokens`; **latch first-sight**, add deltas, and on
  a drop (bridge restart) resync without crediting. Level-up sets a pending flag → celebrate.
- Counters: `approvals`, `denials`, `napSeconds`. Persist on significant events only
  (approval/denial/nap-end/level-up/settings change) to limit flash wear.

**`nvm` layout** (single `struct`-packed record, written sparingly):

```
magic 'B' (1) | version (1) | tokens u32 | approvals u16 | denials u16 |
napSeconds u32 | level u8 | velIdx u8 | velCount u8 | velocity[8] u16 (16) |
settings bitfield u8 | brightLevel u8 | speciesIdx u8 |
petName 24s | ownerName 32s
```
≈ 95 bytes — well under the ~256B `nvm`. **Verify `len(microcontroller.nvm)` on-device in
Phase 2**; if smaller than expected, drop names to a shorter cap. A leading magic+version lets
us detect uninitialized/format-changed nvm and reset to defaults.

**Nap substitute (no IMU):** the screensaver-idle period *is* the nap. When the screen
dims/sleeps after inactivity, mark nap start; on wake (touch), `on_nap_end(elapsed)` +
`on_wake()` (refills energy). Approximates "set it face-down to rest."

---

## 6. Pet system — faithful animations

Port the reference's procedural ASCII animation, not just static faces.

**Data shape** (`bud_species.py`), one entry per species:
```python
# state -> (frames, sequence, divisor, particles)
#   frames    : tuple of pose strings (each pose = "\n"-joined lines, fixed width)
#   sequence  : tuple of frame indices (the beat pattern)
#   divisor   : tick // divisor selects the beat (controls speed)
#   particles : None or a spec (kind, colors, motion params) for Zzz/confetti/hearts/stars/dots
```
This is a direct translation of each `buddies/<name>.cpp`: the `LOAF/BREATHE/...` pose arrays
→ `frames`, the `SEQ[]` → `sequence`, the `/N` in `(t/N)` → `divisor`, and the per-state
particle loops → `particles`.

**Renderer** (`bud_pets`):
- Body: one `label.Label` (terminalio mono), text swapped each beat; scale chosen so a
  ~12×5 pose fills the upper home area (and a smaller scale for PET/INFO "peek").
- Particles: a small pool of reused `label.Label`s (or a single `Bitmap`/`TileGrid`) updated
  per tick — Zzz drift, confetti rain, rising hearts, orbiting stars, busy dots.
- Tick ~8–12 fps. Cat ships first (already proven), then the other 17 in Phase 5.

**RAM mitigation:** if all 18 species resident is too heavy, lazy-import the active species'
data and `gc.collect()` the rest on switch. Decide empirically in Phase 5; the renderer API
stays the same either way.

---

## 7. Navigation & screens (touch)

**Persistent top bar** (~28px): `HOME │ PET │ INFO` tabs + a `≡` menu button. Tap a tab to
switch mode; tap `≡` to open the menu overlay. (On-screen controls over swipe — resistive
touch is twitchy; this mirrors the reference's explicit A=next-screen / hold-A=menu.)

- **HOME** — animated pet + bottom HUD: state badge, `run/wait/tot`, activity msg, `tok/today`.
  (v1's screen, minus the scale-6 dominance, with the tab bar on top.)
- **PET** — 2 pages (tap page dots to flip): **stats** (mood ♥, fed pips, energy bars,
  `Lv`, approved/denied/napped/tokens/today — the screen in the user's photo) and **how-to**.
- **INFO** — pages: About, **Touch** (replaces "Buttons"), Claude (sessions/link), Device
  (power/heap/uptime/owner), Credits. Bluetooth page adapted (link status, device name).

**Approval relayout** (the headline ask) — on `prompt` present + `waiting>0`:
```
┌────────────────────────────┐
│ (•‿•) attention      12s    │  pet → small chip + wait timer (HOT after 10s)
├────────────────────────────┤
│ APPROVE?                    │
│ <tool>          (large)     │
│ <hint>                      │
│ ┌────────────────────────┐ │
│ │        APPROVE         │ │  full-width, ~90px tall, green
│ └────────────────────────┘ │
│ ┌────────────────────────┐ │
│ │         DENY           │ │  full-width, ~90px tall, red
│ └────────────────────────┘ │
└────────────────────────────┘
```
Tab bar suppressed until decided. Reuses v1's calibrated/debounced touch + audio cues;
just larger hit zones and the pet shrinks instead of staying scale-6. After a decision: show
`sent: approve/deny`, fire celebrate→heart / dizzy, then return to the prior screen.

---

## 8. Menu, settings, demo, power, personalization

- **Menu** (`≡`): settings · screen off · help (→INFO Touch) · about (→INFO About) ·
  demo on/off · close.
- **Settings** (touch list, tap to change): brightness (display.brightness levels), sound
  on/off, led (NeoPixel) on/off, transcript/HUD on/off, ascii pet (cycle species), reset.
- **Reset**: factory reset = clear `nvm` → defaults (+ delete-char once Phase 6 exists).
  Tap-twice confirm (`really?`), as in the reference.
- **Demo mode**: cycle the reference `_FAKES` scenarios every 8s, driving the UI without live
  data — enables webcam verification of all 7 states. Off by default.
- **Owner / pet name**: parse `owner`/`name` commands, persist to nvm; boot splash
  "`<owner>'s <petName>`" or "Hello! a buddy appears".
- **Power**: NeoPixel pulses on attention (respects `led`). Screen dims then sleeps after idle
  (default ~30s; never while a prompt is up); any touch wakes (and ends the "nap").

---

## 9. Phase plan & acceptance

Each phase is independently runnable on-device and ends with a **webcam verification**
(`device-eyes` skill).

| Phase | Deliverable | Acceptance (webcam-verified) |
|---|---|---|
| **0** | Modularize `buddy_ui.py` into the §2 modules (no behavior change) + `nvm` scaffolding + CLAUDE.md | device boots, shows the same v1 cat/HUD, connects, approves/denies — i.e. **no regression** |
| **1** | Approval relayout (§7) | a prompt shows small pet chip + big APPROVE/DENY; tap sends the right decision |
| **2** | Gamification + persistence (§5) | level/fed/mood/energy update from live tokens & decisions; survive a reboot |
| **3** | Screen nav + PET stats + INFO (§7) | tabs switch HOME/PET/INFO; PET shows the stats screen; pages flip |
| **4** | Menu/settings/reset/demo/owner-name/splash/NeoPixel/screen-off (§8) | menu opens; settings persist; demo cycles states; NeoPixel pulses on attention |
| **5** | Faithful 18 species (§6) | cycle through 18 animated species; choice persists; particles render |
| **6** | GIF pets (folder-push + `gifio` + microSD) | drag a pack from desktop → device switches to GIF mode live |

**Global non-regression invariant:** at every phase the device must still connect to Claude
Desktop and approve/deny correctly — that's the one feature that already works and must not break.

---

## 10. Risks

- **RAM** with 18 species resident (§6) — mitigate via lazy-load + `gc.collect()`.
- **`nvm` size** assumption (§5) — verify on-device; design fits regardless.
- **Animation perf** — label-text swaps at ~10fps should be cheap; if particle labels cost too
  much, switch the particle layer to a single Bitmap.
- **Deploy churn** — each `code.py` save resets the ESP32 and drops BLE (~30–60s reconnect);
  expected, documented in PROGRESS.
- **Touch reliability** — keep v1's try/except + debounce; size touch targets generously.
```
