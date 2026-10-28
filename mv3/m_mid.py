# 4 Growth · 5 Erosion · 6 Crystal · 7 Life
import math

import numpy as np

from core import BAYER, COLS, DH, DT, DW, ROWS, cell_mean, dots_layers, gradient, hexc, mix, splat
from term import gid
from world import Material, material

STEM = hexc("7fbf8e")
STEM_OLD = hexc("3f6a4c")
LEAF = hexc("a8d8a0")
STEEL = hexc("8d97a8")
CRACK = hexc("c94f4f")
ASH = hexc("3b3a3f")
EMBER = hexc("8a2a12")
DUST = hexc("6e6a66")
ICE = hexc("bfe8ff")
WHITE = hexc("ffffff")
HEART = hexc("e8ecf4")

U, D, L, R = 1, 2, 4, 8
MOVE = {U: (0, -1), D: (0, 1), L: (-1, 0), R: (1, 0)}
OPP = {U: D, D: U, L: R, R: L}
LIGHT = {U | D: "│", L | R: "─", D | R: "╭", D | L: "╮", U | R: "╰", U | L: "╯", U | D | R: "├", U | D | L: "┤",
         L | R | D: "┬", L | R | U: "┴", U | D | L | R: "┼", U: "╵", D: "╷", L: "╴", R: "╶"}
HEAVY = {U | D: "┃", L | R: "━", D | R: "┏", D | L: "┓", U | R: "┗", U | L: "┛", U | D | R: "┣", U | D | L: "┫",
         L | R | D: "┳", L | R | U: "┻", U | D | L | R: "╋", U: "╹", D: "╻", L: "╸", R: "╺"}
GL_LIGHT = {k: gid(v) for k, v in LIGHT.items()}
GL_HEAVY = {k: gid(v) for k, v in HEAVY.items()}


