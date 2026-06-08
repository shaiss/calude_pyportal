"""
Audio + "haptic" feedback for the PyPortal-Claude-Buddy.

Lifted from the proven NEAR Pulse AudioManager (same Titano hardware): it uses
simpleio.tone() for reliable blocking tones and drives board.SPEAKER_ENABLE so the
amp is actually on. There is no vibration motor on the Titano, so "haptic" feedback
is faked with a quick low-frequency thud through the speaker -- a click you can feel.

All methods degrade to no-ops if the speaker/pin/simpleio are unavailable, so the
buddy keeps running silently rather than crashing if audio can't initialize.
"""

import time
import board
import digitalio

try:
    from simpleio import tone as _simpleio_tone
    HAS_SIMPLEIO = True
except ImportError:
    HAS_SIMPLEIO = False
    _simpleio_tone = None


class AudioManager:
    """simpleio.tone() based audio with Mario/NES-inspired cues."""

    def __init__(self):
        self.speaker_enable = None
        self.audio_pin = None
        self.audio = True
        try:
            if hasattr(board, "SPEAKER_ENABLE"):
                self.speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
                self.speaker_enable.switch_to_output(value=True)

            if hasattr(board, "AUDIO_OUT"):
                self.audio_pin = board.AUDIO_OUT
            elif hasattr(board, "A0"):
                self.audio_pin = board.A0
            elif hasattr(board, "SPEAKER"):
                self.audio_pin = board.SPEAKER
            else:
                print("[audio] no output pin")
                self.audio = False
                return

            if not HAS_SIMPLEIO:
                print("[audio] simpleio missing")
                self.audio = False
                return

            print("[audio] ready (simpleio)")
        except Exception as e:
            print("[audio] init failed:", e)
            self.audio = False

    def _enable_speaker(self):
        if self.speaker_enable:
            try:
                self.speaker_enable.value = True
            except Exception:
                pass

    def _disable_speaker(self):
        if self.speaker_enable:
            try:
                self.speaker_enable.value = False
            except Exception:
                pass

    def play_tone(self, frequency=440, duration=0.1):
        if not self.audio or not HAS_SIMPLEIO or not self.audio_pin:
            return
        try:
            self._enable_speaker()
            _simpleio_tone(self.audio_pin, frequency, duration)
            self._disable_speaker()
        except Exception as e:
            print("[audio] tone failed:", e)

    def haptic_tap(self):
        """Quick low thud -- tactile 'click' for any touch."""
        if not self.audio:
            return
        self.play_tone(150, 0.03)
        time.sleep(0.01)
        self.play_tone(100, 0.02)

    def beep(self):
        """Coin: A5 -> E6 ascending -- 'something needs you' alert."""
        if not self.audio:
            return
        self.play_tone(880, 0.05)
        time.sleep(0.02)
        self.play_tone(1319, 0.08)

    def startup_chime(self):
        """Power-up: C5 -> E5 -> G5 -> B5."""
        if not self.audio:
            return
        self.play_tone(523, 0.1)
        time.sleep(0.03)
        self.play_tone(659, 0.1)
        time.sleep(0.03)
        self.play_tone(784, 0.1)
        time.sleep(0.03)
        self.play_tone(988, 0.15)

    def error_buzz(self):
        """Damage: descending low tones -- used for DENY."""
        if not self.audio:
            return
        self.play_tone(200, 0.08)
        time.sleep(0.02)
        self.play_tone(150, 0.1)
        time.sleep(0.02)
        self.play_tone(100, 0.12)

    def success_chime(self):
        """1-up: C5 -> E5 -> G5 -> C6 -- used for APPROVE."""
        if not self.audio:
            return
        self.play_tone(523, 0.06)
        time.sleep(0.02)
        self.play_tone(659, 0.06)
        time.sleep(0.02)
        self.play_tone(784, 0.06)
        time.sleep(0.02)
        self.play_tone(1047, 0.1)

    def jump_sound(self):
        """Jump: quick ascending tone."""
        if not self.audio:
            return
        self.play_tone(440, 0.04)
        time.sleep(0.01)
        self.play_tone(554, 0.06)
