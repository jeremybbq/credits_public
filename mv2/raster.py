# Turns a term.Screen into a 1920x1080 RGB frame: glyph atlas compositing in numpy + a light CRT pass.
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from term import GLYPHS

CW, CH = 16, 30
FONT_DIR = "/usr/share/fonts/truetype/"
_fonts = {}


def _font(bold, fallback=False):
    key = (bold, fallback)
    if key not in _fonts:
        if fallback:
            path = FONT_DIR + ("dejavu/DejaVuSansMono-Bold.ttf" if bold else "dejavu/DejaVuSansMono.ttf")
        else:
            path = FONT_DIR + "jetbrains-mono/JetBrainsMono-{}.ttf".format("ExtraBold" if bold else "Medium")
        _fonts[key] = ImageFont.truetype(path, 25)
    return _fonts[key]


def _aa_canvas(scale=4):
    return np.zeros((CH * scale, CW * scale), np.float32), scale


def _downsample(a, s):
    return a.reshape(CH, s, CW, s).mean((1, 3))


# Box drawing: (up, down, left, right) with 1 = light, 2 = heavy, 3 = double.
BOX = {
    "─": (0, 0, 1, 1), "│": (1, 1, 0, 0), "┌": (0, 1, 0, 1), "┐": (0, 1, 1, 0), "└": (1, 0, 0, 1),
    "┘": (1, 0, 1, 0), "├": (1, 1, 0, 1), "┤": (1, 1, 1, 0), "┬": (0, 1, 1, 1), "┴": (1, 0, 1, 1),
    "┼": (1, 1, 1, 1), "━": (0, 0, 2, 2), "┃": (2, 2, 0, 0), "┏": (0, 2, 0, 2), "┓": (0, 2, 2, 0),
    "┗": (2, 0, 0, 2), "┛": (2, 0, 2, 0), "┣": (2, 2, 0, 2), "┫": (2, 2, 2, 0), "┳": (0, 2, 2, 2),
    "┻": (2, 0, 2, 2), "╋": (2, 2, 2, 2), "═": (0, 0, 3, 3), "║": (3, 3, 0, 0), "╔": (0, 3, 0, 3),
    "╗": (0, 3, 3, 0), "╚": (3, 0, 0, 3), "╝": (3, 0, 3, 0), "╴": (0, 0, 1, 0), "╶": (0, 0, 0, 1),
    "╵": (1, 0, 0, 0), "╷": (0, 1, 0, 0), "╸": (0, 0, 2, 0), "╺": (0, 0, 0, 2),
}
ROUND = {"╭": (0, 1, 0, 1), "╮": (0, 1, 1, 0), "╯": (1, 0, 1, 0), "╰": (1, 0, 0, 1)}