# ------------------------------------------------------------------ 4 · growth
@material("growth")
class Growth(Material):
    """Stems grow out of the ash, one cell per spoken word; "by" splits, "like you" opens leaves.
    From "Broadcast Corporation" on, growth turns into a rigid steel lattice that later cracks."""

    def __init__(self, prev, ctx):
        self.fuel = getattr(prev, "fuel", np.full(DW, 6.0))
        self.conn = np.zeros((ROWS, COLS), np.uint8)
        self.style = np.zeros((ROWS, COLS), np.uint8)      # 1 organic, 2 rigid
        self.born = np.zeros((ROWS, COLS), np.float32)
        self.crack = np.full((ROWS, COLS), -1.0, np.float32)
        self.rng = np.random.default_rng(1848)
        ground = (DH - self.fuel) / 4.0
        self.ground = np.array([int(min(ground[2 * x], ground[2 * x + 1])) for x in range(COLS)])
        self.tips = []
        for x in (14, 33, 52, 70, 88, 106):
            y = int(self.ground[x]) - 1
            self.tips.append([x, y, U, 1])
            self.conn[y, x] |= D
            self.style[y, x] = 1
        self.leaves = np.zeros((DH, DW), bool)
        self.leaf_born = np.zeros((DH, DW), np.float32)
        self.fx = self.fy = self.fvx = self.fvy = np.zeros(0)
        self.dx = self.dy = self.dvy = self.dlife = np.zeros(0)
        self.ember = 1.0
        self.ever = np.zeros((ROWS, COLS), bool)
        self.ever_conn = np.zeros((ROWS, COLS), np.uint8)
        self.ever_style = np.zeros((ROWS, COLS), np.uint8)

    def _grow(self, b, rigid):
        new = []
        for tip in self.tips:
            x, y, d, st = tip
            if rigid:
                st = 2
                opts = [d] * 8 + [L, R, U] if d in (L, R) else [U] * 4 + [L, R]
            elif d in (L, R):
                opts = [U, U, U, d]          # a sideways step turns back upward soon
            else:
                opts = [U] * 6 + [L, R]
            self.rng.shuffle(opts)
            for nd in opts:
                dx, dy = MOVE[nd]
                nx, ny = x + dx, y + dy
                if 0 <= nx < COLS and 3 <= ny < ROWS - 1 and self.conn[ny, nx] == 0 and ny < self.ground[nx]:
                    self.conn[y, x] |= nd
                    self.conn[ny, nx] |= OPP[nd]
                    self.style[ny, nx] = st
                    if rigid:
                        self.style[y, x] = 2
                    self.born[ny, nx] = b
                    new.append([nx, ny, nd, st])
                    break
        self.tips = new
        self.ever |= self.conn > 0
        self.ever_conn |= self.conn
        self.ever_style = np.maximum(self.ever_style, self.style)

    def _split(self, cap):
        add = []
        for x, y, d, st in self.tips:
            if len(self.tips) + len(add) >= cap:
                break
            if self.rng.random() < 0.6:
                add.append([x, y, L if self.rng.random() < 0.5 else R, st])
        self.tips += add

    def _leaves(self, b):
        for x, y, d, st in self.tips:
            n = 9
            px = x * 2 + 1 + self.rng.normal(0, 2.4, n)
            py = y * 4 + 2 + self.rng.normal(0, 3.0, n)
            m = splat(px, py)
            self.leaves |= m
            self.leaf_born[m] = b

    def step(self, ctx):
        b = ctx.b
        self.ember = max(0.0, self.ember - DT / 2.5)
        rigid = b >= 2354
        for _, _, kind, tok, _ in ctx.voice(("funding:0",), ("word", "line")):
            if kind == "word":
                self._grow(b, rigid)
                low = tok.lower()
                if "by" in low and not rigid:
                    self._split(14)
                if ("you" in low or "like" in low) and not rigid:
                    self._leaves(b)
                if rigid and self.rng.random() < 0.3:
                    self._split(20)
            elif tok and len(self.tips) < 3:
                # A new line re-seeds growth from the ground if everything stopped.
                x = int(self.rng.integers(6, COLS - 6))
                self.tips.append([x, int(self.ground[x]) - 1, U, 2 if rigid else 1])

        # Signature moment: every leaf falls at once.
        if ctx.crossed(2618) and self.leaves.any():
            ys, xs = np.nonzero(self.leaves)
            self.fx, self.fy = xs.astype(float), ys.astype(float)
            self.fvx = self.rng.normal(0, 6, len(xs))
            self.fvy = self.rng.uniform(5, 25, len(xs))
            self.leaves[:] = False
        if len(self.fx):
            self.fvy += 40 * DT
            self.fx += (self.fvx + 10 * np.sin(self.fy * 0.2 + ctx.t * 3)) * DT
            self.fy += self.fvy * DT
            keep = self.fy < DH - 2
            self.fx, self.fy, self.fvx, self.fvy = self.fx[keep], self.fy[keep], self.fvx[keep], self.fvy[keep]

        # The lattice cracks as the voice corrupts; cracked cells turn red, then fall as dust.
        if b >= 2700:
            p = 0.004 + 0.05 * min(1.0, (b - 2700) / 276) ** 2
            if b >= 2900:
                p += 0.04
            live = (self.conn > 0) & (self.crack < 0)
            hit = live & (self.rng.random(live.shape) < p * DT * 10)
            self.crack[hit] = b
        gone = (self.crack >= 0) & (b - self.crack > 10)
        if gone.any():
            ys, xs = np.nonzero(gone)
            self.conn[gone] = 0
            self.crack[gone] = -1
            n = len(xs) * 3
            self.dx = np.append(self.dx, np.repeat(xs, 3) * 2 + self.rng.random(n) * 2)
            self.dy = np.append(self.dy, np.repeat(ys, 3) * 4 + self.rng.random(n) * 4)
            self.dvy = np.append(self.dvy, self.rng.uniform(10, 40, n))
            self.dlife = np.append(self.dlife, self.rng.uniform(1.0, 2.5, n))
        if len(self.dx):
            self.dvy += 60 * DT
            self.dy += self.dvy * DT
            self.dlife -= DT
            keep = (self.dlife > 0) & (self.dy < DH)
            self.dx, self.dy, self.dvy, self.dlife = self.dx[keep], self.dy[keep], self.dvy[keep], self.dlife[keep]

    def draw(self, s, ctx):
        b = ctx.b
        # Ash ground with the last embers.
        yy = np.arange(DH)[:, None]
        depth = yy - (DH - self.fuel)[None, :]
        ground = ((depth >= 0) & (depth < 1.2)) | ((depth >= 1.2) & ((0.3 * np.exp(-depth / 20) + 0.06) > BAYER))
        gcol = mix(ASH, EMBER * 1.3, self.ember * 0.7)
        leafcol = LEAF * 0.85
        fall = splat(self.fx, self.fy)
        dust = splat(self.dx, self.dy)
        dots_layers(s, [(ground, gcol), (self.leaves, leafcol), (fall, LEAF * 0.6), (dust, DUST * 0.8)])
        ys, xs = np.nonzero(self.conn)
        for y, x in zip(ys, xs):
            c = int(self.conn[y, x])
            rigid = self.style[y, x] == 2
            g = (GL_HEAVY if rigid else GL_LIGHT).get(c)
            if g is None:
                continue
            age = b - self.born[y, x]
            if self.crack[y, x] >= 0:
                col = CRACK
            elif rigid:
                col = mix(WHITE, STEEL, min(age / 8, 1.0))
            else:
                col = mix(WHITE, mix(STEM, STEM_OLD, min(age / 400, 1.0)), min(age / 6, 1.0))
            s.ch[y, x] = g
            s.fg[y, x] = col


