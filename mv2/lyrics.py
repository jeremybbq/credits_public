# Beat-accurate lyric lookup built from data/lyrics.json (see extract_lyrics.py).
import bisect
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "lyrics.json")


class Stream:
    def __init__(self, entries):
        self.entries = entries
        self.beats = [e["b"] for e in entries]
        self.commits = [(e["b"], e["commit"]) for e in entries if "commit" in e]
        self.commit_beats = [c[0] for c in self.commits]

    def at(self, b):
        """The entry shown at beat b, or None before the stream starts."""
        i = bisect.bisect_right(self.beats, b) - 1
        return self.entries[i] if i >= 0 else None

    def lines(self, b):
        """Typed lines (char-typewriter streams)."""
        e = self.at(b)
        return e["lines"] if e and "lines" in e else []

    def current(self, b):
        """Line being typed right now (word-typewriter streams); '' right after a commit."""
        e = self.at(b)
        if not e or "commit" in e:
            return ""
        return e.get("cur", "")

    def history(self, b):
        """Committed lines up to beat b, oldest first, as (beat, text, kind, indent)."""
        n = bisect.bisect_right(self.commit_beats, b)
        return [(cb, c["text"], c["kind"], c["indent"]) for cb, c in self.commits[:n]]

    def last_change(self, b):
        """Beat of the most recent visible change (for hit flashes)."""
        e = self.at(b)
        return e["b"] if e else -999


_streams = None


def stream(key):
    global _streams
    if _streams is None:
        with open(_PATH) as f:
            _streams = {k: Stream(v) for k, v in json.load(f).items()}
    return _streams[key]
