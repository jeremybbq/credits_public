# 3:53-4:36 the final drop: a character tunnel carrying the last lyrics, then flashbacks, then CRT power-off.
import math

import numpy as np

import timeline as tl
from lyrics import stream
from scenes.common import (AMBER, BG, BLUE, CYAN, DIM, FG, GREEN, MUTED, ORANGE, PINK, RED, VIOLET, WHITE,
                           status_bar)
from scenes.forecast import bayer
from term import gradient, mix

HUES = [CYAN, BLUE, VIOLET, PINK, RED, ORANGE, AMBER, GREEN, CYAN]
LYRICS_END = 6030
FLASHBACKS = ((520, "forecast"), (1420, "title"), (2260, "funding"), (3250, "reboot"), (3560, "crash"),
              (4150, "ocean"), (5050, "network"), (900, "forecast"), (1600, "title"), (3700, "crash"))


def tunnel(s, ctx, y0=1, y1=35, boost=0.0, freeze=False):
    rows = y1 - y0
    H, W = rows * 4, s.cols * 2
    t = tl.beat_time(tl.MOMENTS["tunnel_freeze"][0]) if freeze else ctx.t
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    cx = W / 2 + 18 * math.sin(t * 0.45)
    cy = H / 2 + 8 * math.cos(t * 0.6)
    dx = X + 0.5 - cx
    dy = (Y + 0.5 - cy) * 0.94
    r = np.hypot(dx, dy) + 1e-3
    ang = np.arctan2(dy, dx)
    u = 280.0 / r + t * 2.4
    v = ang / (2 * math.pi) * 16 + t * 0.3 + 20.0 / r * math.sin(t * 0.7)
    check = 0.5 + 0.5 * np.sin(u * 2 * math.pi) * np.sin(v * 2 * math.pi)
    fade = np.clip((r - 8) / 60, 0, 1) ** 0.9
    val = np.clip(check * fade * (0.8 + 0.2 * ctx.kick + boost), 0, 1)
    dots = val > bayer(H, W) * 0.95 + 0.04
    cu = u[:H, :W].reshape(rows, 4, s.cols, 2).mean((1, 3))
    cv = val.reshape(rows, 4, s.cols, 2).mean((1, 3))
    hue = np.mod(cu * 0.03 + t * 0.06, 1.0)
    col = gradient(HUES, hue) * (0.3 + 0.55 * cv)[..., None]
    if freeze:
        col = np.broadcast_to(WHITE * 0.85, col.shape)
    s.braille(0, y0, dots, np.clip(col, 0, 255))


