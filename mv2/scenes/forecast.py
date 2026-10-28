# 0:00 boot prompt  ·  0:05-0:48 the NWS forecast: lyric panel, radar over Boston, braille ocean.
import math

import numpy as np

import timeline as tl
from lyrics import stream
from scenes.common import (AMBER, BG, BLUE, CYAN, DIM, FG, GREEN, MUTED, RED, WHITE,
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
# Real coastline (lon, lat): mainland from Cape Ann to the canal, Cape Cod as a loop, and the I-495 arc.
MAINLAND = ((-70.60, 42.66), (-70.66, 42.60), (-70.77, 42.56), (-70.88, 42.52), (-70.92, 42.43), (-70.97, 42.38),
            (-71.04, 42.35), (-71.00, 42.28), (-70.89, 42.30), (-70.80, 42.24), (-70.72, 42.20), (-70.67, 42.10),
            (-70.66, 42.04), (-70.62, 41.95), (-70.55, 41.90), (-70.60, 41.74), (-70.71, 41.68), (-70.85, 41.60),
            (-71.00, 41.55), (-71.12, 41.50))
CAPE = ((-70.60, 41.74), (-70.50, 41.77), (-70.30, 41.71), (-70.15, 41.75), (-70.00, 41.77), (-70.03, 41.93),
        (-70.07, 42.00), (-70.19, 42.06), (-70.23, 42.08), (-70.03, 42.03), (-69.97, 41.93), (-69.95, 41.83),
        (-69.95, 41.67), (-69.99, 41.60), (-70.08, 41.67), (-70.28, 41.63), (-70.43, 41.60), (-70.60, 41.54),
        (-70.67, 41.52), (-70.62, 41.70))
I495 = ((-70.90, 42.82), (-71.15, 42.68), (-71.32, 42.62), (-71.45, 42.53), (-71.55, 42.36), (-71.50, 42.20),
        (-71.40, 42.08), (-71.20, 41.97), (-71.00, 41.88), (-70.75, 41.77))
BOSTON = (-71.06, 42.36)
VIEW = (-71.75, -69.85, 41.45, 42.85)  # lon0, lon1, lat0, lat1


def _proj(lon, lat, W, H):
    lon0, lon1, lat0, lat1 = VIEW
    k = H / (lat1 - lat0)
    xspan = (lon1 - lon0) * 0.74 * k
    x = (W - xspan) / 2 + (lon - lon0) * 0.74 * k
    return x, (lat1 - lat) * k


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
VALUES = {
    "intro": None,
    "tonight": (("low", "43°F"), ("wind", "W 10–15 mph"), ("gusts", "25 mph"), ("rain", "20%")),
    "friday": (("high", "52°F"), ("wind", "NW 10–15 mph"), ("gusts", "25 mph"), ("rain", "4%")),
    "saturday": (("high", "high-igh-igh"), ("wind", "--"), ("gusts", "--"), ("rain", "--")),
}


def radar(s, ctx, x, y, w, h, accent, glitch, flare=None):
    H, W = h * 4, w * 2
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = _proj(*BOSTON, W, H)
    ang = 2 * math.pi * ((ctx.b - tl.BEAT_PHASE) / 64.0)
    phi = np.arctan2(yy - cy, xx - cx)
    lag = np.mod(ang - phi, 2 * math.pi)
    after = np.exp(-lag * 1.3)
    if flare is not None:
        after = np.maximum(after, (1 - flare) ** 2)

    t = ctx.t
    rain = np.zeros((H, W), np.float32)
    rng = np.random.default_rng(7)
    for i in range(7):
        bx = (rng.random() * W * 1.4 + t * (1.5 + rng.random() * 1.5)) % (W * 1.4) - W * 0.2
        by = rng.random() * H
        r = 5 + rng.random() * 10
        rain += np.exp(-((xx - bx) ** 2 + ((yy - by) * 1.3) ** 2) / (r * r)) * (0.5 + 0.4 * rng.random())
    rain *= 0.6 + 0.4 * np.sin(xx * 0.31 + yy * 0.17 + t) ** 2
    bright = rain * (0.15 + 0.85 * after)
    dots_rain = bright > bayer(H, W) * 1.2 + 0.12
    cell = bright[:h * 4, :w * 2].reshape(h, 4, w, 2).mean((1, 3))
    rain_col = gradient([GREEN * 0.45, GREEN * 0.8, AMBER, RED], np.clip(cell * 1.5, 0, 1))

    def poly(points, every=1):
        m = np.zeros((H, W), bool)
        pts = [_proj(lo, la, W, H) for lo, la in points]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            draw_line(m, x0, y0, x1, y1)
        if every > 1:
            m &= (np.indices((H, W)).sum(0) % every == 0)
        return m

    coast = poly(MAINLAND) | poly(CAPE)
    hwy = poly(I495, every=2)
    ring = (np.abs(np.hypot(xx - cx, yy - cy) - 30) < 0.5) & ((xx.astype(int) + yy.astype(int)) % 4 == 0)
    sweep = np.zeros((H, W), bool)
    draw_line(sweep, cx, cy, cx + math.cos(ang) * 70, cy + math.sin(ang) * 70)
    if glitch > 0.05:
        dots_rain ^= ctx.rng(31).random((H, W)) < glitch * 0.25

    layers = [(ring, DIM * 0.7), (hwy, AMBER * 0.4), (coast, MUTED * 0.9), (dots_rain, rain_col),
              (sweep, mix(accent, WHITE, 0.3) * 0.8)]
    if flare is not None:
        # Signature moment: one ping ring travels out from Boston.
        ping = np.abs(np.hypot(xx - cx, yy - cy) - (4 + flare * 80)) < 0.9
        layers.append((ping, WHITE * (1 - flare) ** 0.7))
    braille_layers(s, x, y, layers)
    bx, by = x + int(cx / 2), y + int(cy / 4)
    s.put(bx, by, "◉", WHITE, bold=True)
    s.text(bx - 4, by, "bos", FG)
    capex, capey = _proj(-70.1, 41.86, W, H)
    s.text(x + int(capex / 2) + 1, y + int(capey / 4), "cape cod", DIM)
    hx, hy = _proj(-71.5, 42.5, W, H)
    s.text(x + int(hx / 2) - 2, y + int(hy / 4), "i-495", AMBER * 0.5)


def ocean(s, ctx, x, y, w, h, col, glitch):
    H, W = h * 4, w * 2
    t = ctx.t
    xs = np.arange(W, dtype=np.float32)
    amp = 1.0 + 0.8 * ctx.level + 0.6 * ctx.kick
    surf = (H * 0.3 + 1.8 * amp * np.sin(xs * 0.04 + t * 1.0) + 1.0 * np.sin(xs * 0.10 - t * 1.7)
            + 0.5 * np.sin(xs * 0.23 + t * 2.4))
    yy = np.arange(H, dtype=np.float32)[:, None]
    depth = yy - surf[None, :]
    dens = np.where(depth >= 0, np.exp(-depth / (H * 0.22)) * 0.4, 0)
    dots = dens > bayer(H, W)
    dots |= np.abs(depth) < 0.55
    if glitch > 0.0:
        dots ^= ctx.rng(13).random((H, W)) < glitch * 0.35
    rowc = gradient([mix(col, WHITE, 0.15), col * 0.8, col * 0.3, col * 0.1], np.linspace(0, 1, h))
    s.braille(x, y, dots, np.broadcast_to(rowc[:, None, :], (h, w, 3)))


def forecast(s, ctx):
    s.clear(BG)
    b = ctx.b
    part = _part(b)
    acc = PART_ACCENT[part]
    g_raw = _lookup(GLITCH, b)
    glitch = (math.log(g_raw) / math.log(2500)) ** 2 if g_raw > 1 else 0.0
    flare = tl.moment("radar_flare", b)

    # Lyrics lead: open space, a small header and a rule, no box.
    head = mix(acc, WHITE, (1 - flare) * 0.8) if flare is not None else acc * 0.85
    s.text(4, 2, "nws forecast · eastern massachusetts", head)
    s.text(4, 3, "─" * 64, DIM * 0.8)
    st = stream("ocean_b:1")
    typing = (ctx.bi - st.last_change(ctx.bi)) < 3
    typed_lines(s, 4, 5, st.lines(ctx.bi), 64, WHITE, mix(acc, WHITE, 0.3), ctx, max_rows=11, typing=typing)

    vals = VALUES[part]
    if vals is None:
        s.text(4, 18, "{} receiving forecast".format(spinner(ctx)), MUTED)
    else:
        x = 4
        for lab, val in vals:
            s.text(x, 18, lab, MUTED)
            s.text(x + len(lab) + 1, 18, val, acc * 0.9)
            x += len(lab) + len(val) + 5

    s.box(72, 2, 46, 20, DIM * 0.8, title="radar · boston", title_fg=MUTED)
    radar(s, ctx, 73, 3, 44, 18, acc, glitch, flare)

    ocean(s, ctx, 0, 26, 120, 9, _lookup(OCEAN_COL, b), glitch)

    # Saturday: "High-igh-igh" echoes take over as the glitch ramps.
    if b >= 1000:
        rng = ctx.rng(5, step=2)
        for _ in range(int(glitch * 70)):
            ex, ey = rng.integers(0, 110), rng.integers(1, 35)
            word = ("High-igh-igh", "-igh", "igh-", "HIGH")[rng.integers(0, 4)]
            s.text(ex, ey, word, mix(RED, WHITE, rng.random() * 0.6), bold=rng.random() < 0.4)
        for _ in range(int(glitch * 14)):
            s.shift_row(int(rng.integers(1, 35)), int(rng.integers(-8, 9)))
        s.corrupt(rng, glitch * 0.05, fg=RED)
        s.post["aberr"] = glitch * 7
        s.post["shake"] = (int(rng.integers(-1, 2) * glitch * 6), 0)

    status_bar(s, ctx, acc, extra=part)
