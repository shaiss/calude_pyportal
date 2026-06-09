# pyportal-claude-buddy : gamification + persistence, ported from the reference stats.h.
# Pure (struct only); the nvm object is injected so this runs under host pytest with a
# plain bytearray. On the device, code.py passes microcontroller.nvm. Save sparingly
# (significant events only) -- flash has limited write cycles.
import struct

TOKENS_PER_LEVEL = 50000

# magic, ver, tokens, appr, deny, nap, lvl, vIdx, vCnt, vel[8],
# settingsBits, bright, species, petName(24), ownerName(32)
_FMT = "<BBIHHIBBB8HBBB24s32s"
NVM_SIZE = struct.calcsize(_FMT)   # 92
_MAGIC = ord("B")
_VERSION = 1
DEFAULT_SETTINGS = 0b00001111      # sound|led|hud|spare on; demo (0x10) off by default

# settings_bits flags
S_SOUND = 0x01
S_LED = 0x02
S_HUD = 0x04
S_DEMO = 0x10


def energy_tier(energy_at_nap, hours_since_nap):
    """0..5. Boots/refills at energy_at_nap, drains one tier per 2h since the last nap."""
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
        self.velocity = [0] * 8       # ring buffer: seconds-to-respond per approval
        self.settings_bits = DEFAULT_SETTINGS
        self.bright_level = 4
        self.species_idx = 0
        self.pet_name = "Buddy"
        self.owner_name = ""
        # runtime-only token latch (not persisted)
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
        vel = (list(self.velocity) + [0] * 8)[:8]
        return struct.pack(
            _FMT, _MAGIC, _VERSION, self.tokens & 0xFFFFFFFF,
            self.approvals & 0xFFFF, self.denials & 0xFFFF, self.nap_seconds & 0xFFFFFFFF,
            self.level & 0xFF, self.vel_idx & 0xFF, self.vel_count & 0xFF, *vel,
            self.settings_bits & 0xFF, self.bright_level & 0xFF, self.species_idx & 0xFF,
            self.pet_name.encode("utf-8")[:24], self.owner_name.encode("utf-8")[:32])

    def save(self, nvm):
        nvm[0:NVM_SIZE] = self.pack()

    def level_of(self):
        return self.tokens // TOKENS_PER_LEVEL

    def fed(self):
        return (self.tokens % TOKENS_PER_LEVEL) // (TOKENS_PER_LEVEL // 10)

    def on_bridge_tokens(self, total):
        """Bridge sends a cumulative total since IT started; we track deltas. Latch on first
        sight (so a device reboot doesn't re-credit the whole session); a drop = bridge
        restart -> resync without crediting."""
        if not self._synced:
            self._last_bridge = total
            self._synced = True
            return
        if total < self._last_bridge:
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

    def setting(self, mask):
        return bool(self.settings_bits & mask)

    def toggle_setting(self, mask):
        self.settings_bits ^= mask
        return bool(self.settings_bits & mask)

    def on_nap_end(self, secs):
        self.nap_seconds += int(secs)

    def median_velocity(self):
        if self.vel_count == 0:
            return 0
        t = sorted(self.velocity[:self.vel_count])
        return t[len(t) // 2]

    def mood(self):
        """0..4. Velocity sets the base; a heavy denial ratio drags it down."""
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
