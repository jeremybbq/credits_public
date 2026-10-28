# Accretion (mv3)

A third, independent music video for Frums — Credits EX, in terminal art. No interface, no on-screen lyrics,
one continuous take: a world is built grain by grain out of the song's weather forecast, paid for by viewers
like you, and then given back. The full directing script is in [SCRIPT.md](SCRIPT.md).

| time | material | the song |
|---|---|---|
| 0:00 | seed | the intro riser gathers around one dot, then it bursts |
| 0:05 | weather → sand | every forecast syllable rains grains that land as dunes; the sun comes out on "Friday"; time hiccups on "high-igh-igh" |
| 0:48 | fire | the dunes ignite; dotted flames follow the bass; the fire inhales on the 1:15 hit |
| 1:20 | growth | stems grow one cell per word; "by" splits them, "like you" opens leaves; "Corporation" turns them into a steel lattice that cracks |
| 2:08 | erosion | everything crumbles to dust; a heartbeat dot remains |
| 2:14 | crystal | a six-fold snowflake accretes, pushed by "annual financial support" |
| 2:25 | life | the snowflake shatters into a cellular automaton whose rules change every two bars; one glider escapes "This is PBS!" |
| 2:46 | water | each syllable of the Logan Airport observations is a drop; the surface drifts with the southwest wind |
| 3:10 | orbit | crests become bodies orbiting a centre; each chopped "funding" adds one; they gather into a ring |
| 3:53 | light | the ring becomes a lit torus banded with every material so far; it shatters on "…viewers like you" |
| 4:36 | settle | every grain falls into one dune; then the only words in the film |

## Run

Needs Python 3.8+, `numpy`, `pillow` and an `ffmpeg` binary. The song is not included (see `media/README.txt`).

```sh
python3 mv3/render.py --audio path/to/credits.mp3 --out accretion.mp4          # 1920x1080, 60 fps
python3 mv3/render.py --audio path/to/credits.mp3 --stills 30,95,170 --outdir previews/
python3 mv3/play.py --audio path/to/credits.mp3                               # live, in a 24-bit terminal
```

## How it works

- Every material is a small simulation stepped 60 times a second: falling sand with avalanches, a fire heat
  field, branching growth on the cell grid, a symmetric crystal, cellular automata, a wave equation, orbital
  gravity, a shaded 3D torus. Each hands its final state to the next (`world.py`), so there are no cuts.
- The music drives them: kicks, snares and loudness from the audio (`mv2/audio.py`), and the voice as
  syllable events from the original project's hand-timed vocal data (`core.Voice`).
- Because each frame depends on the last, `render.py` simulates in order and rasterises in parallel.
- Only the drawing and video tools are shared with mv2 (cell screen, braille drawing, rasteriser with a light
  CRT glow, audio analysis, beat grid); none of its scenes or visuals.
