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


def test_tap_outside_horizontal_margin_is_none():
    assert SC.approval_hit(2, SC.APPROVE_Y + 10, W, H) is None


def test_buttons_fit_on_screen():
    # both 92px buttons + gap must fit within the 480px-tall panel
    assert SC.DENY_Y + SC.BTN_H <= H