def _flashback(ctx):
    """During the outro, short cuts back to earlier scenes."""
    if ctx.b < LYRICS_END:
        return None
    lb = ctx.b - LYRICS_END
    period, length = (32, 8) if ctx.b < 6270 else (16, 6)
    if lb % period >= length:
        return None
    i = int(lb // period)
    beat, name = FLASHBACKS[i % len(FLASHBACKS)]
    return beat + (lb % period), name, i


def _mosaic(s, ctx, p):
    """Signature moment: four earlier scenes at once, one per quadrant."""
    from director import frame_at_beat
    picks = ((900, "forecast"), (2260, "funding"), (4150, "ocean"), (5050, "network"))
    lb = ctx.b - tl.MOMENTS["mosaic"][0]
    for q, (beat, name) in enumerate(picks):
        snap = frame_at_beat(beat + lb, ctx.audio, name)
        ys = slice(1, 18) if q < 2 else slice(18, 35)
        xs = slice(0, 60) if q % 2 == 0 else slice(60, 120)
        s.ch[ys, xs], s.fg[ys, xs], s.bg[ys, xs] = snap.ch[ys, xs], snap.fg[ys, xs] * 0.8, snap.bg[ys, xs]
    s.text(0, 17, "─" * 120, DIM)
    s.vline(60, 1, 34, DIM)
    s.put(60, 17, "┼", DIM)


def _spaced(word):
    return " ".join(word.upper())


def finale(s, ctx):
    from director import frame_at_beat
    s.clear(BG)
    b = ctx.b
    st0, st1 = stream("fdg_down:0"), stream("fdg_down:1")
    cur0, cur1 = st0.current(ctx.bi), st1.current(ctx.bi)

    mz = tl.moment("mosaic", b)
    if mz is not None:
        _mosaic(s, ctx, mz)
        status_bar(s, ctx, PINK, extra="replay")
        return

    vw = tl.moment("viewers", b)
    if vw is not None:
        # Signature moment: the tunnel is gone; only the last line of the song is left.
        s.clear((0, 0, 0))
        line1 = cur1 or (st1.history(ctx.bi)[-1][1] if st1.history(ctx.bi) else "")
        s.ctext(16, cur0, DIM)
        s.ctext(18, line1, WHITE, bold=True)
        status_bar(s, ctx, PINK)
        return

    fb = _flashback(ctx)
    if fb:
        beat, name, i = fb
        snap = frame_at_beat(beat, ctx.audio, name)
        s.paste(snap)
        tint = HUES[i % len(HUES)]
        s.fg[:] = s.fg * 0.75 + tint * 0.25 * (s.fg.max(-1, keepdims=True) / 255)
        s.post["aberr"] = 3
        s.fill(0, 0, 120, 1, BG)
        s.text(1, 0, "▶ replay {:02d}:{:05.2f}".format(int(tl.beat_time(beat) // 60), tl.beat_time(beat) % 60), tint)
        return

    freeze = tl.moment("tunnel_freeze", b) is not None
    tunnel(s, ctx, boost=0.15 if b >= 6270 else 0.0, freeze=freeze)

    if 5788 <= b < LYRICS_END:
        # A quiet band: the current word letter-spaced, the line under it.
        s.fill(0, 13, 120, 9, BG)
        s.text(0, 13, "─" * 120, DIM * 0.7)
        s.text(0, 21, "─" * 120, DIM * 0.7)
        words = cur0.split()
        if words:
            w = words[-1].strip(".,") or words[-1]
            s.ctext(15, _spaced(w)[:100], WHITE, bold=True)
        s.ctext(17, cur0, FG)
        if cur1:
            s.ctext(19, cur1, PINK * 0.85)

    if b >= 6270:
        s.post["aberr"] = 1 + 2 * ctx.kick
    status_bar(s, ctx, PINK)


def poweroff(s, ctx):
    t0 = tl.beat_time(6508)
    dt = ctx.t - t0
    s.clear((0, 0, 0))
    mid = s.rows // 2
    if dt < 0.22:
        from director import frame_at_beat
        snap = frame_at_beat(6507.5, ctx.audio, "finale")
        p = dt / 0.22
        hh = max(1, int(s.rows * (1 - p) ** 2))
        for i in range(hh):
            src = int(i / hh * s.rows)
            y = mid - hh // 2 + i
            s.ch[y], s.fg[y] = snap.ch[src], mix(snap.fg[src], np.float32(255), p)
            s.bg[y] = mix(snap.bg[src], np.float32(60), p)
        s.post["glow"] = 1.5
        return
    if dt < 0.5:
        p = (dt - 0.22) / 0.28
        w = int(120 * (1 - p) ** 1.5)
        s.text(60 - w // 2, mid, "━" * w, WHITE, bold=True)
        s.post["glow"] = 2.5
        return
    if dt < 1.7:
        k = 1 - (dt - 0.5) / 1.2
        s.put(60, mid, "•", WHITE * k, bold=True)
        s.post["glow"] = 2.0
        return
    if dt > 1.9:
        msg = "end of transmission"
        n = int((dt - 1.9) * 24)
        s.ctext(mid - 1, msg[:n], MUTED)
        if dt > 2.4:
            s.ctext(mid + 1, "original animation · plaaosert      music · Frums — Credits EX", DIM)
