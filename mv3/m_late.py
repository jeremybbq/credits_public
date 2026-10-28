# 8 Water · 9 Orbit · 10 Light · 11 Settle
import math

import numpy as np

from core import BAYER, DH, DT, DW, cell_mean, dots_layers, gradient, hexc, splat
from term import gid
from world import Material, material

RIPPLE = hexc("6fc3df")
CREST = hexc("d8f3ff")
DEEPWATER = hexc("0a1a2a")
BODY = hexc("e9e4ff")
TRAIL = hexc("6f5fbf")
SAND = hexc("c9a46c")
SAND_DEEP = hexc("5e4628")
TEXT = hexc("d8dbe6")
WHITE = hexc("ffffff")
# The world so far, as bands of colour on one object.
BANDS = [hexc("c9a46c"), hexc("ff7a1a"), hexc("7fbf8e"), hexc("8d97a8"), hexc("bfe8ff"), hexc("ff8a7a"),
         hexc("6fc3df"), hexc("b4a8ff")]
RAMP = np.array([gid(c) for c in ".,-~:;=!*#$@"], np.int32)
CX, CY = DW / 2, DH / 2


# ------------------------------------------------------------------ 8 · water
@material("water")
class Water(Material):
    """A wave simulation: every syllable of the observations is a drop; rings spread and interfere."""

    def __init__(self, prev, ctx):
        self.u = np.zeros((DH, DW), np.float32)
        self.up = np.zeros((DH, DW), np.float32)
        self.rng = np.random.default_rng(3896)
        yy, xx = np.mgrid[0:DH, 0:DW].astype(np.float32)
        self.yy, self.xx = yy, xx
        live = getattr(prev, "live", None)
        if live is not None and live.any():
            ys, xs = np.nonzero(live)
            self.drop(xs.mean(), ys.mean(), 3.0)
        else:
            self.drop(CX, CY, 3.0)
        self.frames = 0
        self.flash = 0.0
        self.crests = None

    def drop(self, x, y, a, sigma=1.6):
        x0, x1 = int(max(x - 8, 0)), int(min(x + 9, DW))
        y0, y1 = int(max(y - 8, 0)), int(min(y + 9, DH))
        g = np.exp(-((self.xx[y0:y1, x0:x1] - x) ** 2 + (self.yy[y0:y1, x0:x1] - y) ** 2) / (2 * sigma * sigma))
        self.u[y0:y1, x0:x1] -= a * g

    def step(self, ctx):
        b = ctx.b
        self.flash *= 0.8
        if b >= 4401:
            # The surface flickers and freezes; the brightest crests stay as points.
            if self.crests is None:
                v = self.u
                peak = (v > 0.12) & (v >= np.roll(v, 1, 0)) & (v >= np.roll(v, -1, 0)) & (v >= np.roll(v, 1, 1)) & \
                    (v >= np.roll(v, -1, 1))
                ys, xs = np.nonzero(peak)
                order = np.argsort(-v[ys, xs])[:36]
                self.crests = (xs[order].astype(float), ys[order].astype(float))
            return
        for _, _, _, c, word in ctx.voice(("ocean_c:1",), ("char",)):
            if word:
                self.drop(self.rng.uniform(20, DW - 20), self.rng.uniform(14, DH - 14), 1.4)
        if b >= 4186 and self.rng.random() < 0.06:
            self.drop(self.rng.uniform(5, DW - 5), self.rng.uniform(5, DH - 5), 0.35, 1.0)
        if ctx.crossed(3963):
            self.drop(CX, CY, 4.5, 3.0)
            self.flash = 0.18
        for _ in range(2):
            lap = np.roll(self.u, 1, 0) + np.roll(self.u, -1, 0) + np.roll(self.u, 1, 1) + np.roll(self.u, -1, 1) - 4 * self.u
            un = (2 * self.u - self.up + 0.22 * lap) * 0.989
            self.up, self.u = self.u, un.astype(np.float32)
        self.frames += 1
        if self.frames % 10 == 0:  # "wind southwest at 13": the whole surface drifts north-east
            self.u = np.roll(np.roll(self.u, -1, 0), 1, 1)
            self.up = np.roll(np.roll(self.up, -1, 0), 1, 1)

    def draw(self, s, ctx):
        b = ctx.b
        gain = 3.0 * (1 + 0.4 * np.clip((b - 4319) / 80, 0, 1))
        if b >= 4401 and int(b - 4401) % 4 >= 2 and b < 4412:
            return
        if b >= 4412 and self.crests is not None:
            xs, ys = self.crests
            dots_layers(s, [(splat(xs, ys), CREST)])
            return
        v = np.clip(self.u * gain, 0, 1)
        # Thin rings: only a narrow band of each crest is drawn, dithered.
        # Two thin contour lines of the surface, like a topographic map: rings stay rings when it gets busy.
        dots = ((v > 0.16) & (v < 0.27)) | ((v > 0.55) & (v < 0.66))
        col = gradient([RIPPLE * 0.55, RIPPLE, CREST], np.clip(cell_mean(v) * 2.2, 0, 1))
        tint = np.clip((b - 4319) / 80, 0, 1) * 0.5
        if tint:
            s.bg[:] = s.bg + DEEPWATER * tint
        dots_layers(s, [(dots, col)])
        s.post["flash"] = self.flash