def _box_glyph(arms, rounded=False):
    s = 4
    a, _ = _aa_canvas(s)
    H, W = CH * s, CW * s
    cx, cy = W // 2, H // 2
    up, down, left, right = arms
    th = {1: 2 * s, 2: 4 * s}

    def seg(kind, x0, y0, x1, y1):
        if kind == 3:
            for o in (-3 * s, 3 * s):
                if x0 == x1:
                    a[y0:y1, x0 + o - s:x0 + o + s] = 1
                else:
                    a[y0 + o - s:y0 + o + s, x0:x1] = 1
            return
        t = th[kind] // 2
        if x0 == x1:
            a[y0:y1, x0 - t:x0 + t] = 1
        else:
            a[y0 - t:y0 + t, x0:x1] = 1

    if rounded:
        r = 7 * s
        t = s
        yy, xx = np.mgrid[0:H, 0:W]
        # Corner centre sits r away from the cell centre, towards the open side.
        ox = cx + (r if right else -r)
        oy = cy + (r if down else -r)
        d = np.hypot(xx - ox, yy - oy)
        quad = ((xx - ox) * (1 if right else -1) <= 0) & ((yy - oy) * (1 if down else -1) <= 0)
        a[(np.abs(d - r) <= t) & quad] = 1
        if down:
            a[oy:H, cx - t:cx + t] = 1
        if up:
            a[0:oy, cx - t:cx + t] = 1
        if right:
            a[cy - t:cy + t, ox:W] = 1
        if left:
            a[cy - t:cy + t, 0:ox] = 1
        return _downsample(a, s)

    ext = {1: th[1] // 2, 2: th[2] // 2, 3: 4 * s, 0: 0}
    reach = max(ext[left], ext[right], ext[up], ext[down])
    if up:
        seg(up, cx, 0, cx, cy + reach)
    if down:
        seg(down, cx, cy - reach, cx, H)
    if left:
        seg(left, 0, cy, cx + reach, cy)
    if right:
        seg(right, cx - reach, cy, W, cy)
    return _downsample(a, s)


def _braille_glyph(code):
    s = 4
    a, _ = _aa_canvas(s)
    yy, xx = np.mgrid[0:CH * s, 0:CW * s]
    bits = code - 0x2800
    order = ((0, 0, 1), (0, 1, 2), (0, 2, 4), (1, 0, 8), (1, 1, 16), (1, 2, 32), (0, 3, 64), (1, 3, 128))
    for col, row, bit in order:
        if bits & bit:
            px = (4.5 + col * 7) * s
            py = (4.0 + row * 7.3) * s
            a[np.hypot(xx - px, yy - py) <= 2.4 * s] = 1
    return _downsample(a, s)


def _block_glyph(c):
    a = np.zeros((CH, CW), np.float32)
    eighths_low = " ▁▂▃▄▅▆▇█"
    eighths_left = " ▏▎▍▌▋▊▉█"
    if c in eighths_low:
        n = eighths_low.index(c)
        a[CH - round(CH * n / 8):, :] = 1
    elif c in eighths_left:
        n = eighths_left.index(c)
        a[:, :round(CW * n / 8)] = 1
    elif c == "▀":
        a[:CH // 2] = 1
    elif c == "▐":
        a[:, CW // 2:] = 1
    elif c == "▔":
        a[:CH // 8] = 1
    elif c == "▕":
        a[:, CW - CW // 8:] = 1
    elif c in "░▒▓":
        a[:] = {"░": 0.22, "▒": 0.45, "▓": 0.7}[c]
    else:
        q = {"▖": (0, 0, 1, 0), "▗": (0, 0, 0, 1), "▘": (1, 0, 0, 0), "▝": (0, 1, 0, 0),
             "▙": (1, 0, 1, 1), "▚": (1, 0, 0, 1), "▛": (1, 1, 1, 0), "▜": (1, 1, 0, 1),
             "▞": (0, 1, 1, 0), "▟": (0, 1, 1, 1)}.get(c)
        if q is None:
            return None
        h, w = CH // 2, CW // 2
        if q[0]: a[:h, :w] = 1
        if q[1]: a[:h, w:] = 1
        if q[2]: a[h:, :w] = 1
        if q[3]: a[h:, w:] = 1
    return a


_notdef = {}


def _font_glyph(c, bold):
    for fb in (False, True):
        f = _font(bold, fb)
        if fb not in _notdef:
            _notdef[fb] = np.asarray(f.getmask("\U000F0000")).tobytes()
        m = f.getmask(c)
        if np.asarray(m).tobytes() == _notdef[fb] and fb is False:
            continue
        img = Image.new("L", (CW * 2, CH), 0)
        d = ImageDraw.Draw(img)
        d.text((CW, 22), c, font=f, fill=255, anchor="ms")
        a = np.asarray(img, np.float32)[:, CW // 2:CW // 2 + CW] / 255.0
        return a
    return np.zeros((CH, CW), np.float32)


def glyph_mask(c, bold):
    if c == " ":
        return np.zeros((CH, CW), np.float32)
    o = ord(c)
    if 0x2800 <= o <= 0x28FF:
        return _braille_glyph(o)
    if c in BOX:
        arms = BOX[c]
        if bold:
            arms = tuple(2 if v == 1 else v for v in arms)
        return _box_glyph(arms)
    if c in ROUND:
        return _box_glyph(ROUND[c], rounded=True)
    if 0x2580 <= o <= 0x259F:
        b = _block_glyph(c)
        if b is not None:
            return b
    return _font_glyph(c, bold)


class Atlas:
    def __init__(self):
        self.masks = np.zeros((0, CH, CW), np.float32)

    def sync(self):
        n = len(GLYPHS)
        if n > len(self.masks):
            new = [glyph_mask(c, b) for c, b in GLYPHS[len(self.masks):n]]
            self.masks = np.concatenate([self.masks, np.stack(new)])
        return self.masks


_atlas = Atlas()


_vignette = None


def _crt_mask(W, H):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = 1 - 0.28 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.5
    scan = 1 - 0.07 * ((np.arange(H) % 3) == 2)
    m = np.clip(v, 0, 1) * scan[:, None] * 255
    return Image.fromarray(np.repeat(m[..., None], 3, -1).astype(np.uint8))


def rasterise(screen, crt=True):
    global _vignette
    masks = _atlas.sync()
    R, C = screen.ch.shape
    out = np.empty((R, C, CH, CW, 3), np.float32)
    out[:] = screen.bg[:, :, None, None, :]
    nz = screen.ch != 0
    if nz.any():
        A = masks[screen.ch[nz]][..., None]
        bg = screen.bg[nz][:, None, None, :]
        fg = screen.fg[nz][:, None, None, :]
        out[nz] = bg + (fg - bg) * A
    p = screen.post
    if p.get("bright", 1.0) != 1.0:
        out *= p["bright"]
    fl = p.get("flash", 0.0)
    if fl > 0:
        out += (255 - out) * min(fl, 1.0)
    img = np.clip(out, 0, 255).astype(np.uint8).transpose(0, 2, 1, 3, 4).reshape(R * CH, C * CW, 3)

    dx, dy = p.get("shake", (0, 0))
    if dx or dy:
        img = np.roll(img, (int(dy), int(dx)), axis=(0, 1))
    ab = int(p.get("aberr", 0))
    if ab:
        img = img.copy()
        img[:, :, 0] = np.roll(img[:, :, 0], ab, axis=1)
        img[:, :, 2] = np.roll(img[:, :, 2], -ab, axis=1)
    if not crt:
        return np.ascontiguousarray(img)

    H, W = img.shape[:2]
    im = Image.fromarray(np.ascontiguousarray(img))
    # Light glow: blurred quarter-size copy, screen-blended back on top.
    small = im.reduce(4).point(lambda v: max(v - 30, 0) * 0.42 * p.get("glow", 1.0))
    small = small.filter(ImageFilter.BoxBlur(4)).filter(ImageFilter.BoxBlur(4))
    im = ImageChops.screen(im, small.resize((W, H), Image.BILINEAR))
    # Faint scanlines + vignette.
    if _vignette is None or _vignette.size != (W, H):
        _vignette = _crt_mask(W, H)
    im = ImageChops.multiply(im, _vignette)
    return np.asarray(im)
