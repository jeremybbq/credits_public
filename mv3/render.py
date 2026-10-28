# Render "Accretion": 1920x1080 @ 60 fps with the song muxed in.
#
#   python3 mv3/render.py --audio credits.mp3 --out accretion.mp4
#   python3 mv3/render.py --audio credits.mp3 --stills 20,60,150 --outdir previews/
#
# The world is simulated in order (each frame depends on the last); rasterising runs in parallel.
import argparse
import os
import subprocess
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import core                  # noqa: E402,F401  (sets up paths to the shared tools)
import audio as au           # noqa: E402
import raster                # noqa: E402
import term                  # noqa: E402
import timeline as tl        # noqa: E402
from core import FPS         # noqa: E402
from world import World      # noqa: E402

_crt = True


def _init(crt):
    global _crt
    _crt = crt


def _raster(job):
    glyphs, screen = job
    # Cells index the main process's glyph table; mirror it here before rasterising.
    if len(glyphs) > len(term.GLYPHS):
        for g in glyphs[len(term.GLYPHS):]:
            term.gid(*g)
    return raster.rasterise(screen, crt=_crt).tobytes()


def frames(world, n0, n1, every=1):
    for f in range(0, n1):
        world.advance(f / FPS)
        if f >= n0 and (f - n0) % every == 0:
            yield f, world.draw()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, help="Frums - Credits EX (mp3/wav)")
    ap.add_argument("--out", default="accretion.mp4")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=tl.SONG_LENGTH)
    ap.add_argument("--stills", help="comma separated times (s) to save as PNG instead of a video")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--no-crt", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()

    where = a.outdir if a.stills else (os.path.dirname(os.path.abspath(a.out)) or ".")
    os.makedirs(where, exist_ok=True)
    feats = au.Features(au.analyse(a.audio, FPS, os.path.join(where, ".audio_features_{}fps.npz".format(FPS))), FPS)
    world = World(feats)

    if a.stills:
        from PIL import Image
        want = sorted(int(round(float(x) * FPS)) for x in a.stills.split(","))
        for f in range(0, want[-1] + 1):
            world.advance(f / FPS)
            if f in want:
                p = os.path.join(a.outdir, "still_{:07.2f}.png".format(f / FPS))
                Image.fromarray(raster.rasterise(world.draw(), crt=not a.no_crt)).save(p)
                print(p, flush=True)
        return

    n0, n1 = int(a.start * FPS), int(a.end * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080",
           "-r", str(FPS), "-i", "-", "-ss", str(a.start), "-t", str(a.end - a.start), "-i", a.audio,
           "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k", "-c:v", "libx264", "-preset", "medium",
           "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", a.out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    batch, pending, done = [], None, 0
    with Pool(a.workers, initializer=_init, initargs=(not a.no_crt,)) as pool:
        def flush(res):
            nonlocal done
            for buf in res.get():
                ff.stdin.write(buf)
                done += 1
                if done % 600 == 0:
                    print("frame {}/{}  {:.0f}s".format(done, n1 - n0, time.time() - t0), flush=True)

        for f, screen in frames(world, n0, n1):
            batch.append((list(term.GLYPHS), screen))
            if len(batch) == 96:
                res = pool.map_async(_raster, batch, chunksize=8)
                if pending:
                    flush(pending)
                pending, batch = res, []
        if batch:
            res = pool.map_async(_raster, batch, chunksize=8)
            if pending:
                flush(pending)
            pending = res
        if pending:
            flush(pending)
    ff.stdin.close()
    ff.wait()
    print("wrote", a.out, "in {:.0f}s".format(time.time() - t0))


if __name__ == "__main__":
    main()
