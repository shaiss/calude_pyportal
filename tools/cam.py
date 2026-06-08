"""Grab one frame from the USB webcam pointed at the Titano and save it as cam.jpg."""
import sys
import time
import cv2

OUT = r"C:\Users\Shai\pyportal-claude-buddy\cam.jpg"


def grab(idx):
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        frame = None
        for _ in range(20):          # warm-up so auto-exposure settles
            ok, f = cap.read()
            if ok and f is not None:
                frame = f
            time.sleep(0.05)
        cap.release()
        if frame is not None:
            return frame, backend
    return None, None


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    frame, backend = grab(idx)
    if frame is None:
        print("capture FAILED on index", idx)
        # list candidate indices
        for i in range(4):
            c = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            print("  index", i, "opened:", c.isOpened())
            c.release()
        return
    cv2.imwrite(OUT, frame)
    print("captured idx=%d backend=%d shape=%s -> %s" % (idx, backend, frame.shape, OUT))


if __name__ == "__main__":
    main()
