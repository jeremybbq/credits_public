# Play "Accretion" live in a real terminal (24-bit colour, 120x36 or larger), synced to the song.
#
#   python3 mv3/play.py --audio credits.mp3
#
# The world always simulates at 60 steps per second; the terminal shows as many frames as it can keep up with.
import argparse
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import importlib.util      # noqa: E402

import core                 # noqa: E402,F401  (sets up paths to the shared tools)
import audio as au          # noqa: E402
import timeline as tl       # noqa: E402
from core import FPS, ROOT  # noqa: E402
from term import to_ansi    # noqa: E402
from world import World     # noqa: E402

# Reuse mv2's terminal player helpers (audio clock, flash/brightness in cells, cropping).
_spec = importlib.util.spec_from_file_location("mv2_play", os.path.join(ROOT, "mv2", "play.py"))
_mv2_play = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mv2_play)
Clock, apply_post, crop = _mv2_play.Clock, _mv2_play.apply_post, _mv2_play.crop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, help="Frums - Credits EX (mp3/wav)")
    ap.add_argument("--fps", type=float, default=30.0, help="terminal refresh rate")
    ap.add_argument("--mute", action="store_true")
    a = ap.parse_args()

    cache = os.path.join(tempfile.gettempdir(), "accretion_features_{}.npz".format(os.path.getsize(a.audio)))
    print("analysing audio…", flush=True)
    world = World(au.Features(au.analyse(a.audio, FPS, cache), FPS))
    size = shutil.get_terminal_size((120, 36))
    if size.columns < 120 or size.lines < 36:
        print("terminal is {}x{}; 120x36 or larger looks best. starting in 2s…".format(size.columns, size.lines))
        time.sleep(2)

    clock = Clock(a.audio, 0.0, a.mute)
    out = sys.stdout
    out.write("\033[?1049h\033[?25l\033[2J")
    out.flush()
    prev, f = None, 0
    try:
        clock.begin()
        while True:
            t = clock.now()
            if t >= tl.SONG_LENGTH:
                break
            target = int(t * FPS)
            while f <= target:          # catch the simulation up to the music
                world.advance(f / FPS)
                f += 1
            s = world.draw()
            apply_post(s)
            s = crop(s, size.columns, size.lines)
            out.write(to_ansi(s, prev) + "\033[0m")
            out.flush()
            prev = s
            spare = 1.0 / a.fps - (clock.now() - t)
            if spare > 0:
                time.sleep(spare)
    except KeyboardInterrupt:
        pass
    finally:
        clock.stop()
        out.write("\033[0m\033[?25h\033[?1049l")
        out.flush()


if __name__ == "__main__":
    main()
