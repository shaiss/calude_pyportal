# pyportal-claude-buddy : multi-species pet loader (LAZY -- one species resident at a time).
#
# 18 species of pose data will not fit in the SAMD51's RAM at once (loading them all was a
# MemoryError), so each species lives in its own `bud_species_<name>.py` (a single DATA dict
# of per-state {frames, seq, div}) and is imported ON DEMAND. Switching species frees the
# previously-resident module first, so memory stays flat no matter how many species exist.
#
# Add a species: write flash/bud_species_<name>.py with a DATA dict (same shape as the
# others -- 7 states, each {"div": N, "seq": (...), "frames": (5-line strings...)}) and add
# its name to _NAMES below. deploy.ps1 copies every bud_*.py automatically.
import gc
import sys

SPECIES_SCALE = 4          # 5-line poses ~12 chars wide; scale 4 fits the 320px screen
ANIM_FPS = 12              # base tick rate; per-state `div` slows specific states

# Registry / display order. Lazy: only the active one is ever held in RAM.
_NAMES = ("cat", "axolotl", "blob", "cactus", "capybara", "chonk", "dragon", "duck",
          "ghost", "goose", "mushroom", "octopus", "owl", "penguin", "rabbit", "robot",
          "snail", "turtle")

_cur_idx = -1
_cur = None


def count():
    return len(_NAMES)


def name(idx):
    return _NAMES[idx % len(_NAMES)]


def _load(idx):
    """Return the active species' DATA dict, importing it on demand and freeing the previous."""
    global _cur_idx, _cur
    idx %= len(_NAMES)
    if idx == _cur_idx and _cur is not None:
        return _cur
    if _cur_idx >= 0:                      # free the previously-resident species
        prev = "bud_species_" + _NAMES[_cur_idx]
        _cur = None
        if prev in sys.modules:
            del sys.modules[prev]
        gc.collect()
    mod = __import__("bud_species_" + _NAMES[idx])
    _cur = mod.DATA
    _cur_idx = idx
    return _cur


def color(idx):
    return _load(idx)["color"]


def frame(idx, state, t):
    """Pose string for species `idx`, persona `state`, at time `t` seconds."""
    d = _load(idx)
    st = d.get(state) or d["idle"]
    seq = st["seq"]
    beat = (int(t * ANIM_FPS) // st["div"]) % len(seq)
    return st["frames"][seq[beat]]


# state-keyed particle overlay (shared across species, like the reference's overlays):
# drifting Zzz on sleep, floating hearts, confetti on celebrate, swirl on dizzy, etc.
_PARTICLE = {
    "sleep": ("z  ", " z ", "  z", "   "),
    "disc": ("z  ", " z ", "  z", "   "),
    "heart": ("<3 ", " <3", "<3 ", "   "),
    "celebrate": ("\\*/", "* *", " * ", ". ."),
    "dizzy": ("*  ", "  *", " * ", "*  "),
    "busy": (".  ", ".. ", "...", "   "),
    "attention": ("!", " ", "!", " "),
}


def particle(state, t):
    """Tiny state-keyed particle string (empty for idle); cycles ~2 Hz."""
    seq = _PARTICLE.get(state)
    return seq[int(t * 2) % len(seq)] if seq else ""
