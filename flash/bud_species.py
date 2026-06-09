# pyportal-claude-buddy : multi-species ASCII pet data + frame selector.
# Pure data + pure functions (host-testable). Each species defines, per persona state, a
# tuple of 5-line pose strings + a beat `seq` (indices into the poses) + a `div` (lower =
# faster). frame(idx, state, t) picks the pose for time t. Ported from the reference
# src/buddies/*.cpp (the P[]/SEQ[] pose machine), rendered as a single label at SPECIES_SCALE.
#
# Add a species: append a dict to SPECIES with the 7 states (sleep/idle/busy/attention/
# celebrate/dizzy/heart); missing states fall back to "idle".

SPECIES_SCALE = 4          # 5-line poses are ~12 chars wide; scale 4 fits the 320px screen
ANIM_FPS = 12              # base tick rate; per-state `div` slows specific states


def _f(*lines):
    return "\n".join(lines)


# ── cat ── faithful subset of src/buddies/cat.cpp pose sequences ──────────────────
_CAT = {
    "name": "cat",
    "color": 0xC2A6,
    "sleep": {"div": 6, "seq": (0, 1, 0, 1, 2, 2, 0, 1),
              "frames": (
                  _f("            ", "            ", "   .-..-.   ", "  ( -.- )   ", "  `------`~ "),
                  _f("            ", "            ", "   .-..-.   ", "  ( -.- )_  ", " `~------'~ "),
                  _f("            ", "            ", "   .-/\\.    ", "  (  ..  )) ", "  `~~~~~~`  "))},
    "idle": {"div": 6, "seq": (0, 0, 0, 1, 0, 0, 2, 0, 3, 0, 0, 4),
             "frames": (
                 _f("            ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )  ", '  (")_(")   '),
                 _f("            ", "   /\\_/\\    ", "  (o    o ) ", "  (  w   )  ", '  (")_(")   '),
                 _f("            ", "   /\\_/\\    ", "  ( o    o) ", "  (  w   )  ", '  (")_(")   '),
                 _f("            ", "   /\\_/\\    ", "  ( -   - ) ", "  (  w   )  ", '  (")_(")   '),
                 _f("            ", "   /\\_/\\    ", "  ( ^   ^ ) ", "  (  P   )  ", '  (")_(")   '))},
    "busy": {"div": 4, "seq": (0, 0, 1, 2, 1, 2, 0, 3),
             "frames": (
                 _f("            ", "   /\\_/\\    ", "  ( O   O ) ", "  (  w   )  ", '  (")_(")   '),
                 _f("      .     ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )/ ", '  (")_(")   '),
                 _f("    .       ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )_ ", '  (")_(")   '),
                 _f("            ", "   /\\_/\\    ", "  ( -   - ) ", "  (  w   )  ", '  (")_(")   '))},
    "attention": {"div": 3, "seq": (0, 1, 0, 2, 0, 3),
                  "frames": (
                      _f("            ", "   /^_^\\    ", "  ( O   O ) ", "  (  v   )  ", '  (")_(")   '),
                      _f("            ", "   /^_^\\    ", "  (O    O ) ", "  (  v   )  ", '  (")_(")   '),
                      _f("            ", "   /^_^\\    ", "  ( O    O) ", "  (  v   )  ", '  (")_(")   '),
                      _f("            ", "   /^_^\\    ", "  ( O   O ) ", "  (  >   )  ", '  (")_(")   '))},
    "celebrate": {"div": 3, "seq": (0, 1, 2, 1, 0),
                  "frames": (
                      _f("            ", "   /\\_/\\    ", "  ( ^   ^ ) ", "  (  W   )  ", ' /(")_(")\\  '),
                      _f("  \\^   ^/   ", "    /\\_/\\   ", "  ( ^   ^ ) ", "  (  W   )  ", '  (")_(")   '),
                      _f("  \\^   ^/   ", "    /\\_/\\   ", "  ( * * * ) ", "  (  W   )  ", '  (")_(")~  '))},
    "dizzy": {"div": 4, "seq": (0, 1, 0, 1, 2, 2),
              "frames": (
                  _f("            ", "  /\\_/\\     ", " ( @   @ )  ", " (   ~~  )  ", ' (")_(")    '),
                  _f("            ", "    /\\_/\\   ", "  ( @   @ ) ", "  (  ~~  )  ", '    (")_(") '),
                  _f("            ", "   /\\_/\\    ", "  ( x   @ ) ", "  (  v   )  ", '  (")_(")~  '))},
    "heart": {"div": 5, "seq": (0, 0, 1, 0, 2, 0),
              "frames": (
                  _f("            ", "   /\\_/\\    ", "  ( ^   ^ ) ", "  (  u   )  ", '  (")_(")~  '),
                  _f("            ", "   /\\_/\\    ", "  ( <3<3 ) ", "  (  u   )  ", '  (")_(")~  '),
                  _f("            ", "   /\\_/\\    ", "  (#^   ^#) ", "  (  u   )  ", '  (")_(")   '))},
}

SPECIES = [_CAT]


def count():
    return len(SPECIES)


def name(idx):
    return SPECIES[idx % len(SPECIES)]["name"]


def color(idx):
    return SPECIES[idx % len(SPECIES)]["color"]


def frame(idx, state, t):
    """Return the pose string for species `idx`, persona `state`, at time `t` seconds."""
    sp = SPECIES[idx % len(SPECIES)]
    st = sp.get(state) or sp["idle"]
    seq = st["seq"]
    beat = (int(t * ANIM_FPS) // st["div"]) % len(seq)
    return st["frames"][seq[beat]]
