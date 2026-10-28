# 2:08 melt + no signal  ·  2:14 reboot with wire globe  ·  2:25-2:46 the crash: four tmux panes.
import math

import numpy as np

import timeline as tl
from lyrics import stream
from scenes.common import (AMBER, BG, CYAN, DIM, FG, GREEN, HOTRED, MUTED, PANEL, RED, WHITE, input_line,
                           log_panel, progress_bar, spinner, status_bar)
from term import big_text_mask, mix

# ------------------------------------------------------------------ melt / no signal
MELT_END = 3022


def melt(s, ctx):
    from scenes.funding import funding
    if ctx.b < MELT_END:
        snap = s.copy()
        funding(snap, ctx.at_beat(2975.5))
        dt = max(ctx.t - ctx.at_beat(2976).t, 0)
        cols = s.cols
        rng = np.random.default_rng(4)
        delay = rng.random(cols) * 0.7
        grav = 22 + rng.random(cols) * 30
        off = (np.maximum(dt - delay, 0) ** 2 * grav).astype(int)
        ys = np.arange(s.rows)[:, None] - off[None, :]
        valid = ys >= 1
        ys = np.clip(ys, 0, s.rows - 1)
        xs = np.broadcast_to(np.arange(cols)[None, :], ys.shape)
        s.clear(BG)
        s.ch[:] = np.where(valid, snap.ch[ys, xs], 0)
        fade = max(0.0, 1 - dt / 1.8)
        s.fg[:] = np.where(valid[..., None], snap.fg[ys, xs], 0) * fade
        s.bg[:] = np.where(valid[..., None], BG + (snap.bg[ys, xs] - BG) * fade, BG)
        s.post["aberr"] = 4 * fade
        return

    s.clear(BG)
    blip = tl.moment("carrier_blip", ctx.b)
    if blip is not None:
        # Signature moment: the static drops out and, for a breath, the carrier is there.
        s.clear((0, 0, 0))
        s.ctext(17, "◉  57.25 MHz", WHITE if blip < 0.6 else MUTED, bold=True)
        status_bar(s, ctx, MUTED)
        return
    rng = ctx.rng(2)
    H, W = s.rows * 4, s.cols * 2
    static = rng.random((H, W)) < 0.22
    roll = int((ctx.t * 40) % (H + 40)) - 20
    band = np.zeros((H, W), bool)
    band[max(roll, 0):max(roll + 10, 0)] = True
    s.braille(0, 0, static & ~band, DIM * 0.55)
    s.braille(0, 0, static & band, MUTED)
    left = max(0.0, (3132 - ctx.b) * 0.0419)
    s.box(40, 14, 40, 7, MUTED, bg=PANEL, title="rx", title_fg=MUTED)
    s.ctext(16, "◌  no carrier", WHITE, PANEL, bold=True)
    s.ctext(18, "{}  retrying in {:.1f}s".format(spinner(ctx), left), MUTED, PANEL)
    status_bar(s, ctx, MUTED, alert=True)


# ------------------------------------------------------------------ reboot
BOOT_LOG = (
    ("OK", "Started Signal Recovery Daemon."), ("OK", "Mounted /archive/pbs/2009-10-22."),
    ("OK", "Reached target Weather Service."), ("OK", "Started NWS Forecast Decoder."),
    ("FAILED", "Failed to start Carrier Lock (57.25 MHz)."), ("OK", "Started Pledge Drive Ledger."),
    ("OK", "Listening on viewers-like-you.socket."), ("OK", "Started Annual Financial Support Service."),
    ("WARN", "corporation-for-public-broadcasting: no response"), ("OK", "Reached target Funding."),
    ("OK", "Started Funding for this Program."), ("OK", "Started Funding for this Program."),
    ("FAILED", "Failed to start Funding for this Program."), ("OK", "Mounted /dev/ocean."),
    ("OK", "Started Logan Airport Observations."), ("OK", "Reached target Boston Metropolitan Area."),
    ("WARN", "dew point 47 · relative humidity 46%"), ("OK", "Started Access Point Search."),
    ("FAILED", "Failed to start PBS #01."), ("FAILED", "Failed to start PBS #02."),
    ("FAILED", "Failed to start PBS #03."), ("OK", "Started Annual Financial Suppor-"),
    ("OK", "Started Annual Financial Suppor-"), ("OK", "Started Annual Financial Suppor-"),
    ("WARN", "Annual financial suppor- (repeated 5 times)"), ("OK", "Reached target Viewers Like You."),
    ("OK", "Started Bi-Annual Funding Timer."), ("FAILED", "Failed to start Broadcast."),
    ("OK", "Reached target Emergency Mode."), ("WARN", "kernel: by by by by by by by"),
    ("FAILED", "Failed to start Thank You."), ("OK", "Reached target Please Wait."),
)
TAG = {"OK": ("[  OK  ]", GREEN), "FAILED": ("[FAILED]", HOTRED), "WARN": ("[ WARN ]", AMBER)}


