# Phase 0–1 Implementation Plan — Modularize + Approval Relayout

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a tested, modular foundation for the Titano buddy (Phase 0) and ship the
approval-screen relayout — shrink the pet, big touch APPROVE/DENY buttons (Phase 1) — without
regressing the working BLE approve/deny path.

**Architecture:** Pull pure logic (wire protocol, gamification/persistence) out of the 450-line
`flash/buddy_ui.py` into import-pure modules (`bud_proto`, `bud_stats`) that take hardware as
parameters (dependency injection), so they run under host pytest. `buddy_ui.py` keeps the main
loop + display and wires the real UART/nvm in. UI modules (`bud_screens`, `bud_pets`, etc.) are
carved out in their own phases as they're rewritten, not pre-emptively. Spec:
`docs/superpowers/specs/2026-06-08-pyportal-titano-parity-design.md`.

**Tech stack:** CircuitPython 10.x (SAMD51), `displayio`/`terminalio`/`adafruit_display_*`,
`busio.UART` to the ESP32 BLE radio, `microcontroller.nvm`, `struct`, `json`. Host tests: CPython
3.12 + `pytest`.

---

## Testing approach (read first)

- **Pure modules** (`bud_proto`, `bud_stats`) import only `json`/`struct` (present in both CPython
  and CircuitPython) and never touch `board`/`displayio`/`microcontroller`. They take buffers and
  numbers as parameters. → Unit-tested on the host with `pytest`.
- **UI / hardware** (approval relayout, pet render) → verified **on-device** by deploying and
  capturing the screen with the `device-eyes` skill (`python tools/cam.py`, then Read `cam.jpg`).
- **Non-regression invariant (every task):** the device must still connect to Claude Desktop and
  send correct `{"cmd":"permission",...}` decisions. If a deploy crashes to the REPL, the webcam
  frame will be blank/error text — that's a failed task.

**Run host tests:** `python -m pytest tests/ -v` (from repo root).

**Deploy to device:** `tools/deploy.ps1` (copies `flash/buddy_ui.py`→`D:\code.py` +
`flash/*.py` modules). A deploy resets the ESP32 → BLE reconnects in ~30–60s.

---

## File structure

| File | Responsibility | Phase |
|---|---|---|
| `flash/bud_proto.py` | NEW. `TamaState`, `parse_line`, `status_ack`, `permission_cmd` — pure | 0 |
| `flash/bud_stats.py` | NEW. `Stats` (nvm pack/unpack + level/fed/mood/energy + event hooks) — pure | 0 |
| `flash/bud_screens.py` | NEW. `build_approval()` group + `approval_hit()` | 1 |
| `flash/buddy_ui.py` | MODIFY. Use `bud_proto` for parsing; rebuild approval via `bud_screens` | 0,1 |
| `tests/conftest.py` | NEW. Put `flash/` on `sys.path` | 0 |
| `tests/test_proto.py` | NEW. protocol parsing tests | 0 |
| `tests/test_stats.py` | NEW. gamification + nvm tests | 0 |
| `tests/test_screens.py` | NEW. approval hit-test | 1 |

---

# PHASE 0 — Modular, tested foundation (no behavior change)

### Task 0.1: Host test harness

**Files:** Create `tests/conftest.py`

- [ ] **Step 1: Create conftest that exposes the device modules to pytest**

```python
# tests/conftest.py
import os
import sys

# Device modules live in flash/ and are import-pure (json/struct only), so they
# import cleanly under host CPython for unit testing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "flash"))
```

- [ ] **Step 2: Verify pytest collects (no tests yet is fine)**

Run: `python -m pytest tests/ -v`
Expected: "no tests ran" (exit 5) — confirms pytest + path work, no import errors.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "Add host pytest harness for pure device modules"
```

---

### Task 0.2: `bud_proto` — wire protocol (pure)

**Files:** Create `flash/bud_proto.py`, `tests/test_proto.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_proto.py
import bud_proto as P

