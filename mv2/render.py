# Render the music video: 1920x1080 @ 60 fps with the song muxed in.
#
#   python3 mv2/render.py --audio credits.mp3 --out credits_mv.mp4
#   python3 mv2/render.py --audio credits.mp3 --stills 12,30,95 --outdir previews/     (PNG stills)
#   python3 mv2/render.py --audio credits.mp3 --out clip.mp4 --start 40 --end 55        (a section clip)
import argparse
import os
import subprocess
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audio as au          # noqa: E402
import director             # noqa: E402
import raster               # noqa: E402
import timeline as tl       # noqa: E402

_audio = None
_crt = True


def _init(audio_path, fps, cache, crt):
    global _audio, _crt
    _crt = crt
    if audio_path:
        _audio = au.Features(au.analyse(audio_path, fps, cache), fps)
    else:
        _audio = au.Silent()


def _render(t):
    return raster.rasterise(director.frame(t, _audio), crt=_crt).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", help="Frums - Credits EX (mp3/wav)")
    ap.add_argument("--out", default="credits_mv.mp4")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=tl.SONG_LENGTH)
    ap.add_argument("--stills", help="comma separated times (s) to save as PNG instead of a video")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--no-crt", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()

    cache = None
    if a.audio:
        where = a.outdir if a.stills else (os.path.dirname(os.path.abspath(a.out)) or ".")
        os.makedirs(where, exist_ok=True)
        cache = os.path.join(where, ".audio_features_{}fps.npz".format(a.fps))
        au.analyse(a.audio, a.fps, cache)  # build the cache once before forking

    if a.stills:
        from PIL import Image
        _init(a.audio, a.fps, cache, not a.no_crt)
        os.makedirs(a.outdir, exist_ok=True)
        for ts in a.stills.split(","):
            t = float(ts)
            img = raster.rasterise(director.frame(t, _audio), crt=not a.no_crt)
            p = os.path.join(a.outdir, "still_{:07.2f}.png".format(t))
            Image.fromarray(img).save(p)
            print(p)
        return

    W, H = 1920, 1080
    times = [f / a.fps for f in range(int(a.start * a.fps), int(a.end * a.fps))]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "{}x{}".format(W, H),
           "-r", str(a.fps), "-i", "-"]
    if a.audio:
        cmd += ["-ss", str(a.start), "-t", str(a.end - a.start), "-i", a.audio, "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-b:a", "256k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-shortest", a.out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    with Pool(a.workers, initializer=_init, initargs=(a.audio, a.fps, cache, not a.no_crt)) as pool:
        for i, buf in enumerate(pool.imap(_render, times, chunksize=8)):
            ff.stdin.write(buf)
            if i % 600 == 0:
                el = time.time() - t0
                print("frame {}/{}  {:.0f}s elapsed".format(i, len(times), el), flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", a.out, "in {:.0f}s".format(time.time() - t0))


if __name__ == "__main__":
    main()
