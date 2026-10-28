# 3:10-3:53 searching for access points: a radial network of 24 PBS stations, pings travel on the beat.
import math

import numpy as np

import timeline as tl
from lyrics import stream
from scenes.common import (AMBER, BG, DIM, FG, GREEN, HOTRED, MUTED, PINK, VIOLET, WHITE, input_line,
                           log_panel, status_bar)
from scenes.forecast import draw_line
from term import mix

CX, CY = 60, 12
SEARCH_FROM, SEARCH_TO = 4540, 5480
ACTIVE, WEAK = 7, 16  # PBS #08 answers, PBS #17 barely does
N = 24
STYLE = {"key": ("❯ ", GREEN, True), "line": ("› ", VIOLET, False), "fluff": ("  ", DIM, False)}


def _nodes():
    pts = []
    for i in range(8):
        a = i / 8 * 2 * math.pi + 0.2
        pts.append((CX + 26 * math.cos(a), CY + 5.5 * math.sin(a)))
    for i in range(16):
        a = i / 16 * 2 * math.pi + 0.05
        pts.append((CX + 54 * math.cos(a), CY + 10 * math.sin(a)))
    return pts


NODES = _nodes()
SLOT = (SEARCH_TO - SEARCH_FROM) / N


def _parent(k):
    """Outer nodes route through the nearest inner node."""
    if k < 8:
        return None
    x, y = NODES[k]
    return min(range(8), key=lambda j: (NODES[j][0] - x) ** 2 + ((NODES[j][1] - y) * 2) ** 2)


def _path(k):
    p = _parent(k)
    return [(CX, CY)] + ([NODES[p]] if p is not None else []) + [NODES[k]]


def _at(path, f):
    seg = len(path) - 1
    f = min(max(f, 0), 0.999) * seg
    i = int(f)
    (x0, y0), (x1, y1) = path[i], path[i + 1]
    u = f - i
    return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u


def network(s, ctx):
    s.clear(BG)
    b = ctx.b
    H, W = 24 * 4, 120 * 2
    edges = np.zeros((H, W), bool)
    live = np.zeros((H, W), bool)
    searching = int((b - SEARCH_FROM) // SLOT) if b >= SEARCH_FROM else -1

    def dot(p):
        return p[0] * 2 + 1, p[1] * 4 + 2

    for k in range(N):
        path = _path(k)
        for a, c in zip(path, path[1:]):
            draw_line(live if (k == ACTIVE and searching > ACTIVE) else edges, *dot(a), *dot(c))
    for i in range(16):
        draw_line(edges, *dot(NODES[8 + i]), *dot(NODES[8 + (i + 1) % 16]))
    edges &= (np.indices((H, W)).sum(0) % 2 == 0)
    s.braille(0, 1, edges, VIOLET * 0.35)
    s.braille(0, 1, live, GREEN * 0.7)

    # Hub pulse ring.
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ph = ((b - tl.BEAT_PHASE) % 8) / 8
    ring = np.abs(np.hypot((xx - CX * 2) / 2.0, (yy - CY * 4) / 1.0) * 1.0 - ph * 30) < 0.6
    s.braille(0, 1, ring, mix(VIOLET, BG, ph))

    # Packets: during a node's slot, one ping every 8 steps travels hub → node.
    if 0 <= searching < N:
        f = ((b - tl.BEAT_PHASE) % 8) / 8
        px, py = _at(_path(searching), f)
        s.put(px, py + 1, "●", WHITE, bold=True)
    if searching > ACTIVE:
        f = ((b - tl.BEAT_PHASE) % 16) / 16
        px, py = _at(_path(ACTIVE), 1 - f)
        s.put(px, py + 1, "●", GREEN, bold=True)

    for k, (x, y) in enumerate(NODES):
        x, y = int(round(x)), int(round(y)) + 1
        label = "PBS #{:02d}".format(k + 1)
        if k < searching or (searching >= N):
            if k == ACTIVE:
                g, c, st = "●", GREEN, "active"
            elif k == WEAK:
                g, c, st = "◐", AMBER, "weak"
            else:
                g, c, st = "✕", HOTRED * 0.6, ""
        elif k == searching:
            ping = int((b - SEARCH_FROM - k * SLOT) // 8) + 1
            g = "◎" if (ctx.bi // 2) % 2 else "◌"
            c, st = AMBER, "ping {}".format(ping)
        else:
            g, c, st = "○", DIM, ""
        s.put(x, y, g, c, bold=True)
        lx = x + 2 if x < CX else x - 1 - len(label)
        s.text(lx, y, label, mix(c, FG, 0.3) if (k == searching or k in (ACTIVE, WEAK) and k < searching) else DIM)
        if st:
            s.text(lx, y + 1, st, c * 0.8)
    s.put(CX, CY + 1, "◉", WHITE, bold=True)
    s.text(CX - 1, CY + 2, "RX", WHITE, bold=True)

    # Summary line + console.
    done = max(0, min(searching, N))
    reach = (1 if done > ACTIVE else 0) + (1 if done > WEAK else 0)
    s.text(2, 24, "stations {}   searched {:2d}   reachable {}   last contact 3,651 days ago".format(N, done, reach), MUTED)
    st = stream("fdg_single:1")
    s.box(1, 25, 118, 10, VIOLET * 0.6, title="uplink console", title_fg=VIOLET, tag="pbs://boston", tag_fg=DIM)
    log_panel(s, 3, 26, 114, 6, st.history(ctx.bi), ctx, styles=STYLE)
    input_line(s, 3, 33, 114, st.current(ctx.bi), ctx, PINK)

    status_bar(s, ctx, VIOLET, extra="{}/{} searched".format(done, N))
