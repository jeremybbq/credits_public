# Shared scene context, palette and UI chrome (status line, log panels).
import datetime

import numpy as np

import timeline as tl
from term import SPINNER, gradient, hexc, mix

# Palette (night-terminal base + per-section accents).
BG = hexc("0a0b12")
PANEL = hexc("12141f")
FG = hexc("c8d0f0")
DIM = hexc("5a628c")
MUTED = hexc("7a83ad")
BLUE = hexc("7aa2f7")
CYAN = hexc("7dcfff")
GREEN = hexc("9ece6a")
AMBER = hexc("e0af68")
ORANGE = hexc("ff9e64")
RED = hexc("f7768e")
HOTRED = hexc("ff4d6d")
VIOLET = hexc("bb9af7")
PINK = hexc("ff79c6")
CORAL = hexc("ff8f8f")
WHITE = hexc("f4f6ff")
BLACK = hexc("000000")

ACCENT = {
    "boot": GREEN, "forecast": BLUE, "title": ORANGE, "funding": AMBER, "melt": MUTED,
    "reboot": GREEN, "crash": HOTRED, "ocean": CYAN, "network": VIOLET, "finale": PINK, "poweroff": WHITE,
}
LABEL = {
    "boot": "boot", "forecast": "nws.forecast", "title": "credits", "funding": "pledge.drive",
    "melt": "carrier.lost", "reboot": "rx.reboot", "crash": "core.dump", "ocean": "obs.logan",
    "network": "uplink.search", "finale": "viewers.like.you", "poweroff": "eot",
}


class Ctx:
    def __init__(self, t, audio, b=None):
        self.t = t
        self.b = tl.time_beat(t) if b is None else b
        self.bi = int(np.floor(self.b))
        self.frac = self.b - self.bi
        self.audio = audio
        self.s0, self.sec = tl.section_at(self.bi)
        self.lb = self.b - self.s0

    def at_beat(self, b):
        """Context for another beat (used for snapshots / flashbacks). Audio is read at that time."""
        return Ctx(tl.beat_time(b), self.audio, b)

    def rng(self, salt=0, step=1):
        return np.random.default_rng((self.bi // step + 10000) * 7919 + salt * 104729 + 17)

    def since(self, beat):
        return self.b - beat

    @property
    def kick(self):
        return self.audio.kick(self.t)

    @property
    def snare(self):
        return self.audio.snare(self.t)

    @property
    def level(self):
        return self.audio.level(self.t)

    def bands(self):
        return self.audio.bands(self.t)


def pulse(ctx, every=8, decay=3.0):
    """1 on each quarter-note hit (every N steps, on the song's measured phase), decaying over `decay` steps."""
    ph = (ctx.b - tl.BEAT_PHASE) % every
    return max(0.0, 1 - ph / decay)


def broadcast_date(beat, start_beat, start=datetime.date(2009, 10, 22)):
    """One day per 64 steps, like the original's date ticker."""
    return start + datetime.timedelta(days=max(0, int((beat - start_beat) // 64)))


def clock(beat):
    """Broadcast wall-clock: 7:21:00 PM plus song time."""
    secs = int(max(tl.beat_time(beat), 0))
    t0 = 19 * 3600 + 21 * 60
    s = t0 + secs
    return "{:02}:{:02}:{:02}".format(s // 3600 % 24, s // 60 % 60, s % 60)


def status_bar(s, ctx, accent, label=None, extra=None, alert=False):
    """One quiet line: recording dot, section name, song time."""
    y = 0
    s.fill(0, y, s.cols, 1, s.base_bg)
    on = alert or (ctx.b - tl.BEAT_PHASE) % 16 < 8
    s.put(1, y, "●" if on else "○", HOTRED if alert else accent * 0.8)
    name = label or LABEL.get(ctx.sec, ctx.sec)
    s.text(3, y, name, accent * 0.9)
    if extra:
        s.text(4 + len(name), y, "· " + extra, MUTED)
    t = max(ctx.t, 0)
    right = "{:02}:{:05.2f}".format(int(t // 60), t % 60)
    s.text(s.cols - len(right) - 1, y, right, MUTED)


def wrap(lines, width):
    out = []
    for ln in lines:
        if not ln:
            out.append("")
        while len(ln) > width:
            out.append(ln[:width])
            ln = ln[width:]
        if ln:
            out.append(ln)
    return out


def typed_lines(s, x, y, lines, width, fg, accent, ctx, cursor=True, max_rows=None, typing=True):
    """Draw char-typewriter lines; the most recent characters glow in the accent colour."""
    rows = wrap(lines, width)
    if max_rows and len(rows) > max_rows:
        rows = rows[-max_rows:]
    for i, ln in enumerate(rows):
        last = i == len(rows) - 1
        if last and typing:
            n = len(ln)
            s.text(x, y + i, ln, lambda j: mix(fg, accent, 1 - (n - j) / 7) if n - j <= 7 else fg)
        else:
            s.text(x, y + i, ln, fg)
    if cursor:
        cy = y + max(len(rows) - 1, 0)
        cx = x + (len(rows[-1]) if rows else 0)
        if typing or (ctx.bi // 6) % 2 == 0:
            s.put(cx, cy, "▌", accent)
    return len(rows)


KIND_STYLE = {
    "key": ("❯ ", GREEN, True),
    "line": ("• ", AMBER, False),
    "fluff": ("  ", DIM, False),
}


def log_panel(s, x, y, w, h, history, ctx, stamp=True, styles=None, fade=True, colour_override=None):
    """Bottom-aligned log of committed lyric lines: newest at the bottom, older ones fade."""
    styles = styles or KIND_STYLE
    rows = history[-h:]
    off = h - len(rows)
    for i, (cb, text, kind, indent) in enumerate(rows):
        yy = y + off + i
        pre, col, bold = styles.get(kind, styles["line"])
        if colour_override is not None:
            col = colour_override
        age = len(rows) - 1 - i
        k = 1.0 if not fade else max(0.25, 1 - age / (h * 1.1))
        fresh = max(0.0, 1 - (ctx.b - cb) / 10)
        if fresh > 0:
            s.fill(x, yy, w, 1, mix(s.base_bg, col, 0.18 * fresh))
        xx = x
        if stamp:
            s.text(xx, yy, clock(cb), DIM * k)
            xx += 9
        line = pre + " " * min(indent, 30) + text
        c = mix(col * k, WHITE, fresh * 0.8)
        s.text(xx, yy, line, c, bold=bold, maxw=w - (xx - x))


def input_line(s, x, y, w, text, ctx, accent, prompt="❯ ", fg=FG):
    s.text(x, y, prompt, accent, bold=True)
    room = w - len(prompt) - 1
    shown = text[-room:] if len(text) > room else text
    s.text(x + len(prompt), y, shown, fg)
    if (ctx.bi // 4) % 2 == 0 or text:
        s.put(x + len(prompt) + len(shown), y, "▌", accent)


def spinner(ctx, speed=2):
    return SPINNER[(ctx.bi // speed) % len(SPINNER)]


def progress_bar(s, x, y, w, p, c0, c1, empty=DIM, head=True):
    p = float(np.clip(p, 0, 1))
    n = p * w
    full = int(n)
    for i in range(w):
        if i < full:
            s.put(x + i, y, "━", gradient([c0, c1], i / max(w - 1, 1)))
        elif i == full and head and p < 1:
            s.put(x + i, y, "╸", c1)
        else:
            s.put(x + i, y, "━", empty * 0.6)
