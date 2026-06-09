---
name: device-eyes
description: Use when you need to see what is actually on the PyPortal Titano's screen — to verify a deploy or UI change rendered correctly, check the device's current state/face, confirm a touch target's position, or trust real pixels over what the code "should" draw. A USB webcam is aimed at the device. Keywords: webcam, camera, screenshot, screen, display, HX8357, cam.py, visual verification, look at the device.
---

# Device Eyes (Webcam)

## Overview

A USB webcam is physically pointed at the Titano's screen. This is Claude's only
direct view of the hardware. **Close the loop: deploy → capture → read the pixels →
verify** — never claim a UI change "works" from code alone; look at it.

## When to use

- Right after `tools/deploy.ps1` (or any `code.py` change) — confirm it rendered, didn't crash to the REPL.
- Verifying a screen, pet face, layout, or color looks right.
- Checking the live state (connected? which state? is the screen dimmed/asleep?).
- Reading the on-screen touch-calibration readout (`TOUCH_DEBUG=True`).
- Before reporting any visual result to the user.

## Capture, then view

Run from the **repo root**, then **view the JPG with the Read tool** (Read renders images):

```powershell
python tools/cam.py
# captured idx=0 backend=700 1920x1080 -> C:\...\claude-buddy\cam.jpg
```

`Read` the path printed after `->` (here `cam.jpg` at the repo root). It is `.gitignored`
and overwritten each run.

| Need | Command |
|---|---|
| Default grab (auto-scan indices 0..3) | `python tools/cam.py` |
| Force a camera index | `python tools/cam.py 1` |
| Custom output path | `python tools/cam.py -o shot.jpg` |
| Washed-out frame? longer exposure warm-up | `python tools/cam.py --warmup 50` |
| Which cameras exist? | `python tools/cam.py --list` |

## Caveats

- **Glare/reflection:** the HX8357 glass is glossy and reflects the room (and your face).
  If content looks washed out, dim ambient light, tilt the device slightly, or just
  re-run — each capture warms the sensor's auto-exposure (`--warmup`, default 25 frames).
- **Dimmed/asleep screen** reads as nearly black. The buddy dims after idle; if the frame
  is dark, the device may simply be in screensaver — note that rather than assuming a crash.
- **Wrong camera:** auto-scan takes the first index that yields a frame (index 0 here). If
  you have multiple cameras and get the wrong one, pass an explicit index.
- **Capture fails / no frame:** another app may be holding the camera — close it, or run
  `python tools/cam.py --list` to see which indices open.
- Requires `opencv-python` (`cv2`) on the host (already installed).

## Common mistakes

- Reading a **stale** `cam.jpg` — always re-run the capture immediately before viewing.
- Calling a render "verified" from a blurry/glared frame — re-grab until it's legible.
- Capturing while the device is mid-reload (a `code.py` deploy resets the ESP32; give it a
  moment, then grab).