def wire_globe(s, ctx, x, y, w, h, col, back_col):
    H, W = h * 4, w * 2
    R = min(W, H) * 0.42
    cx, cy = W / 2, H / 2
    rot = ctx.t * 0.7
    tilt = 0.35
    pts = []
    for lat in np.radians(np.arange(-75, 76, 15)):
        lon = np.linspace(0, 2 * np.pi, 220)
        pts.append(np.stack([np.cos(lat) * np.cos(lon), np.full_like(lon, np.sin(lat)), np.cos(lat) * np.sin(lon)], 1))
    for lon0 in np.radians(np.arange(0, 180, 20)):
        lat = np.linspace(0, 2 * np.pi, 200)
        pts.append(np.stack([np.cos(lat) * np.cos(lon0), np.sin(lat), np.cos(lat) * np.sin(lon0)], 1))
    p = np.concatenate(pts)
    c, sn = np.cos(rot), np.sin(rot)
    p = p @ np.array([[c, 0, -sn], [0, 1, 0], [sn, 0, c]], np.float32)
    ct, st = np.cos(tilt), np.sin(tilt)
    p = p @ np.array([[1, 0, 0], [0, ct, -st], [0, st, ct]], np.float32)
    px = (cx + p[:, 0] * R).astype(int)
    py = (cy - p[:, 1] * R).astype(int)
    ok = (px >= 0) & (px < W) & (py >= 0) & (py < H)
    front = np.zeros((H, W), bool)
    back = np.zeros((H, W), bool)
    f = ok & (p[:, 2] > 0)
    bk = ok & (p[:, 2] <= 0)
    back[py[bk], px[bk]] = True
    front[py[f], px[f]] = True
    s.braille(x, y, back, back_col)
    s.braille(x, y, front, col)
    # Orbiting satellite.
    a = ctx.t * 1.6
    sx = x + w / 2 + math.cos(a) * w * 0.47
    sy = y + h / 2 + math.sin(a) * h * 0.18
    s.put(int(sx), int(sy), "◆", AMBER if math.sin(a) > 0 else AMBER * 0.4)


