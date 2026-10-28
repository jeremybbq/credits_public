# 0:48-1:20 title drop: half-block CREDITS logo, warp starfield, credit lines, live spectrum.
import numpy as np

from scenes.common import BG, BLUE, DIM, FG, MUTED, ORANGE, PINK, RED, VIOLET, WHITE, hint_bar, pulse, status_bar
from term import BARS, big_text_mask, gradient, mix

LOGO_STOPS = [ORANGE, RED, PINK, VIOLET, BLUE, VIOLET, PINK, RED, ORANGE]
CREDITS = (
    (1144, "original animation", "plaaosert"),
    (1208, "music", "Frums — Credits EX"),
    (1272, "reimagined in", "python 3 · numpy · 24-bit colour"),
    (1336, "still running", "in the command line"),
)


def starfield(s, ctx, colour, speed=0.35, n=220):
    H, W = s.rows * 4, s.cols * 2
    rng = np.random.default_rng(11)
    X = rng.uniform(-1, 1, n)
    Y = rng.uniform(-1, 1, n)
    z = np.mod(rng.random(n) - ctx.t * speed, 1.0) + 0.02
    px = (W / 2 + X / z * W * 0.18).astype(int)
    py = (H / 2 + Y / z * H * 0.18).astype(int)
    ok = (px >= 0) & (px < W) & (py >= 0) & (py < H)
    dots = np.zeros((H, W), bool)
    dots[py[ok], px[ok]] = True
    # Streaks for the nearest stars.
    near = ok & (z < 0.25)
    dots[np.clip(py[near] + 1, 0, H - 1), px[near]] = True
    s.braille(0, 0, dots, colour)


def spectrum(s, ctx, y, h, colour, mirror=False):
    bands = ctx.bands()
    nb = len(bands)
    # Peak hold from the recent past.
    peaks = np.max([ctx.audio.bands(max(ctx.t - k / 60, 0)) - k * 0.012 for k in range(0, 40, 3)], axis=0)
    bw = s.cols // nb
    for i in range(nb):
        v = float(np.clip(bands[i] * (0.6 + 0.6 * ctx.level), 0, 1))
        idx = i
        if mirror:
            idx = nb // 2 + (i // 2 if i % 2 == 0 else -(i // 2) - 1)
        x = idx * bw
        total = v * h * 8
        for r in range(h):
            fill = int(np.clip(total - r * 8, 0, 8))
            if fill <= 0:
                break
            c = gradient([colour * 0.7, colour, WHITE], r / max(h - 1, 1))
            s.text(x, y + h - 1 - r, BARS[fill] * (bw - 1), c)
        pr = int(np.clip(peaks[i], 0, 1) * h)
        if 0 < pr <= h:
            s.text(x, y + h - pr, "▔" * (bw - 1), WHITE * 0.8)


def logo(s, ctx, cx, y, reveal=1.0, dissolve=0.0, split=0):
    m = big_text_mask("CREDITS", 26)
    h, w = m.shape
    xs = np.linspace(0, 1, w)
    hue = np.mod(xs * 0.6 + ctx.t * 0.12, 1.0)
    base = gradient(LOGO_STOPS, hue)
    k = 0.55 * ctx.kick
    rgb = np.broadcast_to(mix(base, WHITE, k)[None], (h, w, 3)).copy()
    # A highlight band sweeping down every two bars.
    band = ((ctx.b / 64.0) % 1.0) * (h + 8) - 4
    rgb += (np.exp(-((np.arange(h) - band) ** 2) / 6.0)[:, None, None] * 90)
    rgb = np.clip(rgb, 0, 255)
    mask = m.copy()
    rng = ctx.rng(3)
    if reveal < 1:
        cut = int(reveal * w)
        noise = rng.random((h, w)) < 0.35
        mask[:, cut:] = noise[:, cut:] & (np.arange(w)[None, cut:] < cut + 14)
    if dissolve > 0:
        mask &= rng.random((h, w)) > dissolve
    x0 = cx - w // 2
    if split:
        empty = np.where(~m.any(0))[0]
        half = int(empty[np.argmin(np.abs(empty - w * 4 / 7))]) if len(empty) else w // 2
        s.halfblock(x0 - split + 1, y + 1, rgb[:, :half] * 0.25, mask[:, :half])
        s.halfblock(x0 + half + split + 1, y + 1, rgb[:, half:] * 0.25, mask[:, half:])
        s.halfblock(x0 - split, y, rgb[:, :half], mask[:, :half])
        s.halfblock(x0 + half + split, y, rgb[:, half:], mask[:, half:])
    else:
        s.halfblock(x0 + 1, y + 1, rgb * 0.25, mask)
        s.halfblock(x0, y, rgb, mask)
    # Snare hits slice the logo sideways for a frame.
    if ctx.snare > 0.55:
        for r in range(y, y + h // 2 + 1):
            if rng.random() < 0.35:
                s.shift_row(r, int(rng.integers(-6, 7)))
    return h // 2


def title(s, ctx):
    s.clear(BG)
    lb = ctx.b - 1080
    accent = gradient(LOGO_STOPS, (ctx.t * 0.12) % 1.0)
    starfield(s, ctx, mix(DIM, accent, 0.25 + 0.4 * ctx.level), speed=0.3 + 0.25 * (ctx.b >= 1336))

    reveal = min(lb / 28.0, 1.0)
    dissolve = max(0.0, (ctx.b - 1800) / 44.0)
    split = 0
    if ctx.b >= 1336:
        side = 1 if (ctx.bi // 8) % 2 else -1
        split = int(round(2 + 2 * pulse(ctx, 8, 4))) if side > 0 else 0
    lh = logo(s, ctx, 60, 4, reveal, dissolve, split)

    # Credit lines, typed in on the original title beats.
    y0 = 6 + lh
    for i, (start, lab, val) in enumerate(CREDITS):
        if ctx.b < start:
            continue
        n = int((ctx.b - start) * 1.2)
        yy = y0 + i * 2
        s.text(58 - len(lab), yy, lab[:n], MUTED)
        s.text(59, yy, "▸", accent)
        shown = val[:max(0, n - 4)]
        s.text(61, yy, shown, FG, bold=True)
        if 0 < n - 4 <= len(val):
            s.put(61 + len(shown), yy, "▌", accent)

    spectrum(s, ctx, 26, 8, accent, mirror=ctx.b >= 1336)

    if ctx.b >= 1336:
        lv = ctx.level
        for side_x in (0, s.cols - 1):
            hgt = int(lv * 24)
            for r in range(hgt):
                s.put(side_x, 33 - r, "┃", gradient([accent, WHITE], r / 24))

    if ctx.b >= 1800:
        p = (ctx.b - 1800) / 48.0
        s.ctext(25, "{} tuning pledge.drive {:3d}%".format("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[ctx.bi // 2 % 10], int(p * 100)), MUTED)

    status_bar(s, ctx, accent)
    hint_bar(s, ctx, accent)
