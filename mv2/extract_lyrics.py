# Runs the original animation engine headlessly and records what every typewriter shows on every beat.
# Output: mv2/data/lyrics.json — the lyric timing source of truth for the new video.
#
# Usage (from repo root):  python3 mv2/extract_lyrics.py
import io
import json
import os
import random
import sys
import types

sys.dont_write_bytecode = True  # keep the original project tree clean
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
random.seed(2009)

# The original imports these for audio / key input; neither is needed to step the engine.
sys.modules.setdefault("keyboard", types.SimpleNamespace(is_pressed=lambda k: False))
sys.modules.setdefault("just_playback", types.SimpleNamespace(Playback=object))

real_stdout = sys.stdout
sys.stdout = io.StringIO()

import animation_scenes  # noqa: E402

orig_type_text = animation_scenes.type_text
orig_typewrite = animation_scenes.typewrite_by_word

CALL = [0]
streams = {}


def stream_key(g):
    return "{}:{}".format(g.scene.name, g.scene.generators.index(g))


def record(g, entry):
    s = streams.setdefault(stream_key(g), [])
    if s and s[-1]["b"] == entry["b"]:
        s[-1] = entry
    else:
        s.append(entry)


def type_text(c, g, layer, x, y, col, render=True):
    text, offset = g.get_data("text"), g.get_data("offset")
    if text and render:
        if text.startswith("[##CLEAR|"):
            record(g, {"b": CALL[0], "lines": []})
        else:
            lines, total = [], 0
            for line in text.split("\n"):
                local = offset - total
                if local < 0:
                    break
                lines.append(line[:local].replace("~", "").replace("@", ""))
                total += len(line)
            record(g, {"b": CALL[0], "lines": lines})
    return orig_type_text(c, g, layer, x, y, col, render)


def typewrite_by_word(c, g, layer, x, y, col, render=True, history_var="history"):
    text, offset, lineno = g.get_data("text"), g.get_data("offset"), g.get_data("lineno")
    if text and lineno < len(text) and render:
        line = text[lineno]
        if line and not line[0].startswith("[~~CLEAR|"):
            total = "".join(line[:offset])
            entry = {"b": CALL[0], "cur": total.replace("~", "")}
            if offset >= len(line):
                # The line is complete and gets committed to the log, same categories as the original.
                kind = "fluff" if (total.startswith(" ") or not total) else ("key" if total.endswith("~") else "line")
                entry["commit"] = {"text": total.strip(" ").replace("~", ""), "kind": kind, "indent": len(total) - len(total.lstrip(" "))}
            record(g, entry)
    return orig_typewrite(c, g, layer, x, y, col, render, history_var)


animation_scenes.type_text = type_text
animation_scenes.typewrite_by_word = typewrite_by_word

src = open("credits.py").read().split("paused_this_frame = False")[0]
ns = {"__name__": "credits_extract"}
exec(compile(src, "credits.py", "exec"), ns)
controller, canvas = ns["controller"], ns["canvas"]

for k in range(6560):
    CALL[0] = k
    controller.request_next()
    canvas.layers[0].new_groups.clear()
    sys.stdout.seek(0)
    sys.stdout.truncate()

sys.stdout = real_stdout
out = os.path.join(ROOT, "mv2", "data", "lyrics.json")
with open(out, "w") as f:
    json.dump(streams, f, separators=(",", ":"))
for k, v in streams.items():
    print("{:16} {:5} entries  beats {}..{}".format(k, len(v), v[0]["b"], v[-1]["b"]))
