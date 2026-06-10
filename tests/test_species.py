import bud_species as S

STATES = ("sleep", "idle", "busy", "attention", "celebrate", "dizzy", "heart")


def test_count_and_metadata():
    assert S.count() >= 1
    assert S.name(0) == "cat"
    for idx in range(S.count()):
        assert isinstance(S.name(idx), str) and S.name(idx)
        assert isinstance(S.color(idx), int)


def test_every_species_every_state_is_a_5_line_pose():
    # the strongest structural check: each pose must render as exactly 5 lines, or the
    # renderer's fixed layout breaks. Catches any bad port across all species/states.
    for idx in range(S.count()):
        for st in STATES:
            for tick in range(0, 40):
                f = S.frame(idx, st, tick * 0.1)
                assert isinstance(f, str), (idx, st)
                assert f.count("\n") == 4, (S.name(idx), st, repr(f))


def test_unknown_state_falls_back_to_idle():
    for idx in range(S.count()):
        assert S.frame(idx, "bogus", 0.0) == S.frame(idx, "idle", 0.0)


def test_frame_advances_over_time():
    for idx in range(S.count()):
        seen = set(S.frame(idx, "idle", t * 0.1) for t in range(60))
        assert len(seen) >= 2, S.name(idx)


def test_species_index_wraps():
    assert S.frame(S.count(), "idle", 0.0) == S.frame(0, "idle", 0.0)


def test_particle_idle_empty_and_sleep_cycles_z():
    assert S.particle("idle", 0.0) == ""
    seen = set(S.particle("sleep", t * 0.1) for t in range(40))
    assert len(seen) >= 2
    assert any("z" in p for p in seen)