# ------------------------------------------------------------------ 5 · erosion
@material("erosion")
class Erosion(Material):
    """The structure crumbles to drifting dust; one heartbeat dot remains."""

    def __init__(self, prev, ctx):
        self.rng = np.random.default_rng(2976)
        conn = getattr(prev, "conn", np.zeros((ROWS, COLS), np.uint8))
        self.outline = getattr(prev, "ever_conn", conn).copy()
        self.style = getattr(prev, "ever_style", np.zeros((ROWS, COLS), np.uint8)).copy()
        ys, xs = np.nonzero(conn)
        n = len(xs) * 4
        self.x = np.repeat(xs, 4) * 2 + self.rng.random(n) * 2
        self.y = np.repeat(ys, 4) * 4 + self.rng.random(n) * 4
        self.vx = self.rng.normal(0, 4, n)
        self.vy = self.rng.normal(-2, 3, n)
        self.life = self.rng.uniform(0.6, 2.6, n)
        self.age = 0.0
        self.fuel = getattr(prev, "fuel", np.full(DW, 6.0))

    def step(self, ctx):
        self.age += DT
        self.vx += self.rng.normal(0, 20, len(self.x)) * DT
        self.vy += self.rng.normal(0, 20, len(self.x)) * DT + 3 * DT
        self.x += self.vx * DT + 8 * DT
        self.y += self.vy * DT
        self.life -= DT
        keep = self.life > 0
        self.x, self.y, self.vx, self.vy, self.life = (a[keep] for a in (self.x, self.y, self.vx, self.vy, self.life))

    def draw(self, s, ctx):
        b = ctx.b
        fade = np.clip(self.life / 1.5, 0, 1)
        lo = splat(self.x[fade < 0.5], self.y[fade < 0.5])
        hi = splat(self.x[fade >= 0.5], self.y[fade >= 0.5])
        gfade = max(0.0, 1 - self.age / 2.0)
        yy = np.arange(DH)[:, None]
        depth = yy - (DH - self.fuel)[None, :]
        ground = ((depth >= 0) & (depth < 1.2)) & (BAYER < gfade)
        dots_layers(s, [(ground, ASH), (lo, DUST * 0.45), (hi, DUST)])
        # Signature moment: the outline of the lost structure flashes once.
        p = ctx.hit("outline", 8)
        if p is not None:
            k = (1 - p) ** 2 * 0.5
            ys, xs = np.nonzero(self.outline)
            for y, x in zip(ys, xs):
                g = (GL_HEAVY if self.style[y, x] == 2 else GL_LIGHT).get(int(self.outline[y, x]))
                if g is not None:
                    s.ch[y, x] = g
                    s.fg[y, x] = HEART * k
        # Heartbeat: a double pulse every bar once the dust has settled.
        if b >= 3000:
            ph = (b - 6) % 32
            beat = math.exp(-ph / 1.5) + 0.7 * math.exp(-max(ph - 5, 0) / 1.5) * (ph >= 5)
            s.put(60, 18, "•" if beat > 0.4 else "·", HEART * (0.35 + 0.65 * min(beat, 1.0)), bold=beat > 0.4)


