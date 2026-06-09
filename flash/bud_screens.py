# pyportal-claude-buddy : approval-screen geometry + touch hit-testing.
# Pure (no displayio) so it host-tests. These constants are the SINGLE SOURCE OF TRUTH
# shared by the renderer (buddy_ui builds the Rects from them) and the hit-test below, so
# a tap can never disagree with what's drawn.
#
# Layout on the 320x480 portrait panel: a small pet chip + prompt text up top, then two
# big full-width buttons stacked in the lower half -- APPROVE over DENY.

BTN_MARGIN = 14          # left/right inset of the buttons
BTN_H = 92               # button height
APPROVE_Y = 270          # top of the APPROVE button
DENY_Y = APPROVE_Y + BTN_H + 16   # top of the DENY button (= 378; bottom 470, fits H=480)


def approval_hit(px, py, w, h):
    """Map a portrait tap to 'approve' / 'deny' / None using the two button bands."""
    if px < BTN_MARGIN or px > w - BTN_MARGIN:
        return None
    if APPROVE_Y <= py <= APPROVE_Y + BTN_H:
        return "approve"
    if DENY_Y <= py <= DENY_Y + BTN_H:
        return "deny"
    return None


# --- top tab bar: HOME | PET | INFO (equal thirds across the top) -------------------
TAB_H = 45          # 1.5x the original 30px -> bigger, easier touch target
TABS = ("home", "pet", "info")


def tab_hit(px, py, w):
    """Map a tap in the top tab band to a screen name, else None."""
    if py > TAB_H:
        return None
    i = px // (w // len(TABS))
    if i >= len(TABS):
        i = len(TABS) - 1
    return TABS[i]