def test_heartbeat_populates_state():
    st = P.TamaState()
    P.parse_line('{"total":8,"running":1,"waiting":0,"tokens":97000,'
                 '"tokens_today":241000,"msg":"git push"}', st)
    assert (st.total, st.running, st.waiting) == (8, 1, 0)
    assert st.tokens == 97000 and st.tokens_today == 241000
    assert st.msg == "git push"

def test_status_poll_returns_ack_with_uptime():
    st = P.TamaState()
    reply = P.parse_line('{"cmd":"status"}', st, uptime=42)
    assert reply is not None and '"ack":"status"' in reply
    assert '"up":42' in reply and '"name":"Claude-PyPortal"' in reply

def test_prompt_set_and_clear():
    st = P.TamaState()
    P.parse_line('{"total":1,"running":0,"waiting":1,'
                 '"prompt":{"id":"req_1","tool":"Bash","hint":"rm -rf x"}}', st)
    assert (st.prompt_id, st.prompt_tool, st.prompt_hint) == ("req_1", "Bash", "rm -rf x")
    P.parse_line('{"total":1,"running":0,"waiting":0}', st)
    assert st.prompt_id == ""

def test_entries_bump_line_gen_only_on_change():
    st = P.TamaState()
    P.parse_line('{"total":1,"entries":["a","b"]}', st)
    g1 = st.line_gen
    P.parse_line('{"total":1,"entries":["a","b"]}', st)   # unchanged
    assert st.line_gen == g1
    P.parse_line('{"total":1,"entries":["a","b","c"]}', st)  # changed
    assert st.line_gen == g1 + 1

def test_permission_cmd_format():
    assert P.permission_cmd("req_9", "once") == \
        '{"cmd":"permission","id":"req_9","decision":"once"}'
    assert P.permission_cmd("req_9", "deny") == \
        '{"cmd":"permission","id":"req_9","decision":"deny"}'

def test_owner_and_name_commands():
    st = P.TamaState()
    assert '"ack":"owner"' in P.parse_line('{"cmd":"owner","name":"Shai"}', st)
    assert st.owner_pending == "Shai"
    assert '"ack":"name"' in P.parse_line('{"cmd":"name","name":"Clawd"}', st)
    assert st.name_pending == "Clawd"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_proto.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bud_proto'`.

- [ ] **Step 3: Implement `bud_proto.py`**

```python
# flash/bud_proto.py — wire protocol, pure (json only). No I/O, no hardware.
import json


class TamaState:
    def __init__(self):
        self.total = 0
        self.running = 0
        self.waiting = 0
        self.tokens = 0
        self.tokens_today = 0
        self.msg = ""
        self.lines = []
        self.line_gen = 0
        self.prompt_id = ""
        self.prompt_tool = ""
        self.prompt_hint = ""
        self.connected = False
        self.owner_pending = None   # set when an owner cmd arrives; consumed by caller
        self.name_pending = None


def _ack(name):
    return '{"ack":"%s","ok":true}' % name


def status_ack(uptime):
    return ('{"ack":"status","ok":true,"data":{"name":"Claude-PyPortal",'
            '"sec":true,"sys":{"up":%d}}}' % int(uptime))


def permission_cmd(pid, decision):
    return '{"cmd":"permission","id":"%s","decision":"%s"}' % (pid, decision)


def parse_line(line, st, uptime=0):
    """Parse one JSON line into `st`. Return a reply string to send, or None. Pure: no I/O."""
    try:
        d = json.loads(line)
    except (ValueError, MemoryError):
        return None
    cmd = d.get("cmd")
    if cmd == "status":
        return status_ack(uptime)
    if cmd == "owner":
        st.owner_pending = d.get("name", "")
        return _ack("owner")
    if cmd == "name":
        st.name_pending = d.get("name", "")
        return _ack("name")
    if "total" in d:
        st.total = d.get("total", st.total)
        st.running = d.get("running", st.running)
        st.waiting = d.get("waiting", st.waiting)
        st.tokens = d.get("tokens", st.tokens)
        st.tokens_today = d.get("tokens_today", st.tokens_today)
        st.msg = d.get("msg", st.msg)
        entries = d.get("entries")
        if isinstance(entries, list):
            new = [str(e) for e in entries[:8]]
            if new != st.lines:
                st.lines = new
                st.line_gen += 1
        pr = d.get("prompt")
        if pr:
            st.prompt_id = str(pr.get("id", ""))
            st.prompt_tool = str(pr.get("tool", ""))
            st.prompt_hint = str(pr.get("hint", ""))
        else:
            st.prompt_id = st.prompt_tool = st.prompt_hint = ""
        return None
    return None
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python -m pytest tests/test_proto.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add flash/bud_proto.py tests/test_proto.py
git commit -m "Add bud_proto: pure wire-protocol parsing with host tests"
```

