# pyportal-claude-buddy : wire protocol, pure (json only). No I/O, no hardware imports,
# so it runs under host pytest as well as on the device. The UART read/write and the
# newline framing live in code.py; this module only interprets one decoded line at a time.
import json


class TamaState:
    """Everything the UI needs to know about the Claude side. Mirrors the reference's
    TamaState (data.h). Mutated in place by parse_line; nothing else writes it."""

    def __init__(self):
        self.total = 0
        self.running = 0
        self.waiting = 0
        self.tokens = 0
        self.tokens_today = 0
        self.msg = ""
        self.lines = []
        self.line_gen = 0          # bumps when transcript lines change -> lets UI reset scroll
        self.prompt_id = ""        # pending permission request id; "" = no prompt
        self.prompt_tool = ""
        self.prompt_hint = ""
        self.connected = False
        self.owner_pending = None  # set when an owner cmd arrives; consumed + cleared by caller
        self.name_pending = None


def _ack(name):
    return '{"ack":"%s","ok":true}' % name


def status_ack(uptime):
    return ('{"ack":"status","ok":true,"data":{"name":"Claude-PyPortal",'
            '"sec":true,"sys":{"up":%d}}}' % int(uptime))


def permission_cmd(pid, decision):
    return '{"cmd":"permission","id":"%s","decision":"%s"}' % (pid, decision)


def parse_line(line, st, uptime=0):
    """Parse one JSON line into `st`. Return a reply string to send back, or None.

    Pure: does no I/O. `line` is an already-decoded, stripped, non-empty str.
    `uptime` (seconds) is passed in so this stays free of any time/hardware call.
    """
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