def reboot(s, ctx):
    s.clear(BG)
    b = ctx.b
    lb = b - 3132
    fast = b >= 3376
    s.box(1, 2, 66, 24, DIM, title="journalctl -f", title_fg=GREEN)
    n = min(int(lb // 8) + 1, len(BOOT_LOG))
    shown = BOOT_LOG[max(0, n - 22):n]
    for i, (k, msg) in enumerate(shown):
        tag, c = TAG[k]
        fresh = i == len(shown) - 1 and (lb % 8) < 3
        s.text(3, 3 + i, tag, c, bold=True)
        s.text(12, 3 + i, msg, WHITE if fresh else (FG if k == "OK" else c * 0.9))

    s.box(68, 2, 51, 24, DIM, title="antenna · searching", title_fg=CYAN)
    wire_globe(s, ctx, 69, 3, 49, 22, mix(CYAN, WHITE, 0.2 + 0.5 * ctx.kick), DIM * 0.7)

    st = stream("loadingbar:6")
    s.box(1, 27, 118, 7, GREEN * 0.6, title="recv annual_financial_support.dat", title_fg=GREEN)
    if fast:
        p = min((b - 3376) / 12.0, 1.0)
        label = "please wait…"
    else:
        # Progress with stalls, like a real download.
        raw = lb / (3376 - 3132)
        p = 0.92 * (raw - 0.06 * np.sin(raw * 18) ** 2)
        label = "{} receiving".format(spinner(ctx))
    progress_bar(s, 3, 28, 100, p, GREEN * 0.7, GREEN)
    s.text(105, 28, "{:5.1f}%".format(p * 100), WHITE, bold=True)
    s.text(3, 29, label, MUTED)
    hist = st.history(ctx.bi)[-2:]
    for i, (cb, text, kind, ind) in enumerate(hist):
        s.text(3, 30 + i, "chunk {:03d} ".format(len(st.history(ctx.bi)) - len(hist) + i), DIM)
        s.text(13, 30 + i, text, AMBER * 0.85)
    input_line(s, 60, 31, 56, st.current(ctx.bi), ctx, GREEN)
    if fast:
        s.post["flash"] = 0.25 * (1 - p)
    status_bar(s, ctx, GREEN)


# ------------------------------------------------------------------ crash
LAYOUTS = (
    ((0, 1, 60, 17), (60, 1, 60, 17), (0, 18, 60, 17), (60, 18, 60, 17)),
    ((0, 1, 70, 34), (70, 1, 50, 12), (70, 13, 50, 11), (70, 24, 50, 11)),
    ((0, 1, 120, 18), (0, 19, 40, 16), (40, 19, 40, 16), (80, 19, 40, 16)),
    ((50, 1, 70, 34), (0, 1, 50, 12), (0, 13, 50, 11), (0, 24, 50, 11)),
)
HEX_SRC = ("Funding for this program was made possible by viewers like you. The Corporation for Public "
           "Broadcasting and bi-annual financial support. This is PBS. ")
PANES = ("stderr", "dates", "search", "hexdump")
RED_STYLE = {"key": ("❯ ", WHITE, True), "line": ("✕ ", HOTRED, False), "fluff": ("  ", RED * 0.6, False)}


def pane_stderr(s, ctx, x, y, w, h):
    st = stream("fundingx2:0")
    log_panel(s, x, y, w, h - 2, st.history(ctx.bi), ctx, stamp=False, styles=RED_STYLE)
    input_line(s, x, y + h - 1, w, st.current(ctx.bi), ctx, HOTRED, prompt="✕ ", fg=mix(HOTRED, WHITE, 0.3))


def pane_dates(s, ctx, x, y, w, h):
    st = stream("fundingx2:1")
    hist = st.history(ctx.bi)
    rows = hist[-(h - 2):]
    for i, (cb, text, kind, ind) in enumerate(rows):
        yy = y + (h - 2 - len(rows)) + i
        if kind == "key":
            s.text(x, yy, text, WHITE, bold=True)
            continue
        d, _, rest = text.partition(" ")
        fresh = max(0.0, 1 - (ctx.b - cb) / 12)
        s.text(x, yy, "▪ " + d, mix(AMBER * 0.8, WHITE, fresh))
        s.text(x + 13, yy, rest, mix(HOTRED * 0.7, WHITE, fresh))
    input_line(s, x, y + h - 1, w, st.current(ctx.bi), ctx, AMBER, prompt="$ ")


def pane_search(s, ctx, x, y, w, h):
    st = stream("fundingx2:3")
    hist = st.history(ctx.bi)
    rows = hist[-(h - 3):]
    for i, (cb, text, kind, ind) in enumerate(rows):
        found = text.startswith("Found")
        s.text(x, y + i, ("✓ " if found else "✕ ") + text, GREEN if found else MUTED, bold=found, maxw=w)
    cur = st.current(ctx.bi)
    s.text(x, y + h - 2, spinner(ctx) + " ", CYAN)
    s.text(x + 2, y + h - 2, cur, CYAN, maxw=w - 2)
    sweep = int((ctx.b * 0.7) % w)
    s.text(x, y + h - 1, "".join("━" if abs(i - sweep) < 6 else "─" for i in range(w)),
           lambda i: CYAN if abs(i - sweep) < 6 else DIM)


def pane_hexdump(s, ctx, x, y, w, h):
    top = ctx.bi
    for r in range(h):
        row = top + r
        rng = np.random.default_rng(row)
        n = 8 if w < 60 else 16
        src = HEX_SRC[(row * n) % len(HEX_SRC):] + HEX_SRC
        real = rng.random() < 0.45
        data = [ord(c) if real else int(v) for c, v in zip(src[:n], rng.integers(0, 256, n))]
        s.text(x, y + r, "{:06x} ".format(row * n), DIM)
        hx = " ".join("{:02x}".format(v) for v in data)
        s.text(x + 7, y + r, hx, (HOTRED * 0.8) if real else (MUTED * 0.7))
        asc = "".join(chr(v) if 32 <= v < 127 else "·" for v in data)
        s.text(x + 8 + len(hx), y + r, "│" + asc + "│", WHITE if real else DIM, maxw=w - 8 - len(hx))


PANE_FN = {"stderr": pane_stderr, "dates": pane_dates, "search": pane_search, "hexdump": pane_hexdump}


def crash(s, ctx):
    s.clear(hexc_bg())
    lb = ctx.b - 3390
    k = int(lb // 64)
    layout = LAYOUTS[k % 4]
    hit = ctx.snare > 0.55
    rng = ctx.rng(21)
    panes = [(PANES[(i + k) % 4], rect) for i, rect in enumerate(layout)]
    collapse = tl.moment("crash_collapse", ctx.b)
    if collapse is not None:
        # Signature moment: everything else is gone, stderr has the whole screen.
        panes = [("stderr", (0, 1, 120, 34))]
    for name, rect in panes:
        x, y, w, h = rect
        main = name == "stderr"
        col = WHITE if hit else (HOTRED if main else DIM)
        s.box(x, y, w, h, col, title="{}:{}".format(PANES.index(name), name), title_fg=HOTRED if main else MUTED,
              style="heavy" if main else "round")
        PANE_FN[name](s, ctx, x + 2, y + 1, w - 4, h - 2)

    since_cut = lb - k * 64
    if since_cut < 6:
        s.post["flash"] = 0.35 * (1 - since_cut / 6)
        s.post["aberr"] = 6
    if hit:
        s.post["aberr"] = max(s.post["aberr"], 4)
        for _ in range(4):
            s.shift_row(int(rng.integers(1, 35)), int(rng.integers(-4, 5)))
    s.corrupt(rng, 0.004 + 0.01 * ctx.level, fg=HOTRED)

    # "| This is PBS!" — the key line lands; it takes the whole screen.
    if ctx.b >= 3877:
        m = big_text_mask("THIS IS PBS!", 11)
        hh, ww = m.shape
        s.fill(0, 13, 120, hh // 2 + 2, mix(BG, HOTRED, 0.2))
        rgb = np.broadcast_to(WHITE if (ctx.bi // 2) % 2 else HOTRED, (hh, ww, 3)).copy()
        s.halfblock(60 - ww // 2, 14, rgb, m)
        s.post["aberr"] = 5

    status_bar(s, ctx, HOTRED, alert=True, extra="segfault at 0x0179")
    # tmux status line.
    bar = mix(hexc_bg(), GREEN, 0.15)
    s.fill(0, 35, 120, 1, bar)
    tabs = "  ".join("{}:{}{}".format(i, n, "*" if n == "stderr" else "") for i, n in enumerate(PANES))
    s.text(0, 35, " [pbs] " + tabs, GREEN * 0.85, bar)
    right = ' "core.dump" 22-Oct-09 '
    s.text(120 - len(right), 35, right, GREEN * 0.6, bar)


def hexc_bg():
    return np.array([12, 7, 10], np.float32)
