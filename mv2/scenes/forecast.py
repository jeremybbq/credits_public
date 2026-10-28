# 0:00 boot prompt  ·  0:05-0:48 the NWS forecast: lyric panel, radar over Boston, braille ocean.
import math

import numpy as np

from lyrics import stream
from scenes.common import (AMBER, BG, BLUE, CYAN, DIM, FG, GREEN, MUTED, RED, WHITE, hint_bar,
                           progress_bar, spinner, status_bar, typed_lines)
from term import gradient, hexc, mix

BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16


def bayer(h, w):
    return np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]


def braille_layers(s, x, y, layers):
    """Merge several braille dot layers; per cell the last layer present decides the colour."""
    H, W = layers[0][0].shape
    h, w = H // 4, W // 2
    total = np.zeros((H, W), bool)
    col = np.zeros((h, w, 3), np.float32)
    for dots, c in layers:
        total |= dots
        present = dots[:h * 4, :w * 2].reshape(h, 4, w, 2).any((1, 3))
        cc = np.broadcast_to(np.asarray(c, np.float32), (h, w, 3))
        col[present] = cc[present]
    s.braille(x, y, total, col)


def draw_line(dots, x0, y0, x1, y1):
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 1
    xs = np.linspace(x0, x1, n).round().astype(int)
    ys = np.linspace(y0, y1, n).round().astype(int)
    ok = (xs >= 0) & (xs < dots.shape[1]) & (ys >= 0) & (ys < dots.shape[0])
    dots[ys[ok], xs[ok]] = True


# ------------------------------------------------------------------ boot
BOOT_CMD = "rx --tune pbs://boston --archive 2009-10-22T19:21 --decode"


def boot(s, ctx):
    t = ctx.t
    s.clear(BG)
    rng = ctx.rng(1)
    # Faint static that rises with the intro riser.
    k = min(t / 5.4, 1)
    H, W = 36 * 4, 120 * 2
    noise = rng.random((H, W)) < 0.015 + 0.05 * k
    s.braille(0, 0, noise, DIM * (0.25 + 0.5 * k))

    y = 3
    if t < 0.6:
        if int(t * 4) % 2 == 0:
            s.put(3, y, "▌", GREEN)
        return
    n = int((t - 0.6) * 32)
    cmd = BOOT_CMD[:n]
    s.text(3, y, "❯ ", GREEN, bold=True)
    s.text(5, y, cmd, FG)
    if n < len(BOOT_CMD) or int(t * 4) % 2 == 0:
        s.put(5 + len(cmd), y, "▌", GREEN)
    done = 0.6 + len(BOOT_CMD) / 32
    if t < done + 0.1:
        return
    p = min((t - done - 0.1) / 1.0, 1)
    if p < 1:
        s.text(5, y + 2, spinner(ctx, 1) + " scanning carriers", CYAN)
    else:
        s.text(5, y + 2, "✓ carrier locked ", GREEN)
        s.text(22, y + 2, "57.25 MHz · ch 2 · 525 lines", MUTED)
    progress_bar(s, 5, y + 3, 50, p, BLUE, CYAN)
    s.text(57, y + 3, "{:5.1f} MHz".format(54 + 34 * p), MUTED)
    steps = (("✓ vbi stream    ", "1,019 frames · 0 errors", 0.3), ("✓ audio sync    ", "179 bpm · offset 5.492 s", 0.7),
             ("✓ decoder       ", "nws forecast · eastern massachusetts", 1.1))
    for i, (a, b2, dt) in enumerate(steps):
        if t > done + 1.1 + dt:
            s.text(5, y + 5 + i, a, GREEN)
            s.text(5 + len(a), y + 5 + i, b2, MUTED)
    if t > done + 2.4:
        s.text(5, y + 9, "▶ playing", WHITE, bold=True)
    if t > 3.0:
        status_bar(s, ctx, GREEN, label="boot")


# ------------------------------------------------------------------ forecast
COAST = [(0.70, 0.00), (0.68, 0.12), (0.63, 0.25), (0.60, 0.36), (0.56, 0.44), (0.60, 0.50), (0.58, 0.58),
         (0.62, 0.66), (0.66, 0.74), (0.74, 0.78), (0.84, 0.78), (0.90, 0.72), (0.92, 0.62), (0.90, 0.55),
         (0.86, 0.52), (0.89, 0.50), (0.95, 0.60), (0.97, 0.74), (0.93, 0.84), (0.78, 0.88), (0.66, 0.92),
         (0.62, 1.00)]
GLITCH = ((60, 1), (310, 3), (666, 6), (1000, 13), (1044, 102), (1048, 230), (1052, 500), (1056, 760),
          (1060, 1600), (1064, 2500))
