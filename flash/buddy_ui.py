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
    if snd is None:
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


def react(face_key, color, dur=1.5, then=None):
    """Briefly take over the pet's face with an emotion, then it settles back.

    `then` optionally chains a follow-up (face_key, color, dur) for a two-beat pop.
    """
    global reacting, react_until, react_then
    pet.text = FACES.get(face_key, FACES["idle"])
    pet.color = color
    react_until = time.monotonic() + dur
    reacting = True
    react_then = then


# ---------- build UI ----------
root = displayio.Group()
root.append(Rect(0, 0, W, H, fill=BG))

badge = label.Label(terminalio.FONT, text="starting", color=DIM, scale=2, x=10, y=18)
root.append(badge)

# live touch readout (raw landscape -> portrait); stays blank until the screen is tapped
dbg = label.Label(terminalio.FONT, text="", color=AMBER, scale=2, x=10, y=44)
root.append(dbg)

pet = label.Label(terminalio.FONT, text=FACES["idle"], color=FG, scale=6,
                  x=46, y=70, line_spacing=0.95)
root.append(pet)

root.append(Rect(8, 286, W - 16, 2, fill=DIV))

counts = label.Label(terminalio.FONT, text="", color=FG, scale=2, x=10, y=312)
root.append(counts)
msg = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=348, line_spacing=1.1)
root.append(msg)
toks = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=10, y=462)
root.append(toks)

# approval panel (hidden until a prompt arrives) -- big zones (touch wiring is v2)
appr = displayio.Group()
appr.append(Rect(6, 292, W - 12, H - 298, fill=0x161B22, outline=RED))
appr_head = label.Label(terminalio.FONT, text="approve?", color=AMBER, scale=2, x=16, y=314)
appr.append(appr_head)
appr_tool = label.Label(terminalio.FONT, text="", color=FG, scale=2, x=16, y=344, line_spacing=1.0)
appr.append(appr_tool)
appr_hint = label.Label(terminalio.FONT, text="", color=DIM, scale=2, x=16, y=378, line_spacing=1.1)
appr.append(appr_hint)
appr.append(Rect(12, 412, (W // 2) - 18, 58, fill=0x0C3A17, outline=GREEN))
appr.append(label.Label(terminalio.FONT, text="APPROVE", color=GREEN, scale=2, x=26, y=441))
appr.append(Rect(W // 2 + 6, 412, (W // 2) - 18, 58, fill=0x3A0C0C, outline=RED))
appr.append(label.Label(terminalio.FONT, text="DENY", color=RED, scale=2, x=W // 2 + 40, y=441))
appr.hidden = True
root.append(appr)

# touch marker (drawn on top); parked off-screen until a touch lands
dot = Rect(-20, -20, 12, 12, fill=PINK)
root.append(dot)

display.root_group = root

# ---------- state ----------
boot = time.monotonic()
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
        play("beep")
    waited = int(time.monotonic() - prompt_t0)
    appr_head.text = "approve?  " + fmt_dur(waited)
    appr_head.color = RED if waited >= 10 else AMBER
    appr_tool.text = wrap2(prompt.get("tool", "?"), 22)
    appr_hint.text = short_mid(prompt.get("hint", ""), 22)
    if not last_appr:
        appr.hidden = False
        msg.hidden = True
        toks.hidden = True
        last_appr = True


def hide_approval():
    global last_appr
    if last_appr:
        appr.hidden = True
        msg.hidden = False
        toks.hidden = False
        last_appr = False


play("startup_chime")
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
            # status poll -> ack (keeps the link alive)
            if b'"cmd"' in line and b'"status"' in line:
                up = int(time.monotonic() - boot)
                uart.write(('{"ack":"status","ok":true,"data":{"name":"Claude-PyPortal",'
                            '"sec":true,"sys":{"up":%d}}}\n' % up).encode("utf-8"))
                last_data = time.monotonic()
                continue
            # heartbeat snapshot -> drive the UI
            if line.startswith(b'{"total"'):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                last_data = time.monotonic()
                running = d.get("running", 0)
                waiting = d.get("waiting", 0)
                total = d.get("total", 0)
                prompt = d.get("prompt")
                if waiting and waiting > 0:
                    set_state("attention")
                elif running and running > 0:
                    set_state("busy")
                else:
                    set_state("idle")
                if (waiting and waiting > 0) or (running and running > 0) or prompt:
                    last_lively = time.monotonic()
                    if dimmed:
                        set_bright(1.0)
                        dimmed = False
                cs = "run %d  wait %d  tot %d" % (running, waiting, total)
                if cs != last_counts:
                    counts.text = cs
                    last_counts = cs
                if prompt and waiting and waiting > 0:
                    show_approval(prompt)
                else:
                    hide_approval()
                    mtxt = wrap2(d.get("msg", ""), 26)
                    if mtxt != last_msg:
                        msg.text = mtxt
                        last_msg = mtxt
                    toks.text = "tok %s  today %s" % (fmtk(d.get("tokens", 0)),
                                                      fmtk(d.get("tokens_today", 0)))
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
                    set_bright(1.0)
                    dimmed = False
                if last_appr and prompt_id and (nowt - last_touch_act) > 1.2:
                    if 412 <= py <= 470 and 12 <= px <= 154:
                        uart.write(('{"cmd":"permission","id":"%s","decision":"once"}\n'
                                    % prompt_id).encode("utf-8"))
                        appr_head.text = "sent: approve"
                        appr_head.color = GREEN
                        last_touch_act = nowt
                        play("success_chime")
                        react("celebrate", GREEN, 0.8, then=("heart", PINK, 0.9))
                        print("[touch] APPROVE id=%s" % prompt_id)
                    elif 412 <= py <= 470 and 166 <= px <= 308:
                        uart.write(('{"cmd":"permission","id":"%s","decision":"deny"}\n'
                                    % prompt_id).encode("utf-8"))
                        appr_head.text = "sent: deny"
                        appr_head.color = RED
                        last_touch_act = nowt
                        play("error_buzz")
                        react("dizzy", AMBER, 1.5)
                        print("[touch] DENY id=%s" % prompt_id)

    # pet reactions / blink + screensaver dim after idle
    now = time.monotonic()
    if reacting:
        if now >= react_until:
            if react_then is not None:
                nxt = react_then
                react(nxt[0], nxt[1], nxt[2])    # chain the next beat
            else:
                pet.text = face_for(last_state)
                pet.color = SCOL.get(last_state, FG)
                reacting = False
                next_blink = now + 1.5
    elif blinking:
        if now >= blink_until:
            pet.text = face_for(last_state)
            blinking = False
            next_blink = now + 2.6 + (int(now * 10) % 14) * 0.1
    elif now >= next_blink:
        f = face_for(last_state)
        if int(now) % 5 == 0:
            pet.text = eye_swap(f, "( o.- )")    # occasional wink
            blink_until = now + 0.22
        else:
            pet.text = blink_face(f)             # normal blink
            blink_until = now + 0.14
        blinking = True
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
