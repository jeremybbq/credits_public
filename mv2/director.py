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


# White flash at these section starts (strength, decay in steps). The flash peaks two steps before the cut,
# on the quarter-note hit the cut belongs to (see timeline.BEAT_PHASE).
FLASH = {"forecast": (0.6, 6), "title": (0.7, 8), "funding": (0.4, 5), "crash": (0.7, 6), "ocean": (0.35, 8),
         "network": (0.4, 6), "finale": (0.7, 10)}
FLASH_LEAD = 2


def _flash(b):
    for start, name in tl.SECTIONS:
        if name in FLASH:
            k, d = FLASH[name]
            since = b - (start - FLASH_LEAD)
            if 0 <= since < d + FLASH_LEAD:
                return k * (1 - since / (d + FLASH_LEAD)) ** 2
    return 0.0


def draw_section(screen, ctx, name):
    scenes = _load()
    scenes[name](screen, ctx)


def frame(t, audio):
    ctx = Ctx(t, audio)
    s = Screen()
    draw_section(s, ctx, ctx.sec)
    s.post["flash"] = max(s.post.get("flash", 0), _flash(ctx.b))
    return s


def frame_at_beat(b, audio, name=None):
    """Draw one section at an arbitrary beat (snapshots, flashbacks)."""
    ctx = Ctx(tl.beat_time(b), audio, b)
    s = Screen()
    draw_section(s, ctx, name or ctx.sec)
    return s
