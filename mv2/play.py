# Play the video live in a real terminal: 24-bit colour ANSI output synced to the song.
#
#   python3 mv2/play.py --audio credits.mp3            (terminal should be at least 120x36)
#   python3 mv2/play.py --audio credits.mp3 --start 145
#
# Audio plays through just_playback if installed (the original project's player), else ffplay, else silently.
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audio as au          # noqa: E402
import director             # noqa: E402
import timeline as tl       # noqa: E402
from term import to_ansi    # noqa: E402


class Clock:
    """Song position in seconds, from the audio player when it can tell us, else wall time."""

    def __init__(self, path, start, mute):
        self.start, self.t0, self.proc, self.pb = start, None, None, None
        if path and not mute:
            try:
                from just_playback import Playback
                self.pb = Playback()
                self.pb.load_file(path)
            except Exception:
                self.pb = None
                if shutil.which("ffplay"):
                    self.proc = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-ss", str(start), path],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def begin(self):
        if self.pb:
            self.pb.play()
            self.pb.seek(self.start)
        self.t0 = time.time()

    def now(self):
        if self.pb and self.pb.active:
            return self.pb.curr_pos
        return self.start + time.time() - self.t0

    def stop(self):
        if self.pb:
            self.pb.stop()
        if self.proc:
            self.proc.terminate()


def apply_post(s):
    """Terminal version of the video post effects that make sense in cells (flash, brightness)."""
    p = s.post
    k = p.get("bright", 1.0)
    if k != 1.0:
        s.fg *= k
        s.bg *= k
    fl = min(p.get("flash", 0.0), 1.0)
    if fl > 0:
        s.fg += (255 - s.fg) * fl
        s.bg += (255 - s.bg) * fl
    np.clip(s.fg, 0, 255, out=s.fg)
    np.clip(s.bg, 0, 255, out=s.bg)


def crop(s, cols, rows):
    if cols >= s.cols and rows >= s.rows:
        return s
    c, r = min(cols, s.cols), min(rows, s.rows)
    s.ch, s.fg, s.bg = s.ch[:r, :c], s.fg[:r, :c], s.bg[:r, :c]
    s.cols, s.rows = c, r
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", help="Frums - Credits EX (mp3/wav). Without it the visuals run silent and unreactive.")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--mute", action="store_true", help="analyse the audio but don't play it")
    a = ap.parse_args()

    if a.audio:
        cache = os.path.join(tempfile.gettempdir(), "credits_mv_features_{}.npz".format(os.path.getsize(a.audio)))
        print("analysing audio…", flush=True)
        feats = au.Features(au.analyse(a.audio, 60, cache), 60)
    else:
        feats = au.Silent()

    size = shutil.get_terminal_size((120, 36))
    if size.columns < 120 or size.lines < 36:
        print("terminal is {}x{}; 120x36 or larger looks best (it will be cropped). starting in 2s…".format(
            size.columns, size.lines), flush=True)
        time.sleep(2)

    clock = Clock(a.audio, a.start, a.mute)
    out = sys.stdout
    out.write("\033[?1049h\033[?25l\033[2J")
    out.flush()
    prev = None
    try:
        clock.begin()
        frame_dt = 1.0 / a.fps
        while True:
            t = clock.now()
            if t >= tl.SONG_LENGTH:
                break
            s = director.frame(t, feats)
            apply_post(s)
            s = crop(s, size.columns, size.lines)
            out.write(to_ansi(s, prev) + "\033[0m")
            out.flush()
            prev = s
            spare = frame_dt - (clock.now() - t)
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
