# A truecolor character-cell screen plus the drawing tools every scene uses.
# The screen is plain arrays (glyph index, fg RGB, bg RGB per cell), so it can be rasterised to video
# (raster.py) or printed to a real terminal as ANSI (play.py).
import colorsys

import numpy as np

COLS, ROWS = 120, 36

# ---------------------------------------------------------------- glyph table
# Cells store an index into GLYPHS. Index 0 is a blank space. Bold variants get their own index.
GLYPHS = [(" ", False)]
_INDEX = {(" ", False): 0}


def gid(ch, bold=False):
    key = (ch, bold)
    i = _INDEX.get(key)
    if i is None:
        i = len(GLYPHS)
        GLYPHS.append(key)
        _INDEX[key] = i
    return i


BRAILLE = np.array([gid(chr(0x2800 + i)) for i in range(256)], np.int32)
BRAILLE[0] = 0
RAMP = " .,:;-=+*#%@"
RAMP_IDX = np.array([gid(c) for c in RAMP], np.int32)
BARS = " ▁▂▃▄▅▆▇█"
UPPER = gid("▀")
FULL = gid("█")
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


# ---------------------------------------------------------------- colour helpers
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def mix(a, b, t):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    return a + (b - a) * np.clip(t, 0, 1)


def hsv(h, s, v):
    return np.array(colorsys.hsv_to_rgb(h % 1.0, s, v), np.float32) * 255


def hsv_arr(h, s, v):
    """Vectorised HSV → RGB (arrays broadcast), output 0-255."""
    h = np.mod(h, 1.0) * 6
    s, v = np.broadcast_arrays(np.asarray(s, np.float32), np.asarray(v, np.float32))
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1).astype(np.float32) * 255


