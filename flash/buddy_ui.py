# pyportal-claude-buddy : SAMD51 buddy app with touchscreen pet UI (v1, portrait 320x480).
# ESP32 = native BLE radio (NUS). This SAMD51 = brain: speaks the wire protocol over UART
# AND renders the pet + status on the Titano's HX8357, ported from the M5StickC original.
# v1 = display + state-driven pet + status HUD + approval panel (touch approve/deny is v2).
import time
import json
import board
import busio
import digitalio
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
import adafruit_touchscreen
import bud_proto
import bud_screens
import bud_stats
import bud_species
import microcontroller

# ---------- ESP32 (native BLE firmware) in run mode ----------
gpio0 = digitalio.DigitalInOut(board.ESP_GPIO0)
gpio0.switch_to_output(True)
reset = digitalio.DigitalInOut(board.ESP_RESET)
reset.switch_to_output(True)
gpio0.value = True
reset.value = False
time.sleep(0.1)
reset.value = True
time.sleep(0.6)
uart = busio.UART(board.ESP_TX, board.ESP_RX, baudrate=115200,
                  timeout=0, receiver_buffer_size=8192)

# ---------- Display: portrait 320x480 ----------
display = board.DISPLAY
try:
    display.rotation = 0
    if display.width > display.height:      # ensure portrait
        display.rotation = 90
except Exception as e:
    print("[ui] rotation err:", e)
W, H = display.width, display.height
print("[ui] display %dx%d" % (W, H))

# Resistive touch. Use the Titano's known-good LANDSCAPE calibration (proven by the Pulse
# UI) so touch_point reliably returns a point, then rotate that point into our portrait
# pixel space ourselves. The on-screen "t lx,ly>px,py" readout lets the webcam confirm and
# lock the rotation/flips without needing a serial console.
TS_LW, TS_LH = 480, 320          # native landscape extents the calibration maps onto
try:
    ts = adafruit_touchscreen.Touchscreen(
        board.TOUCH_XL, board.TOUCH_XR, board.TOUCH_YD, board.TOUCH_YU,
        calibration=((5200, 59000), (5800, 57000)), size=(TS_LW, TS_LH))
except Exception as e:
    print("[ui] touch init err:", e)
    ts = None

# landscape (lx 0..480, ly 0..320) -> portrait (px 0..320, py 0..480).
# Best-guess 90deg rotation; the readout lets us flip these live after one real tap.
TOUCH_SWAP = True
TOUCH_FLIP_X = False
TOUCH_FLIP_Y = True
TOUCH_DEBUG = False   # True -> show the raw "t lx,ly>px,py" readout for recalibration


def to_portrait(lx, ly):
    px, py = (ly, lx) if TOUCH_SWAP else (lx, ly)
    if TOUCH_FLIP_X:
        px = W - px
    if TOUCH_FLIP_Y:
        py = H - py
    return int(px), int(py)


# ---------- audio + haptic feedback (reused from the proven Pulse AudioManager) ----------
try:
    import buddy_audio
    snd = buddy_audio.AudioManager()
    if not getattr(snd, "audio", False):
        snd = None
except Exception as e:
    print("[ui] audio init err:", e)
    snd = None


def play(name):
    if snd is None or not stats.setting(bud_stats.S_SOUND):
        return
    try:
        getattr(snd, name)()
    except Exception:
        pass


BG = 0x000000
FG = 0xFFFFFF
DIM = 0x8B949E
GREEN = 0x3FB950
RED = 0xF85149
AMBER = 0xD29922
BLUE = 0x58A6FF
PINK = 0xF778BA
DIV = 0x30363D

FACES = {
    "idle":      " /\\_/\\\n( o.o )\n  >^<",
    "busy":      " /\\_/\\\n( -.- )\n  >~<",
    "attention": " /\\_/\\\n( O.O )\n  >!<",
    "sleep":     " /\\_/\\\n( z.z )\n  >_<",
    "celebrate": " /\\_/\\\n( ^o^ )\n  >v<",
    "dizzy":     " /\\_/\\\n( @.@ )\n  >x<",
    "heart":     " /\\_/\\\n( ^.^ )\n  <3",
}
SCOL = {"idle": GREEN, "busy": BLUE, "attention": RED, "sleep": DIM,
        "celebrate": AMBER, "dizzy": AMBER, "heart": PINK, "disc": DIM}