OCEAN_COL = ((60, CYAN), (310, BLUE), (312, CYAN), (314, BLUE), (590, MUTED), (656, AMBER),
             (666, hexc("ffd479")), (850, AMBER), (1000, MUTED))


def _lookup(table, b):
    v = table[0][1]
    for k, val in table:
        if b >= k:
            v = val
    return v


def _part(b):
    if b < 310:
        return "intro"
    if b < 646:
        return "tonight"
    if b < 1000:
        return "friday"
    return "saturday"


PART_ACCENT = {"intro": BLUE, "tonight": CYAN, "friday": AMBER, "saturday": RED}
CHIPS = {
    "intro": (("TEMP", "--°F"), ("WIND", "-- mph"), ("GUSTS", "-- mph"), ("RAIN", "--%")),
    "tonight": (("LOW", "43°F"), ("WIND", "W 10-15"), ("GUSTS", "25 mph"), ("RAIN", "20%")),
    "friday": (("HIGH", "52°F"), ("WIND", "NW 10-15"), ("GUSTS", "25 mph"), ("RAIN", "4%")),
    "saturday": (("HIGH", "HIGH-IGH"), ("WIND", "--"), ("GUSTS", "--"), ("RAIN", "--")),
}


def radar(s, ctx, x, y, w, h, accent, glitch):
    H, W = h * 4, w * 2
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * 0.55, H * 0.46
    ang = 2 * math.pi * (ctx.b / 64.0)
    phi = np.arctan2(yy - cy, (xx - cx) * 1.0)
    lag = np.mod(ang - phi, 2 * math.pi)
    after = np.exp(-lag * 1.1)

    t = ctx.t
    rain = np.zeros((H, W), np.float32)
    rng = np.random.default_rng(7)
    for i in range(8):
        bx = (rng.random() * W * 1.4 + t * (2.0 + rng.random() * 2)) % (W * 1.4) - W * 0.2
        by = rng.random() * H
        r = 6 + rng.random() * 12
        rain += np.exp(-((xx - bx) ** 2 + ((yy - by) * 1.3) ** 2) / (r * r)) * (0.6 + 0.4 * rng.random())
    rain *= 0.55 + 0.45 * np.sin(xx * 0.31 + yy * 0.17 + t) ** 2
    bright = rain * (0.3 + 0.9 * after)
    dots_rain = bright > bayer(H, W) * 1.1 + 0.08

    cell = bright[:h * 4, :w * 2].reshape(h, 4, w, 2).mean((1, 3))
    rain_col = gradient([GREEN * 0.6, GREEN, AMBER, RED], np.clip(cell * 1.6, 0, 1))

    rings = np.zeros((H, W), bool)
    d = np.hypot(xx - cx, (yy - cy) * 1.0)
    for r in (14, 28, 42):
        rings |= (np.abs(d - r) < 0.55) & ((xx.astype(int) + yy.astype(int)) % 3 == 0)
    coast = np.zeros((H, W), bool)
    for (a0, b0), (a1, b1) in zip(COAST, COAST[1:]):
        draw_line(coast, a0 * W, b0 * H, a1 * W, b1 * H)
    ring495 = np.zeros((H, W), bool)
    th = np.linspace(math.pi * 0.42, math.pi * 1.58, 160)
    rx_, ry_ = cx + 26 * np.cos(th), cy + 28 * np.sin(th)
    ok = (rx_ >= 0) & (rx_ < W) & (ry_ >= 0) & (ry_ < H)
    ring495[ry_[ok].astype(int), rx_[ok].astype(int)] = True
    sweep = np.zeros((H, W), bool)
    draw_line(sweep, cx, cy, cx + math.cos(ang) * 60, cy + math.sin(ang) * 60)

    if glitch > 0.05:
        g = ctx.rng(31)
        flip = g.random((H, W)) < glitch * 0.25
        dots_rain ^= flip

    braille_layers(s, x, y, [
        (rings, DIM * 0.9), (ring495, AMBER * 0.55), (coast, MUTED), (dots_rain, rain_col),
        (sweep, mix(accent, WHITE, 0.4)),
    ])
    bx, by = x + int(cx / 2), y + int(cy / 4)
    s.put(bx, by, "◉", WHITE, bold=True)
    s.text(bx + 2, by, "BOS", WHITE, bold=True)
    s.text(x + 1, y + h - 1, "I-495", AMBER * 0.8)
    s.text(x + w - 14, y + h - 1, "{:3d}° sweep".format(int(math.degrees(ang)) % 360), DIM)