def gradient(stops, t):
    """Sample a list of colours at t in [0, 1] (scalar or array)."""
    stops = np.asarray(stops, np.float32)
    t = np.clip(np.asarray(t, np.float32), 0, 1) * (len(stops) - 1)
    i = np.minimum(np.floor(t).astype(int), len(stops) - 2)
    f = (t - i)[..., None]
    return stops[i] * (1 - f) + stops[i + 1] * f


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- screen
class Screen:
    def __init__(self, cols=COLS, rows=ROWS, bg=(8, 9, 14)):
        self.cols, self.rows = cols, rows
        self.ch = np.zeros((rows, cols), np.int32)
        self.fg = np.zeros((rows, cols, 3), np.float32)
        self.bg = np.empty((rows, cols, 3), np.float32)
        self.bg[:] = bg
        self.base_bg = np.asarray(bg, np.float32)
        # Post effects read by the rasteriser: chromatic offset (px), white flash, glow boost, shake.
        self.post = {"aberr": 0.0, "flash": 0.0, "glow": 1.0, "shake": (0, 0), "bright": 1.0}

    def copy(self):
        s = Screen(self.cols, self.rows, self.base_bg)
        s.ch[:], s.fg[:], s.bg[:] = self.ch, self.fg, self.bg
        s.post = dict(self.post)
        return s

    def paste(self, other):
        self.ch[:], self.fg[:], self.bg[:] = other.ch, other.fg, other.bg

    def clear(self, bg=None):
        self.ch[:] = 0
        self.fg[:] = 0
        if bg is not None:
            self.base_bg = np.asarray(bg, np.float32)
        self.bg[:] = self.base_bg

    # -- primitives ------------------------------------------------------------
    def put(self, x, y, c, fg, bg=None, bold=False):
        x, y = int(x), int(y)
        if 0 <= x < self.cols and 0 <= y < self.rows:
            self.ch[y, x] = gid(c, bold)
            self.fg[y, x] = fg
            if bg is not None:
                self.bg[y, x] = bg

    def text(self, x, y, s, fg, bg=None, bold=False, maxw=None):
        """fg may be a colour or a function(i) -> colour for per-character gradients."""
        x, y = int(x), int(y)
        if not 0 <= y < self.rows:
            return
        if maxw is not None:
            s = s[:maxw]
        call = callable(fg)
        for i, c in enumerate(s):
            xx = x + i
            if 0 <= xx < self.cols:
                self.ch[y, xx] = 0 if c == " " else gid(c, bold)
                self.fg[y, xx] = fg(i) if call else fg
                if bg is not None:
                    self.bg[y, xx] = bg

    def ctext(self, y, s, fg, bg=None, bold=False, cx=None):
        cx = self.cols // 2 if cx is None else cx
        self.text(cx - len(s) // 2, y, s, fg, bg, bold)

    def fill(self, x, y, w, h, bg=None, c=" ", fg=(0, 0, 0)):
        x0, y0, x1, y1 = max(int(x), 0), max(int(y), 0), min(int(x + w), self.cols), min(int(y + h), self.rows)
        if x1 <= x0 or y1 <= y0:
            return
        self.ch[y0:y1, x0:x1] = gid(c) if c != " " else 0
        self.fg[y0:y1, x0:x1] = fg
        if bg is not None:
            self.bg[y0:y1, x0:x1] = bg

    def hline(self, x, y, w, fg, c="─"):
        self.text(x, y, c * int(w), fg)

    def vline(self, x, y, h, fg, c="│"):
        for i in range(int(h)):
            self.put(x, y + i, c, fg)

    def box(self, x, y, w, h, fg, title=None, title_fg=None, bg=None, style="round", tag=None, tag_fg=None):
        x, y, w, h = int(x), int(y), int(w), int(h)
        if w < 2 or h < 2:
            return
        tl, tr, bl, br, hz, vt = {
            "round": "╭╮╰╯─│", "square": "┌┐└┘─│", "heavy": "┏┓┗┛━┃", "double": "╔╗╚╝═║",
        }[style]
        if bg is not None:
            self.fill(x + 1, y + 1, w - 2, h - 2, bg)
        self.text(x, y, tl + hz * (w - 2) + tr, fg)
        self.text(x, y + h - 1, bl + hz * (w - 2) + br, fg)
        for i in range(1, h - 1):
            self.put(x, y + i, vt, fg)
            self.put(x + w - 1, y + i, vt, fg)
        if title:
            self.text(x + 2, y, " " + title + " ", title_fg if title_fg is not None else fg, bold=True)
        if tag:
            self.text(x + w - 3 - len(tag), y, " " + tag + " ", tag_fg if tag_fg is not None else fg)

    def blit(self, x, y, ch, fg, bg=None, mask=None):
        """Write arrays of glyph ids / colours at (x, y), clipped. mask selects which cells to write."""
        h, w = ch.shape
        x, y = int(x), int(y)
        sx0, sy0 = max(0, -x), max(0, -y)
        x0, y0 = x + sx0, y + sy0
        x1, y1 = min(x + w, self.cols), min(y + h, self.rows)
        if x1 <= x0 or y1 <= y0:
            return
        sl = (slice(y0, y1), slice(x0, x1))
        src = (slice(sy0, sy0 + y1 - y0), slice(sx0, sx0 + x1 - x0))
        m = np.ones((y1 - y0, x1 - x0), bool) if mask is None else mask[src]
        fg = np.broadcast_to(np.asarray(fg, np.float32), (h, w, 3))
        self.ch[sl][m] = ch[src][m]
        self.fg[sl][m] = fg[src][m]
        if bg is not None:
            bg = np.broadcast_to(np.asarray(bg, np.float32), (h, w, 3))
            self.bg[sl][m] = bg[src][m]

    # -- sub-cell canvases -----------------------------------------------------
    def braille(self, x, y, dots, fg, only_set=True):
        """dots: bool array (h*4, w*2). fg: colour or (h, w, 3) per-cell colours."""
        H, W = dots.shape
        h, w = H // 4, W // 2
        d = dots[:h * 4, :w * 2].reshape(h, 4, w, 2)
        bits = (d[:, 0, :, 0] * 1 + d[:, 1, :, 0] * 2 + d[:, 2, :, 0] * 4 + d[:, 0, :, 1] * 8 +
                d[:, 1, :, 1] * 16 + d[:, 2, :, 1] * 32 + d[:, 3, :, 0] * 64 + d[:, 3, :, 1] * 128)
        self.blit(x, y, BRAILLE[bits], fg, mask=(bits > 0) if only_set else None)

    def halfblock(self, x, y, rgb, alpha=None):
        """rgb: (h*2, w, 3) pixel colours; alpha: (h*2, w) bool of which pixels are drawn."""
        H, W = rgb.shape[:2]
        h = H // 2
        top, bot = rgb[0:h * 2:2], rgb[1:h * 2:2]
        if alpha is None:
            self.blit(x, y, np.full((h, W), UPPER, np.int32), top, bot)
            return
        at, ab = alpha[0:h * 2:2], alpha[1:h * 2:2]
        # Cells with both halves on: ▀ with fg=top, bg=bottom. Only one half: ▀ or ▄ on the existing bg.
        both = at & ab
        self.blit(x, y, np.full((h, W), UPPER, np.int32), top, bot, mask=both)
        self.blit(x, y, np.full((h, W), UPPER, np.int32), top, mask=at & ~ab)
        self.blit(x, y, np.full((h, W), gid("▄"), np.int32), bot, mask=ab & ~at)

    def shade(self, x, y, value, fg, bg=None, ramp=RAMP_IDX, mask=None):
        """Draw a 0-1 value field with a character density ramp."""
        idx = ramp[np.clip((np.asarray(value) * (len(ramp) - 1) + 0.5).astype(int), 0, len(ramp) - 1)]
        self.blit(x, y, idx, fg, bg, mask=mask if mask is not None else idx > 0)

    # -- effects ---------------------------------------------------------------
    def shift_row(self, y, dx):
        if 0 <= y < self.rows and dx:
            for a in (self.ch, self.fg, self.bg):
                a[y] = np.roll(a[y], dx, axis=0)

    def corrupt(self, rng, amount, chars="▓▒░#%&$?/\\|<>~", fg=None):
        n = int(self.cols * self.rows * amount)
        if n <= 0:
            return
        ys = rng.integers(0, self.rows, n)
        xs = rng.integers(0, self.cols, n)
        ids = np.array([gid(c) for c in chars])[rng.integers(0, len(chars), n)]
        self.ch[ys, xs] = ids
        if fg is not None:
            self.fg[ys, xs] = fg

    def dim(self, k):
        self.fg *= k
        self.bg[:] = self.base_bg + (self.bg - self.base_bg) * k


# ---------------------------------------------------------------- bitmap text (for big half-block words)
_big_cache = {}


def big_text_mask(s, px=14, weight="ExtraBold"):
    """Render s with a bold font into a boolean pixel mask (for halfblock big lettering)."""
    key = (s, px, weight)
    if key in _big_cache:
        return _big_cache[key]
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-{}.ttf".format(weight), px)
    l, t, r, b = font.getbbox(s)
    img = Image.new("L", (r - l + 2, b - t + 2), 0)
    ImageDraw.Draw(img).text((1 - l, 1 - t), s, font=font, fill=255)
    m = np.asarray(img) > 110
    if m.shape[0] % 2:
        m = np.vstack([m, np.zeros((1, m.shape[1]), bool)])
    _big_cache[key] = m
    return m


def to_ansi(screen, prev=None):
    """Truecolor ANSI string for a real terminal. With prev, only changed cells are emitted."""
    out = []
    ch, fg, bg = screen.ch, screen.fg.astype(np.uint8), screen.bg.astype(np.uint8)
    if prev is not None:
        changed = (ch != prev.ch) | (fg != prev.fg.astype(np.uint8)).any(-1) | (bg != prev.bg.astype(np.uint8)).any(-1)
    last = None
    for y in range(screen.rows):
        if prev is not None and not changed[y].any():
            continue
        out.append("\033[{};1H".format(y + 1))
        last = None
        for x in range(screen.cols):
            g = GLYPHS[ch[y, x]]
            key = (tuple(fg[y, x]), tuple(bg[y, x]), g[1])
            if key != last:
                out.append("\033[{};38;2;{};{};{};48;2;{};{};{}m".format(
                    1 if g[1] else 22, *key[0], *key[1]))
                last = key
            out.append(g[0])
    return "".join(out)