def fmtk(n):
    try:
        n = int(n)
    except Exception:
        return "?"
    if n >= 1000000:
        return "%.1fM" % (n / 1000000.0)
    if n >= 1000:
        return "%dk" % (n // 1000)
    return str(n)


def fmt_dur(s):
    s = int(s)
    if s < 60:
        return "%ds" % s
    if s < 3600:
        return "%dm%02ds" % (s // 60, s % 60)
    return "%dh%02dm" % (s // 3600, (s % 3600) // 60)


def wrap2(s, n):
    s = str(s)
    out = []
    while s and len(out) < 2:
        out.append(s[:n])
        s = s[n:]
    return "\n".join(out)


def short_mid(s, n):
    s = str(s)
    if len(s) <= n:
        return s
    keep = n - 2
    left = keep // 2
    return s[:left] + ".." + s[-(keep - left):]


def eye_swap(face, eyes):
    lines = face.split("\n")
    if len(lines) >= 2:
        lines[1] = eyes
    return "\n".join(lines)


def blink_face(face):
    return eye_swap(face, "( -.- )")


def face_for(st):
    if st == "disc":
        return FACES["sleep"]
    return FACES.get(st, FACES["idle"])


SS_IDLE = 60.0  # seconds with no Claude activity before the panel dims (screensaver)


def set_bright(level):
    try:
        display.brightness = level
    except Exception:
        pass


def react(state_key, color=None, dur=1.5, then=None):
    """Briefly show an emotion *state* over the base animation; optionally chain `then`
    as a follow-up (state_key, color, dur). The loop renders the species frames for
    react_state while a reaction is active; `color` is ignored (state drives color)."""
    global reacting, react_until, react_then, react_state
    react_state = state_key
    react_until = time.monotonic() + dur
    reacting = True
    react_then = then


# ---------- build UI ----------
root = displayio.Group()
root.append(Rect(0, 0, W, H, fill=BG))

# top tab bar: HOME | PET | INFO | SET (tap to switch screens); active tab brightened.
TAB_W = W // len(bud_screens.TABS)
tab_lbls = []
for _i, _nm in enumerate(bud_screens.TABS):
    _lb = label.Label(terminalio.FONT, text=_nm.upper(), color=DIM, scale=3,
                      x=_i * TAB_W + 8, y=16)
    tab_lbls.append(_lb)
    root.append(_lb)
root.append(Rect(0, bud_screens.TAB_H, W, 1, fill=DIV))

# ---- HOME: pet + status HUD ----
home_grp = displayio.Group()
badge = label.Label(terminalio.FONT, text="starting", color=DIM, scale=2, x=10, y=62)
home_grp.append(badge)
dbg = label.Label(terminalio.FONT, text="", color=AMBER, scale=2, x=10, y=86)
home_grp.append(dbg)
pet = label.Label(terminalio.FONT, text=FACES["idle"], color=FG, scale=bud_species.SPECIES_SCALE,
                  x=16, y=110, line_spacing=0.95)
home_grp.append(pet)
home_grp.append(Rect(8, 300, W - 16, 2, fill=DIV))
counts = label.Label(terminalio.FONT, text="", color=FG, scale=2, x=10, y=322)
home_grp.append(counts)
msg = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=356, line_spacing=1.1)
home_grp.append(msg)
toks = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=462)
home_grp.append(toks)
root.append(home_grp)

# ---- PET: gamification stats (the photo screen); texts set by draw_pet() ----
pet_grp = displayio.Group()
_py = bud_screens.TAB_H + 14
pet_title = label.Label(terminalio.FONT, text="Buddy", color=FG, scale=2, x=10, y=_py)
pet_mood = label.Label(terminalio.FONT, text="", color=PINK, scale=2, x=10, y=_py + 30)
pet_fed = label.Label(terminalio.FONT, text="", color=GREEN, scale=2, x=10, y=_py + 56)
pet_energy = label.Label(terminalio.FONT, text="", color=AMBER, scale=2, x=10, y=_py + 82)
pet_lv = label.Label(terminalio.FONT, text="", color=FG, scale=3, x=10, y=_py + 118)
pet_appr = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=_py + 152)
pet_deny = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=_py + 176)
pet_nap = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=_py + 200)
pet_tok = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=_py + 224)
pet_today = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=_py + 248)
for _l in (pet_title, pet_mood, pet_fed, pet_energy, pet_lv,
           pet_appr, pet_deny, pet_nap, pet_tok, pet_today):
    pet_grp.append(_l)