# ------------------------------------------------------------------ 9 · orbit
@material("orbit")
class Orbit(Material):
    """Points orbit a centre under gravity, leaving trails; each chopped syllable adds a body.
    Over the section they are drawn into one ring."""

    GM = 3.0e5
    RING = 36.0

    def __init__(self, prev, ctx):
        self.rng = np.random.default_rng(4460)
        crest = getattr(prev, "crests", None)
        if crest is None or not len(crest[0]):
            a = self.rng.uniform(0, 2 * math.pi, 12)
            crest = (CX + np.cos(a) * 40, CY + np.sin(a) * 30)
        self.x, self.y = np.array(crest[0], float), np.array(crest[1], float)
        self.vx, self.vy = self._tangent(self.x, self.y)
        self.trail = np.zeros((DH, DW), np.float32)
        self.pings = []

    def _tangent(self, x, y):
        dx, dy = x - CX, y - CY
        r = np.hypot(dx, dy) + 1e-3
        v = np.sqrt(self.GM / np.maximum(r, 12)) * self.rng.uniform(0.8, 1.1, len(x))
        return -dy / r * v, dx / r * v

    def add(self):
        a = self.rng.uniform(0, 2 * math.pi)
        r = self.rng.uniform(16, 60)
        x, y = np.array([CX + math.cos(a) * r]), np.array([CY + math.sin(a) * r * 0.9])
        vx, vy = self._tangent(x, y)
        self.x, self.y = np.append(self.x, x), np.append(self.y, y)
        self.vx, self.vy = np.append(self.vx, vx), np.append(self.vy, vy)

    def step(self, ctx):
        b = ctx.b
        for _ in ctx.voice(("fdg_single:1",), ("word",)):
            if len(self.x) < 140:
                self.add()
        pull = float(np.clip((b - 4560) / 850, 0, 1)) ** 1.5
        for _ in range(2):
            h = DT / 2
            dx, dy = self.x - CX, self.y - CY
            r = np.hypot(dx, dy) + 1e-3
            a = -self.GM / (r * r + 225)
            ax, ay = a * dx / r, a * dy / r
            # Drawn into a ring: a radial spring and a nudge towards circular speed.
            k = pull * 12.0
            ax += -k * (r - self.RING) * dx / r
            ay += -k * (r - self.RING) * dy / r
            vt = np.sqrt(self.GM / self.RING)
            tx, ty = -dy / r, dx / r
            vr = self.vx * dx / r + self.vy * dy / r
            vtan = self.vx * tx + self.vy * ty
            ax += pull * (-1.5 * vr * dx / r + 1.5 * (vt - vtan) * tx)
            ay += pull * (-1.5 * vr * dy / r + 1.5 * (vt - vtan) * ty)
            self.vx += ax * h
            self.vy += ay * h
            self.x += self.vx * h
            self.y += self.vy * h
            self.trail[np.clip(self.y.astype(int), 0, DH - 1), np.clip(self.x.astype(int), 0, DW - 1)] = 1.0
        self.trail *= 0.955
        if ctx.kick_hit and len(self.x):
            i = int(self.rng.integers(0, len(self.x)))
            self.pings.append([self.x[i], self.y[i], 0.0])
        for p in self.pings:
            p[2] += DT
        self.pings = [p for p in self.pings if p[2] < 0.5]

    def draw(self, s, ctx):
        yy, xx = np.mgrid[0:DH, 0:DW]
        layers = [(self.trail > BAYER * 0.9 + 0.05, gradient([TRAIL * 0.5, TRAIL], np.clip(cell_mean(self.trail) * 3, 0, 1)))]
        for px, py, age in self.pings:
            ring = np.abs(np.hypot(xx - px, yy - py) - age * 50) < 0.6
            layers.append((ring, BODY * 0.5 * (1 - age / 0.5)))
        dots_layers(s, layers)
        for x, y in zip(self.x, self.y):
            s.put(int(x / 2), int(y / 4), "•", BODY, bold=True)