---

### Task 0.3: Wire `bud_proto` into `buddy_ui.py` (behavior-preserving), verify on-device

**Files:** Modify `flash/buddy_ui.py`

The v1 loop hand-parses lines inline (`buddy_ui.py:310-366`). Replace that block's JSON handling
with `bud_proto`, keeping the *same* UI behavior. The UART read/buffer/`\n`-split stays; only the
per-line interpretation moves to `parse_line`.

- [ ] **Step 1: Import and construct state**

Near the top imports of `buddy_ui.py`, add:
```python
import bud_proto
```
After the `# ---------- state ----------` block, add:
```python
tama = bud_proto.TamaState()
```

- [ ] **Step 2: Replace inline parsing with `parse_line`**

In the `while b"\n" in buf:` loop, replace the two `if line ...` branches (status poll + heartbeat)
with:
```python
reply = bud_proto.parse_line(line.decode("utf-8", "ignore"), tama,
                             uptime=int(time.monotonic() - boot))
if reply is not None:
    uart.write((reply + "\n").encode("utf-8"))
last_data = time.monotonic()
# drive the existing UI from tama (keep the v1 set_state / counts / msg / approval calls):
if tama.waiting > 0:
    set_state("attention")
elif tama.running > 0:
    set_state("busy")
else:
    set_state("idle")
if tama.waiting > 0 or tama.running > 0 or tama.prompt_id:
    last_lively = time.monotonic()
    if dimmed:
        set_bright(1.0); dimmed = False
cs = "run %d  wait %d  tot %d" % (tama.running, tama.waiting, tama.total)
if cs != last_counts:
    counts.text = cs; last_counts = cs
if tama.prompt_id and tama.waiting > 0:
    show_approval({"id": tama.prompt_id, "tool": tama.prompt_tool, "hint": tama.prompt_hint})
else:
    hide_approval()
    mtxt = wrap2(tama.msg, 26)
    if mtxt != last_msg:
        msg.text = mtxt; last_msg = mtxt
    toks.text = "tok %s  today %s" % (fmtk(tama.tokens), fmtk(tama.tokens_today))
```
Delete the now-dead inline `if b'"cmd"'...` and `if line.startswith(b'{"total"'...)` blocks. Keep
`show_approval`/`hide_approval`/`set_state` as in v1 (Phase 1 rewrites the approval visuals).

- [ ] **Step 3: Deploy**

Run: `tools/deploy.ps1`
Expected: copies `buddy_ui.py`→`D:\code.py` and `bud_proto.py`→`D:\bud_proto.py`. (If
`deploy.ps1` only copies `buddy_ui.py`+`buddy_audio.py`, update it to also copy `flash/bud_*.py` —
see Task 0.5.)

- [ ] **Step 4: Verify on-device (no regression)**

Run: `python tools/cam.py` then Read `cam.jpg`.
Expected: device boots to the cat/HUD exactly as before (sleepy cat if disconnected, or live
counts if connected). NOT a REPL traceback. If connected, confirm a real approve/deny still works.

- [ ] **Step 5: Commit**

```bash
git add flash/buddy_ui.py
git commit -m "Route buddy_ui parsing through bud_proto (no behavior change)"
```

---

### Task 0.4: `bud_stats` — gamification + nvm persistence (pure scaffolding)

**Files:** Create `flash/bud_stats.py`, `tests/test_stats.py`. Not yet wired to UI (Phase 2 does
that), so no behavior change on-device.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_stats.py
import bud_stats as S

