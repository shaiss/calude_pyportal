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
    s = S.Stats.load(bytearray(256))   # all zero -> bad magic
    assert s.tokens == 0 and s.pet_name == "Buddy" and s.level == 0


def test_level_and_fed():
    s = S.Stats(); s.tokens = 125000
    assert s.level_of() == 2          # 125000 // 50000
    assert s.fed() == 5               # (25000 // 5000)


def test_token_latch_ignores_first_sight_then_adds_delta():
    s = S.Stats()
    s.on_bridge_tokens(100000)            # first sight: latch, credit nothing
    assert s.tokens == 0
    s.on_bridge_tokens(100000 + 60000)    # +60k crosses a level
    assert s.tokens == 60000 and s.level == 1 and s.poll_levelup() is True
    assert s.poll_levelup() is False


def test_bridge_restart_resyncs_without_crediting():
    s = S.Stats()
    s.on_bridge_tokens(100000); s.on_bridge_tokens(120000)
    assert s.tokens == 20000
    s.on_bridge_tokens(5000)              # number dropped -> restart
    assert s.tokens == 20000              # unchanged
    s.on_bridge_tokens(5000 + 3000)
    assert s.tokens == 23000


def test_mood_drops_with_heavy_denial():
    s = S.Stats()
    for _ in range(5):
        s.on_approval(10)                 # fast -> high base tier
    high = s.mood()
    s.denials = 10                        # d > a
    assert s.mood() < high


def test_energy_drains_over_time():
    assert S.energy_tier(5, 0.0) == 5
    assert S.energy_tier(5, 4.0) == 3     # -1 per 2h
    assert S.energy_tier(5, 100.0) == 0   # floored
