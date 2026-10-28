# 2:46-3:10 the calm break: a perspective ASCII sea at night, moon road, Logan observations as subtitles.
import math

import numpy as np

from lyrics import stream
from scenes.common import BG, CORAL, CYAN, DIM, HOTRED, MUTED, WHITE, hint_bar, status_bar, typed_lines
from term import gid, gradient, hexc, mix

SKY_TOP = hexc("04050b")
SKY_LOW = hexc("121a3a")
SEA_BG = hexc("060914")
DEEP = hexc("0e2a5c")
CREST = hexc("8fd8ff")
MOON = hexc("f3efd9")
HORIZON = 14
SEA_RAMP = np.array([gid(c) for c in " .,-~=≈"], np.int32)
METAR = "METAR KBOS 230000Z 22011KT 10SM BKN045 20/08 A2999 RMK AO2 SLP157 T02000083"


def sky(s, ctx):
    for r in range(1, HORIZON + 1):
        s.fill(0, r, s.cols, 1, gradient([SKY_TOP, SKY_LOW], (r - 1) / HORIZON))
    H, W = HORIZON * 4, s.cols * 2
    rng = np.random.default_rng(5)
    n = 140
    xs, ys = rng.integers(0, W, n), rng.integers(4, H - 6, n)
    ph, f = rng.random(n) * 6.28, 0.5 + rng.random(n) * 2.5
    on = np.sin(ctx.t * f + ph) > -0.2
    dots = np.zeros((H, W), bool)
    dots[ys[on], xs[on]] = True
    s.braille(0, 1, dots, MUTED * 0.9)
    # Moon (half-block disc with soft shading).
    mh, mw = 14, 14
    yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)
    d = np.hypot(xx - 6.5, (yy - 6.5))
    m = d < 6.3
    shade = np.clip(1.05 - 0.25 * np.hypot(xx - 4, yy - 4) / 6 - 0.15 * (np.sin(xx * 1.7) * np.cos(yy * 1.3) > 0.6), 0, 1)
    rgb = MOON[None, None] * shade[..., None]
    s.halfblock(92, 2, rgb, m)


def sea(s, ctx, x_moon=99):
    rows = s.rows - 2 - HORIZON
    C = s.cols
    r = np.arange(rows, dtype=np.float32)[:, None] + 0.6
    c = np.arange(C, dtype=np.float32)[None, :]
    z = 26.0 / r
    wx = (c - 60) * z / 24
    t = ctx.t
    amp = 1.0 + 0.6 * ctx.level + 0.8 * ctx.kick
    h = (np.sin(wx * 0.9 + z * 0.55 - t * 1.3) + 0.55 * np.sin(wx * 2.1 - z * 1.2 + t * 1.9)
         + 0.3 * np.sin(wx * 4.3 + z * 2.0 - t * 2.7)) * amp
    v = np.clip((h + 1.9) / 3.8, 0, 1)
    near = np.clip(r / rows, 0, 1)
    # Moon road: a shimmering column that widens towards the viewer.
    spread = 1.5 + r * 0.9
    road = np.exp(-((c - x_moon) / spread) ** 2) * (v > 0.55)
    val = np.clip(v * (0.35 + 0.65 * near) + road * 0.6, 0, 1)
    idx = SEA_RAMP[np.clip((val * (len(SEA_RAMP) - 1) + 0.4).astype(int), 0, len(SEA_RAMP) - 1)]
    col = gradient([DEEP * 0.6, DEEP, CYAN * 0.7, CREST], val)
    col = mix(col, MOON, np.clip(road * 1.3, 0, 1)[..., None])
    bg = np.broadcast_to(SEA_BG, (rows, C, 3))
    s.blit(0, HORIZON + 1, idx, col, bg)
    s.text(0, HORIZON, "─" * C, lambda i: mix(DIM, MOON * 0.6, math.exp(-((i - x_moon) / 10) ** 2)))


def ocean(s, ctx):
    s.clear(BG)
    sky(s, ctx)
    sea(s, ctx)

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
    hint_bar(s, ctx, CYAN)