def test_pack_roundtrip_through_a_fake_nvm():
    nvm = bytearray(256)
    a = S.Stats()
    a.tokens = 184502; a.approvals = 42; a.denials = 3; a.nap_seconds = 740
    a.species_idx = 5; a.pet_name = "Buddy"; a.owner_name = "Shai"
    a.velocity = [12, 8, 30, 0, 0, 0, 0, 0]; a.vel_count = 3
    a.save(nvm)
    b = S.Stats.load(nvm)
    assert b.tokens == 184502 and b.approvals == 42 and b.denials == 3
    assert b.nap_seconds == 740 and b.species_idx == 5
    assert b.pet_name == "Buddy" and b.owner_name == "Shai"
    assert b.velocity[:3] == [12, 8, 30] and b.vel_count == 3

def test_uninitialized_nvm_loads_defaults():
    s = S.Stats.load(bytearray(256))   # all zero → bad magic
    assert s.tokens == 0 and s.pet_name == "Buddy" and s.level == 0

def test_level_and_fed():
    s = S.Stats(); s.tokens = 125000
    assert s.level_of() == 2          # 125000 // 50000
    assert s.fed() == 5               # (25000 // 5000)

def test_token_latch_ignores_first_sight_then_adds_delta():
    s = S.Stats()
    s.on_bridge_tokens(100000)        # first sight: latch, credit nothing
    assert s.tokens == 0
    s.on_bridge_tokens(100000 + 60000)   # +60k crosses a level
    assert s.tokens == 60000 and s.level == 1 and s.poll_levelup() is True
    assert s.poll_levelup() is False

def test_bridge_restart_resyncs_without_crediting():
    s = S.Stats()
    s.on_bridge_tokens(100000); s.on_bridge_tokens(120000)
    assert s.tokens == 20000
    s.on_bridge_tokens(5000)          # number dropped → restart
    assert s.tokens == 20000          # unchanged
    s.on_bridge_tokens(5000 + 3000)
    assert s.tokens == 23000

def test_mood_drops_with_heavy_denial():
    s = S.Stats()
    for _ in range(5):
        s.on_approval(10)             # fast → high base tier
    high = s.mood()
    s.denials = 10                    # d > a
    assert s.mood() < high

def test_energy_drains_over_time():
    assert S.energy_tier(5, 0.0) == 5
    assert S.energy_tier(5, 4.0) == 3     # -1 per 2h
    assert S.energy_tier(5, 100.0) == 0   # floored
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bud_stats'`.

- [ ] **Step 3: Implement `bud_stats.py`**

