# 2:46-3:10 the calm break: a perspective ASCII sea at night, moon road, Logan observations as subtitles.
import math

import numpy as np

import timeline as tl
from lyrics import stream
from scenes.common import BG, CORAL, CYAN, DIM, HOTRED, MUTED, WHITE, status_bar, typed_lines
from term import gid, gradient, hexc, mix

SKY_TOP = hexc("04050b")
SKY_LOW = hexc("121a3a")
SEA_BG = hexc("060914")
DEEP = hexc("0e2a5c")
CREST = hexc("8fd8ff")
MOON = hexc("f3efd9")
HORIZON = 14
SEA_GLYPHS = np.array([gid(c) for c in " ·-─"], np.int32)
METAR = "METAR KBOS 230000Z 22011KT 10SM BKN045 20/08 A2999 RMK AO2 SLP157 T02000083"
MOON_X = 97


def lightning(b):
    """Signature moment: a double flash of sheet lightning, then a slow fade."""
    p = tl.moment("lightning", b)
    if p is None:
        return 0.0
    step = p * tl.MOMENTS["lightning"][1]
    if step < 1.5:
        return 1.0
    if step < 2.5:
        return 0.25
    if step < 3.5:
        return 0.8
    return 0.8 * (1 - (step - 3.5) / 10.5) ** 2


def sky(s, ctx, flash):
    pale = hexc("8ea2d8")
    for r in range(1, HORIZON + 1):
        c = gradient([SKY_TOP, SKY_LOW], (r - 1) / HORIZON)
        s.fill(0, r, s.cols, 1, mix(c, pale, flash * 0.55 * (0.6 + 0.4 * r / HORIZON)))
    if flash < 0.3:
        H, W = HORIZON * 4, s.cols * 2
        rng = np.random.default_rng(5)
        n = 90
        xs, ys = rng.integers(0, W, n), rng.integers(4, H - 6, n)
        ph, f = rng.random(n) * 6.28, 0.3 + rng.random(n) * 1.2
        on = np.sin(ctx.t * f + ph) > 0.0
        dots = np.zeros((H, W), bool)
        dots[ys[on], xs[on]] = True
        s.braille(0, 1, dots, MUTED * 0.7)
    # Moon: small half-block disc, soft limb darkening.
    yy, xx = np.mgrid[0:10, 0:10].astype(np.float32)
    d = np.hypot(xx - 4.5, yy - 4.5)
    shade = np.clip(1.0 - 0.3 * (d / 4.6) ** 2, 0, 1)
    s.halfblock(MOON_X - 5, 3, MOON[None, None] * shade[..., None], d < 4.6)


def sea(s, ctx, flash):
    rows = s.rows - 2 - HORIZON
    C = s.cols
    r = np.arange(rows, dtype=np.float32)[:, None] + 0.6
    c = np.arange(C, dtype=np.float32)[None, :]
    z = 26.0 / r
    wx = (c - 60) * z / 24
    t = ctx.t
    amp = 1.0 + 0.3 * ctx.level
    h = (np.sin(wx * 0.9 + z * 0.55 - t * 1.0) + 0.5 * np.sin(wx * 2.1 - z * 1.2 + t * 1.5)
         + 0.25 * np.sin(wx * 4.3 + z * 2.0 - t * 2.1)) * amp
    v = np.clip((h + 1.75) / 3.5, 0, 1)
    near = np.clip(r / rows, 0, 1)
    road = np.exp(-((c - MOON_X) / (1.2 + r * 0.7)) ** 2) * (v > 0.5)
    val = np.clip(v * (0.55 + 0.45 * near) + road * 0.45 + flash * 0.15, 0, 1)
    level = np.digitize(val, (0.5, 0.62, 0.74))
    idx = SEA_GLYPHS[level]
    col = gradient([DEEP, CYAN * 0.55, CREST * 0.8], np.clip((val - 0.5) / 0.5, 0, 1))
    col = mix(col, MOON, np.clip(road * 1.2 + flash * 0.4, 0, 1)[..., None])
    s.blit(0, HORIZON + 1, idx, col, np.broadcast_to(SEA_BG, (rows, C, 3)))
    s.text(0, HORIZON, "─" * C, lambda i: mix(DIM * 0.8, MOON * 0.5, math.exp(-((i - MOON_X) / 9) ** 2)))


def ocean(s, ctx):
    s.clear(BG)
    flash = lightning(ctx.b)
    sky(s, ctx, flash)
    sea(s, ctx, flash)

    # Observations (the clean stream), with the corrupted copies flickering over it.
    lines = stream("ocean_c:1").lines(ctx.bi)
    glitchy = None
    for k in ("ocean_c:2", "ocean_c:3", "ocean_c:4"):
        st = stream(k)
        if st.last_change(ctx.bi) == ctx.bi and st.lines(ctx.bi):
            glitchy = st.lines(ctx.bi)
    st1 = stream("ocean_c:1")
    typing = (ctx.bi - st1.last_change(ctx.bi)) < 3
    if glitchy:
        typed_lines(s, 4, 2, glitchy, 70, HOTRED, WHITE, ctx, max_rows=11)
        s.post["aberr"] = 3
    else:
        typed_lines(s, 4, 2, lines, 70, CORAL, WHITE, ctx, max_rows=11, typing=typing)

    n = int(max(ctx.b - 3896, 0) / 2)
    s.text(2, 33, METAR[:n], MUTED * 0.8)

    if 4401 <= ctx.b < 4412:
        s.post["bright"] = 0.35 if (ctx.bi // 2) % 2 else 1.0
    if ctx.b >= 4412:
        s.post["bright"] = max(0.15, 1 - (ctx.b - 4412) / 48)

    status_bar(s, ctx, CYAN, extra="KBOS 7PM")
