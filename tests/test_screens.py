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


def test_tab_hit_maps_each_zone():
    n = len(SC.TABS)
    zone = W // n
    for i, name in enumerate(SC.TABS):
        cx = i * zone + zone // 2
        assert SC.tab_hit(cx, 10, W) == name


def test_tab_hit_rightmost_edge_clamps_to_last():
    assert SC.tab_hit(W - 1, 10, W) == SC.TABS[-1]


def test_tab_hit_below_bar_is_none():
    assert SC.tab_hit(160, SC.TAB_H + 5, W) is None


def test_menu_hit_maps_each_row():
    for i, name in enumerate(SC.MENU_ROWS):
        cy = SC.MENU_TOP + i * SC.MENU_ROW_H + SC.MENU_ROW_H // 2
        assert SC.menu_hit(W // 2, cy, W, H) == name


def test_menu_hit_above_first_row_is_none():
    assert SC.menu_hit(W // 2, SC.MENU_TOP - 5, W, H) is None


def test_menu_hit_below_last_row_is_none():
    below = SC.MENU_TOP + len(SC.MENU_ROWS) * SC.MENU_ROW_H + 5
    assert SC.menu_hit(W // 2, below, W, H) is None
