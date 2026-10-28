# 1:20-2:08 "Funding for this program…": a btop-style pledge-drive dashboard that slowly loses the carrier.
import math

import numpy as np

import timeline as tl
from lyrics import stream
from scenes.common import (AMBER, BG, CYAN, DIM, FG, GREEN, HOTRED, MUTED, RED, WHITE, broadcast_date,
                           input_line, log_panel, progress_bar, status_bar)
from scenes.forecast import bayer
from term import gradient, mix

START = 1848
RESET = 2348          # the original clears the log here and switches to "Broadcast Corporation"
DECAY_FROM = 2700     # the carrier starts to break up
CONDS = ("Cloudy", "Sunny", "Partly sunny", "Rain", "Drizzle", "Showers", "Clear", "Overcast")


def day_weather(d):
    """Deterministic daily weather; the first three days match the original's forecast."""
    fixed = {0: ("Cloudy", 43, 20, 13, "W"), 1: ("Sunny", 52, 4, 12, "NW"), 2: ("Partly sunny", 48, 7, 8, "N")}
    if d in fixed:
        return fixed[d]
    r = np.random.default_rng(1000 + d)
    temp = int(46 + 8 * math.sin(d * 0.4) + r.normal(0, 4))
    precip = int(np.clip(r.normal(33, 22), 0, 99))
    cond = CONDS[3 if precip > 60 else 4 if precip > 45 else int(r.integers(0, 8))]
    return cond, temp, precip, int(r.integers(4, 25)), ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[int(r.integers(0, 8))]


def icon(kind, t, w=16, h=10):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rgb = np.zeros((h, w, 3), np.float32)
    a = np.zeros((h, w), bool)
    sun_c = np.array([255, 205, 90], np.float32)
    if kind in ("Sunny", "Clear", "Partly sunny"):
        cx, cy = (6, 4) if kind == "Partly sunny" else (8, 5)
        d = np.hypot(xx - cx, (yy - cy) * 1.0)
        rays = (np.abs(np.sin(np.arctan2(yy - cy, xx - cx) * 4 + t * 2)) > 0.8) & (d < 5.5)
        m = (d < 2.8) | rays
        rgb[m], a[m] = sun_c, True
    if kind not in ("Sunny", "Clear"):
        cloud = ((np.hypot(xx - 6, yy - 6) < 3.2) | (np.hypot(xx - 10, yy - 5) < 3.6) |
                 (np.hypot(xx - 13, yy - 7) < 2.4)) & (yy < 9)
        shade = np.array([200, 210, 235], np.float32) if kind != "Overcast" else np.array([140, 145, 165], np.float32)
        rgb[cloud], a[cloud] = shade, True
    if kind in ("Rain", "Drizzle", "Showers", "Cloudy") and kind != "Cloudy":
        drops = ((xx.astype(int) + (yy + t * 8).astype(int)) % 4 == 0) & (yy >= 8)
        rgb[drops], a[drops] = np.array([120, 170, 255]), True
    return rgb, a


