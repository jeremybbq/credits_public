# Beat grid shared with the original animation: 179 BPM, eighth-note steps.
# "Beat" here means the original engine's step index, so event numbers from credits.py carry over 1:1.

BPM = 179
STEP = 60.0 / BPM / 8.0      # seconds per step (the original's `delay`)
OFFSET = 5.492               # the original's `offset`
FIRST = 61                   # the original loop starts at beat -60 and fires one step late
SONG_LENGTH = 278.8          # Frums - Credits EX
BEAT_PHASE = 6               # quarter-note hits land on steps where (b - 6) % 8 == 0 (measured from the audio)


def beat_time(b):
    return OFFSET + (b - FIRST) * STEP


def time_beat(t):
    return (t - OFFSET) / STEP + FIRST


# Section map (start beat, name). Boundaries are the original's scene-change events.
SECTIONS = (
    (-200, "boot"),
    (60, "forecast"),
    (1080, "title"),
    (1848, "funding"),
    (2976, "melt"),
    (3132, "reboot"),
    (3390, "crash"),
    (3896, "ocean"),
    (4460, "network"),
    (5500, "finale"),
    (6508, "poweroff"),
)


def section_at(b):
    cur = SECTIONS[0]
    for s in SECTIONS:
        if b >= s[0]:
            cur = s
    return cur


# Hand-placed signature moments on the song's biggest hits inside sections (beat, length in steps).
MOMENTS = {
    "radar_flare": (570, 16),
    "title_invert": (1722, 16),
    "funding_freeze": (2618, 14),
    "carrier_blip": (3066, 10),
    "crash_collapse": (3706, 32),
    "lightning": (3963, 14),
    "tunnel_freeze": (5690, 10),
    "viewers": (6010, 18),
    "mosaic": (6202, 16),
}


def moment(name, b):
    """Progress 0..1 through a signature moment, or None outside it."""
    start, length = MOMENTS[name]
    if start <= b < start + length:
        return (b - start) / length
    return None
