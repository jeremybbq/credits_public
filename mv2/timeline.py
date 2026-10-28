# Beat grid shared with the original animation: 179 BPM, eighth-note steps.
# "Beat" here means the original engine's step index, so event numbers from credits.py carry over 1:1.

BPM = 179
STEP = 60.0 / BPM / 8.0      # seconds per step (the original's `delay`)
OFFSET = 5.492               # the original's `offset`
FIRST = 61                   # the original loop starts at beat -60 and fires one step late
SONG_LENGTH = 278.8          # Frums - Credits EX


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