def ocean(s, ctx, x, y, w, h, col, glitch):
    H, W = h * 4, w * 2
    t = ctx.t
    xs = np.arange(W, dtype=np.float32)
    amp = 1.0 + 1.6 * ctx.level + 2.0 * ctx.kick
    surf = (H * 0.28 + 2.2 * amp * np.sin(xs * 0.045 + t * 1.2) + 1.4 * np.sin(xs * 0.11 - t * 2.3)
            + 0.8 * np.sin(xs * 0.27 + t * 3.1))
    yy = np.arange(H, dtype=np.float32)[:, None]
    depth = yy - surf[None, :]
    dens = np.where(depth >= 0, np.exp(-depth / (H * 0.35)) * 0.75, 0)
    sparkle = 0.12 * np.sin(xs[None, :] * 0.7 + yy * 0.9 + t * 5)
    dots = (dens + sparkle) > bayer(H, W)
    dots |= np.abs(depth) < 0.6
    if glitch > 0.0:
        g = ctx.rng(13)
        dots ^= g.random((H, W)) < glitch * 0.35
    rowc = gradient([mix(col, WHITE, 0.3), col, col * 0.35, col * 0.12], np.linspace(0, 1, h))
    colours = np.broadcast_to(rowc[:, None, :], (h, w, 3))
    s.braille(x, y, dots, colours)


def forecast(s, ctx):
    s.clear(BG)
    b = ctx.b
    part = _part(b)
    acc = PART_ACCENT[part]
    g_raw = _lookup(GLITCH, b)
    glitch = (math.log(g_raw) / math.log(2500)) ** 2 if g_raw > 1 else 0.0
    ocean_col = _lookup(OCEAN_COL, b)

    # Lyric panel.
    lines = stream("ocean_b:1").lines(ctx.bi)
    s.box(2, 2, 68, 14, acc * 0.8, title="◆ nws forecast · eastern massachusetts", title_fg=acc,
          tag="LIVE ●" if (ctx.bi // 8) % 2 == 0 else "LIVE ○", tag_fg=acc)
    st = stream("ocean_b:1")
    typing = (ctx.bi - st.last_change(ctx.bi)) < 3
    typed_lines(s, 5, 4, lines, 62, FG, mix(acc, WHITE, 0.3), ctx, max_rows=11, typing=typing)

    # Weather chips.
    for i, (lab, val) in enumerate(CHIPS[part]):
        cx = 2 + i * 17
        s.box(cx, 17, 16, 5, DIM, style="round")
        s.text(cx + 2, 18, lab, MUTED)
        v = val
        if part == "intro":
            v = val.replace("--", spinner(ctx) * 2)
        s.text(cx + 2, 19, v, mix(acc, WHITE, 0.25), bold=True)
        seed = np.random.default_rng(i * 31 + {"intro": 0, "tonight": 1, "friday": 2, "saturday": 3}[part])
        walk = np.cumsum(seed.normal(0, 1, 40))
        k = int(ctx.b / 16) % 28
        seg = walk[k:k + 12]
        seg = (seg - seg.min()) / (np.ptp(seg) + 1e-6)
        s.text(cx + 2, 20, "".join(" ▁▂▃▄▅▆▇"[int(v * 7)] for v in seg), acc * 0.6)

    # Radar.
    s.box(72, 2, 46, 20, DIM, title="radar · boston", title_fg=MUTED, tag="reflectivity", tag_fg=DIM)
    radar(s, ctx, 73, 3, 44, 18, acc, glitch)

    # Ocean.
    s.text(2, 23, "◢ swell · boston harbor", MUTED)
    s.text(26, 23, "{:.1f} ft · {} kt".format(1.4 + 2.5 * ctx.level, 10 + int(5 * ctx.level)), DIM)
    ocean(s, ctx, 0, 24, 120, 11, ocean_col, glitch)

    # Saturday: "High-igh-igh" echoes take over as the glitch ramps.
    if b >= 1000:
        rng = ctx.rng(5, step=2)
        n = int(glitch * 70)
        for _ in range(n):
            ex, ey = rng.integers(0, 110), rng.integers(1, 35)
            word = ("High-igh-igh", "-igh", "igh-", "HIGH")[rng.integers(0, 4)]
            s.text(ex, ey, word, mix(RED, WHITE, rng.random() * 0.6), bold=rng.random() < 0.4)
        for _ in range(int(glitch * 14)):
            s.shift_row(int(rng.integers(1, 35)), int(rng.integers(-8, 9)))
        s.corrupt(rng, glitch * 0.05, fg=RED)
        s.post["aberr"] = glitch * 7
        s.post["shake"] = (int(rng.integers(-1, 2) * glitch * 6), 0)

    status_bar(s, ctx, acc, extra=part)
    hint_bar(s, ctx, acc)