pet_grp.hidden = True
root.append(pet_grp)

# ---- INFO: what it is + hardware (static for now) ----
info_grp = displayio.Group()
# one multi-line label (not 12) -- far fewer displayio objects = less RAM/fragmentation
info_grp.append(label.Label(
    terminalio.FONT, scale=2, color=DIM, x=10, y=bud_screens.TAB_H + 20, line_spacing=1.3,
    text=("I watch your Claude\ndesktop sessions and\nsurface approvals.\n\n"
          "tap a prompt's\nAPPROVE / DENY.\n\n"
          "PyPortal Titano\nSAMD51 + ESP32 BLE\n\ngithub.com/shaiss\n/calude_pyportal")))
info_grp.hidden = True
root.append(info_grp)

# ---- SET: settings rows (tap a row to toggle/cycle); texts set by draw_set() ----
set_grp = displayio.Group()
set_rows = []
for _i, _nm in enumerate(bud_screens.MENU_ROWS):
    _r = label.Label(terminalio.FONT, text=_nm, color=FG, scale=3, x=14,
                     y=bud_screens.MENU_TOP + _i * bud_screens.MENU_ROW_H + 14)
    set_rows.append(_r)
    set_grp.append(_r)
set_grp.hidden = True
root.append(set_grp)

# approval overlay: full-screen, so the base pet/HUD is covered -- the cat shrinks to a
# small chip and the screen is dominated by big APPROVE / DENY buttons (bud_screens geometry).
appr = displayio.Group()
appr.append(Rect(0, 0, W, H, fill=BG))                       # opaque cover over the base UI
appr_face = label.Label(terminalio.FONT, text=FACES["attention"], color=RED, scale=2,
                        x=196, y=26, line_spacing=0.95)        # the shrunken pet, top-right
