# The edit: which scene draws at which beat, plus the cuts between sections.
import timeline as tl
from scenes.common import Ctx
from term import Screen

_SCENES = {}


def _load():
    # Imported lazily: finale/poweroff call back into this module for flashbacks.
    if not _SCENES:
        from scenes import finale, forecast, funding, network, ocean, system, title
        _SCENES.update({
            "boot": forecast.boot, "forecast": forecast.forecast, "title": title.title, "funding": funding.funding,
            "melt": system.melt, "reboot": system.reboot, "crash": system.crash, "ocean": ocean.ocean,
            "network": network.network, "finale": finale.finale, "poweroff": finale.poweroff,
        })
    return _SCENES


# White flash on these section starts (strength, decay in steps).
FLASH = {"forecast": (0.9, 6), "title": (1.0, 8), "funding": (0.6, 5), "crash": (0.9, 6), "ocean": (0.5, 8),
         "network": (0.6, 6), "finale": (1.0, 10)}


def draw_section(screen, ctx, name):
    scenes = _load()
    scenes[name](screen, ctx)


def frame(t, audio):
    ctx = Ctx(t, audio)
    s = Screen()
    draw_section(s, ctx, ctx.sec)
    if ctx.sec in FLASH:
        k, d = FLASH[ctx.sec]
        since = ctx.b - ctx.s0
        if 0 <= since < d:
            s.post["flash"] = max(s.post.get("flash", 0), k * (1 - since / d) ** 2)
    return s


def frame_at_beat(b, audio, name=None):
    """Draw one section at an arbitrary beat (snapshots, flashbacks)."""
    ctx = Ctx(tl.beat_time(b), audio, b)
    s = Screen()
    draw_section(s, ctx, name or ctx.sec)
    return s
