# 1:20-2:08 "Funding for this program…": a btop-style pledge-drive dashboard that slowly loses the carrier.
import math

import numpy as np

from lyrics import stream
from scenes.common import (AMBER, BG, CYAN, DIM, FG, GREEN, HOTRED, MUTED, PANEL, RED, WHITE, broadcast_date,
                           hint_bar, input_line, log_panel, status_bar)
from scenes.forecast import bayer
from term import big_text_mask, gradient, mix

START = 1848
RESET = 2348          # the original clears the log here and switches to "Broadcast Corporation"
DECAY_FROM = 2700     # the carrier starts to break up
CONDS = ("Cloudy", "Sunny", "Partly sunny", "Rain", "Drizzle", "Showers", "Clear", "Overcast")
TICKER = ("  ★  funding for this program was made possible by viewers like you  ★  "
          "pledge now · 1-800-555-0179  ★  annual financial support from the corporation for public broadcasting  ")


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

    # --- broadcast log -------------------------------------------------------
    history = st.history(ctx.bi)
    if b >= RESET:
        history = [h for h in history if h[0] >= RESET]
    title = "broadcast.log" if b < RESET else "broadcast.log · corporation"
    s.box(1, 2, 72, 30, border, title=title, title_fg=acc, tag="tail -f", tag_fg=DIM)
    log_panel(s, 3, 3, 68, 24, history, ctx)
    s.text(1, 28, "├" + "─" * 70 + "┤", border)
    input_line(s, 3, 29, 68, cur, ctx, acc)
    s.text(3, 30, "{} lines · {} key".format(len(history), sum(1 for h in history if h[2] == "key")), DIM)

    # --- weather card --------------------------------------------------------
    day = int((b - START) // 64)
    cond, temp, precip, wind, wdir = day_weather(day)
    date = broadcast_date(b, START)
    s.box(75, 2, 44, 11, DIM, title="weather · boston", title_fg=CYAN, tag=date.strftime("%d.%m.%Y"), tag_fg=AMBER)
    rgb, a = icon(cond, ctx.t)
    s.halfblock(78, 4, rgb, a)
    tm = big_text_mask("{}°".format(temp), 11)
    tcol = gradient([CYAN, AMBER, RED], (temp - 30) / 40)
    s.halfblock(97, 4, np.broadcast_to(tcol, tm.shape + (3,)).copy(), tm)
    s.text(97, 9, cond.lower(), FG, bold=True)
    s.text(78, 10, "wind {:2d} mph {:<2}".format(wind, wdir), CYAN)
    s.text(97, 10, "precip {:2d}%".format(precip), mix(CYAN, MUTED, 0.3))
    s.text(78, 11, date.strftime("%A").lower(), MUTED)

    # --- temperature history (braille line chart) ----------------------------
    s.box(75, 13, 44, 10, DIM, title="temperature · 30 days", title_fg=MUTED)
    W, H = 80, 28
    days = np.arange(day - 39, day + 1)
    temps = np.array([day_weather(int(d))[1] for d in days], np.float32)
    precs = np.array([day_weather(int(d))[2] for d in days], np.float32)
    ys = H - 2 - (temps - 30) / 32 * (H - 3)
    xs = np.linspace(0, W - 1, len(days))
    line = np.zeros((H, W), bool)
    fine_x = np.arange(W)
    fine_y = np.interp(fine_x, xs, ys)
    for xx_, yy_ in zip(fine_x, fine_y):
        line[int(np.clip(yy_, 0, H - 1)), xx_] = True
    area = (np.arange(H)[:, None] > fine_y[None, :]) & (bayer(H, W) < 0.18)
    s.braille(77, 14, area, AMBER * 0.35)
    s.braille(77, 14, line, AMBER)
    bars = "".join(" ▁▂▃▄▅▆▇█"[int(p / 100 * 8)] for p in precs)
    s.text(77, 21, bars, CYAN * 0.7)

    # --- pledge drive -------------------------------------------------------
    s.box(75, 23, 44, 9, DIM, title="pledge drive", title_fg=GREEN, tag="viewers like you", tag_fg=DIM)
    worth = {"key": 2500, "line": 180, "fluff": 25}
    raised = 12480 + sum(worth[h[2]] for h in st.history(ctx.bi))
    goal = 100000
    s.text(77, 24, "raised", MUTED)
    s.text(84, 24, "${:,}".format(raised), GREEN, bold=True)
    s.text(105, 24, "/ ${:,}".format(goal), DIM)
    p = raised / goal
    n = int(40 * p)
    s.text(77, 25, "".join("█" if i < n else "░" for i in range(40)), lambda i: gradient([GREEN, AMBER], i / 40) if i < n else DIM * 0.6)
    bands = ctx.bands()
    for i, (lab, band) in enumerate((("members", 3), ("viewers", 9), ("corporation", 16), ("foundation", 21))):
        v = float(np.clip(bands[band] * 1.1, 0, 1))
        s.text(77, 27 + i, "{:<12}".format(lab), MUTED)
        bl = int(v * 26)
        bar = "━" * bl + "╸"
        s.text(90, 27 + i, bar, lambda j: gradient([acc * 0.5, acc, mix(acc, WHITE, 0.5)], j / 26))

    # --- ticker --------------------------------------------------------------
    off = int(ctx.t * 18) % len(TICKER)
    tick = (TICKER * 3)[off:off + 118]
    s.fill(0, 33, 120, 1, PANEL)
    s.text(1, 33, tick, mix(AMBER, MUTED, 0.3), PANEL)

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
    hint_bar(s, ctx, acc)