# ------------------------------------------------------------------ 6 · crystal
@material("crystal")
class Crystal(Material):
    """A snowflake accreting from the heartbeat: six arms with mirrored side branches at 60°.
    Each "Annual / financial / suppor-" syllable pushes the growth; faint particles drift in to it."""

    RMAX = 64.0

    def __init__(self, prev, ctx):
        self.rng = np.random.default_rng(3132)
        self.occ = np.zeros((DH, DW), bool)
        self.age = np.zeros((DH, DW), np.float32)
        self.cx, self.cy = DW / 2, DH / 2
        # Branch: [x, y (wedge coords, arm along +x), angle, length grown, max length, depth, next split]
        self.branches = [[0.0, 0.0, 0.0, 0.0, self.RMAX, 0, 5.0]]
        self.push = 0.0
        self.wx = np.zeros(0)
        self.wy = np.zeros(0)

    def _stamp(self, x0, y0, x1, y1, b):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        xs, ys = np.linspace(x0, x1, n), np.linspace(y0, y1, n)
        for k in range(6):
            a = k * math.pi / 3
            c, sn = math.cos(a), math.sin(a)
            for m in (1, -1):
                X = self.cx + c * xs - sn * ys * m
                Y = self.cy + (sn * xs + c * ys * m) * 0.94
                xi, yi = np.round(X).astype(int), np.round(Y).astype(int)
                ok = (xi >= 0) & (xi < DW) & (yi >= 0) & (yi < DH)
                xi, yi = xi[ok], yi[ok]
                new = ~self.occ[yi, xi]
                self.occ[yi[new], xi[new]] = True
                self.age[yi[new], xi[new]] = b

    def step(self, ctx):
        b = ctx.b
        for _ in ctx.voice(("loadingbar:6",), ("word",)):
            self.push += 1.0
        rate = 0.045 + 0.1 * ctx.level + min(self.push, 0.4)
        self.push = max(0.0, self.push - 0.4)
        if b >= 3376:
            rate = 3.0
        grow = []
        for br in self.branches:
            x, y, ang, done, mx, depth, nxt = br
            if done >= mx:
                continue
            d = min(rate * (1.0 if depth == 0 else 0.8), mx - done)
            nx, ny = x + math.cos(ang) * d, y + math.sin(ang) * d
            self._stamp(x, y, nx, ny, b)
            br[0], br[1], br[3] = nx, ny, done + d
            if depth < 2 and br[3] >= nxt:
                remain = mx - br[3]
                side = remain * (0.42 if depth == 0 else 0.35) * (0.7 + 0.6 * self.rng.random())
                if side > 2:
                    grow.append([nx, ny, ang + math.pi / 3, 0.0, side, depth + 1, 3.0 + self.rng.random() * 3])
                br[6] = nxt + (5.0 if depth == 0 else 3.5) + self.rng.random() * 3
        self.branches += grow

        # Faint particles drifting in to the crystal (the accretion, made visible).
        if len(self.wx) < 90:
            a = self.rng.uniform(0, 2 * math.pi, 6)
            self.wx = np.append(self.wx, self.cx + np.cos(a) * 110)
            self.wy = np.append(self.wy, self.cy + np.sin(a) * 75)
        ang = np.arctan2(self.cy - self.wy, self.cx - self.wx)
        self.wx += (np.cos(ang) * 22 + self.rng.normal(0, 25, len(self.wx))) * DT
        self.wy += (np.sin(ang) * 16 + self.rng.normal(0, 25, len(self.wy))) * DT
        r = np.hypot(self.wx - self.cx, (self.wy - self.cy) / 0.94)
        reach = max(br[3] for br in self.branches[:1]) + 4
        keep = r > reach
        self.wx, self.wy = self.wx[keep], self.wy[keep]

    def draw(self, s, ctx):
        b = ctx.b
        new = self.occ & (b - self.age < 6)
        old = self.occ & ~new
        walkers = splat(self.wx, self.wy)
        agec = np.clip(cell_mean(np.where(self.occ, b - self.age, 0)) / 80, 0, 1)
        dots_layers(s, [(walkers, ICE * 0.25), (old, gradient([ICE, ICE * 0.6], agec)), (new, WHITE)])


