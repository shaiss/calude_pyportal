"""Grab one frame from the USB webcam pointed at the PyPortal Titano and save it as a JPG.

The point: visually verify what is *actually* on the device screen (deploy -> capture ->
look) instead of trusting that the code "should" render correctly. Tries the DSHOW / MSMF /
ANY OpenCV backends in turn and warms the sensor up so auto-exposure settles before grabbing.

Usage:
    python tools/cam.py                 # auto-scan indices 0..3, write ./cam.jpg
    python tools/cam.py 1               # force camera index 1
    python tools/cam.py -o shot.jpg     # custom output path
    python tools/cam.py --list          # just list which camera indices open
"""
import argparse
import os
import sys
import time

import cv2


def grab(idx, width, height, warmup):
    """Open camera `idx`, discard `warmup` frames so exposure settles, return one frame."""
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        frame = None
        for _ in range(warmup):
            ok, f = cap.read()
            if ok and f is not None:
                frame = f
            time.sleep(0.05)
        cap.release()
        if frame is not None:
            return frame, backend
    return None, None


def list_indices(n=5):
    print("scanning camera indices:")
    for i in range(n):
        c = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        print("  index %d opened: %s" % (i, c.isOpened()))
        c.release()


def main():
    ap = argparse.ArgumentParser(description="Capture one webcam frame of the Titano screen.")
    ap.add_argument("index", nargs="?", type=int, default=None,
                    help="camera index (default: auto-scan 0..3 until one yields a frame)")
    ap.add_argument("-o", "--out", default="cam.jpg",
                    help="output JPG path (default: ./cam.jpg, which is .gitignored)")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--warmup", type=int, default=25,
                    help="frames to discard while auto-exposure settles")
    ap.add_argument("--list", action="store_true", help="list camera indices and exit")
    args = ap.parse_args()

    if args.list:
        list_indices()
        return 0

    out = os.path.abspath(args.out)
    indices = [args.index] if args.index is not None else [0, 1, 2, 3]

    for i in indices:
        frame, backend = grab(i, args.width, args.height, args.warmup)
        if frame is not None:
            if not cv2.imwrite(out, frame):
                print("ERROR: captured idx=%d but could not write %s "
                      "(does the parent directory exist?)" % (i, out))
                return 2
            h, w = frame.shape[:2]
            print("captured idx=%d backend=%d %dx%d -> %s" % (i, backend, w, h, out))
            return 0
        print("idx %d: no frame" % i)

    print("CAPTURE FAILED on indices %s" % indices)
    list_indices()
    return 1


if __name__ == "__main__":
    sys.exit(main())
