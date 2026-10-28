# 0:48-1:20 title: a quiet letter-spaced wordmark, thin rules, credit lines and a single oscilloscope trace.
import numpy as np

import timeline as tl
from scenes.common import BG, DIM, FG, MUTED, ORANGE, PINK, WHITE, pulse, status_bar
from term import gradient, mix

WORD = "c r e d i t s"
GLYPHS = "⠁⠃⠇⠏⠟⠿⡿⣿░▒/\\|-=+*#"
CREDITS = (
    (1144, "original animation", "plaaosert"),
    (1208, "music", "Frums — Credits EX"),
    (1272, "reimagined in", "python 3 · numpy · 24-bit colour"),
    (1336, "still running", "in the command line"),
)


def starfield(s, ctx, colour, speed=0.12, n=90):
    H, W = s.rows * 4, s.cols * 2
    rng = np.random.default_rng(11)
    X = rng.uniform(-1, 1, n)
    Y = rng.uniform(-1, 1, n)
    z = np.mod(rng.random(n) - ctx.t * speed, 1.0) + 0.05
    px = (W / 2 + X / z * W * 0.18).astype(int)
    py = (H / 2 + Y / z * H * 0.18).astype(int)
    ok = (px >= 0) & (px < W) & (py >= 0) & (py < H)
    dots = np.zeros((H, W), bool)
    dots[py[ok], px[ok]] = True
    s.braille(0, 0, dots, colour)


def scope(s, ctx, y, h, colour):
    """A single thin trace built from the spectrum: flat when quiet, alive when loud."""
    H, W = h * 4, s.cols * 2
    bands = ctx.bands()
    xs = np.linspace(0, len(bands) - 1, W)
    amp = np.interp(xs, np.arange(len(bands)), bands) * (0.4 + 0.6 * ctx.level)
    phase = np.linspace(0, 18 * np.pi, W) + ctx.t * 6
    trace = H / 2 + np.sin(phase) * amp * (H / 2 - 1) * np.hanning(W) ** 0.5
    dots = np.zeros((H, W), bool)
    ys = np.clip(trace.round().astype(int), 0, H - 1)
    dots[ys, np.arange(W)] = True
    s.braille(0, y, dots, colour)


def title(s, ctx):
    s.clear(BG)
    b = ctx.b
    lb = b - 1080
    accent = gradient([ORANGE, PINK, ORANGE], (ctx.t * 0.05) % 1.0)
    starfield(s, ctx, DIM * 0.55)

    inv = tl.moment("title_invert", b)
    dim_rest = 0.3 if inv is not None else 1.0

    # Wordmark: each letter decodes from noise, left to right.
    y = 10
    rng = ctx.rng(3)
    out = b >= 1800
    x0 = 60 - len(WORD) // 2
    for i, c in enumerate(WORD):
        if c == " ":
            continue
        settle = 6 + i * 2.2
        gone = out and rng.random() < (b - 1800) / 40
        if lb < settle or gone:
            s.put(x0 + i, y, GLYPHS[int(rng.integers(0, len(GLYPHS)))], accent * 0.7)
        else:
            s.put(x0 + i, y, c, WHITE, bold=True)
    if inv is not None:
        k = 1 - inv
        s.fill(x0 - 3, y, len(WORD) + 6, 1, mix(BG, WHITE, 0.4 + 0.6 * k))
        s.text(x0, y, WORD, BG, bold=True)

    # Thin rules that breathe on the quarter-note.
    p = pulse(ctx, 8, 5) if b >= 1336 else 0.0
    half = int(min(lb / 2, 22) + 2 * p)
    rule = mix(DIM, accent, 0.5 + 0.4 * p) * dim_rest
    if half > 0:
        s.text(60 - half, y - 2, "─" * (half * 2), rule)
        s.text(60 - half, y + 2, "─" * (half * 2), rule)

    # Credit lines, typed in on the original title beats.
    for i, (start, lab, val) in enumerate(CREDITS):
        if b < start:
            continue
        n = int((b - start) * 1.2)
        yy = 15 + i * 2
        s.text(57 - len(lab), yy, lab[:n], MUTED * dim_rest)
        s.text(59, yy, "·", accent * 0.7 * dim_rest)
        shown = val[:max(0, n - 4)]
        s.text(61, yy, shown, FG * dim_rest)
        if 0 < n - 4 <= len(val):
            s.put(61 + len(shown), yy, "▌", accent)

    scope(s, ctx, 27, 4, mix(DIM, accent, 0.35 + 0.4 * ctx.level) * dim_rest)

    if b >= 1800:
        pr = (b - 1800) / 48.0
        s.ctext(31, "tuning pledge.drive {:3d}%".format(int(pr * 100)), MUTED)

    status_bar(s, ctx, accent)