appr.append(appr_face)
appr_head = label.Label(terminalio.FONT, text="approve?", color=AMBER, scale=2, x=14, y=40)
appr.append(appr_head)
appr_tool = label.Label(terminalio.FONT, text="", color=FG, scale=3, x=14, y=120, line_spacing=1.0)
appr.append(appr_tool)
appr_hint = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=14, y=180, line_spacing=1.1)
appr.append(appr_hint)
_AM, _AH = bud_screens.BTN_MARGIN, bud_screens.BTN_H
appr.append(Rect(_AM, bud_screens.APPROVE_Y, W - 2 * _AM, _AH, fill=0x0C3A17, outline=GREEN))
appr.append(label.Label(terminalio.FONT, text="APPROVE", color=GREEN, scale=4,
                        x=W // 2 - 84, y=bud_screens.APPROVE_Y + 28))
appr.append(Rect(_AM, bud_screens.DENY_Y, W - 2 * _AM, _AH, fill=0x3A0C0C, outline=RED))
appr.append(label.Label(terminalio.FONT, text="DENY", color=RED, scale=4,
                        x=W // 2 - 48, y=bud_screens.DENY_Y + 28))
appr.hidden = True
root.append(appr)

# touch marker (drawn on top); parked off-screen until a touch lands
dot = Rect(-20, -20, 12, 12, fill=PINK)
root.append(dot)

display.root_group = root

# ---------- state ----------
boot = time.monotonic()
tama = bud_proto.TamaState()
stats = bud_stats.Stats.load(microcontroller.nvm)
print("[stats] loaded: lvl=%d tok=%d appr=%d deny=%d name=%s owner=%s (nvm=%dB, need=%dB)"
      % (stats.level, stats.tokens, stats.approvals, stats.denials,
         stats.pet_name, stats.owner_name or "-",
         len(microcontroller.nvm), bud_stats.NVM_SIZE))
set_bright(stats.bright_level / 4.0)
if not stats.setting(bud_stats.S_HUD):
    msg.hidden = True
    toks.hidden = True
screen = "home"
last_pet_draw = 0.0
energy_at_nap = 3
last_nap_end = boot
species_idx = stats.species_idx % bud_species.count()
react_state = "idle"
reset_armed = False
reset_t = 0.0
last_data = 0.0
buf = b""
last_state = ""
last_counts = ""
last_msg = ""
last_appr = False
prompt_id = ""
prompt_t0 = 0.0
last_touch_print = 0.0
last_touch_act = 0.0
last_touch_hb = 0.0
last_tap = 0.0
blinking = False
blink_until = 0.0
next_blink = 0.0
reacting = False
react_until = 0.0
react_then = None
dimmed = False
last_lively = boot
last_touch_seen = 0.0


def set_state(st):
    global last_state
    if st == last_state:
        return
    # reconnect delight: we were disconnected, now Claude is back
    if last_state == "disc":
        play("beep")
        react("heart", PINK, 1.2)
    last_state = st
    badge.text = ("zzz waiting for claude" if st == "disc" else "* " + st)
    badge.color = SCOL.get(st, DIM)
    if not reacting:
        pet.text = face_for(st)
        pet.color = SCOL.get(st, FG)


def show_approval(prompt):
    global last_appr, prompt_id, prompt_t0
    pid = str(prompt.get("id", ""))
    if pid != prompt_id:
        prompt_id = pid
        prompt_t0 = time.monotonic()
        appr_face.text = FACES["attention"]
        appr_face.color = RED
        play("beep")
    waited = int(time.monotonic() - prompt_t0)
    appr_head.text = "approve?  " + fmt_dur(waited)
    appr_head.color = RED if waited >= 10 else AMBER
    appr_tool.text = wrap2(prompt.get("tool", "?"), 14)   # scale-3 -> ~14 chars wide
    appr_hint.text = short_mid(prompt.get("hint", ""), 26)
    if not last_appr:
        appr.hidden = False
        last_appr = True


def hide_approval():
    global last_appr
    if last_appr:
        appr.hidden = True
        last_appr = False


def draw_pet():
    pet_title.text = (stats.owner_name + "'s " + stats.pet_name) if stats.owner_name else stats.pet_name
    m = stats.mood()
    pet_mood.text = "mood   " + "* " * m + ". " * (4 - m)
    fed = stats.fed()
    pet_fed.text = "fed    " + "#" * fed + "." * (10 - fed)
    en = bud_stats.energy_tier(energy_at_nap, (time.monotonic() - last_nap_end) / 3600.0)
    pet_energy.text = "energy " + "|" * en + "_" * (5 - en)
    pet_lv.text = "Lv %d" % stats.level
    pet_appr.text = "approved %d" % stats.approvals
    pet_deny.text = "denied   %d" % stats.denials
    pet_nap.text = "napped   " + fmt_dur(stats.nap_seconds)
    pet_tok.text = "tokens   %s" % fmtk(stats.tokens)
    pet_today.text = "today    %s" % fmtk(tama.tokens_today)


def draw_set():
    set_rows[0].text = "sound  " + ("on" if stats.setting(bud_stats.S_SOUND) else "off")
    set_rows[1].text = "bright %d/4" % stats.bright_level
    set_rows[2].text = "hud    " + ("on" if stats.setting(bud_stats.S_HUD) else "off")
    set_rows[3].text = "led    " + ("on" if stats.setting(bud_stats.S_LED) else "off")
    set_rows[4].text = "demo   " + ("on" if stats.setting(bud_stats.S_DEMO) else "off")
    set_rows[5].text = "reset  " + ("again?" if reset_armed else "x2")


def set_screen(name):
    global screen
    screen = name
    home_grp.hidden = name != "home"
    pet_grp.hidden = name != "pet"
    info_grp.hidden = name != "info"
    set_grp.hidden = name != "set"
    for _i, _nm in enumerate(bud_screens.TABS):
        tab_lbls[_i].color = FG if _nm == name else DIM
    if name == "pet":
        draw_pet()
    elif name == "set":
        draw_set()


set_screen("home")

# boot splash: greet by name, then settle into HOME (reference parity)
_splash = displayio.Group()
_splash.append(Rect(0, 0, W, H, fill=BG))
if stats.owner_name:
    _l1 = stats.owner_name + "'s"
    _splash.append(label.Label(terminalio.FONT, text=_l1, color=FG, scale=3,
                               x=max(4, W // 2 - len(_l1) * 9), y=H // 2 - 24))
    _splash.append(label.Label(terminalio.FONT, text=stats.pet_name, color=PINK, scale=3,
                               x=max(4, W // 2 - len(stats.pet_name) * 9), y=H // 2 + 16))
else:
    _splash.append(label.Label(terminalio.FONT, text="Hello!", color=PINK, scale=4,
                               x=W // 2 - 48, y=H // 2 - 24))
    _splash.append(label.Label(terminalio.FONT, text="a buddy appears", color=DIM, scale=2,
                               x=W // 2 - 90, y=H // 2 + 20))
display.root_group = _splash
play("startup_chime")
time.sleep(1.8)
display.root_group = root
print("[ui] buddy UI ready; waiting for Claude")

while True:
    n = uart.in_waiting
    if n:
        b = uart.read(n)
        if b:
            buf += b
        if len(buf) > 20000:
            buf = buf[-20000:]
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            # route the line through bud_proto; `reply` is the status/owner/name ack (if any)
            decoded = line.decode("utf-8", "ignore")
            reply = bud_proto.parse_line(decoded, tama, uptime=int(time.monotonic() - boot))
            if reply is not None:
                uart.write((reply + "\n").encode("utf-8"))
                last_data = time.monotonic()
            # owner / pet-name commands -> persist + reflect on the PET screen title
            if tama.owner_pending is not None:
                stats.owner_name = tama.owner_pending
                tama.owner_pending = None
                stats.save(microcontroller.nvm)
            if tama.name_pending is not None:
                stats.pet_name = tama.name_pending or "Buddy"
                tama.name_pending = None
                stats.save(microcontroller.nvm)
            # heartbeat -> drive the UI from tama (parse_line already updated it)
            if decoded.startswith('{"total"'):
                last_data = time.monotonic()
                stats.on_bridge_tokens(tama.tokens)
                if stats.poll_levelup():
                    stats.save(microcontroller.nvm)
                    react("celebrate", AMBER, 2.5)
                    print("[stats] LEVEL UP -> %d" % stats.level)
                if tama.waiting > 0:
                    set_state("attention")
                elif tama.running > 0:
                    set_state("busy")
                else:
                    set_state("idle")
                if tama.waiting > 0 or tama.running > 0 or tama.prompt_id:
                    last_lively = time.monotonic()
                    if dimmed:
                        set_bright(stats.bright_level / 4.0)
                        dimmed = False
                cs = "run %d  wait %d  tot %d" % (tama.running, tama.waiting, tama.total)
                if cs != last_counts:
                    counts.text = cs
                    last_counts = cs
                if tama.prompt_id and tama.waiting > 0:
                    show_approval({"id": tama.prompt_id, "tool": tama.prompt_tool,
                                   "hint": tama.prompt_hint})
                else:
                    hide_approval()
                    mtxt = wrap2(tama.msg, 26)
                    if mtxt != last_msg:
                        msg.text = mtxt
                        last_msg = mtxt
                    toks.text = "tok %s  today %s" % (fmtk(tama.tokens), fmtk(tama.tokens_today))
            continue
            # turn events / others: ignored in v1 (can be large)

    # ---- touch: live readout + haptic + approve / deny ----
    if ts is not None:
        try:
            tp = ts.touch_point
        except Exception:
            tp = None
        if tp is not None:
            lx, ly = int(tp[0]), int(tp[1])
            px, py = to_portrait(lx, ly)
            nowt = time.monotonic()
            dot.x = px - 6
            dot.y = py - 6
            last_touch_seen = nowt
            if nowt - last_touch_print > 0.20:
                if TOUCH_DEBUG:
                    dbg.text = "t %d,%d>%d,%d" % (lx, ly, px, py)
                print("[touch] L %d,%d -> P %d,%d" % (lx, ly, px, py))
                last_touch_print = nowt
            # one debounced tap -> tactile click, then hit-test the buttons
            if nowt - last_tap > 0.30:
                last_tap = nowt
                play("haptic_tap")
                last_lively = nowt
                if dimmed:
                    set_bright(stats.bright_level / 4.0)
                    dimmed = False
                if last_appr and prompt_id and (nowt - last_touch_act) > 1.2:
                    hit = bud_screens.approval_hit(px, py, W, H)
                    if hit == "approve":
                        uart.write((bud_proto.permission_cmd(prompt_id, "once") + "\n").encode("utf-8"))
                        appr_head.text = "sent: approve"
                        appr_head.color = GREEN
                        appr_face.text = FACES["celebrate"]
                        appr_face.color = GREEN
                        last_touch_act = nowt
                        stats.on_approval(int(nowt - prompt_t0))
                        stats.save(microcontroller.nvm)
                        play("success_chime")
                        react("celebrate", GREEN, 0.8, then=("heart", PINK, 0.9))
                        print("[touch] APPROVE id=%s" % prompt_id)
                    elif hit == "deny":
                        uart.write((bud_proto.permission_cmd(prompt_id, "deny") + "\n").encode("utf-8"))
                        appr_head.text = "sent: deny"
                        appr_head.color = RED
                        appr_face.text = FACES["dizzy"]
                        appr_face.color = AMBER
                        last_touch_act = nowt
                        stats.on_denial()
                        stats.save(microcontroller.nvm)
                        play("error_buzz")
                        react("dizzy", AMBER, 1.5)
                        print("[touch] DENY id=%s" % prompt_id)
                elif not last_appr:
                    t = bud_screens.tab_hit(px, py, W)
                    if t and t != screen:
                        play("jump_sound")
                        set_screen(t)
                        print("[ui] screen -> %s" % t)
                    elif t is None and screen == "home" and py > bud_screens.TAB_H:
                        species_idx = (species_idx + 1) % bud_species.count()
                        stats.species_idx = species_idx
                        stats.save(microcontroller.nvm)
                        play("jump_sound")
                        print("[ui] species -> %s (%d)" % (bud_species.name(species_idx), species_idx))
                    elif t is None and screen == "set":
                        row = bud_screens.menu_hit(px, py, W, H)
                        if row == "bright":
                            stats.bright_level = stats.bright_level % 4 + 1
                            set_bright(stats.bright_level / 4.0)
                        elif row == "hud":
                            _on = stats.toggle_setting(bud_stats.S_HUD)
                            msg.hidden = not _on
                            toks.hidden = not _on
                        elif row == "sound":
                            stats.toggle_setting(bud_stats.S_SOUND)
                        elif row == "led":
                            stats.toggle_setting(bud_stats.S_LED)
                        elif row == "demo":
                            stats.toggle_setting(bud_stats.S_DEMO)
                        elif row == "reset":
                            if reset_armed and (nowt - reset_t) < 4:
                                bud_stats.Stats().save(microcontroller.nvm)
                                stats = bud_stats.Stats.load(microcontroller.nvm)
                                species_idx = 0
                                reset_armed = False
                                react("dizzy", AMBER, 1.2)
                                print("[ui] factory reset")
                            else:
                                reset_armed = True
                                reset_t = nowt
                        if row:
                            if row != "reset":
                                reset_armed = False
                                stats.save(microcontroller.nvm)
                            play("beep")
                            draw_set()

    # pet reactions / blink + screensaver dim after idle
    now = time.monotonic()
    anim_state = last_state if last_state != "disc" else "sleep"
    if reacting:
        if now >= react_until:
            if react_then is not None:
                react(react_then[0], react_then[1], react_then[2])
                anim_state = react_state
            else:
                reacting = False
        else:
            anim_state = react_state
    pet.text = bud_species.frame(species_idx, anim_state, now)
    pet.color = SCOL.get(anim_state, FG)
    if screen == "pet" and now - last_pet_draw > 0.5:
        draw_pet()
        last_pet_draw = now
    if not dimmed and (now - last_lively) > SS_IDLE:
        set_bright(0.15)
        dimmed = True
    # transient touch marker: flash where tapped, then hide shortly after lift
    if dot.x >= 0 and (now - last_touch_seen) > 0.5:
        dot.x = -20
        dot.y = -20

    # link liveness
    if time.monotonic() - last_data > 8:
        set_state("disc")
    time.sleep(0.01)