# ------------------------------------------------------------------ 10 · light
def torus_points(n_t=80, n_p=260):
    th = np.linspace(0, 2 * math.pi, n_t, endpoint=False)
    ph = np.linspace(0, 2 * math.pi, n_p, endpoint=False)
    T, P = np.meshgrid(th, ph)
    return T.ravel(), P.ravel()


@material("light")
class Light(Material):
    """The ring thickens into a lit, rotating torus banded with every earlier material.
    Then it shatters into grains that hang, split into four materials, and swirl."""

    def __init__(self, prev, ctx):
        self.rng = np.random.default_rng(5500)
        self.T, self.P = torus_points()
        self.A, self.B = math.pi / 2, 0.0
        self.spin = 0.0
        self.frozen = False
        self.g = None          # grains after the shatter: x, y, vx, vy, colour
        self.ring = getattr(prev, "RING", 50.0)

    def project(self, ctx):
        b = ctx.b
        grow = float(np.clip((b - 5500) / 32, 0, 1))
        r = 0.02 + 0.43 * grow
        R = 1.0
        breath = 1 + 0.04 * ctx.level + 0.05 * ctx.kick
        cA, sA, cB, sB = math.cos(self.A), math.sin(self.A), math.cos(self.B), math.sin(self.B)
        cT, sT, cP, sP = np.cos(self.T), np.sin(self.T), np.cos(self.P), np.sin(self.P)
        cx_, cy_ = R + r * cT, r * sT
        x = cx_ * (cB * cP + sA * sB * sP) - cy_ * cA * sB
        y = cx_ * (sB * cP - sA * cB * sP) + cy_ * cA * cB
        z = cA * cx_ * sP + cy_ * sA
        L = cP * cT * sB - cA * cT * sP - sA * sT + cB * (cA * sT - cT * sA * sP)
        K2 = 5.0
        scale = (self.ring / 4.0) * (K2 + 0.0) / (R) * breath
        ooz = 1 / (z + K2)
        col = 60 + x * ooz * scale * 1.875
        row = 18 - y * ooz * scale
        return col, row, ooz, L / 1.42, z

    def step(self, ctx):
        b = ctx.b
        for _ in ctx.voice(("fdg_down:0", "fdg_down:1"), ("word",)):
            self.spin += 0.35
        frozen = ctx.hit("freeze", 10) is not None
        if self.g is None and not frozen:
            grow = float(np.clip((b - 5500) / 32, 0, 1))
            self.A = math.pi / 2 - 0.9 * grow + 0.3 * math.sin(ctx.t * 0.4) * grow
            self.B += (0.9 * grow + self.spin) * DT
            self.spin *= 0.92
        # Signature moment: "…viewers like you" — it shatters into grains that hang in the air.
        if self.g is None and ctx.crossed(6010):
            col, row, ooz, L, z = self.project(ctx)
            sel = self.rng.random(len(col)) < 0.25
            gx = col[sel] * 2 + self.rng.random(sel.sum()) * 2
            gy = row[sel] * 4 + self.rng.random(sel.sum()) * 4
            band = (self.P[sel] / (2 * math.pi) * len(BANDS)).astype(int) % len(BANDS)
            dx, dy = gx - CX, gy - CY
            r = np.hypot(dx, dy) + 1e-3
            sp = self.rng.uniform(25, 80, len(gx))
            self.g = [gx, gy, dx / r * sp, dy / r * sp, band]
        if self.g is not None:
            gx, gy, vx, vy, band = self.g
            if b >= 6270:
                dx, dy = gx - CX, gy - CY
                r = np.hypot(dx, dy) + 1e-3
                k = min(1.0, (b - 6270) / 200)
                vx += (-dy / r * 60 * k - dx / r * 8 * k) * DT
                vy += (dx / r * 60 * k - dy / r * 8 * k) * DT
            vx *= 0.975
            vy *= 0.975
            gx += vx * DT
            gy += vy * DT
            self.g = [gx, gy, vx, vy, band]

    def draw(self, s, ctx):
        if self.g is None:
            col, row, ooz, L, z = self.project(ctx)
            ci, ri = np.round(col).astype(int), np.round(row).astype(int)
            ok = (ci >= 0) & (ci < 120) & (ri >= 0) & (ri < 36)
            ci, ri, ooz, L = ci[ok], ri[ok], ooz[ok], L[ok]
            band = (self.P[ok] / (2 * math.pi) * len(BANDS)).astype(int) % len(BANDS)
            key = ri * 120 + ci
            order = np.lexsort((ooz, key))
            last = np.r_[key[order][1:] != key[order][:-1], True]
            pick = order[last]
            lum = np.clip(L[pick], 0, 1)
            frozen = ctx.hit("freeze", 10) is not None
            pal = np.array(BANDS, np.float32)
            colours = np.full((len(pick), 3), WHITE, np.float32) if frozen else pal[band[pick]]
            colours = colours * (0.25 + 0.85 * lum)[:, None]
            idx = RAMP[np.clip((lum * (len(RAMP) - 1)).astype(int), 0, len(RAMP) - 1)]
            s.ch[ri[pick], ci[pick]] = idx
            s.fg[ri[pick], ci[pick]] = colours
            return
        gx, gy, vx, vy, band = self.g
        pal = np.array(BANDS, np.float32)
        q = None
        p = ctx.hit("mosaic", 16)
        if p is not None:
            # Signature moment: for a breath the cloud is four materials at once, one per quadrant.
            q = (gx >= CX).astype(int) + 2 * (gy >= CY).astype(int)
            quad = np.array([hexc("c9a46c"), hexc("ff7a1a"), hexc("bfe8ff"), hexc("6fc3df")], np.float32)
            colours = quad[q]
        else:
            colours = pal[band]
        img = splat(gx, gy)
        ci = np.clip((gx / 2).astype(int), 0, 119)
        ri = np.clip((gy / 4).astype(int), 0, 35)
        acc = np.zeros((36, 120, 3), np.float32)
        cnt = np.zeros((36, 120), np.float32)
        np.add.at(acc, (ri, ci), colours)
        np.add.at(cnt, (ri, ci), 1)
        cc = acc / np.maximum(cnt, 1)[..., None]
        dots_layers(s, [(img, cc)])


