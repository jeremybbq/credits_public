# Shared pieces for "Accretion": paths to the reused drawing/video tools, the per-frame context,
# syllable events from the song's voice, and small drawing helpers.
import bisect
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Only the drawing / video tools are reused from mv2 (cell screen, rasteriser, audio analysis, beat grid).
sys.path.insert(0, os.path.join(ROOT, "mv2"))

import timeline as tl                     # noqa: E402
from term import gradient, hexc, mix      # noqa: E402,F401

FPS = 60
DT = 1.0 / FPS
COLS, ROWS = 120, 36
DW, DH = COLS * 2, ROWS * 4               # braille dot grid
BLACK = hexc("050507")

# Section starts (beats): one material each, handing over to the next.
SECTIONS = ((-10 ** 9, "seed"), (60, "sand"), (1080, "fire"), (1848, "growth"), (2976, "erosion"),
            (3132, "crystal"), (3390, "life"), (3896, "water"), (4460, "orbit"), (5500, "light"), (6508, "settle"))

# The song's biggest hits inside sections (measured from the audio), used as signature moments.
HITS = {"breathe": 570, "inhale": 1722, "leaffall": 2618, "outline": 3066, "dieoff": 3706, "bigdrop": 3963,
        "freeze": 5690, "shatter": 6010, "mosaic": 6202}


def section_at(b):
    name = SECTIONS[0][1]
    for start, n in SECTIONS:
        if b >= start:
            name = n
    return name


# ---------------------------------------------------------------- the voice as events
class Voice:
    """Syllable-level events from the hand-timed vocal data (what the original typed on each beat).

    kind 'char' : one character spoken/typed (char streams); word=True at the start of a word
    kind 'word' : one new word / syllable token (word streams)
    kind 'line' : a line finished
    """

    def __init__(self):
        with open(os.path.join(ROOT, "mv2", "data", "lyrics.json")) as f:
            streams = json.load(f)
        ev = []
        for key, entries in streams.items():
            prev_lines, prev_cur = [], ""
            for e in entries:
                b = e["b"]
                if "lines" in e:
                    lines = e["lines"]
                    if lines and len(lines) >= len(prev_lines):
                        old = prev_lines[len(lines) - 1] if len(prev_lines) >= len(lines) else ""
                        new = lines[-1]
                        if new.startswith(old) and len(new) > len(old):
                            for i, c in enumerate(new[len(old):]):
                                pos = len(old) + i
                                if c.strip():
                                    word = pos == 0 or not new[pos - 1].strip()
                                    ev.append((b, key, "char", c, word))
                    prev_lines = lines
                else:
                    cur = e.get("cur", "")
                    if cur and cur != prev_cur:
                        tok = cur[len(prev_cur):] if cur.startswith(prev_cur) else cur
                        if tok.strip():
                            ev.append((b, key, "word", tok.strip(), True))
                    if "commit" in e:
                        ev.append((b, key, "line", e["commit"]["text"], e["commit"]["kind"] == "key"))
                        cur = ""
                    prev_cur = cur
        ev.sort(key=lambda x: x[0])
        self.ev = ev
        self.beats = [x[0] for x in ev]

    def between(self, b0, b1, keys=None, kinds=None):
        i0 = bisect.bisect_right(self.beats, b0)
        i1 = bisect.bisect_right(self.beats, b1)
        out = self.ev[i0:i1]
        if keys:
            out = [x for x in out if x[1] in keys]
        if kinds:
            out = [x for x in out if x[2] in kinds]
        return out


VOICE = None


def voice():
    global VOICE
    if VOICE is None:
        VOICE = Voice()
    return VOICE


# ---------------------------------------------------------------- per-frame context
class Ctx:
    def __init__(self, t, audio, t_prev):
        self.t = t
        self.b = tl.time_beat(t)
        self.b0 = tl.time_beat(t_prev)
        self.audio = audio
        self.level = audio.level(t)
        self.kick = audio.kick(t)
        self.snare = audio.snare(t)
        k_prev = audio.kick(t_prev)
        s_prev = audio.snare(t_prev)
        self.kick_hit = self.kick > 0.55 and self.kick - k_prev > 0.15
        self.snare_hit = self.snare > 0.55 and self.snare - s_prev > 0.15

    def voice(self, keys=None, kinds=None):
        return voice().between(self.b0, self.b, keys, kinds)

    def crossed(self, beat):
        return self.b0 < beat <= self.b

    def hit(self, name, length):
        """Progress 0..1 through a signature moment of `length` steps, else None."""
        start = HITS[name]
        if start <= self.b < start + length:
            return (self.b - start) / length
        return None

    def steps(self):
        """Integer beat steps crossed this frame (for things that update once per step)."""
        return int(np.floor(self.b)) - int(np.floor(self.b0))


# ---------------------------------------------------------------- drawing helpers
BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16
BAYER = np.tile(BAYER4, (DH // 4, DW // 4))


def dots_layers(s, layers, x=0, y=0):
    """Merge braille dot layers [(dots, colour or per-cell colours)]; the last layer present in a cell wins."""
    H, W = layers[0][0].shape
    h, w = H // 4, W // 2
    total = np.zeros((H, W), bool)
    col = np.zeros((h, w, 3), np.float32)
    for dots, c in layers:
        total |= dots
        present = dots.reshape(h, 4, w, 2).any((1, 3))
        cc = np.broadcast_to(np.asarray(c, np.float32), (h, w, 3))
        col[present] = cc[present]
    s.braille(x, y, total, col)


def cell_mean(a):
    """Average a dot-resolution field down to cells."""
    H, W = a.shape
    return a.reshape(H // 4, 4, W // 2, 2).mean((1, 3))


def splat(points_x, points_y, W=DW, H=DH):
    """Boolean dot image with the given (float) points set."""
    img = np.zeros((H, W), bool)
    xi = np.round(points_x).astype(int)
    yi = np.round(points_y).astype(int)
    ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    img[yi[ok], xi[ok]] = True
    return img
