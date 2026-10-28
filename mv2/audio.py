# Audio features per video frame: loudness, kick / snare hits and a log-spaced spectrum.
# Needs only numpy + an ffmpeg binary. Results are cached next to the output video.
import os
import subprocess

import numpy as np

SR = 22050
BANDS = 24


def decode(path):
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True, stdout=subprocess.PIPE
    ).stdout
    return np.frombuffer(raw, np.float32)


def _norm(x, pct=98):
    hi = np.percentile(x, pct) + 1e-9
    return np.clip(x / hi, 0, 1)


def analyse(path, fps, cache=None):
    if cache and os.path.exists(cache):
        d = np.load(cache)
        if int(d["fps"]) == fps:
            return {k: d[k] for k in d.files}

    a = decode(path)
    hop = SR / fps
    n_frames = int(len(a) / hop)
    win = 2048
    pad = np.pad(a, (win // 2, win))
    starts = (np.arange(n_frames) * hop).astype(int)
    hann = np.hanning(win).astype(np.float32)
    spec, rms = [], []
    for c in range(0, n_frames, 2000):
        frames = np.stack([pad[s:s + win] for s in starts[c:c + 2000]]) * hann
        spec.append(np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32))
        rms.append(np.sqrt((frames ** 2).mean(1)))
    spec, rms = np.concatenate(spec), np.concatenate(rms)
    freqs = np.fft.rfftfreq(win, 1 / SR)

    def band(lo, hi):
        m = (freqs >= lo) & (freqs < hi)
        return spec[:, m].sum(1)

    # Onset = positive change of band energy (log), smoothed decay so hits read as a short flash.
    def onset(e):
        le = np.log1p(e * 10)
        d = np.maximum(np.diff(le, prepend=le[0]), 0)
        d = _norm(d, 99.5)
        out = np.zeros_like(d)
        acc = 0.0
        decay = 0.5 ** (60.0 / fps / 6)
        for i, v in enumerate(d):
            acc = max(v, acc * decay)
            out[i] = acc
        return out

    edges = np.geomspace(40, 11000, BANDS + 1)
    bands = np.stack([band(edges[i], edges[i + 1]) for i in range(BANDS)], 1)
    bands = np.log1p(bands)
    bands = np.clip((bands - np.percentile(bands, 5, 0)) / (np.percentile(bands, 99, 0) - np.percentile(bands, 5, 0) + 1e-9), 0, 1)

    out = {
        "fps": np.array(fps),
        "level": _norm(rms).astype(np.float32),
        "kick": onset(band(35, 130)).astype(np.float32),
        "snare": onset(band(1800, 6000)).astype(np.float32),
        "bands": bands.astype(np.float32),
    }
    if cache:
        np.savez_compressed(cache, **out)
    return out


class Features:
    def __init__(self, data, fps):
        self.d = data
        self.fps = fps
        self.n = len(data["level"])

    def _i(self, t):
        return int(min(max(t * self.fps, 0), self.n - 1))

    def level(self, t):
        return float(self.d["level"][self._i(t)])

    def kick(self, t):
        return float(self.d["kick"][self._i(t)])

    def snare(self, t):
        return float(self.d["snare"][self._i(t)])

    def bands(self, t):
        return self.d["bands"][self._i(t)]


class Silent:
    """Stand-in when no audio file is given (previews of layout only)."""
    def level(self, t): return 0.5
    def kick(self, t): return 0.0
    def snare(self, t): return 0.0
    def bands(self, t): return np.full(BANDS, 0.3, np.float32)
