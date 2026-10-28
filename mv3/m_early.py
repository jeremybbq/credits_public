# 1 Seed · 2 Weather → sand · 3 Fire
import math

import numpy as np

from core import BAYER, DH, DT, DW, cell_mean, dots_layers, gradient, hexc, mix, splat
from world import Material, material

WHITE = hexc("e8ecf4")
RAIN = hexc("8aa4c8")
SAND = hexc("c9a46c")
SAND_DEEP = hexc("5e4628")
GOLD = hexc("e8bd62")
SUN = hexc("ffcf7a")
CLOUD = hexc("5c6a80")
FIRE = [hexc("000000"), hexc("3a0a06"), hexc("b3261e"), hexc("ff7a1a"), hexc("ffd27a"), hexc("fff6e0")]
ASH = hexc("3b3a3f")
EMBER = hexc("8a2a12")


def value_noise(h, w, cell, rng):
    g = rng.random((h // cell + 2, w // cell + 2))
    ys, xs = np.arange(h) / cell, np.arange(w) / cell
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a, b = g[y0][:, x0], g[y0][:, x0 + 1]
    c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy


# ------------------------------------------------------------------ 1 · seed
@material("seed")
class Seed(Material):
    def __init__(self, prev, ctx):
        self.rng = np.random.default_rng(1)

    def draw(self, s, ctx):
        t60 = 5.45
        r = 2 + 46 * ctx.level ** 1.4
        if ctx.t > t60 - 0.45:
            r *= max(0.0, (t60 - ctx.t) / 0.45)
        n = int(20 + 260 * ctx.level)
        ang = self.rng.uniform(0, 2 * math.pi, n)
        rad = r * np.sqrt(self.rng.random(n))
        img = splat(DW / 2 + np.cos(ang) * rad, DH / 2 + np.sin(ang) * rad * 0.94)
        img[DH // 2, DW // 2] = False
        s.braille(0, 0, img, WHITE * (0.25 + 0.35 * ctx.level))
        s.put(60, 18, "·", WHITE, bold=True)


# ------------------------------------------------------------------ 2 · weather → sand
def _cloud_amount(b):
    pts = ((60, 0.0), (130, 0.3), (328, 0.55), (360, 0.8), (659, 0.8), (760, 0.18), (1009, 0.18), (1030, 0.45))
    xs, ys = zip(*pts)
    return float(np.interp(b, xs, ys))


STUTTER = ((1044, 0.15), (1048, 0.25), (1052, 0.4), (1056, 0.55), (1060, 0.75), (1064, 0.95))


@material("sand")
class Sand(Material):
    G = 150.0

    def __init__(self, prev, ctx):
        rng = np.random.default_rng(60)
        n = 280
        ang = rng.uniform(-math.pi * 0.92, -math.pi * 0.08, n)
        sp = rng.uniform(40, 150, n)
        self.x = DW / 2 + rng.normal(0, 1.0, n)
        self.y = np.full(n, DH / 2.0)
        self.vx, self.vy = np.cos(ang) * sp, np.sin(ang) * sp
        self.h = np.zeros(DW, np.float32)
        self.rng = np.random.default_rng(61)
        self.tex = value_noise(48, 960, 24, np.random.default_rng(62)) * 0.65 + \
            value_noise(48, 960, 9, np.random.default_rng(63)) * 0.35
        self.drift = 0.0
        self.gold = 0.0
        self.flick = 0.0

    def clouds(self, b):
        A = _cloud_amount(b)
        xs = (np.arange(DW) + int(-self.drift)) % self.tex.shape[1]
        n = self.tex[:, xs]
        prof = np.exp(-((np.arange(48) - 14) / 11.0) ** 2)[:, None]
        return np.clip((n * prof - (1 - A) * 0.75) * 3.0, 0, 1)

    def spawn(self, n, cloud, focus=1.0):
        col = cloud.sum(0) ** focus + 1e-3
        xs = self.rng.choice(DW, n, p=col / col.sum())
        self.x = np.append(self.x, xs + self.rng.random(n))
        self.y = np.append(self.y, 14 + self.rng.random(n) * 14)
        self.vx = np.append(self.vx, 6 + self.rng.normal(0, 3, n))
        self.vy = np.append(self.vy, 18 + self.rng.random(n) * 10)

    def step(self, ctx):
        b = ctx.b
        if 1079 <= b:
            return
        self.drift -= 6 * DT
        cloud = self.clouds(b)
        focus = 3.0 if 370 <= b < 498 else 1.0
        for _, _, _, c, word in ctx.voice(("ocean_b:1",), ("char",)):
            self.spawn(22 if word else 8, cloud, focus)
        if self.rng.random() < 0.6 * _cloud_amount(b):
            self.spawn(2, cloud, focus)
        if b >= 659:
            self.gold = min(1.0, self.gold + DT / 3.0)
        for _, _, _, c, _ in ctx.voice(("ocean_b:1",), ("char",)):
            if b >= 1043 and c in "iI":
                self.flick = 1.0
        self.flick *= 0.85

        # Signature moment: the ground breathes — the top layer of every dune goes up and comes down.
        if ctx.crossed(570):
            k = np.minimum(self.h, 3).astype(int)
            cols = np.repeat(np.arange(DW), k)
            self.h -= k
            m = len(cols)
            self.x = np.append(self.x, cols + self.rng.random(m))
            self.y = np.append(self.y, DH - 1 - self.h[cols] - self.rng.random(m) * 3)
            self.vx = np.append(self.vx, self.rng.normal(0, 8, m))
            self.vy = np.append(self.vy, -self.rng.uniform(40, 95, m))

        # Saturday: time hiccups — falling grains jerk back upward, more and more often.
        p = 0.0
        for beat, v in STUTTER:
            if b >= beat:
                p = v
        if p and ctx.steps() and self.rng.random() < p:
            self.vy = -np.abs(self.vy) * 0.9 - 25
            k = int(p * 50)
            cols = self.rng.integers(0, DW, k)
            take = self.h[cols] > 1
            cols = cols[take]
            self.h[cols] -= 1
            self.x = np.append(self.x, cols.astype(float))
            self.y = np.append(self.y, DH - 1 - self.h[cols])
            self.vx = np.append(self.vx, self.rng.normal(0, 6, len(cols)))
            self.vy = np.append(self.vy, -self.rng.uniform(30, 70, len(cols)))

        self.vy += self.G * DT
        self.x += self.vx * DT
        self.y += self.vy * DT
        xi = np.clip(self.x.astype(int), 0, DW - 1)
        land = self.y >= DH - 1 - self.h[xi]
        gone = (self.x < 0) | (self.x >= DW)
        np.add.at(self.h, xi[land & ~gone], 1)
        keep = ~land & ~gone
        self.x, self.y, self.vx, self.vy = self.x[keep], self.y[keep], self.vx[keep], self.vy[keep]

        thr = 0.7 if ctx.kick_hit else 1.8
        for _ in range(3 if ctx.kick_hit else 1):
            d = np.diff(self.h)
            flow = np.sign(d) * np.clip((np.abs(d) - thr) / 2, 0, None) * 0.5
            self.h[:-1] += flow
            self.h[1:] -= flow

    def dune_dots(self):
        yy = np.arange(DH)[:, None]
        top = DH - self.h[None, :]
        depth = yy - top
        surf = (depth >= 0) & (depth < 1.2)
        body = (depth >= 1.2) & ((0.5 * np.exp(-depth / 30) + 0.12) > BAYER)
        return surf | body, np.clip(depth / 40, 0, 1)

    def draw(self, s, ctx):
        b = ctx.b
        sun = 0.0
        if b >= 659:
            sun = min(1.0, (b - 659) / 50)
        if b >= 1009:
            sun = 0.55
        sun *= 1 - 0.8 * self.flick
        if sun > 0:
            yy, xx = np.mgrid[0:36, 0:120].astype(np.float32)
            d = np.hypot((xx - 104) / 46, (yy - 1) / 15)
            s.bg[:] = s.bg + SUN * (0.16 * sun * np.exp(-d * d))[..., None]
        cloud = self.clouds(b)
        cdots = np.zeros((DH, DW), bool)
        cdots[:48] = cloud * 0.8 > BAYER[:48]
        dune, depth = self.dune_dots()
        sand_top = mix(SAND, GOLD, self.gold)
        dcol = gradient([sand_top, sand_top * 0.75, SAND_DEEP], cell_mean(depth))
        air = splat(self.x, self.y)
        cfull = np.zeros((DH, DW), np.float32)
        cfull[:48] = cloud
        ccol = CLOUD * (0.45 + 0.55 * np.clip(cell_mean(cfull) * 3, 0, 1))[..., None]
        dots_layers(s, [(cdots, ccol), (dune, dcol), (air, mix(RAIN, sand_top, 0.15 * self.gold))])


# ------------------------------------------------------------------ 3 · fire
@material("fire")
class Fire(Material):
    """Dotted flames on the braille grid, rising from the dunes, which burn down to ash."""

    def __init__(self, prev, ctx):
        self.fuel = (prev.h.copy() if isinstance(prev, Sand) else np.full(DW, 30.0)).astype(np.float32) + 1
        self.gold = prev.gold if isinstance(prev, Sand) else 1.0
        self.F = np.zeros((DH, DW), np.float32)
        self.rng = np.random.default_rng(1080)
        self.sx = self.sy = self.svx = self.svy = self.slife = np.zeros(0)
        self.cool_tex = value_noise(DH * 3, DW, 10, np.random.default_rng(1081))

    def step(self, ctx):
        b = ctx.b
        ign = np.arange(DW) < (b - 1080) / 14.0 * DW
        die = 1.0 if b < 1784 else max(0.0, 1 - (b - 1784) / 64)
        surf = np.clip(DH - 1 - self.fuel.astype(int), 1, DH - 1)
        heat = (0.65 + 0.45 * ctx.level + 0.35 * ctx.kick) * (0.5 + 0.5 * self.rng.random(DW)) * die
        cols = np.where(ign)[0]
        for k in (0, 1, 2):
            r = np.clip(surf[cols] - k, 0, DH - 1)
            self.F[r, cols] = np.maximum(self.F[r, cols], heat[cols] * (1 - 0.1 * k))
        below = np.roll(self.F, -1, 0)
        below[-1] = 0
        below2 = np.roll(below, -1, 0)
        below2[-1] = 0
        avg = (np.roll(below, 1, 1) + below + np.roll(below, -1, 1) + below2) / 4.0
        cool = 0.017 if b < 1336 else 0.013
        if b >= 1784:
            cool += 0.04 * (b - 1784) / 64
        off = int(ctx.t * 70) % (DH * 2)
        n = self.cool_tex[off:off + DH]
        self.F = np.clip(avg - cool * (0.3 + 1.4 * n), 0, 1).astype(np.float32)
        self.fuel = np.maximum(self.fuel - 0.012 * ign * die, 3.0)

        if ctx.snare_hit and die > 0:
            k = 5
            xs = self.rng.uniform(0, DW, k)
            self.sx = np.append(self.sx, xs)
            self.sy = np.append(self.sy, DH - 1 - self.fuel[xs.astype(int)] - 4)
            self.svx = np.append(self.svx, self.rng.normal(0, 20, k))
            self.svy = np.append(self.svy, -self.rng.uniform(60, 130, k))
            self.slife = np.append(self.slife, self.rng.uniform(0.6, 1.3, k))
        self.svy += 50 * DT
        self.sx += self.svx * DT
        self.sy += self.svy * DT
        self.slife -= DT
        keep = self.slife > 0
        self.sx, self.sy, self.svx, self.svy, self.slife = (a[keep] for a in (self.sx, self.sy, self.svx, self.svy, self.slife))

    def draw(self, s, ctx):
        F = self.F
        # Signature moment: the fire inhales to the centre and exhales.
        p = ctx.hit("inhale", 16)
        if p is not None:
            k = 1 - 0.75 * math.sin(math.pi * p)
            src = (np.arange(DW) - DW / 2) / k + DW / 2
            ok = (src >= 0) & (src < DW - 1)
            G = np.zeros_like(F)
            G[:, ok] = F[:, src[ok].astype(int)]
            F = G
        yy = np.arange(DH)[:, None]
        depth = yy - (DH - self.fuel)[None, :]
        ground = ((depth >= 0) & (depth < 1.2)) | ((depth >= 1.2) & ((0.45 * np.exp(-depth / 30) + 0.1) > BAYER))
        heat_col = F.max(0)
        glow = np.clip(cell_mean(np.broadcast_to(heat_col[None, :], (DH, DW))) * 1.5, 0, 1)
        sand = mix(SAND, GOLD, self.gold)
        gcol = mix(mix(sand * 0.6, ASH, np.clip((ctx.b - 1080) / 500, 0, 1)), EMBER * 1.4, glow[..., None] * 0.8)
        flame = F > BAYER * 0.85 + 0.06
        fcol = gradient(FIRE[1:], np.clip(cell_mean(F) * 1.6, 0, 1))
        dots_layers(s, [(ground, gcol), (flame & ~ground, fcol)])
        for x, y, life in zip(self.sx, self.sy, self.slife):
            c = mix(FIRE[3], FIRE[5], min(life, 1.0))
            s.put(int(x / 2), int(y / 4), "•" if life > 0.8 else "·", c * min(1.0, life * 1.2))