```python
# flash/bud_stats.py — gamification + nvm persistence. Pure (struct only); nvm injected.
import struct

TOKENS_PER_LEVEL = 50000
_FMT = "<BBIHHIBBB8HBBB24s32s"     # magic,ver,tokens,appr,deny,nap,lvl,vIdx,vCnt,vel[8],
                                   # settingsBits,bright,species,petName,ownerName
NVM_SIZE = struct.calcsize(_FMT)   # 92
_MAGIC = ord("B")
_VERSION = 1
DEFAULT_SETTINGS = 0b00001111      # sound|led|hud|(spare) on; adjust as settings land


def energy_tier(energy_at_nap, hours_since_nap):
    e = int(energy_at_nap) - int(hours_since_nap // 2)
    return 0 if e < 0 else 5 if e > 5 else e


class Stats:
    def __init__(self):
        self.tokens = 0
        self.approvals = 0
        self.denials = 0
        self.nap_seconds = 0
        self.level = 0
        self.vel_idx = 0
        self.vel_count = 0
        self.velocity = [0] * 8
        self.settings_bits = DEFAULT_SETTINGS
        self.bright_level = 4
        self.species_idx = 0
        self.pet_name = "Buddy"
        self.owner_name = ""
        self._last_bridge = 0
        self._synced = False
        self._levelup = False

    @classmethod
    def load(cls, nvm):
        s = cls()
        if len(nvm) >= NVM_SIZE:
            try:
                v = struct.unpack(_FMT, bytes(nvm[:NVM_SIZE]))
            except Exception:
                v = None
            if v and v[0] == _MAGIC and v[1] == _VERSION:
                (_, _, s.tokens, s.approvals, s.denials, s.nap_seconds,
                 s.level, s.vel_idx, s.vel_count,
                 v0, v1, v2, v3, v4, v5, v6, v7,
                 s.settings_bits, s.bright_level, s.species_idx, pn, on) = v
                s.velocity = [v0, v1, v2, v3, v4, v5, v6, v7]
                s.pet_name = pn.split(b"\x00", 1)[0].decode("utf-8", "ignore") or "Buddy"
                s.owner_name = on.split(b"\x00", 1)[0].decode("utf-8", "ignore")
        return s

    def pack(self):
        return struct.pack(
            _FMT, _MAGIC, _VERSION, self.tokens & 0xFFFFFFFF,
            self.approvals & 0xFFFF, self.denials & 0xFFFF, self.nap_seconds & 0xFFFFFFFF,
            self.level & 0xFF, self.vel_idx & 0xFF, self.vel_count & 0xFF,
            *(self.velocity + [0] * 8)[:8],
            self.settings_bits & 0xFF, self.bright_level & 0xFF, self.species_idx & 0xFF,
            self.pet_name.encode("utf-8")[:24], self.owner_name.encode("utf-8")[:32])

    def save(self, nvm):
        nvm[0:NVM_SIZE] = self.pack()

    def level_of(self):
        return self.tokens // TOKENS_PER_LEVEL

    def fed(self):
        return (self.tokens % TOKENS_PER_LEVEL) // (TOKENS_PER_LEVEL // 10)

    def on_bridge_tokens(self, total):
        if not self._synced:
            self._last_bridge = total
            self._synced = True
            return
        if total < self._last_bridge:        # bridge restarted
            self._last_bridge = total
            return
        delta = total - self._last_bridge
        self._last_bridge = total
        if delta == 0:
            return
        before = self.tokens // TOKENS_PER_LEVEL
        self.tokens += delta
        after = self.tokens // TOKENS_PER_LEVEL
        if after > before:
            self.level = after
            self._levelup = True

    def poll_levelup(self):
        r = self._levelup
        self._levelup = False
        return r

    def on_approval(self, secs):
        self.approvals += 1
        self.velocity[self.vel_idx] = min(int(secs), 65535)
        self.vel_idx = (self.vel_idx + 1) % 8
        if self.vel_count < 8:
            self.vel_count += 1

    def on_denial(self):
        self.denials += 1

    def on_nap_end(self, secs):
        self.nap_seconds += int(secs)

    def median_velocity(self):
        if self.vel_count == 0:
            return 0
        t = sorted(self.velocity[:self.vel_count])
        return t[len(t) // 2]

    def mood(self):
        v = self.median_velocity()
        if v == 0:
            tier = 2
        elif v < 15:
            tier = 4
        elif v < 30:
            tier = 3
        elif v < 60:
            tier = 2
        elif v < 120:
            tier = 1
        else:
            tier = 0
        a, d = self.approvals, self.denials
        if a + d >= 3:
            if d > a:
                tier -= 2
            elif d * 2 > a:
                tier -= 1
        return max(0, tier)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python -m pytest tests/test_stats.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add flash/bud_stats.py tests/test_stats.py
git commit -m "Add bud_stats: gamification + nvm persistence (pure) with host tests"
```

---

### Task 0.5: Ensure `deploy.ps1` copies the new modules

**Files:** Modify `tools/deploy.ps1`

- [ ] **Step 1: Read `tools/deploy.ps1`** and confirm whether it copies all `flash/*.py`.

- [ ] **Step 2: If it only copies `buddy_ui.py`+`buddy_audio.py`, make it copy every `flash/*.py`**