def funding(s, ctx):
    s.clear(BG)
    b = ctx.b
    decay = float(np.clip((b - DECAY_FROM) / (2976 - DECAY_FROM), 0, 1))
    st = stream("funding:0")
    cur = st.current(ctx.bi)
    lost = "CONNECTION" in cur or b >= 2930
    acc = mix(AMBER, HOTRED, decay)
    border = HOTRED if lost and (ctx.bi // 4) % 2 == 0 else mix(DIM, acc, 0.5)

    # --- broadcast log (the lead) ---------------------------------------------
    history = st.history(ctx.bi)
    if b >= RESET:
        history = [h for h in history if h[0] >= RESET]
    title = "broadcast.log" if b < RESET else "broadcast.log · corporation"
    s.box(1, 2, 72, 32, border, title=title, title_fg=acc)
    log_panel(s, 3, 3, 68, 27, history, ctx)
    s.text(1, 30, "├" + "─" * 70 + "┤", border)
    input_line(s, 3, 31, 68, cur, ctx, acc)

    # --- weather card --------------------------------------------------------
    day = int((b - START) // 64)
    cond, temp, precip, wind, wdir = day_weather(day)
    date = broadcast_date(b, START)
    s.box(75, 2, 44, 9, DIM * 0.8, title="weather · boston", title_fg=MUTED, tag=date.strftime("%d.%m.%Y"), tag_fg=DIM)
    rgb, a = icon(cond, ctx.t)
    s.halfblock(78, 4, rgb * 0.85, a)
    s.text(98, 4, "{}°F".format(temp), gradient([CYAN, AMBER, RED], (temp - 30) / 40), bold=True)
    s.text(98, 5, cond.lower(), FG)
    s.text(98, 7, "wind {} {}".format(wind, wdir), MUTED)
    s.text(98, 8, "rain {}%".format(precip), MUTED)

    # --- temperature history (braille line chart) ----------------------------
    s.box(75, 12, 44, 10, DIM * 0.8, title="temperature · 30 days", title_fg=MUTED)
    W, H = 80, 28
    days = np.arange(day - 39, day + 1)
    temps = np.array([day_weather(int(d))[1] for d in days], np.float32)
    ys = H - 2 - (temps - 30) / 32 * (H - 3)
    xs = np.linspace(0, W - 1, len(days))
    line = np.zeros((H, W), bool)
    fine_y = np.interp(np.arange(W), xs, ys)
    line[np.clip(fine_y.astype(int), 0, H - 1), np.arange(W)] = True
    area = (np.arange(H)[:, None] > fine_y[None, :]) & (bayer(H, W) < 0.12)
    s.braille(77, 13, area, AMBER * 0.25)
    s.braille(77, 13, line, AMBER * 0.85)

    # --- pledge drive -------------------------------------------------------
    s.box(75, 23, 44, 5, DIM * 0.8, title="pledge drive", title_fg=MUTED)
    worth = {"key": 2500, "line": 180, "fluff": 25}
    raised = 12480 + sum(worth[h[2]] for h in st.history(ctx.bi))
    s.text(77, 24, "${:,}".format(raised), GREEN * 0.9, bold=True)
    s.text(91, 24, "of $100,000 · viewers like you", DIM)
    progress_bar(s, 77, 25, 40, raised / 100000, GREEN * 0.5, GREEN * 0.9)

    # --- signature moment: the broadcast freezes, then only the log is left ----
    fz = tl.moment("funding_freeze", b)
    if fz is not None:
        if fz < 2 / 14:
            fg = s.fg.copy()
            s.fg[:], s.bg[:] = s.bg, fg * 0.9
        else:
            k = 0.2 + 0.8 * (fz - 2 / 14) / (12 / 14)
            s.fg[:, 74:] *= k
            s.fg[0] *= k

    # --- carrier decay -----------------------------------------------------------
    if decay > 0:
        rng = ctx.rng(9)
        for _ in range(int(decay * 10)):
            s.shift_row(int(rng.integers(1, 34)), int(rng.integers(-5, 6)))
        s.corrupt(rng, decay * 0.04, fg=HOTRED)
        s.fg[:] = s.fg * (1 - 0.35 * decay) + np.array([255, 60, 80], np.float32) * 0.35 * decay * (s.fg.max(-1, keepdims=True) / 255)
        s.post["aberr"] = decay * 4 + (3 if lost else 0)
    if lost:
        s.box(36, 14, 48, 5, HOTRED, bg=mix(BG, HOTRED, 0.15), style="heavy")
        s.ctext(16, "< C O N N E C T I O N   L O S T >", WHITE if (ctx.bi // 2) % 2 else HOTRED, bold=True)

    status_bar(s, ctx, acc, extra=date.strftime("%d.%m.%Y"), alert=lost)
