# credits mv2 — "Signal Recovered"

A new terminal-art music video for Frums — Credits EX, built on the same beat grid and lyric timing as the
original animation in this repo, with all-new visuals.

**Concept:** a modern terminal picks up the lost 2009 PBS weather broadcast and tries to rebuild it,
failing more and more as the song goes on.

| time | section | visual |
|---|---|---|
| 0:00 | boot | a shell prompt tunes into `pbs://boston`, carrier lock, braille spinners |
| 0:05 | forecast | typed NWS forecast, radar sweep over Boston / I-495, braille ocean; "High-igh-igh" glitch-out |
| 0:48 | title | half-block CREDITS logo, warp starfield, credit lines, live spectrum |
| 1:20 | funding | btop-style pledge-drive dashboard: broadcast log, weather card, charts, ticker → CONNECTION LOST |
| 2:08 | melt | the dashboard falls apart column by column, then "no carrier" static |
| 2:14 | reboot | systemd-style boot log, rotating wire globe, `annual_financial_support.dat` download |
| 2:25 | crash | four tmux panes (stderr / dates / search / hexdump) re-tiling every two bars → THIS IS PBS! |
| 2:46 | ocean | perspective ASCII sea at night, moon road, Logan Airport observations, METAR |
| 3:10 | network | 24 PBS stations on a radial network, pings travel on the beat, one answers |
| 3:53 | finale | braille checkerboard tunnel carrying the last lyrics, then flashbacks to earlier scenes |
| 4:36 | power-off | CRT collapse to a line, a dot, end of transmission |

## Run

Needs Python 3.8+, `numpy`, `pillow` and an `ffmpeg` binary. The song is not included (see `media/README.txt`).

```sh
# Render the video (1920x1080, 60 fps, light CRT glow), with the song muxed in
python3 mv2/render.py --audio path/to/credits.mp3 --out credits_mv.mp4

# Stills or a clip of one section, for previewing
python3 mv2/render.py --audio path/to/credits.mp3 --stills 30,95,170 --outdir previews/
python3 mv2/render.py --audio path/to/credits.mp3 --start 145 --end 166 --out crash.mp4

# Watch it live in a real terminal (24-bit colour, 120x36 or larger)
python3 mv2/play.py --audio path/to/credits.mp3
```

`play.py` plays the audio through `just_playback` (the original project's player) when installed,
otherwise through `ffplay`.

## How it works

- `extract_lyrics.py` runs the original engine headlessly and records what every typewriter shows on every
  beat into `data/lyrics.json`, so the lyrics keep the original's hand-made timing exactly.
- `timeline.py` is the shared beat grid: 179 BPM in 1/8-beat steps, offset 5.492 s; event numbers match `credits.py`.
- `audio.py` measures loudness, kick / snare hits and a 24-band spectrum per frame; scenes use them for
  flashes, swell and spectrum bars.
- `term.py` is the screen: a 120x36 grid of cells with glyph + RGB colours, plus drawing tools (rounded
  panels, braille 2x4 dot canvas, half-block pixels, gradients, glitch effects).
- `scenes/` draw one section each. Every frame is drawn from the current time alone, so any moment can be
  previewed instantly and frames render in parallel.
- `raster.py` turns cells into pixels (braille, blocks and box lines are drawn by code so they join perfectly)
  and adds the CRT pass: soft glow, faint scanlines, vignette.
- `director.py` picks the scene for each beat and adds the cuts; `render.py` / `play.py` are the two outputs.

Credits: original animation and engine by plaaosert; music by Frums.