```powershell
# copy every device module, not just the two originals
Get-ChildItem "$PSScriptRoot\..\flash\*.py" | ForEach-Object {
    $dest = if ($_.Name -eq "buddy_ui.py") { "D:\code.py" } else { "D:\$($_.Name)" }
    Copy-Item $_.FullName $dest -Force
}
```
(Keep `boot.py` handling as-is — it's only for ESP32 reflash, not a runtime module.)

- [ ] **Step 3: Deploy + webcam-verify still boots clean** (`tools/deploy.ps1`; `python tools/cam.py`).

- [ ] **Step 4: Commit**

```bash
git add tools/deploy.ps1
git commit -m "deploy.ps1: copy all flash/*.py modules to the device"
```

---

# PHASE 1 — Approval relayout (shrink pet, big buttons)

### Task 1.1: `approval_hit` — pure touch hit-test

**Files:** Create `flash/bud_screens.py`, `tests/test_screens.py`

The new layout: two stacked full-width buttons in the lower screen. APPROVE on top, DENY below.
Hit-test maps a portrait tap `(px, py)` to `"approve"`, `"deny"`, or `None`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_screens.py
import bud_screens as SC

W, H = 320, 480

def test_tap_in_approve_band():
    assert SC.approval_hit(W // 2, SC.APPROVE_Y + 10, W, H) == "approve"

def test_tap_in_deny_band():
    assert SC.approval_hit(W // 2, SC.DENY_Y + 10, W, H) == "deny"

def test_tap_above_buttons_is_none():
    assert SC.approval_hit(W // 2, 100, W, H) is None

def test_tap_between_buttons_is_none():
    gap_y = (SC.APPROVE_Y + SC.BTN_H + SC.DENY_Y) // 2
    assert SC.approval_hit(W // 2, gap_y, W, H) is None
```

- [ ] **Step 2: Run — verify fail** (`python -m pytest tests/test_screens.py -v` → ModuleNotFound).

- [ ] **Step 3: Implement the geometry + hit-test in `bud_screens.py`**

```python
# flash/bud_screens.py — approval screen layout + hit-testing.
# Geometry constants are the single source of truth shared by the renderer and the hit-test,
# so a tap can never disagree with what's drawn.

BTN_MARGIN = 14
BTN_H = 96
APPROVE_Y = 300          # top of the APPROVE button
DENY_Y = APPROVE_Y + BTN_H + 16   # top of the DENY button


def approval_hit(px, py, w, h):
    """Map a portrait tap to 'approve' / 'deny' / None using the button bands."""
    if px < BTN_MARGIN or px > w - BTN_MARGIN:
        return None
    if APPROVE_Y <= py <= APPROVE_Y + BTN_H:
        return "approve"
    if DENY_Y <= py <= DENY_Y + BTN_H:
        return "deny"
    return None
```

- [ ] **Step 4: Run — verify pass** (`python -m pytest tests/test_screens.py -v` → 4 pass).

- [ ] **Step 5: Commit**

```bash
git add flash/bud_screens.py tests/test_screens.py
git commit -m "Add bud_screens approval geometry + hit-test (host tested)"
```

---

### Task 1.2: Rebuild the approval group + shrink the pet on prompt

**Files:** Modify `flash/buddy_ui.py` (the `appr` group ~`buddy_ui.py:216-230`, `show_approval`
~`279-296`, `hide_approval` ~`298-305`, and the touch hit-test ~`395-413`)

- [ ] **Step 1: Replace the approval `displayio.Group` with the big-button layout**

Replace the current `appr` build block with (uses `bud_screens` constants):
```python
import bud_screens
from adafruit_display_shapes.rect import Rect

appr = displayio.Group()
# small status chip lives at the very top while the prompt is up (pet shrinks to make room)
appr_head = label.Label(terminalio.FONT, text="approve?", color=AMBER, scale=2, x=16, y=250)
appr.append(appr_head)
appr_tool = label.Label(terminalio.FONT, text="", color=FG, scale=3, x=16, y=278)
appr.append(appr_tool)
appr_hint = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=16, y=296)
# (hint sits just above the buttons; keep it short)
_bm, _bh = bud_screens.BTN_MARGIN, bud_screens.BTN_H
appr.append(Rect(_bm, bud_screens.APPROVE_Y, W - 2 * _bm, _bh, fill=0x0C3A17, outline=GREEN))
appr.append(label.Label(terminalio.FONT, text="APPROVE", color=GREEN, scale=4,
                        x=W // 2 - 84, y=bud_screens.APPROVE_Y + _bh // 2))
appr.append(Rect(_bm, bud_screens.DENY_Y, W - 2 * _bm, _bh, fill=0x3A0C0C, outline=RED))
appr.append(label.Label(terminalio.FONT, text="DENY", color=RED, scale=4,
                        x=W // 2 - 48, y=bud_screens.DENY_Y + _bh // 2))
appr.hidden = True
root.append(appr)
```

- [ ] **Step 2: Shrink the pet while a prompt is up**

In `show_approval`, when first showing (`if not last_appr:`), add:
```python
pet.scale = 2
pet.x, pet.y = 220, 20      # tuck the shrunken pet into the top-right as a status chip
```
In `hide_approval`, restore:
```python
pet.scale = 6
pet.x, pet.y = 46, 70
```
(Confirm the exact restore coords match the v1 `pet` Label — `buddy_ui.py:203-204` — adjust if the
tab bar from Phase 3 later moves it.)

- [ ] **Step 3: Replace the touch hit-test with `bud_screens.approval_hit`**

In the touch block, replace the two hardcoded `if 412 <= py <= 470 ...` branches with:
```python
hit = bud_screens.approval_hit(px, py, W, H)
if hit == "approve":
    uart.write((bud_proto.permission_cmd(prompt_id, "once") + "\n").encode("utf-8"))
    appr_head.text = "sent: approve"; appr_head.color = GREEN
    last_touch_act = nowt; play("success_chime")
    react("celebrate", GREEN, 0.8, then=("heart", PINK, 0.9))
    print("[touch] APPROVE id=%s" % prompt_id)
elif hit == "deny":
    uart.write((bud_proto.permission_cmd(prompt_id, "deny") + "\n").encode("utf-8"))
    appr_head.text = "sent: deny"; appr_head.color = RED
    last_touch_act = nowt; play("error_buzz"); react("dizzy", AMBER, 1.5)
    print("[touch] DENY id=%s" % prompt_id)
```

- [ ] **Step 4: Deploy** (`tools/deploy.ps1`).

- [ ] **Step 5: Verify on-device — needs a prompt on screen**

To see the relayout without waiting for a live Claude prompt, temporarily force one: near the top
of the main loop add (REMOVE after verifying):
```python
# TEMP verify-approval: comment back out before committing
if int(time.monotonic() - boot) > 5 and not tama.prompt_id:
    show_approval({"id": "test", "tool": "Bash", "hint": "rm -rf /tmp/foo"}); tama.waiting = 1
```
Deploy, then `python tools/cam.py` → Read `cam.jpg`. Expected: small pet chip top-right, big
APPROVE (green) over big DENY (red) filling the lower screen. Tap each (if reachable) and confirm
the `[touch] APPROVE/DENY` console line. Then REMOVE the TEMP block, redeploy, and confirm a real
prompt still works (or the disconnected cat returns).

- [ ] **Step 6: Commit**

```bash
git add flash/buddy_ui.py
git commit -m "Phase 1: approval relayout — shrink pet, full-width APPROVE/DENY buttons"
```

---

## Self-review

- **Spec coverage (Phase 0–1):** modularization foundation (0.1–0.5) ✔; nvm persistence
  scaffolding (0.4) ✔; protocol extraction (0.2–0.3) ✔; approval relayout — small pet + big
  buttons (1.1–1.2) ✔. Gamification *wiring* into UI is intentionally Phase 2; here it's pure +
  tested only.
- **Placeholders:** none — all code shown in full; the one TEMP block (Task 1.2 Step 5) is an
  explicit, remove-before-commit verification hook, not a stub.
- **Type consistency:** `bud_proto.parse_line`/`permission_cmd` signatures match their usage in
  buddy_ui Tasks 0.3 & 1.2; `bud_screens.APPROVE_Y/DENY_Y/BTN_H/BTN_MARGIN/approval_hit` defined in
  1.1 are exactly what 1.2 consumes; `Stats` fields used in tests match the implementation.
- **Risk note:** if `deploy.ps1` already copies all modules, Task 0.5 is a no-op confirm. Verify the
  v1 `pet` Label coords in Task 1.2 Step 2 against `buddy_ui.py` before trusting the restore values.
```