# ------------------------------------------------------------------ 11 · settle
@material("settle")
class Settle(Material):
    """Gravity returns: every grain falls into one low dune. Then the only words in the film."""

    LINE = "made possible by viewers like you."

    def __init__(self, prev, ctx):
        g = getattr(prev, "g", None)
        if g is None:
            rng = np.random.default_rng(6508)
            g = [rng.uniform(0, DW, 2000), rng.uniform(0, DH / 2, 2000), np.zeros(2000), np.zeros(2000), np.zeros(2000, int)]
        self.x, self.y, self.vx, self.vy, self.band = (np.array(a) for a in g)
        self.vy = self.vy * 0.3
        self.vx = self.vx * 0.3
        self.h = np.zeros(DW, np.float32)
        self.t0 = ctx.t

    def step(self, ctx):
        self.vy += 260 * DT
        self.x += self.vx * DT
        self.y += self.vy * DT
        xi = np.clip(self.x.astype(int), 0, DW - 1)
        land = self.y >= DH - 1 - self.h[xi]
        np.add.at(self.h, xi[land], 1)
        keep = ~land
        self.x, self.y, self.vx, self.vy, self.band = (a[keep] for a in (self.x, self.y, self.vx, self.vy, self.band))
        for _ in range(2):
            d = np.diff(self.h)
            flow = np.sign(d) * np.clip((np.abs(d) - 1.5) / 2, 0, None) * 0.5
            self.h[:-1] += flow
            self.h[1:] -= flow

    def draw(self, s, ctx):
        t = ctx.t
        dim = 1.0 if t < 276.6 else max(0.3, 1 - (t - 276.6) / 1.2)
        yy = np.arange(DH)[:, None]
        depth = yy - (DH - self.h)[None, :]
        dune = ((depth >= 0) & (depth < 1.2)) | ((depth >= 1.2) & ((0.45 * np.exp(-depth / 25) + 0.1) > BAYER))
        dcol = gradient([SAND, SAND * 0.75, SAND_DEEP], np.clip(cell_mean(np.clip(depth, 0, None)) / 30, 0, 1)) * dim
        pal = np.array(BANDS, np.float32)
        air = splat(self.x, self.y)
        acol = pal[self.band].mean(0) if len(self.band) else SAND
        dots_layers(s, [(dune, dcol), (air, acol)])
        if t >= 277.0:
            x0 = 60 - len(self.LINE) // 2
            n = int(max(0.0, t - 277.25) * 28)
            shown = self.LINE[:n]
            s.text(x0, 16, shown, TEXT)
            if n < len(self.LINE) or int(t * 2.5) % 2 == 0:
                s.put(x0 + len(shown), 16, "▌", TEXT * 0.8)
