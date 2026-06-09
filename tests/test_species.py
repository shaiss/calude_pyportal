import bud_species as S

STATES = ("sleep", "idle", "busy", "attention", "celebrate", "dizzy", "heart")


def test_count_and_metadata():
    assert S.count() >= 1
    assert S.name(0) == "cat"
    assert isinstance(S.color(0), int)


def test_frame_returns_5_line_pose_for_every_state():
    for st in STATES:
        f = S.frame(0, st, 0.0)
        assert isinstance(f, str)
        assert f.count("\n") == 4   # 5 lines


def test_unknown_state_falls_back_to_idle():
    assert S.frame(0, "bogus", 0.0) == S.frame(0, "idle", 0.0)


def test_frame_advances_over_time():
    # over a few seconds, idle should cycle through more than one distinct pose
    seen = set(S.frame(0, "idle", t * 0.1) for t in range(60))
    assert len(seen) >= 2


def test_species_index_wraps():
    assert S.frame(S.count(), "idle", 0.0) == S.frame(0, "idle", 0.0)