# ------------------------------------------------------------------ 7 · life
RULES = (  # (birth, survive, colour) — the rule set changes every two bars
    ({3}, {2, 3}, hexc("e6e6e6")),
    ({3, 6}, {2, 3}, hexc("ff8a7a")),
    ({3, 6, 7, 8}, {3, 4, 6, 7, 8}, hexc("7ac8ff")),
    ({3, 6, 8}, {2, 4, 5}, hexc("ffd36b")),
    ({3, 6}, {1, 2, 5}, hexc("b48cff")),
    ({3}, {1, 2, 3, 4}, hexc("7fe0b0")),
    ({3}, {4, 5, 6, 7, 8}, hexc("ff8fb8")),
    ({3, 7}, {2, 3}, hexc("cfeaff")),
)
GLIDER = np.array([[0, 1, 0], [0, 0, 1], [1, 1, 1]], bool)
RPENT = np.array([[0, 1, 1], [1, 1, 0], [0, 1, 0]], bool)
ACORN = np.array([[0, 1, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0, 0], [1, 1, 0, 0, 1, 1, 1]], bool)
LIFE = RULES[0]


@material("life")
class Life(Material):
    """The crystal shatters into living cells: one generation per step, rules swap on the bar line."""

    def __init__(self, prev, ctx):
        self.rng = np.random.default_rng(3390)
        occ = getattr(prev, "occ", np.zeros((DH, DW), bool))
        self.live = occ | (np.roll(occ, 1, 1) & (self.rng.random((DH, DW)) < 0.5))
        self.age = np.zeros((DH, DW), np.float32)
        self.frozen = None
        self.override_until = -1

    def _put(self, pat, x, y):
        h, w = pat.shape
        self.live[y:y + h, x:x + w] |= pat

    def _rule(self, b):
        if b < self.override_until or b >= 3865:
            return LIFE
        return RULES[int((b - 3390) // 64) % len(RULES)]

    def _gen(self, rule):
        L = self.live.astype(np.uint8)
        n = sum(np.roll(np.roll(L, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
        born = np.isin(n, list(rule[0])) & ~self.live
        stay = np.isin(n, list(rule[1])) & self.live
        self.live = born | stay
        self.age = np.where(self.live, self.age + 1, 0)

    def step(self, ctx):
        b = ctx.b
        if ctx.crossed(3865):
            # "This is PBS!": the field freezes; only a single glider is left moving.
            self.frozen = (self.live.copy(), b)
            self.live[:] = False
            self._put(GLIDER, 40, 30)
        if b < 3865:
            if ctx.kick_hit:
                pat = (GLIDER, RPENT, ACORN)[int(self.rng.integers(0, 3))]
                self._put(pat, int(self.rng.integers(4, DW - 10)), int(self.rng.integers(4, DH - 6)))
            for _ in ctx.voice(("fundingx2:0",), ("word",)):
                x, y = int(self.rng.integers(10, DW - 10)), int(self.rng.integers(8, DH - 8))
                self.live[y - 2:y + 3, x - 3:x + 4] |= self.rng.random((5, 7)) < 0.45
            # Signature moment: almost every cell dies at once; one glider survives.
            if ctx.crossed(3706):
                self.live[:] = False
                self._put(GLIDER, 30, 20)
                self.override_until = 3770
        for _ in range(ctx.steps()):
            self._gen(self._rule(b))

    def draw(self, s, ctx):
        b = ctx.b
        rule = self._rule(b)
        young = self.live & (self.age < 3)
        old = self.live & ~young
        layers = []
        if self.frozen is not None:
            k = max(0.0, 1 - (b - self.frozen[1]) / 15)
            if k > 0:
                layers.append((self.frozen[0], rule[2] * 0.6 * k))
        layers += [(old, rule[2] * 0.65), (young, mix(rule[2], WHITE, 0.5))]
        dots_layers(s, layers)
